package main

import (
	"fmt"
	"reflect"
	"time"

	"go.temporal.io/sdk/temporal"
	"go.temporal.io/sdk/workflow"
)

func orderedStages(config RunConfig) []StageConfig {
	byID := make(map[string]StageConfig, len(config.Stages))
	for _, stage := range config.Stages {
		byID[stage.StageID] = stage
	}
	if len(config.StageSequence) > 0 {
		out := make([]StageConfig, 0, len(config.StageSequence))
		for _, stageID := range config.StageSequence {
			stage, ok := byID[stageID]
			if !ok || !stage.Enabled {
				continue
			}
			out = append(out, stage)
		}
		return out
	}
	out := make([]StageConfig, 0, len(config.Stages))
	for _, stage := range config.Stages {
		if stage.Enabled {
			out = append(out, stage)
		}
	}
	return out
}

func pipelineProfiles(stage StageConfig) []PipelineConfig {
	if len(stage.Pipelines) > 0 {
		return stage.Pipelines
	}
	return []PipelineConfig{
		{
			PipelineID:       "default-pipeline",
			ComponentName:    "foundation_model",
			ComponentVersion: "latest",
			MachineType:      "h100-sxm",
			NodeCount:        64,
			GPUsPerNode:      8,
			RankSize:         512,
			ResourcePool:      "foundation",
			StageOverrides:   map[string]any{},
			PipelineType:     "foundation_pretrain",
		},
	}
}

func parallelCapacity(strategy *PipelineStrategy) int {
	if strategy == nil || strategy.Mode != "parallel" {
		return 1
	}
	if strategy.MaxParallelism == nil || *strategy.MaxParallelism <= 0 {
		return 64
	}
	return *strategy.MaxParallelism
}

func isTerminalFailure(status string) bool {
	switch status {
	case "SUCCEEDED", "SUCCESS", "OK":
		return false
	default:
		return true
	}
}

func shouldSkipPipelineStep(target *ReplaySignal, targetIdx int, stage StageConfig, stageIndex int, pipelineID *string, step string) bool {
	if target == nil {
		return false
	}
	if target.TargetStageID != stage.StageID {
		return false
	}
	if stageIndex < targetIdx {
		return true
	}
	if stageIndex > targetIdx {
		return false
	}
	if target.Scope == "stage" {
		return false
	}
	if target.Scope == "pipeline" {
		if pipelineID == nil {
			return false
		}
		if target.TargetPipelineID == nil {
			return false
		}
		return *pipelineID != *target.TargetPipelineID
	}
	// scope == "step"
	return step != target.TargetStep
}

func copyStringPtr(in *string) *string {
	if in == nil {
		return nil
	}
	v := *in
	return &v
}

func copyIntPtr(in *int) *int {
	if in == nil {
		return nil
	}
	v := *in
	return &v
}

func nowMs() int64 {
	return workflow.Now(workflow.WithActivityOptions(contextualContext(), workflow.ActivityOptions{})).UnixNano() / int64(time.Millisecond)
}

// Workflows use contextualContext only for timestamp conversion utility.
func contextualContext() workflow.Context {
	return workflow.Background()
}

type ParentCmdWorkflow struct {
	state string
}

