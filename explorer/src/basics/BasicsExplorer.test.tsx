import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import BasicsExplorer from './BasicsExplorer'

afterEach(() => cleanup())

describe('BasicsExplorer', () => {
  it('explains Temporal through an LLM training story and the six core concepts', () => {
    render(<BasicsExplorer navigate={vi.fn()} />)

    expect(screen.getAllByText(/train model X on FineWeb with 64 A100 GPUs/).length).toBeGreaterThan(0)
    expect(screen.getByText(/turn that intent into a concrete launch plan/)).toBeTruthy()
    expect(screen.getByText(/retry fragile steps, resume after restarts, and expose override points/)).toBeTruthy()
    expect(screen.getByText(/for real at laptop scale/)).toBeTruthy()

    for (const concept of ['Workflow', 'Activity', 'Worker', 'Task Queue', 'History', 'Replay']) {
      expect(screen.getByRole('heading', { name: concept })).toBeTruthy()
    }
    expect(screen.getByText(/pause, resume, and survive restarts/)).toBeTruthy()
    expect(screen.getByText(/retries rerun failed activities/)).toBeTruthy()
    expect(screen.getByText(/waiting for GPUs/)).toBeTruthy()
    expect(screen.getByText(/Signals can record a pause or override/)).toBeTruthy()

    const heroFlow = screen.getByRole('list', { name: 'Model training workflow overview' })
    expect(heroFlow.textContent).toContain('Build deps')
    expect(heroFlow.textContent).toContain('Find quota')
    expect(heroFlow.textContent).toContain('Spec cluster')
    expect(heroFlow.textContent).toContain('Submit and monitor')
    expect(screen.getAllByRole('listitem', { name: /hero overview step/i })).toHaveLength(4)

    const timeline = screen.getByRole('list', { name: 'Model training workflow timeline' })
    const timelineText = timeline.textContent ?? ''
    const timelineStepText = (label: string) => screen.getByText(label).closest('li')?.textContent ?? ''
    const timelineLabels = [
      'Interpret training intent',
      'Build image and deps',
      'Gather resource constraints',
      'Solve placement plan',
      'Reserve and pin resources',
      'Materialize job spec',
      'Submit and monitor with k8s',
      'Hotfix without starting over',
    ]

    for (const label of timelineLabels) {
      expect(timelineText).toContain(label)
    }
    const cueLegend = screen.getByRole('region', { name: 'What to watch for' })
    const cueLegendText = cueLegend.textContent ?? ''
    for (const cueLabel of ['Fragile', 'Can take hours', 'Many systems', 'Inspect this', 'Retry/resume', 'Hotfix']) {
      expect(cueLegendText).toContain(cueLabel)
      expect(screen.getAllByText(cueLabel).length).toBeGreaterThan(0)
    }
    expect(cueLegendText).toContain('slow, brittle, or worth inspecting')

    expect(timelineStepText('Interpret training intent')).not.toContain('Fragile')
    expect(timelineStepText('Build image and deps')).toContain('Fragile')
    expect(timelineStepText('Build image and deps')).toContain('Retry/resume')
    expect(timelineStepText('Gather resource constraints')).toContain('Many systems')
    expect(timelineStepText('Solve placement plan')).toContain('Many systems')
    expect(timelineStepText('Reserve and pin resources')).toContain('Can take hours')
    expect(timelineStepText('Reserve and pin resources')).toContain('Retry/resume')
    expect(timelineStepText('Materialize job spec')).toContain('Inspect this')
    expect(timelineStepText('Submit and monitor with k8s')).toContain('Can take hours')
    expect(timelineStepText('Hotfix without starting over')).toContain('Hotfix')
    expect(timelineStepText('Hotfix without starting over')).toContain('Retry/resume')

    expect(timelineText).toContain('Docker build for CUDA/Torch')
    expect(timelineText).toContain('sync Python deps with uv')
    expect(timelineText).toContain('CUDA/Torch mismatches')
    expect(timelineText).toContain('flaky package indexes')
    expect(timelineText).toContain('registry push timeouts')
    expect(screen.getByRole('region', { name: 'Build image and deps subprocess' })).toBeTruthy()
    expect(timelineText).toContain('CUDA/Torch base')
    expect(timelineText).toContain('driver, and Torch build')
    expect(timelineText).toContain('Docker build')
    expect(timelineText).toContain('native libraries')
    expect(timelineText).toContain('uv sync')
    expect(timelineText).toContain('pinned Python dependencies')
    expect(timelineText).toContain('Push digest')
    expect(timelineText).toContain('immutable digest')
    expect(timelineText).toContain('fan out to multiple external systems')
    expect(timelineText).toContain('storage catalogs')
    expect(timelineText).toContain('cluster us-east-train-7')
    expect(timelineText).toContain('two healthy racks')
    expect(timelineText).toContain('64-A100 node pool')
    expect(timelineText).toContain('FineWeb-local storage')
    expect(screen.getByRole('region', { name: 'Solve placement plan subprocess' })).toBeTruthy()
    expect(timelineText).toContain('Datacenter candidates')
    expect(timelineText).toContain('clusters across regions')
    expect(timelineText).toContain('NVMe')
    expect(timelineText).toContain('InfiniBand')
    expect(timelineText).toContain('rack shape')
    expect(timelineText).toContain('storage reachability')
    expect(timelineText).toContain('GPU fit')
    expect(timelineText).toContain('64 A100s can land together')
    expect(timelineText).toContain('Data locality')
    expect(timelineText).toContain('regional FineWeb replica')
    expect(timelineText).toContain('s3://fineweb-us-east')
    expect(timelineText).toContain('FSx for Lustre mount')
    expect(timelineText).toContain('cross-region copy')
    expect(timelineText).toContain('User quota')
    expect(timelineText).toContain('spend quota in that cluster')
    expect(timelineText).toContain('reservation queue')
    expect(timelineText).toContain('may wait hours')
    expect(timelineText).toContain('10 lines of researcher intent')
    expect(timelineText).toContain('1000-line launch spec')
    expect(timelineText).toContain('record a focused hotfix')
    expect(timelineText).toContain('correcting the wrong env var or flag')
    expect(timelineText).toContain('updating actor pod replicas')
    for (let index = 1; index < timelineLabels.length; index += 1) {
      expect(timelineText.indexOf(timelineLabels[index])).toBeGreaterThan(timelineText.indexOf(timelineLabels[index - 1]))
    }

    const scaleBridge = screen.getByRole('region', { name: 'Shaping the foundation model from a small demo' })
    const scaleBridgeText = scaleBridge.textContent ?? ''
    expect(scaleBridgeText).toContain('Kilvin stays small')
    expect(scaleBridgeText).toContain('master artificer')
    expect(scaleBridgeText).toContain('durable craft')
    expect(scaleBridgeText).toContain('Real training platforms')
    for (const pressure of [
      'Many phases',
      'Base pretraining',
      'continued pretraining',
      'supervised tuning',
      'QAT',
      'Data curriculum',
      'Huge token budgets',
      'long-context windows',
      'Runtime compatibility',
      'CUDA',
      'NCCL',
      'Torch',
      'Scarce capacity',
      'GPU quota',
      'Materialized launch state',
      'image digest',
      'Operator control',
      'targeted replay',
      'heartbeat recovery',
    ]) {
      expect(scaleBridgeText).toContain(pressure)
    }
    expect(scaleBridge.querySelector('a[href$="docs/model-training-systems.md"]')).toBeTruthy()

    const artifacts = screen.getByRole('region', { name: 'What to inspect when debugging' })
    const artifactText = artifacts.textContent ?? ''
    expect(artifactText).toContain('saves researchers from manually assembling')
    expect(artifactText).toContain('see what was decided')
    expect(artifactText).toContain('Materialized job spec')
    expect(artifactText).toContain('env vars')
    expect(artifactText).toContain('Quota decision')
    expect(artifactText).toContain('cache hits or misses')
    expect(artifactText).toContain('Logs and events')
  })

  it('navigates into the merged deep-dive mode', () => {
    const navigate = vi.fn()
    render(<BasicsExplorer navigate={navigate} />)

    fireEvent.click(screen.getByRole('button', { name: 'Deep Dive' }))
    expect(navigate).toHaveBeenCalledWith('deep-dive')
  })

  it('maps the story 1:1 to runnable kilvin-py code', () => {
    render(<BasicsExplorer navigate={vi.fn()} />)

    const panel = screen.getByRole('region', { name: 'The same run as runnable code' })
    const panelText = panel.textContent ?? ''

    expect(panelText).toContain('KilvinTrainingWorkflow — one workflow, intent to running job')
    expect(panelText).not.toContain('ParentKilvinCmdWorkflow')
    expect(panelText).toContain('kilvin-training-task-queue')
    for (const activity of [
      'interpret_training_intent',
      'concretize_dependencies',
      'allocate_resources',
      'materialize_training_bundle',
      'submit_k8s_job',
      'monitor_training',
      'persist_yaml_artifact',
    ]) {
      expect(panelText).toContain(activity)
    }
    for (const signal of ['pause_at_step', 'replay_step']) {
      expect(panelText).toContain(signal)
    }
    for (const query of ['run_status', 'run_step_trace', 'run_artifacts', 'run_plan']) {
      expect(panelText).toContain(query)
    }
    expect(panelText).toContain('quota_decision.yaml')
    expect(panelText).toContain('env_vars.yaml')
    expect(panelText).toContain('logs.yaml')

    const workflowsLink = panel.querySelector('a[href$="kilvin-py/kilvin_py/workflows.py"]')
    expect(workflowsLink).toBeTruthy()
  })

  it('traces timeline steps into the matching deep-dive phase or control path', () => {
    const navigate = vi.fn()
    render(<BasicsExplorer navigate={navigate} />)

    fireEvent.click(screen.getByRole('button', { name: 'Trace in Deep Dive: Start workflow phase' }))
    expect(navigate).toHaveBeenCalledWith('deep-dive', {
      deepDiveTrack: 'lifecycle',
      deepDivePhaseId: 'start',
    })

    fireEvent.click(screen.getByRole('button', { name: 'Trace in Deep Dive: Pause/resume control path' }))
    expect(navigate).toHaveBeenCalledWith('deep-dive', {
      deepDiveTrack: 'control',
      deepDiveScenarioSlug: 'pause-resume',
    })
  })
})
