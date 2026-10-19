"""Demo user seeding. Passwords come from settings (.env / .env.example defaults)."""

from __future__ import annotations

from sqlmodel import Session, select

from app.core.config import Settings
from app.core.security import hash_password
from app.models.user import Role, User

DEMO_USERS: list[dict] = [
    {"username": "worker1", "full_name": "Ramesh Kumar", "role": Role.worker, "centre": "Faridabad cluster"},
    {"username": "worker2", "full_name": "Salma Khatoon", "role": Role.worker, "centre": "Pune cluster"},
    {"username": "assessor1", "full_name": "Anil Verma", "role": Role.assessor, "centre": "ITI Faridabad"},
    {"username": "assessor2", "full_name": "Priya Nair", "role": Role.assessor, "centre": "ITI Pune"},
    {"username": "assessor3", "full_name": "Mohd. Imran", "role": Role.assessor, "centre": "ITI Lucknow"},
    {"username": "qa1", "full_name": "Dr. Kavita Rao", "role": Role.qa_lead, "centre": "ASDC QA cell"},
    {"username": "admin", "full_name": "Platform Admin", "role": Role.admin, "centre": None},
]


def demo_password(settings: Settings, role: str) -> str:
    return {
        Role.worker: settings.demo_password_worker,
        Role.assessor: settings.demo_password_assessor,
        Role.qa_lead: settings.demo_password_qa,
        Role.admin: settings.demo_password_admin,
    }[Role(role)]


def seed_demo_users(session: Session, settings: Settings) -> int:
    """Create the demo accounts if missing. Returns the number created."""
    created = 0
    for spec in DEMO_USERS:
        exists = session.exec(select(User).where(User.username == spec["username"])).first()
        if exists:
            continue
        session.add(
            User(
                username=spec["username"],
                full_name=spec["full_name"],
                role=str(spec["role"]),
                centre=spec["centre"],
                password_hash=hash_password(demo_password(settings, spec["role"])),
            )
        )
        created += 1
    session.commit()
    return created