func (w *ParentCmdWorkflow) Run(input StartKilvinCommandInput) (ParentRunOutput, error) {
	w.state = "RUNNING"
	irName := "kilvin-ir-" + input.RunConfig.RunID
	extracted, err := func() (ExtractCmdConfigOutput, error) {
		var out ExtractCmdConfigOutput
		err := workflow.ExecuteActivity(
			workflow.GetLogger(workflow.WithChildOptions(contextualContext(), workflow.ChildWorkflowOptions{})),
			ExtractCmdConfig,
			ExtractCmdConfigInput{
				RunConfig:    input.RunConfig,
				CmdName:      input.CmdName,
				JobParamsURI: input.JobParamsURI,
			},
		).Get(workflow.WithChildOptions(contextualContext(), workflow.ChildWorkflowOptions{}), &out)
		return out, err
	}()
	if err != nil {
		return ParentRunOutput{RunID: input.RunConfig.RunID, FinalState: "KILVIN_FAILED", Error: strPtr(err.Error())}, err
	}

	childOpts := workflow.ChildWorkflowOptions{
		WorkflowID: fmt.Sprintf("kilvin-training-%s", input.RunConfig.RunID),
		RetryPolicy: &temporal.RetryPolicy{
			MaximumAttempts: int32(max(1, input.RunConfig.Policy.MaxStageRetries)),
		},
	}
	childCtx := workflow.WithChildOptions(contextualContext(), childOpts)
	var trainingOut string
	err = workflow.ExecuteChildWorkflow(
		childCtx,
		TrainingWorkflow.Run,
		TrainingWorkflowInput{
			RunID:     input.RunConfig.RunID,
			RunConfig: input.RunConfig,
			Extracted: extracted,
		},
	).Get(childCtx, &trainingOut)
	if err != nil {
		_ = workflow.ExecuteActivity(contextualContext(), UpdateCmdState, map[string]any{
			"run_id":      input.RunConfig.RunID,
			"final_state": "KILVIN_FAILED",
			"error":       err.Error(),
		}).Get(contextualContext(), nil)
		w.state = "FAILED"
		return ParentRunOutput{
			RunID:      input.RunConfig.RunID,
			FinalState: "KILVIN_FAILED",
			IRName:     &irName,
			Error:      strPtr(err.Error()),
		}, err
	}

	_ = workflow.ExecuteActivity(contextualContext(), UpdateCmdState, map[string]any{
		"run_id":      input.RunConfig.RunID,
		"final_state": "KILVIN_SUCCESS",
		"ir_name":     irName,
		"result":      trainingOut,
	}).Get(contextualContext(), nil)
	w.state = "SUCCEEDED"
	return ParentRunOutput{
		RunID:      input.RunConfig.RunID,
		FinalState: "KILVIN_SUCCESS",
		IRName:     &irName,
	}, nil
}

type TrainingWorkflow struct {
	state                string
	runID                string
	runAttempt           int
	stepTraces           []StepExecutionEnvelope
	failures             []StageExecutionFailure
	currentStep          struct {
		StageID    string
		PipelineID *string
		StepName   *string
	}
	cancelled            bool
	paused               bool
	pauseSignal          *PauseAtStepSignal
	replaySignal         *ReplaySignal
	replayStepWaiting    bool
}

func (w *TrainingWorkflow) QueryStatus() KilvinRunState {
	cp := w.currentStep.PipelineID
	cs := w.currentStep.StepName
	return KilvinRunState{
		RunID:           w.runID,
		RunAttempt:      w.runAttempt,
		CurrentStage:    w.currentStep.StageID,
		CurrentPipeline: cp,
		CurrentStep:     cs,
		OverallStatus:   w.state,
		Paused:          w.paused,
		StageTraces:     w.stepTraces,
		Failures:        w.failures,
	}
}

func (w *TrainingWorkflow) QueryStepTrace() []StepExecutionEnvelope {
	out := make([]StepExecutionEnvelope, len(w.stepTraces))
	copy(out, w.stepTraces)
	return out
}

func (w *TrainingWorkflow) SignalPause(_ PauseSignal) {
	w.paused = true
	w.state = "PAUSED"
}

func (w *TrainingWorkflow) SignalResume(_ ResumeSignal) {
	w.paused = false
	if w.state == "PAUSED" {
		w.state = "RUNNING"
	}
}

func (w *TrainingWorkflow) SignalPauseAtStep(signal PauseAtStepSignal) {
	w.pauseSignal = &signal
}

func (w *TrainingWorkflow) SignalReplay(signal ReplaySignal) {
	w.replaySignal = &signal
	w.replayStepWaiting = signal.Scope == "step"
}

func (w *TrainingWorkflow) SignalCancel(_ CancelSignal) {
	w.cancelled = true
	w.state = "CANCELLED"
}

func (w *TrainingWorkflow) appendTrace(env StepExecutionEnvelope) {
	w.stepTraces = append(w.stepTraces, env)
}

func (w *TrainingWorkflow) setOutput(dst interface{}, src interface{}) {
	if dst == nil || src == nil {
		return
	}
	rv := reflect.ValueOf(dst)
	if rv.Kind() != reflect.Pointer || rv.IsNil() {
		return
	}
	sv := reflect.ValueOf(src)
	if !sv.IsValid() {
		return
	}
	if sv.Type().AssignableTo(rv.Elem().Type()) {
		rv.Elem().Set(sv)
	}
}

