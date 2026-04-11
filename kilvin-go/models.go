package main


type StepIOArtifact struct {
	URI            string `yaml:"uri" json:"uri"`
	Format         string `yaml:"format" json:"format"`
	ChecksumSHA256 string `yaml:"checksum_sha256" json:"checksum_sha256"`
	SizeBytes      int64  `yaml:"size_bytes" json:"size_bytes"`
}

type StepExecutionEnvelope struct {
	RunID           string          `yaml:"run_id" json:"run_id"`
	RunAttempt      int             `yaml:"run_attempt" json:"run_attempt"`
	StageID         string          `yaml:"stage_id" json:"stage_id"`
	StageIndex      int             `yaml:"stage_index" json:"stage_index"`
	StepName        string          `yaml:"step_name" json:"step_name"`
	PipelineID      *string         `yaml:"pipeline_id,omitempty" json:"pipeline_id,omitempty"`
	PipelineIndex   *int            `yaml:"pipeline_index,omitempty" json:"pipeline_index,omitempty"`
	Status          string          `yaml:"status" json:"status"`
	RetryAttempt    int             `yaml:"retry_attempt" json:"retry_attempt"`
	InputArtifact   StepIOArtifact  `yaml:"input_artifact" json:"input_artifact"`
	OutputArtifact  *StepIOArtifact `yaml:"output_artifact,omitempty" json:"output_artifact,omitempty"`
	Error           string          `yaml:"error,omitempty" json:"error,omitempty"`
	InputChecksum   string          `yaml:"input_checksum" json:"input_checksum"`
	OutputChecksum  *string         `yaml:"output_checksum,omitempty" json:"output_checksum,omitempty"`
	StartedAtMS     *int64          `yaml:"started_at_ms,omitempty" json:"started_at_ms,omitempty"`
	CompletedAtMS   *int64          `yaml:"completed_at_ms,omitempty" json:"completed_at_ms,omitempty"`
}

type StageDatasetProfile struct {
	URI                        string            `yaml:"uri"`
	MinExamples                int               `yaml:"min_examples"`
	TokenBudget                int64             `yaml:"token_budget"`
	TokenBudgetToleranceRatio  float64           `yaml:"token_budget_tolerance_ratio"`
	MixRequirements            map[string]float64 `yaml:"mix_requirements,omitempty"`
	QualityThresholds          map[string]float64 `yaml:"quality_thresholds,omitempty"`
}

type StageRuntimeProfile struct {
	TotalTokensTarget int64   `yaml:"total_tokens_target"`
	MaxSteps          int64   `yaml:"max_steps"`
	GlobalBatchTokens int64   `yaml:"global_batch_tokens"`
	LearningRate      float64 `yaml:"learning_rate"`
	Optimizer         string  `yaml:"optimizer"`
	Precision         string  `yaml:"precision"`
}

type PipelineStrategy struct {
	Mode           string `yaml:"mode"` // serial | parallel
	MaxParallelism *int   `yaml:"max_parallelism,omitempty"`
	JoinBehavior   string `yaml:"join_behavior"` // all_required | allow_partial
}

type PipelineConfig struct {
	PipelineID       string             `yaml:"pipeline_id"`
	ComponentName    string             `yaml:"component_name"`
	ComponentVersion string             `yaml:"component_version"`
	MachineType      string             `yaml:"machine_type,omitempty"`
	NodeCount        int                `yaml:"node_count"`
	GPUsPerNode      int                `yaml:"gpus_per_node"`
	RankSize         int                `yaml:"rank_size"`
	ResourcePool     string             `yaml:"resource_pool,omitempty"`
	RDMAProfile      *string            `yaml:"rdma_profile,omitempty"`
	NCCLProfile      *string            `yaml:"nccl_profile,omitempty"`
	MaxSeqLen        *int               `yaml:"max_seq_len,omitempty"`
	ModalityMix      map[string]float64  `yaml:"modality_mix,omitempty"`
	TransportProfile *string            `yaml:"transport_profile,omitempty"`
	PipelineType     string             `yaml:"pipeline_type"`
	StageOverrides   map[string]any     `yaml:"stage_overrides,omitempty"`
}

