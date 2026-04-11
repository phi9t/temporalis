import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from kilvin_py import activities, workflows


async def main() -> None:
    client = await Client.connect("localhost:7233")
    worker = Worker(
        client,
        task_queue="kilvin-training-task-queue",
        workflows=[workflows.ParentCmdWorkflow, workflows.TrainingWorkflow],
        activities=[
            activities.extract_cmd_config,
            activities.dev_prepare,
            activities.validate_checkpoint,
            activities.configure_training_data,
            activities.allocate_resources,
            activities.materialize_training_bundle,
            activities.submit_k8s_job,
            activities.monitor_training,
            activities.purge_resources,
            activities.update_cmd_state,
            activities.update_cmd_state_from_child,
            activities.persist_yaml_artifact,
            activities.submit_k8s_job_activity,
        ],
    )
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
