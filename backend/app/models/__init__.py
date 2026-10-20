"""SQLModel tables. Importing this package registers every table on SQLModel.metadata."""

from app.models.assessment import Assessment
from app.models.audit import AuditEntry, ConsentRecord
from app.models.credential import Credential
from app.models.declaration import Declaration, QPEmbedding
from app.models.evidence import DeviceKey, Evidence
from app.models.lexicon import LexiconAddition
from app.models.scoring import AIAnalysis, PCScore
from app.models.user import Role, User

__all__ = [
    "AIAnalysis",
    "PCScore",
    "Assessment",
    "AuditEntry",
    "ConsentRecord",
    "Credential",
    "Declaration",
    "DeviceKey",
    "Evidence",
    "LexiconAddition",
    "QPEmbedding",
    "Role",
    "User",
]
