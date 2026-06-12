import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from kilvin_py import activities, workflows


async def main() -> None:
    client = await Client.connect("localhost:7233")
    worker = Worker(
        client,
        task_queue="kilvin-training-task-queue",
        workflows=[workflows.KilvinTrainingWorkflow],
        activities=[
            activities.interpret_training_intent,
            activities.dev_prepare,
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