func (w *TrainingWorkflow) persistArtifact(ctx workflow.Context, stage StageConfig, stageIndex int, pipelineID *string, pipelineIndex *int, stepName string, payload any) (StepIOArtifact, error) {
	var artifact StepIOArtifact
	inputName := fmt.Sprintf("%s/%s/%s/in.yaml", stage.StageID, derefPipelineID(pipelineID), stepName)
	err := workflow.ExecuteActivity(
		ctx,
		PersistYAMLArtifact,
		ArtifactWriteInput{
			RunID:        w.runID,
			RunAttempt:   w.runAttempt,
			ArtifactName: inputName,
			Payload:      payload,
		},
	).Get(ctx, &artifact)
	return artifact, err
}

func (w *TrainingWorkflow) markPauseIfMatched(ctx workflow.Context, stage StageConfig, stageIndex int, pipelineID *string, stepName string, when string) error {
	if w.pauseSignal == nil || w.pauseSignal.When != when {
		return nil
	}
	if w.pauseSignal.StageID != stage.StageID {
		return nil
	}
	if w.pauseSignal.StepName != stepName {
		return nil
	}
	if w.pauseSignal.PipelineID != nil && pipelineID != nil && *w.pauseSignal.PipelineID != *pipelineID {
		return nil
	}
	if w.pauseSignal.PipelineID != nil && pipelineID == nil {
		return nil
	}
	w.paused = true
	w.state = "PAUSED"
	workflow.Await(ctx, func() bool { return !w.paused })
	w.state = "RUNNING"
	return nil
}

func (w *TrainingWorkflow) shouldSkip(stage StageConfig, stageIndex int, pipelineID *string, stepName string) bool {
	if w.replaySignal == nil {
		return false
	}
	idx := -1
	for i, st := range orderedStages(w.getRunConfig()) {
		if st.StageID == w.replaySignal.TargetStageID {
			idx = i
			break
		}
	}
	return shouldSkipPipelineStep(w.replaySignal, idx, stage, stageIndex, pipelineID, stepName)
}

func (w *TrainingWorkflow) getRunConfig() RunConfig {
	if cfg, ok := workflow.GetInfo(workflow.WithChildOptions(contextualContext(), workflow.ChildWorkflowOptions{})).GetTypedSearchAttributes()["run_config"].(RunConfig); ok {
		return cfg
	}
	return RunConfig{}
}

