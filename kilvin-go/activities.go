package main

import (
	"context"
	"fmt"
	"time"

	"go.temporal.io/sdk/activity"
)

func ExtractCmdConfig(ctx context.Context, input ExtractCmdConfigInput) (ExtractCmdConfigOutput, error) {
	if len(input.RunConfig.Stages) == 0 {
		return ExtractCmdConfigOutput{}, fmt.Errorf("no stages configured")
	}
	stageZero := input.RunConfig.Stages[0]
	checkpoint := stageZero.DatasetProfile.URI
	uri := "file://./.kilvin-cache/" + input.RunConfig.RunID + "/workflow.yaml"
	return ExtractCmdConfigOutput{
		ModelOutputTosKey: input.JobParamsURI,
		WorkflowConfigURI: uri,
		Checkpoint:       &checkpoint,
		StageIndex:       0,
		ComponentProfile: map[string]any{
			"command":     input.CmdName,
			"dataset_root": stageZero.DatasetProfile.URI,
			"spec_version": input.RunConfig.WorkflowSpec,
		},
	}, nil
}

func UpdateCmdState(ctx context.Context, input map[string]any) error {
	activity.GetLogger(ctx).Info("UpdateCmdState placeholder", "input", input)
	return nil
}

func DevPrepare(ctx context.Context, input DevPrepareInput) (DevPrepareOutput, error) {
	suffix := "scratch"
	if input.Checkpoint != nil && *input.Checkpoint != "" {
		suffix = *input.Checkpoint
	}
	return DevPrepareOutput{
		AutoJobID:  fmt.Sprintf("kilvin-job-%d", time.Now().UnixNano()),
		CodeTosKey: suffix + "/artifacts/code.tar.gz",
	}, nil
}

func ValidateCheckpoint(ctx context.Context, checkpointPath string) (CheckpointOutput, error) {
	uri := checkpointPath
	if uri == "" {
		uri = "s3://models/k2/checkpoint"
	}
	return CheckpointOutput{
		CheckpointPath:   uri,
		ManifestURI:      uri + "/manifest.yaml",
		ModelSizeEstimate: 700_000_000_000,
	}, nil
}

func ConfigureTrainingData(ctx context.Context, input ConfigureTrainingDataInput) (DataConfigureOutput, error) {
	mix := input.DataMixRequirements
	if mix == nil {
		mix = map[string]float64{"text": 1.0}
	}
	quality := input.QualityThresholds
	if quality == nil {
		quality = map[string]float64{"overall": 0.99}
	}
	minExamples := input.MinExamples
	if minExamples < 1 {
		minExamples = 1_000
	}
	shards := minExamples / 10_000
	if shards < 1 {
		shards = 1
	}
	stageMix := map[string]int64{}
	for k, v := range mix {
		stageMix[k] = int64(v * 1000)
	}
	return DataConfigureOutput{
		DatasetID:            "ds-" + safePathLeaf(input.DatasetURI),
		SchemaVersion:        "v1",
		ShardCount:           shards,
		EstimatedTokens:      input.RequiredTokenBudget,
		StageTokenMix:        stageMix,
		CompositionBreakdown:  mix,
		QualityScores:        quality,
		TotalExamples:        minExamples,
		FormatOK:             true,
		ValidationReportPath:  strPtr(input.DatasetURI + "/validation-report.yaml"),
	}, nil
}

func AllocateResources(ctx context.Context, input AllocateResourcesInput) (ReamAllocationOutput, error) {
	allocations := make([]PipelineAllocation, 0, len(input.PipelineProfiles))
	for _, profile := range input.PipelineProfiles {
		allocations = append(allocations, PipelineAllocation{
			PipelineID:    profile.PipelineID,
			ComponentName: profile.ComponentName,
			NodeCount:     profile.NodeCount,
			GPUsPerNode:   profile.GPUsPerNode,
			RankSize:      profile.RankSize,
			MachineType:   profile.MachineType,
			PoolName:      choose(profile.ResourcePool, "foundation"),
			RDMAEnabled:   profile.RDMAProfile != nil,
			NCCLProfile:   choose(profile.NCCLProfile, "nccl"),
			Rendezvous: map[string]string{
				"control": "grpc://kilvin-controller:9001",
			},
		})
	}
	if len(allocations) == 0 {
		allocations = append(allocations, PipelineAllocation{
			PipelineID:    "default-pipeline",
			ComponentName: "foundation_model",
			NodeCount:     64,
			GPUsPerNode:   8,
			RankSize:      512,
			MachineType:   "h100-sxm",
			PoolName:      "foundation",
			RDMAEnabled:   true,
			NCCLProfile:   "nccl",
			Rendezvous: map[string]string{
				"control": "grpc://kilvin-controller:9001",
			},
		})
	}
	return ReamAllocationOutput{
		AllocationID:       "alloc-" + safePathLeaf(input.RunID),
		ResourceEpoch:      1,
		PoolsReservationID: "pool-" + safePathLeaf(input.RunID),
		PipelineAllocations: allocations,
	}, nil
}