type StageConfig struct {
	StageID         string             `yaml:"stage_id"`
	StageType       string             `yaml:"stage_type"`
	Phase           string             `yaml:"phase"`
	Enabled         bool               `yaml:"enabled"`
	DatasetProfile  StageDatasetProfile `yaml:"dataset_profile"`
	RuntimeProfile  StageRuntimeProfile `yaml:"runtime_profile"`
	PipelineStrategy *PipelineStrategy  `yaml:"pipeline_strategy,omitempty"`
	Pipelines       []PipelineConfig   `yaml:"pipelines,omitempty"`
	StageRetry      *int               `yaml:"stage_retry,omitempty"`
	StageTimeoutMin int                `yaml:"stage_timeout_minutes,omitempty"`
	DependsOn       []string           `yaml:"depends_on,omitempty"`
}

type RunPolicy struct {
	MaxStageRetries           int    `yaml:"max_stage_retries"`
	StageTimeoutMinutes       int    `yaml:"stage_timeout_minutes"`
	PurgeOnSuccess            bool   `yaml:"purge_on_success"`
	PreserveArtifactsOnFailure bool  `yaml:"preserve_artifacts_on_failure"`
	PauseOnStepFailure        bool   `yaml:"pause_on_step_failure"`
	MaxStepReplayAttempts     int    `yaml:"max_step_replay_attempts"`
	ArtifactStoreURI          string `yaml:"artifact_store_uri"`
}

type RunConfig struct {
	RunID         string       `yaml:"run_id"`
	KilvinRunName string       `yaml:"kilvin_run_name"`
	WorkflowSpec  string       `yaml:"workflow_spec"`
	Policy        RunPolicy    `yaml:"policy"`
	StageSequence []string     `yaml:"stage_sequence"`
	Stages        []StageConfig `yaml:"stages"`
	Metadata      map[string]any `yaml:"metadata,omitempty"`
}

type StartKilvinCommandInput struct {
	RunConfig    RunConfig `yaml:"run_config"`
	CmdName      string    `yaml:"cmd_name"`
	JobParamsURI string    `yaml:"job_params_uri"`
}

type ParentRunOutput struct {
	RunID      string  `yaml:"run_id"`
	FinalState string  `yaml:"final_state"`
	IRName     *string `yaml:"ir_name,omitempty"`
	Error      *string `yaml:"error,omitempty"`
}

type ExtractCmdConfigInput struct {
	RunConfig    RunConfig `yaml:"run_config"`
	CmdName      string    `yaml:"cmd_name"`
	JobParamsURI string    `yaml:"job_params_uri"`
}

type ExtractCmdConfigOutput struct {
	ModelOutputTosKey string        `yaml:"model_output_tos_key"`
	WorkflowConfigURI string        `yaml:"workflow_config_uri"`
	Checkpoint       *string       `yaml:"checkpoint"`
	StageIndex       int           `yaml:"stage_index"`
	ComponentProfile map[string]any `yaml:"component_profile"`
}

type TrainingWorkflowInput struct {
	RunID     string             `yaml:"run_id"`
	RunConfig RunConfig          `yaml:"run_config"`
	Extracted ExtractCmdConfigOutput `yaml:"extracted"`
}

type PipelineWorkflowInput struct {
	RunID           string            `yaml:"run_id"`
	RunAttempt      int               `yaml:"run_attempt"`
	Stage           StageConfig       `yaml:"stage"`
	StageIndex      int               `yaml:"stage_index"`
	Profile         PipelineConfig    `yaml:"pipeline_profile"`
	Allocation      PipelineAllocation `yaml:"allocation"`
	CurrentCheckpoint string          `yaml:"current_checkpoint"`
	ConfigSnapshot  string            `yaml:"config_snapshot"`
	TaskType        string            `yaml:"task_type"`
}

type PipelineWorkflowOutput struct {
	PipelineID string                `yaml:"pipeline_id"`
	Bundle     MaterializedBundleOutput `yaml:"bundle"`
	Submit     SubmitK8sOutput       `yaml:"submit"`
	Monitor    MonitorOutput         `yaml:"monitor"`
	StepTraces []StepExecutionEnvelope `yaml:"step_traces"`
	Failed     bool                  `yaml:"failed"`
	Error      string                `yaml:"error,omitempty"`
}

