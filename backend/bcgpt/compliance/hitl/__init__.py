"""Human-in-the-Loop approval gate for the agent workflow engine."""

from .gate import ApprovalGate, ApprovalDecision
from .models import ApprovalRequest, ApprovalTicket, ApprovalTicketModel
from .policy import RiskPolicy, ActionClass, RiskTier

ApprovalGates = ApprovalGate()
