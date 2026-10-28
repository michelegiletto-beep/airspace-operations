"""New domain-neutral System Lab task coordination contracts.

This package is original open-source implementation. It does not contain or
relicense Multiagentic Platform's proprietary runtime or SPINS components.
"""
from .contracts import (AgentBudget, AgentScope, Capability, TaskContract,
                        Artifact, ActionReceipt, WaitPolicy)
from .core import admit, reconcile, verify_artifact, wait_decision

__all__ = ["AgentBudget", "AgentScope", "Capability", "TaskContract", "Artifact", "ActionReceipt", "WaitPolicy", "admit", "reconcile", "verify_artifact", "wait_decision"]
__version__ = "0.1.0"
