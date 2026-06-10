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
    example: 'Image/deps build, quota query, dataset lookup, env/flag fetch, k8s spec assembly, submit, and monitor are activities.',
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
    plain: 'The way Temporal rebuilds workflow state after a restart.',
    temporalTerm: 'Replay reruns deterministic workflow code from recorded history.',
    example: 'After a worker restart, the run resumes from recorded decisions instead of rebuilding or resubmitting blindly.',
  },
]

const TIMELINE: TimelineStep[] = [
  {
    label: 'Interpret training intent',
    summary: 'Start with a clean request: train model X on FineWeb with 64 A100 GPUs.',
  },
  {
    label: 'Build image and deps',
    summary: 'The workflow coordinates a fragile build activity, so failures are visible and can be retried or resumed.',
  },
  {
    label: 'Query quota and cluster options',
    summary: 'Activities ask external systems which clusters, racks, and GPU pools can satisfy the run.',
  },
  {
    label: 'Choose target cluster',
    summary: 'Workflow logic chooses the cluster from returned quota, policy, and constraints.',
  },
  {
    label: 'Reserve machines and locate data',
    summary: 'Activities reserve resources and find the FineWeb storage path accessible from the selected cluster.',
  },
  {
    label: 'Materialize job spec',
    summary: 'History records the final command line, env vars, quota decision, cluster details, mounts, and k8s spec.',
  },
  {
    label: 'Submit and monitor with k8s',
    summary: 'Activities submit the job to Kubernetes, monitor status, and heartbeat progress over time.',
  },
  {
    label: 'Resume or override',
    summary: 'Replay rebuilds run state after restarts; signals can later pause or override without starting over.',
  },
]

const HOOD_OPEN_ARTIFACTS: HoodOpenArtifact[] = [
  {
    label: 'Materialized job spec',
    detail: 'The first place to inspect command-line options, env vars, mounts, and the Kubernetes shape.',
  },
  {
    label: 'Quota decision',
    detail: 'Why this cluster, rack, machine pool, and 64 A100 placement were selected.',
  },
  {
    label: 'FineWeb dataset path',
    detail: 'The storage location and mount that are reachable from the selected cluster.',
  },
  {
    label: 'Image/deps output',
    detail: 'The build artifact, dependency bundle, or digest produced by the fragile build step.',
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
            hides the gory cluster, rack, and machine details during launch, but preserves the pointers needed to open
            the hood later. Temporal makes that materialization process durable, inspectable, retryable, resumable, and
            overrideable.
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