func MaterializeTrainingBundle(ctx context.Context, input MaterializeTrainingBundleInput) (PipelineBundleOutput, error) {
	tokenPlan := map[string]int64{
		"total_tokens_target":  input.TotalTokensTarget,
		"global_batch_tokens":  input.GlobalBatchTokens,
		"max_steps":           input.MaxSteps,
		"token_margin":        input.TotalTokensTarget / 20,
	}
	if tokenPlan["token_margin"] <= 0 {
		tokenPlan["token_margin"] = 1_000_000
	}
	bound := map[string]any{
		"component":      input.Allocation.ComponentName,
		"machine_type":   input.Allocation.MachineType,
		"node_count":     input.Allocation.NodeCount,
		"gpus_per_node":  input.Allocation.GPUsPerNode,
		"rank_size":      input.Allocation.RankSize,
		"modality_mix":   input.PipelineProfile.ModalityMix,
		"rdma_profile":   stringOr(input.Allocation.PipelineID, "none"),
		"nccl_profile":   input.Allocation.NCCLProfile,
		"max_seq_len":    input.PipelineProfile.MaxSeqLen,
	}
	setup := map[string]any{
		"checkpoint":       input.Checkpoint,
		"task_type":        input.TaskType,
		"train_stage":      input.TrainStage,
		"model":            input.Model,
		"rdma_enabled":     true,
	}
	if input.PipelineProfile.RDMAProfile != nil {
		setup["rdma_profile"] = *input.PipelineProfile.RDMAProfile
	}
	if input.PipelineProfile.NCCLProfile != nil {
		setup["nccl_profile"] = *input.PipelineProfile.NCCLProfile
	}
	return PipelineBundleOutput{
		PipelineID: input.PipelineID,
		Bundle: MaterializedBundleOutput{
			BundleID:   "bundle-" + safePathLeaf(input.ConfigSnapshot),
			BundlePath: fmt.Sprintf("%s/bundle/%s.yaml", input.ConfigSnapshot, input.PipelineID),
			BoundComponents: []map[string]any{
				bound,
			},
			RuntimeSetup: setup,
			Rendezvous:   input.Allocation.Rendezvous,
			LaunchPlan: []map[string]any{
				{
					"entrypoint": "kilvin-train",
					"args": []string{
						"--config",
						input.ConfigSnapshot,
						"--stage",
						input.TrainStage,
					},
				},
			},
			TokenPlan:    tokenPlan,
			HealthChecks: []string{"nccl-rings", "kv-router", "data-loader", "rdma-topology"},
		},
	}, nil
}

func SubmitK8sJob(ctx context.Context, input SubmitK8sInput) (SubmitK8sOutput, error) {
	namespace := chooseStr(input.Namespace, "kilvin-training")
	return SubmitK8sOutput{
		AutoJobName:  "kilvin-" + input.PipelineID + "-" + safePathLeaf(fmt.Sprintf("%d", time.Now().UnixNano())),
		PrimusJobID:  "p-" + safePathLeaf(fmt.Sprintf("%d", time.Now().UnixNano())),
		PrimusUIURL:  "https://primus.local/job/" + safePathLeaf(fmt.Sprintf("%d", time.Now().UnixNano())),
		K8sNamespace: namespace,
	}, nil
}

func MonitorTraining(ctx context.Context, input MonitorTrainingInput) (MonitorOutput, error) {
	for i := 0; i < 3; i++ {
		activity.RecordHeartbeat(ctx, map[string]any{
			"pipeline_id":  input.PipelineID,
			"auto_job":     input.AutoJobName,
			"primus_job_id": input.PrimusJobID,
			"iteration":    i,
		})
	}
	return MonitorOutput{
		FinalStatus: "SUCCEEDED",
		RunningPods: 1,
		TotalPods:   1,
	}, nil
}

func PurgeResources(_ context.Context, input PurgeInput) error {
	_ = input
	return nil
}

func PersistYAMLArtifact(ctx context.Context, input ArtifactWriteInput) (StepIOArtifact, error) {
	store := NewArtifactStore("file://./.kilvin-artifacts")
	artifact, err := store.WriteYAMLArtifact(input.RunID, input.RunAttempt, input.ArtifactName, input.Payload)
	if err != nil {
		return StepIOArtifact{}, err
	}
	activity.GetLogger(ctx).Info("Persist YAML artifact", "uri", artifact.URI)
	return artifact, nil
}

func validateCheckpoint() {}

func safePathLeaf(raw string) string {
	n := raw
	for len(n) > 0 && (n[len(n)-1] == '/' || n[len(n)-1] == '\\') {
		n = n[:len(n)-1]
	}
	if idx := len(n); idx > 16 {
		n = n[idx-16:]
	}
	if n == "" {
		n = "fallback"
	}
	for i := len(n) - 1; i >= 0; i-- {
		if n[i] >= '0' && n[i] <= '9' || n[i] >= 'a' && n[i] <= 'z' || n[i] >= 'A' && n[i] <= 'Z' {
			continue
		}
	}
	return n
}

func strPtr(v string) *string {
	return &v
}

func choose(base string, fallback string) string {
	if base == "" {
		return fallback
	}
	return base
}

func stringOr(v string, fallback string) string {
	if v == "" {
		return fallback
	}
	return v
}