type DevPrepareInput struct {
	RunID      string  `yaml:"run_id"`
	Checkpoint *string `yaml:"checkpoint"`
}

type DevPrepareOutput struct {
	AutoJobID  string `yaml:"auto_job_id"`
	CodeTosKey string `yaml:"code_tos_key"`
}

type CheckpointOutput struct {
	CheckpointPath   string `yaml:"checkpoint_path"`
	ManifestURI      string `yaml:"manifest_uri"`
	ModelSizeEstimate int64 `yaml:"model_size_estimate"`
}

type ConfigureTrainingDataInput struct {
	DatasetURI                string             `yaml:"dataset_uri"`
	DatasetStage              string             `yaml:"dataset_stage"`
	RequiredTokenBudget       int64              `yaml:"required_token_budget"`
	MinExamples               int                `yaml:"min_examples"`
	TokenBudgetToleranceRatio float64            `yaml:"token_budget_tolerance_ratio"`
	DataMixRequirements       map[string]float64 `yaml:"data_mix_requirements,omitempty"`
	QualityThresholds         map[string]float64 `yaml:"quality_thresholds,omitempty"`
}

type DataConfigureOutput struct {
	DatasetID            string             `yaml:"dataset_id"`
	SchemaVersion        string             `yaml:"schema_version"`
	ShardCount           int                `yaml:"shard_count"`
	EstimatedTokens      int64              `yaml:"estimated_tokens"`
	StageTokenMix        map[string]int64   `yaml:"stage_token_mix"`
	CompositionBreakdown map[string]float64 `yaml:"composition_breakdown"`
	QualityScores        map[string]float64 `yaml:"quality_scores"`
	TotalExamples        int                `yaml:"total_examples"`
	FormatOK             bool               `yaml:"format_ok"`
	ValidationReportPath *string            `yaml:"validation_report_path,omitempty"`
}

type AllocateResourcesInput struct {
	RunID           string           `yaml:"run_id"`
	StageID         string           `yaml:"stage_id"`
	StageIndex      int              `yaml:"stage_index"`
	PipelineProfiles []PipelineConfig `yaml:"pipeline_profiles"`
}

type PipelineAllocation struct {
	PipelineID    string            `yaml:"pipeline_id"`
	ComponentName string            `yaml:"component_name"`
	NodeCount     int               `yaml:"node_count"`
	GPUsPerNode   int               `yaml:"gpus_per_node"`
	RankSize      int               `yaml:"rank_size"`
	MachineType   string            `yaml:"machine_type"`
	PoolName      string            `yaml:"pool_name"`
	RDMAEnabled   bool              `yaml:"rdma_enabled"`
	NCCLProfile   string            `yaml:"nccl_profile"`
	Rendezvous    map[string]string `yaml:"rendezvous,omitempty"`
}

type ReamAllocationOutput struct {
	AllocationID       string               `yaml:"allocation_id"`
	ResourceEpoch      int                  `yaml:"resource_epoch"`
	PoolsReservationID string               `yaml:"pools_reservation_id"`
	PipelineAllocations []PipelineAllocation `yaml:"pipeline_allocations"`
}

type MaterializeTrainingBundleInput struct {
	IRName            string           `yaml:"ir_name"`
	Checkpoint        string           `yaml:"checkpoint"`
	ConfigSnapshot    string           `yaml:"config_snapshot"`
	PipelineID        string           `yaml:"pipeline_id"`
	Allocation        PipelineAllocation `yaml:"allocation"`
	PipelineProfile   PipelineConfig     `yaml:"pipeline_profile"`
	StageIndex        int              `yaml:"stage_index"`
	TrainStage        string           `yaml:"train_stage"`
	TaskType          string           `yaml:"task_type"`
	TotalTokensTarget int64             `yaml:"total_tokens_target"`
	GlobalBatchTokens int64             `yaml:"global_batch_tokens"`
	MaxSteps          int64             `yaml:"max_steps"`
	LearningRate      float64           `yaml:"learning_rate"`
	Model             string            `yaml:"model"`
}