func (w *TrainingWorkflow) runStep(
	ctx workflow.Context,
	stage StageConfig,
	stageIndex int,
	pipelineID *string,
	pipelineIndex *int,
	stepName string,
	activityFn interface{},
	activityInput any,
	out interface{},
	timeout time.Duration,
	skipOut any,
) error {
	if w.cancelled {
		return fmt.Errorf("workflow cancelled")
	}
	w.currentStep = struct {
		StageID    string
		PipelineID *string
		StepName   *string
	}{StageID: stage.StageID, PipelineID: copyStringPtr(pipelineID), StepName: &stepName}

	if err := w.markPauseIfMatched(ctx, stage, stageIndex, pipelineID, stepName, "pre"); err != nil {
		return err
	}

	traceInput, err := w.persistArtifact(ctx, stage, stageIndex, pipelineID, pipelineIndex, stepName, map[string]any{
		"step_name":   stepName,
		"stage_id":    stage.StageID,
		"pipeline_id": pipelineID,
		"payload":     activityInput,
	})
	if err != nil {
		return err
	}
	now := int64(0)
	if !w.shouldSkip(stage, stageIndex, pipelineID, stepName) {
		w.appendTrace(StepExecutionEnvelope{
			RunID:          w.runID,
			RunAttempt:     w.runAttempt,
			StageID:        stage.StageID,
			StageIndex:     stageIndex,
			StepName:       stepName,
			PipelineID:     copyStringPtr(pipelineID),
			PipelineIndex:  copyIntPtr(pipelineIndex),
			Status:         "RUNNING",
			RetryAttempt:   0,
			InputArtifact:  traceInput,
			InputChecksum:  traceInput.ChecksumSHA256,
			StartedAtMS:    &now,
		})
		if out != nil {
			err = workflow.ExecuteActivity(ctx, activityFn, activityInput).Get(ctx, out)
		} else {
			err = workflow.ExecuteActivity(ctx, activityFn, activityInput).Get(ctx, nil)
		}
		if err != nil {
			w.failures = append(w.failures, StageExecutionFailure{
				StageID:    stage.StageID,
				PipelineID: copyStringPtr(pipelineID),
				StepName:   stepName,
				Attempt:    w.runAttempt,
				Error:      err.Error(),
			})
			w.appendTrace(StepExecutionEnvelope{
				RunID:          w.runID,
				RunAttempt:     w.runAttempt,
				StageID:        stage.StageID,
				StageIndex:     stageIndex,
				StepName:       stepName,
				PipelineID:     copyStringPtr(pipelineID),
				PipelineIndex:  copyIntPtr(pipelineIndex),
				Status:         "FAILED",
				RetryAttempt:   0,
				InputArtifact:  traceInput,
				InputChecksum:  traceInput.ChecksumSHA256,
				Error:          err.Error(),
				StartedAtMS:    &now,
				CompletedAtMS:  intPtrPtr(&now),
			})
			return err
		}
		var outArtifact StepIOArtifact
		outName := fmt.Sprintf("%s/%s/%s/out.yaml", stage.StageID, derefPipelineID(pipelineID), stepName)
		_ = workflow.ExecuteActivity(ctx, PersistYAMLArtifact, ArtifactWriteInput{
			RunID:        w.runID,
			RunAttempt:   w.runAttempt,
			ArtifactName: outName,
			Payload:      out,
		}).Get(ctx, &outArtifact)
		cs := nowMs()
		w.appendTrace(StepExecutionEnvelope{
			RunID:          w.runID,
			RunAttempt:     w.runAttempt,
			StageID:        stage.StageID,
			StageIndex:     stageIndex,
			StepName:       stepName,
			PipelineID:     copyStringPtr(pipelineID),
			PipelineIndex:  copyIntPtr(pipelineIndex),
			Status:         "SUCCEEDED",
			RetryAttempt:   0,
			InputArtifact:  traceInput,
			OutputArtifact: &outArtifact,
			InputChecksum:  traceInput.ChecksumSHA256,
			OutputChecksum: &outArtifact.ChecksumSHA256,
			StartedAtMS:    &now,
			CompletedAtMS:  &cs,
		})
	} else {
		w.setOutput(out, skipOut)
		w.appendTrace(StepExecutionEnvelope{
			RunID:          w.runID,
			RunAttempt:     w.runAttempt,
			StageID:        stage.StageID,
			StageIndex:     stageIndex,
			StepName:       stepName,
			PipelineID:     copyStringPtr(pipelineID),
			PipelineIndex:  copyIntPtr(pipelineIndex),
			Status:         "SKIPPED",
			RetryAttempt:   0,
			InputArtifact:  traceInput,
			InputChecksum:  traceInput.ChecksumSHA256,
			Error:          "skipped for replay",
			StartedAtMS:    &now,
			CompletedAtMS:  &now,
		})
	}
	if err := w.markPauseIfMatched(ctx, stage, stageIndex, pipelineID, stepName, "post"); err != nil {
		return err
	}
	return nil
}

