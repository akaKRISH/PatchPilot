"""PatchPilot - Local-first self-healing AI coding agent."""

__version__ = "0.1.0"
__author__ = "Ruru Labs"

from patchpilot.config import PatchPilotConfig
from patchpilot.schemas import RepairStatus, TaskRequest

__all__ = ["PatchPilotConfig", "RepairStatus", "TaskRequest", "__version__"]