type MaterializedBundleOutput struct {
	BundleID        string              `yaml:"bundle_id"`
	BundlePath      string              `yaml:"bundle_path"`
	BoundComponents []map[string]any    `yaml:"bound_components"`
	RuntimeSetup    map[string]any     `yaml:"runtime_setup"`
	Rendezvous      map[string]any     `yaml:"rendezvous"`
	LaunchPlan      []map[string]any   `yaml:"launch_plan"`
	TokenPlan       map[string]int64    `yaml:"token_plan"`
	HealthChecks    []string            `yaml:"health_checks"`
}

type PipelineBundleOutput struct {
	PipelineID string               `yaml:"pipeline_id"`
	Bundle     MaterializedBundleOutput `yaml:"bundle"`
}

type SubmitK8sInput struct {
	PipelineID string             `yaml:"pipeline_id"`
	Bundle     MaterializedBundleOutput `yaml:"bundle"`
	Namespace  string             `yaml:"namespace"`
}

type SubmitK8sOutput struct {
	AutoJobName  string `yaml:"auto_job_name"`
	PrimusJobID  string `yaml:"primus_job_id"`
	PrimusUIURL  string `yaml:"primus_ui_url"`
	K8sNamespace string `yaml:"k8s_namespace"`
}

type MonitorTrainingInput struct {
	PipelineID   string `yaml:"pipeline_id"`
	AutoJobName  string `yaml:"auto_job_name"`
	PrimusJobID  string `yaml:"primus_job_id"`
	IRName       string `yaml:"ir_name"`
	K8sNamespace string `yaml:"k8s_namespace"`
}

type MonitorOutput struct {
	FinalStatus string `yaml:"final_status"`
	RunningPods int    `yaml:"running_pods"`
	TotalPods   int    `yaml:"total_pods"`
}

type PurgeInput struct {
	RunID             string  `yaml:"run_id"`
	StageID           string  `yaml:"stage_id"`
	PreserveArtifacts bool    `yaml:"preserve_artifacts"`
	Checkpoint        *string `yaml:"checkpoint"`
}

type ArtifactWriteInput struct {
	RunID        string `yaml:"run_id"`
	RunAttempt   int    `yaml:"run_attempt"`
	ArtifactName string `yaml:"artifact_name"`
	Payload      any    `yaml:"payload"`
}

type PauseSignal struct {
	Reason *string `yaml:"reason"`
}

type ResumeSignal struct {
	Reason *string `yaml:"reason"`
}

type CancelSignal struct {
	Reason *string `yaml:"reason"`
}

type PauseAtStepSignal struct {
	StageID    string  `yaml:"stage_id"`
	PipelineID *string `yaml:"pipeline_id"`
	StepName   string  `yaml:"step_name"`
	When       string  `yaml:"when"` // pre | post
}

type ReplaySignal struct {
	Scope            string  `yaml:"scope"` // step | pipeline | stage
	TargetStageID    string  `yaml:"target_stage_id"`
	TargetPipelineID *string `yaml:"target_pipeline_id"`
	TargetStep       string  `yaml:"target_step"`
	Force            bool    `yaml:"force"`
	AllowDryRun      bool    `yaml:"allow_dry_run"`
	Reason           *string `yaml:"reason"`
}

type StageExecutionFailure struct {
	StageID    string  `yaml:"stage_id"`
	PipelineID *string `yaml:"pipeline_id,omitempty"`
	StepName   string  `yaml:"step_name"`
	Attempt    int     `yaml:"attempt"`
	Error      string  `yaml:"error"`
}

type KilvinRunState struct {
	RunID           string                  `yaml:"run_id"`
	RunAttempt      int                     `yaml:"run_attempt"`
	CurrentStage    string                  `yaml:"current_stage"`
	CurrentPipeline *string                 `yaml:"current_pipeline"`
	CurrentStep     *string                 `yaml:"current_step"`
	OverallStatus   string                  `yaml:"overall_status"`
	Paused          bool                    `yaml:"paused"`
	StageTraces     []StepExecutionEnvelope `yaml:"stage_traces"`
	Failures        []StageExecutionFailure  `yaml:"failures"`
}