func (w *TrainingWorkflow) Run(input TrainingWorkflowInput) (string, error) {
	w.state = "RUNNING"
	w.runAttempt++
	w.runID = input.RunConfig.RunID

	stages := orderedStages(input.RunConfig)
	if len(stages) == 0 {
		return "", fmt.Errorf("no enabled stages in run config")
	}

	var extractDev DevPrepareOutput
	if err := w.runStep(
		workflow.WithActivityOptions(contextualContext(), workflow.ActivityOptions{StartToCloseTimeout: 120 * time.Second, RetryPolicy: &temporal.RetryPolicy{MaximumAttempts: 3}}),
		stages[0], 0, nil, nil,
		"dev_prepare",
		DevPrepare,
		DevPrepareInput{RunID: input.RunID, Checkpoint: input.Extracted.Checkpoint},
		&extractDev,
		120*time.Second,
		DevPrepareOutput{AutoJobID: "kilvin-replay-dev", CodeTosKey: derefStr(input.Extracted.Checkpoint, "s3://models/k2/checkpoint") + "/artifacts/code.tar.gz"},
	); err != nil {
		w.state = "FAILED"
		return "", err
	}

	var checkpoint CheckpointOutput
	if err := w.runStep(
		workflow.WithActivityOptions(contextualContext(), workflow.ActivityOptions{StartToCloseTimeout: 120 * time.Second, RetryPolicy: &temporal.RetryPolicy{MaximumAttempts: 3}}),
		stages[0], 0, nil, nil,
		"validate_checkpoint",
		ValidateCheckpoint,
		extractDev.CodeTosKey,
		&checkpoint,
		120*time.Second,
		CheckpointOutput{
			CheckpointPath: derefStr(input.Extracted.Checkpoint, "s3://models/k2/checkpoint"),
			ManifestURI:    "file://./.kilvin-artifacts/skip/manifest.yaml",
			ModelSizeEstimate: 700_000_000_000,
		},
	); err != nil {
		w.state = "FAILED"
		return "", err
	}

	currentCheckpoint := checkpoint.CheckpointPath
	for stageIndex, stage := range stages {
		if w.cancelled {
			return "", fmt.Errorf("run cancelled")
		}

		var configured DataConfigureOutput
		if err := w.runStep(
			workflow.WithActivityOptions(contextualContext(), workflow.ActivityOptions{StartToCloseTimeout: 120 * time.Second, RetryPolicy: &temporal.RetryPolicy{MaximumAttempts: 3}}),
			stage, stageIndex, nil, nil,
			"configure_training_data",
			ConfigureTrainingData,
			ConfigureTrainingDataInput{
				DatasetURI:                stage.DatasetProfile.URI,
				DatasetStage:              stage.StageID,
				RequiredTokenBudget:       stage.RuntimeProfile.TotalTokensTarget,
				MinExamples:               stage.DatasetProfile.MinExamples,
				TokenBudgetToleranceRatio:  stage.DatasetProfile.TokenBudgetToleranceRatio,
				DataMixRequirements:       stage.DatasetProfile.MixRequirements,
				QualityThresholds:         stage.DatasetProfile.QualityThresholds,
			},
			&configured,
			120*time.Second,
			DataConfigureOutput{
				DatasetID:           "skip-" + stage.StageID,
				SchemaVersion:       "skip",
				ShardCount:          1,
				EstimatedTokens:      stage.RuntimeProfile.TotalTokensTarget,
				StageTokenMix:       map[string]int64{"skipped": 1},
				CompositionBreakdown: map[string]float64{"skipped": 1.0},
				QualityScores:       map[string]float64{"skipped": 1.0},
				TotalExamples:       1,
				FormatOK:            true,
			},
		); err != nil {
			w.state = "FAILED"
			return "", err
		}

		var allocation ReamAllocationOutput
		if err := w.runStep(
			workflow.WithActivityOptions(contextualContext(), workflow.ActivityOptions{StartToCloseTimeout: 120 * time.Second, RetryPolicy: &temporal.RetryPolicy{MaximumAttempts: 3}}),
			stage, stageIndex, nil, nil,
			"allocate_resources",
			AllocateResources,
			AllocateResourcesInput{
				RunID:           input.RunID,
				StageID:         stage.StageID,
				StageIndex:      stageIndex,
				PipelineProfiles: pipelineProfiles(stage),
			},
			&allocation,
			180*time.Second,
			ReamAllocationOutput{
				AllocationID:       "skip-allocation-" + stage.StageID,
				ResourceEpoch:      1,
				PoolsReservationID: "skip",
				PipelineAllocations: []PipelineAllocation{
					{
						PipelineID:    "default-pipeline",
						ComponentName: "foundation_model",
						NodeCount:     1,
						GPUsPerNode:   1,
						RankSize:      1,
						MachineType:   "h100-sxm",
						PoolName:      "foundation",
						RDMAEnabled:   true,
						NCCLProfile:   "nccl",
					},
				},
			},
		); err != nil {
			w.state = "FAILED"
			return "", err
		}

		_ = configured
		profiles := pipelineProfiles(stage)
		maxParallel := parallelCapacity(stage.PipelineStrategy)
		_ = maxParallel

		pending := make([]workflow.ChildWorkflowFuture, 0, len(profiles))
		for _, profile := range profiles {
			allocationForProfile := findAllocation(profile.PipelineID, allocation.PipelineAllocations)
			childInput := PipelineWorkflowInput{
				RunID:             input.RunID,
				RunAttempt:        w.runAttempt,
				Stage:             stage,
				StageIndex:        stageIndex,
				Profile:           profile,
				Allocation:        allocationForProfile,
				CurrentCheckpoint: currentCheckpoint,
				ConfigSnapshot:    input.Extracted.WorkflowConfigURI,
				TaskType:          "foundation_train",
				Replay:            w.replaySignal,
			}
			cctx := workflow.WithChildOptions(contextualContext(), workflow.ChildWorkflowOptions{
				WorkflowID: fmt.Sprintf("kilvin-%s-%s-%s", input.RunID, stage.StageID, profile.PipelineID),
			})
			pending = append(pending, workflow.ExecuteChildWorkflow(cctx, PipelineExecutionWorkflow, childInput))
		}

		for _, pendingWorkflow := range pending {
			var pipeOut PipelineWorkflowOutput
			if err := pendingWorkflow.Get(contextualContext(), &pipeOut); err != nil {
				w.state = "FAILED"
				return "", err
			}
			w.stepTraces = append(w.stepTraces, pipeOut.StepTraces...)
			if pipeOut.Failed || isTerminalFailure(pipeOut.Monitor.FinalStatus) {
				return "", fmt.Errorf("pipeline %s failed: %s", pipeOut.PipelineID, pipeOut.Error)
			}
		}

		currentCheckpoint = currentCheckpoint + "/" + stage.StageID
		if err := w.runStep(
			workflow.WithActivityOptions(contextualContext(), workflow.ActivityOptions{StartToCloseTimeout: 180 * time.Second, RetryPolicy: &temporal.RetryPolicy{MaximumAttempts: 2}}),
			stage, stageIndex, nil, nil,
			"purge_resources",
			PurgeResources,
			PurgeInput{
				RunID:             input.RunID,
				StageID:           stage.StageID,
				PreserveArtifacts:  input.RunConfig.Policy.PreserveArtifactsOnFailure,
				Checkpoint:        &currentCheckpoint,
			},
			nil,
			180*time.Second,
			nil,
		); err != nil {
			w.state = "FAILED"
			return "", err
		}
	}

	w.state = "COMPLETED"
	return "KILVIN_TRAINING_COMPLETED:" + input.RunID, nil
}

