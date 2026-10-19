"""SQLModel tables. Importing this package registers every table on SQLModel.metadata."""

from app.models.user import Role, User

__all__ = ["Role", "User"]
