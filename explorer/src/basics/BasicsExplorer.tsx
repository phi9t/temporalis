import {
  ArrowRight,
  Boxes,
  Cpu,
  Database,
  Network,
  PackageCheck,
  Play,
  Route,
  ServerCog,
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { ExplorerModeProps } from '@/explorer-kit/mode'

interface ConceptCard {
  title: string
  plain: string
  temporalTerm: string
  example: string
}

interface TimelineStep {
  label: string
  summary: string
  substeps?: TimelineSubstep[]
}

interface TimelineSubstep {
  label: string
  detail: string
}

interface HoodOpenArtifact {
  label: string
  detail: string
}

const CONCEPTS: ConceptCard[] = [
  {
    title: 'Workflow',
    plain: 'The durable materialization process for a training run.',
    temporalTerm: 'Workflow logic coordinates decisions and decides what should happen next.',
    example: 'The workflow turns "train model X on FineWeb with 64 A100s" into concrete cluster, spec, submit, and monitor steps.',
  },
  {
    title: 'Activity',
    plain: 'A real-world action that can fail, retry, or take time.',
    temporalTerm: 'Activities perform side effects outside deterministic workflow code.',
    example: 'Docker CUDA/Torch image build, uv Python dependency sync, quota query, dataset lookup, k8s spec assembly, submit, and monitor are activities.',
  },
  {
    title: 'Worker',
    plain: 'A running process that asks Temporal for work and executes your code.',
    temporalTerm: 'Workers poll task queues for workflow and activity tasks.',
    example: 'Workers with the right credentials and tools execute activities; they do not own the business decision.',
  },
  {
    title: 'Task Queue',
    plain: 'The inbox workers watch for the next piece of work.',
    temporalTerm: 'Temporal Matching hands tasks to polling workers.',
    example: 'Build, quota, cluster, launch, and monitoring workers can each watch the queues meant for their environment.',
  },
  {
    title: 'History',
    plain: 'The durable memory of everything important that happened.',
    temporalTerm: 'History is the source of truth for workflow progress.',
    example: 'History records how intent became concrete launch state: cluster, 64 A100 placement, env vars, dataset path, job id, and progress.',
  },
  {
    title: 'Replay',
    plain: 'The way Temporal reconstructs a run so long-lived work can pause, resume, and survive restarts.',
    temporalTerm:
      'Replay reruns deterministic workflow code from recorded history; retries rerun failed activities, not already-recorded decisions.',
    example:
      'If a worker dies while waiting for GPUs, Temporal replays the placement and reservation history, then resumes from the open wait. Signals can record a pause or override without rebuilding the image or resubmitting blindly.',
  },
]

const TIMELINE: TimelineStep[] = [
  {
    label: 'Interpret training intent',
    summary: 'Start with a clean request: train model X on FineWeb with 64 A100 GPUs.',
  },
  {
    label: 'Build image and deps',
    summary:
      'Run the large Docker build for CUDA/Torch and sync Python deps with uv; CUDA/Torch mismatches, cold layer caches, flaky package indexes, and registry push timeouts make this step worth retrying and resuming.',
    substeps: [
      {
        label: 'CUDA/Torch base',
        detail: 'Pick the image, driver, and Torch build that match the target GPUs.',
      },
      {
        label: 'Docker build',
        detail: 'Compile layers, native libraries, training code, and runtime tools.',
      },
      {
        label: 'uv sync',
        detail: 'Resolve and install pinned Python dependencies for the training environment.',
      },
      {
        label: 'Push digest',
        detail: 'Publish the image and record the immutable digest for the launch spec.',
      },
    ],
  },
  {
    label: 'Gather resource constraints',
    summary:
      'Activities fan out to multiple external systems: quota, inventory, schedulers, rack topology, machine health, storage catalogs, and cluster metadata.',
  },
  {
    label: 'Solve placement plan',
    summary:
      'Workflow logic resolves the placement: cluster us-east-train-7, two healthy racks, a 64-A100 node pool, FineWeb-local storage, and policy-compatible networking.',
    substeps: [
      {
        label: 'Datacenter candidates',
        detail: 'Compare clusters across regions: some have GPUs, but not the needed NVMe, InfiniBand, rack shape, and storage reachability together.',
      },
      {
        label: 'GPU fit',
        detail: 'Find where 64 A100s can land together with healthy racks and compatible networking.',
      },
      {
        label: 'Data locality',
        detail: 'Prefer clusters with a regional FineWeb replica, such as s3://fineweb-us-east plus an FSx for Lustre mount, instead of a cross-region copy.',
      },
      {
        label: 'User quota',
        detail: 'Check whether this researcher or project can actually spend quota in that cluster.',
      },
    ],
  },
  {
    label: 'Reserve and pin resources',
    summary:
      'Activities join the reservation queue and may wait hours for the chosen GPUs; once granted, they pin machines and dataset path so the launch spec has stable pointers.',
  },
  {
    label: 'Materialize job spec',
    summary:
      'History records how roughly 10 lines of researcher intent expand into a 1000-line launch spec: command line, env vars, quota decision, cluster details, mounts, and k8s spec.',
  },
  {
    label: 'Submit and monitor with k8s',
    summary: 'Activities submit the job to Kubernetes, monitor status, and heartbeat progress over time.',
  },
  {
    label: 'Hotfix without starting over',
    summary:
      'Replay rebuilds run state after restarts; signals can record a focused hotfix like correcting the wrong env var or flag, or updating actor pod replicas without starting over.',
  },
]

const HOOD_OPEN_ARTIFACTS: HoodOpenArtifact[] = [
  {
    label: 'Materialized job spec',
    detail: 'The first place to inspect command-line options, env vars, mounts, and the Kubernetes shape.',
  },
  {
    label: 'Quota decision',
    detail: 'Why this cluster, racks, node pool, data locality, and 64 A100 placement were selected.',
  },
  {
    label: 'FineWeb dataset path',
    detail: 'The storage location and mount that are reachable from the selected cluster.',
  },
  {
    label: 'Image/deps output',
    detail: 'The image digest, build logs, cache hits or misses, registry push result, and uv dependency lock or sync output.',
  },
  {
    label: 'Kubernetes job id',
    detail: 'The submitted job handle used for follow-up monitoring and debugging.',
  },
  {
    label: 'Logs and events',
    detail: 'The second layer of truth when runtime behavior diverges from the materialized spec.',
  },
]

function ConceptGrid() {
  return (
    <section aria-labelledby="basics-concepts-title" className="basics-section">
      <div className="basics-section-heading">
        <h2 id="basics-concepts-title">Six ideas to hold onto</h2>
        <p>Temporal becomes easier once these words are tied to one concrete training run.</p>
      </div>
      <div className="basics-concept-grid">
        {CONCEPTS.map((concept) => (
          <Card key={concept.title} className="basics-concept-card">
            <CardHeader>
              <CardTitle>{concept.title}</CardTitle>
              <p>{concept.plain}</p>
            </CardHeader>
            <CardContent>
              <div className="basics-term">{concept.temporalTerm}</div>
              <p>{concept.example}</p>
            </CardContent>
          </Card>
        ))}
      </div>
    </section>
  )
}

function TrainingTimeline() {
  return (
    <section aria-labelledby="basics-timeline-title" className="basics-section">
      <div className="basics-section-heading">
        <h2 id="basics-timeline-title">One training run, one durable story</h2>
        <p>Temporal keeps the story moving while infrastructure decisions, retries, and monitoring unfold over time.</p>
      </div>
      <ol className="basics-timeline" aria-label="Model training workflow timeline">
        {TIMELINE.map((step, index) => (
          <li key={step.label} className="basics-timeline-step">
            <div className="basics-timeline-index">{String(index + 1).padStart(2, '0')}</div>
            <div>
              <div className="basics-timeline-label">{step.label}</div>
              <p>{step.summary}</p>
              {step.substeps ? (
                <div className="basics-subflow" role="region" aria-label={`${step.label} subprocess`}>
                  {step.substeps.map((substep) => (
                    <div key={substep.label} className="basics-subflow-card">
                      <div>{substep.label}</div>
                      <p>{substep.detail}</p>
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          </li>
        ))}
      </ol>
    </section>
  )
}

function HoodOpenArtifacts() {
  return (
    <section aria-labelledby="basics-artifacts-title" className="basics-section">
      <div className="basics-section-heading">
        <h2 id="basics-artifacts-title">Hood-open artifacts</h2>
        <p>
          The pipeline hides cluster/rack/machine details during launch, but it should not become a black box. When a
          run needs debugging, researchers start with the materialized job spec and then read the logs.
        </p>
      </div>
      <div className="basics-artifact-grid">
        {HOOD_OPEN_ARTIFACTS.map((artifact) => (
          <div key={artifact.label} className="basics-artifact">
            <div>{artifact.label}</div>
            <p>{artifact.detail}</p>
          </div>
        ))}
      </div>
    </section>
  )
}

export default function BasicsExplorer({ navigate }: ExplorerModeProps) {
  return (
    <div className="basics-page">
      <section className="basics-hero" aria-labelledby="basics-title">
        <div className="basics-hero-copy">
          <div className="basics-kicker">
            <Cpu size={15} aria-hidden="true" />
            LLM training walkthrough
          </div>
          <h2 id="basics-title">Temporal remembers the process when your code cannot stay awake.</h2>
          <p>
            Imagine an ML researcher asking for one clean thing: train model X on FineWeb with 64 A100 GPUs. The pipeline
            has to turn that intent into a concrete launch plan: build the image, find quota, choose machines, locate
            the dataset, assemble env vars and flags, and submit a Kubernetes job. Temporal keeps that translation
            durable and inspectable, so it can retry fragile steps, resume after restarts, and expose override points
            without forcing researchers to hand-assemble every cluster detail.
          </p>
        </div>
        <div className="basics-flow" aria-label="Model training workflow overview">
          <div>
            <Play size={18} aria-hidden="true" />
            <span>Build deps</span>
          </div>
          <ArrowRight size={16} aria-hidden="true" />
          <div>
            <Boxes size={18} aria-hidden="true" />
            <span>Find quota</span>
          </div>
          <ArrowRight size={16} aria-hidden="true" />
          <div>
            <ServerCog size={18} aria-hidden="true" />
            <span>Spec cluster</span>
          </div>
          <ArrowRight size={16} aria-hidden="true" />
          <div>
            <PackageCheck size={18} aria-hidden="true" />
            <span>Submit and monitor</span>
          </div>
        </div>
      </section>

      <ConceptGrid />
      <TrainingTimeline />
      <HoodOpenArtifacts />

      <section aria-labelledby="basics-next-title" className="basics-next">
        <div>
          <div className="basics-kicker">
            <Database size={15} aria-hidden="true" />
            Where this maps in the deep dive
          </div>
          <h2 id="basics-next-title">Once the basics click, follow the same ideas through the real internals.</h2>
        </div>
        <div className="basics-next-actions">
          <button type="button" className="basics-next-button" onClick={() => navigate('lifecycle')}>
            <Route size={16} aria-hidden="true" />
            Lifecycle Deep Dive
          </button>
          <button type="button" className="basics-next-button" onClick={() => navigate('control')}>
            <Network size={16} aria-hidden="true" />
            Control Paths
          </button>
        </div>
      </section>
    </div>
  )
}