func (w *TrainingWorkflow) PipelineWorkflow(input PipelineWorkflowInput) (PipelineWorkflowOutput, error) {
	return PipelineExecutionWorkflow(input)
}

type PipelineExecutionWorkflow struct {
	state       string
	stepTraces  []StepExecutionEnvelope
	runAttempt  int
	runID       string
	replay      *ReplaySignal
}

func (pw *PipelineExecutionWorkflow) trace() []StepExecutionEnvelope {
	return pw.stepTraces
}

func PipelineExecutionWorkflow(input PipelineWorkflowInput) (PipelineWorkflowOutput, error) {
	pw := &PipelineExecutionWorkflow{
		runAttempt: input.RunAttempt,
		runID:      input.RunID,
		replay:     input.Replay,
		state:      "RUNNING",
	}
	pipelineID := input.Profile.PipelineID

	stageProfiles := pipelineProfiles(input.Stage)
	for _, p := range stageProfiles {
		if p.PipelineID == pipelineID {
			break
		}
	}
	var materialized PipelineBundleOutput
	var outErr error
	ctx := workflow.WithActivityOptions(contextualContext(), workflow.ActivityOptions{
		StartToCloseTimeout: 180 * time.Second,
	})
	if err := pw.runStep(
		ctx,
		input.Stage, input.StageIndex, &pipelineID, nil,
		"materialize_training_bundle",
		MaterializeTrainingBundle,
		MaterializeTrainingBundleInput{
			IRName:            fmt.Sprintf("kilvin-ir-%s-%s", input.RunID, input.Stage.StageID),
			Checkpoint:        input.CurrentCheckpoint,
			ConfigSnapshot:    input.ConfigSnapshot,
			PipelineID:       pipelineID,
			Allocation:       input.Allocation,
			PipelineProfile:  input.Profile,
			StageIndex:       input.StageIndex,
			TrainStage:       input.Stage.StageID,
			TaskType:         input.TaskType,
			TotalTokensTarget: input.Stage.RuntimeProfile.TotalTokensTarget,
			GlobalBatchTokens: input.Stage.RuntimeProfile.GlobalBatchTokens,
			MaxSteps:         input.Stage.RuntimeProfile.MaxSteps,
			LearningRate:     input.Stage.RuntimeProfile.LearningRate,
			Model:            "kilvin-base",
		},
		&materialized,
		180*time.Second,
		PipelineBundleOutput{PipelineID: pipelineID},
	); err != nil {
		outErr = err
	}
	if outErr != nil {
		pw.state = "FAILED"
		return PipelineWorkflowOutput{PipelineID: pipelineID, Failed: true, Error: outErr.Error()}, outErr
	}
	var submit SubmitK8sOutput
	if err := pw.runStep(
		ctx,
		input.Stage, input.StageIndex, &pipelineID, nil,
		"submit_k8s_job",
		SubmitK8sJob,
		SubmitK8sInput{
			PipelineID: pipelineID,
			Bundle:     materialized.Bundle,
			Namespace:  "kilvin-training",
		},
		&submit,
		180*time.Second,
		SubmitK8sOutput{
			AutoJobName:  "replay-skip-" + pipelineID,
			PrimusJobID:  "skip-replay",
			PrimusUIURL:  "skipped://monitor",
			K8sNamespace: "kilvin-training",
		},
	); err != nil {
		pw.state = "FAILED"
		return PipelineWorkflowOutput{PipelineID: pipelineID, Failed: true, Error: err.Error()}, err
	}
	var monitor MonitorOutput
	if err := pw.runStep(
		ctx,
		input.Stage, input.StageIndex, &pipelineID, nil,
		"monitor_training",
		MonitorTraining,
		MonitorTrainingInput{
			PipelineID:   pipelineID,
			AutoJobName:  submit.AutoJobName,
			PrimusJobID:  submit.PrimusJobID,
			IRName:       fmt.Sprintf("kilvin-ir-%s-%s", input.RunID, input.Stage.StageID),
			K8sNamespace: submit.K8sNamespace,
		},
		&monitor,
		3600*time.Second,
		MonitorOutput{FinalStatus: "SUCCEEDED"},
	); err != nil {
		pw.state = "FAILED"
		return PipelineWorkflowOutput{PipelineID: pipelineID, Failed: true, Error: err.Error()}, err
	}
	return PipelineWorkflowOutput{
		PipelineID: pipelineID,
		Bundle:     materialized.Bundle,
		Submit:     submit,
		Monitor:    monitor,
		StepTraces: pw.stepTraces,
	}, nil
}

