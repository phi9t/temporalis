"""Inspectl framework exceptions."""


class InspectlError(RuntimeError):
    """Base exception for inspectl."""


class StepDefinitionError(InspectlError):
    """Raised when a step definition is invalid."""


class PipelineDefinitionError(InspectlError):
    """Raised when a pipeline definition is invalid."""


class DuplicateStepNameError(InspectlError):
    """Raised when two steps share the same effective name."""


class StepPreconditionError(InspectlError):
    """Raised when a step's declared requirements are not satisfied."""


class StepExecutionError(InspectlError):
    """Raised when a step returns an invalid value or cannot execute."""


class PipelinePaused(InspectlError):
    """Raised by run() when the underlying workflow is paused awaiting resume."""
