import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from kilvin_py import activities, workflows
from kilvin_py.config import KilvinSettings
from start_workflow import TASK_QUEUE


async def main() -> None:
    settings = KilvinSettings.load()
    client = await Client.connect(settings.temporal_address)
    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[workflows.KilvinTrainingWorkflow],
        activities=[
            activities.interpret_training_intent,
            activities.concretize_dependencies,
            activities.allocate_resources,
            activities.materialize_training_bundle,
            activities.submit_k8s_job,
            activities.monitor_training,
            activities.persist_yaml_artifact,
        ],
    )
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