func (pw *PipelineExecutionWorkflow) runStep(
	ctx workflow.Context,
	stage StageConfig,
	stageIndex int,
	pipelineID *string,
	pipelineIndex *int,
	stepName string,
	activityFn interface{},
	activityInput any,
	out interface{},
	timeout time.Duration,
	skipOut any,
) error {
	_ = timeout
	ctx = workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
		StartToCloseTimeout: 180 * time.Second,
		RetryPolicy: &temporal.RetryPolicy{MaximumAttempts: 3},
	})
	traceInput, err := PersistYAMLArtifact(ctx, ArtifactWriteInput{
		RunID:        pw.runID,
		RunAttempt:   pw.runAttempt,
		ArtifactName: fmt.Sprintf("%s/%s/%s/in.yaml", stage.StageID, derefPipelineID(pipelineID), stepName),
		Payload: map[string]any{
			"step_name":   stepName,
			"stage_id":    stage.StageID,
			"pipeline_id": derefPipelineID(pipelineID),
			"payload":     activityInput,
		},
	})
	if err != nil {
		return err
	}
	started := nowMs()
	if shouldSkipPipelineStep(pw.replay, 0, stage, stageIndex, pipelineID, stepName) {
		pw.stepTraces = append(pw.stepTraces, StepExecutionEnvelope{
			RunID:          pw.runID,
			RunAttempt:     pw.runAttempt,
			StageID:        stage.StageID,
			StageIndex:     stageIndex,
			StepName:       stepName,
			PipelineID:     copyStringPtr(pipelineID),
			PipelineIndex:  copyIntPtr(pipelineIndex),
			Status:         "SKIPPED",
			RetryAttempt:   0,
			InputArtifact:  traceInput,
			InputChecksum:  traceInput.ChecksumSHA256,
			Error:          "skipped for replay",
			StartedAtMS:    &started,
			CompletedAtMS:  &started,
		})
		if out != nil {
			pw.setOutput(out, skipOut)
		}
		return nil
	}
	pw.stepTraces = append(pw.stepTraces, StepExecutionEnvelope{
		RunID:          pw.runID,
		RunAttempt:     pw.runAttempt,
		StageID:        stage.StageID,
		StageIndex:     stageIndex,
		StepName:       stepName,
		PipelineID:     copyStringPtr(pipelineID),
		PipelineIndex:  copyIntPtr(pipelineIndex),
		Status:         "RUNNING",
		RetryAttempt:   0,
		InputArtifact:  traceInput,
		InputChecksum:  traceInput.ChecksumSHA256,
		StartedAtMS:    &started,
	})
	if out != nil {
		if err = workflow.ExecuteActivity(ctx, activityFn, activityInput).Get(ctx, out); err != nil {
			return err
		}
	} else {
		if err = workflow.ExecuteActivity(ctx, activityFn, activityInput).Get(ctx, nil); err != nil {
			return err
		}
	}
	var outArtifact StepIOArtifact
	_ = workflow.ExecuteActivity(ctx, PersistYAMLArtifact, ArtifactWriteInput{
		RunID:        pw.runID,
		RunAttempt:   pw.runAttempt,
		ArtifactName: fmt.Sprintf("%s/%s/%s/out.yaml", stage.StageID, derefPipelineID(pipelineID), stepName),
		Payload:      out,
	}).Get(ctx, &outArtifact)
	completed := nowMs()
	pw.stepTraces = append(pw.stepTraces, StepExecutionEnvelope{
		RunID:          pw.runID,
		RunAttempt:     pw.runAttempt,
		StageID:        stage.StageID,
		StageIndex:     stageIndex,
		StepName:       stepName,
		PipelineID:     copyStringPtr(pipelineID),
		PipelineIndex:  copyIntPtr(pipelineIndex),
		Status:         "SUCCEEDED",
		RetryAttempt:   0,
		InputArtifact:  traceInput,
		OutputArtifact: &outArtifact,
		InputChecksum:  traceInput.ChecksumSHA256,
		OutputChecksum: &outArtifact.ChecksumSHA256,
		StartedAtMS:    &started,
		CompletedAtMS:  &completed,
	})
	return nil
}

