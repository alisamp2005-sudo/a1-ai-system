"""AI Agents package."""
from src.agents.secretary import SecretaryAgent
from src.agents.lawyer import LawyerAgent
from src.agents.finance import FinanceAgent
from src.agents.procurement import ProcurementAgent
from src.agents.hr import HRAgent
from src.agents.analyst import AnalystAgent
from src.agents.reporter import ReporterAgent

__all__ = [
    "SecretaryAgent",
    "LawyerAgent",
    "FinanceAgent",
    "ProcurementAgent",
    "HRAgent",
    "AnalystAgent",
    "ReporterAgent",
]