func (pw *PipelineExecutionWorkflow) setOutput(dst interface{}, src interface{}) {
	if dst == nil || src == nil {
		return
	}
	rv := reflect.ValueOf(dst)
	if rv.Kind() != reflect.Pointer || rv.IsNil() {
		return
	}
	sv := reflect.ValueOf(src)
	if !sv.IsValid() {
		return
	}
	if sv.Type().AssignableTo(rv.Elem().Type()) {
		rv.Elem().Set(sv)
	}
}

func max(a, b int) int {
	if a > b {
		return a
	}
	return b
}

func derefPipelineID(v *string) string {
	if v == nil {
		return "default"
	}
	return *v
}

func derefStr(v *string, fallback string) string {
	if v == nil || *v == "" {
		return fallback
	}
	return *v
}

func findAllocation(pipelineID string, allocations []PipelineAllocation) PipelineAllocation {
	for _, allocation := range allocations {
		if allocation.PipelineID == pipelineID {
			return allocation
		}
	}
	if len(allocations) > 0 {
		return allocations[0]
	}
	return PipelineAllocation{
		PipelineID:    pipelineID,
		ComponentName: "foundation_model",
		NodeCount:     1,
		GPUsPerNode:   1,
		RankSize:      1,
		MachineType:   "h100-sxm",
		PoolName:      "foundation",
		RDMAEnabled:   true,
		NCCLProfile:   "nccl",
	}
}

func intPtrPtr(v *int64) *int64 { return v }
