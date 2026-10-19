from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlmodel import Session, select

from app.core.db import get_session
from app.core.deps import get_current_user, require_roles
from app.core.security import create_access_token, verify_password
from app.models.user import Role, User, UserPublic
from app.services.users import DEMO_USERS, demo_password

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic


def _authenticate(session: Session, request: Request, username: str, password: str) -> TokenOut:
    user = session.exec(select(User).where(User.username == username)).first()
    if not user or not user.is_active or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
    settings = request.app.state.settings
    token = create_access_token(user.username, user.role, settings.jwt_secret, settings.jwt_expire_minutes)
    return TokenOut(access_token=token, user=UserPublic.model_validate(user, from_attributes=True))


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, request: Request, session: Session = Depends(get_session)) -> TokenOut:
    return _authenticate(session, request, body.username, body.password)


@router.post("/token", response_model=TokenOut, include_in_schema=True)
def token(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session),
) -> TokenOut:
    """OAuth2 form login (used by the Swagger 'Authorize' button)."""
    return _authenticate(session, request, form.username, form.password)


@router.get("/me", response_model=UserPublic)
def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.get("/demo-accounts")
def demo_accounts(request: Request) -> list[dict]:
    """Demo credentials for the login screen. Disabled when APP_ENV=production."""
    settings = request.app.state.settings
    if settings.is_production:
        return []
    return [
        {
            "username": u["username"],
            "full_name": u["full_name"],
            "role": str(u["role"]),
            "password": demo_password(settings, u["role"]),
        }
        for u in DEMO_USERS
    ]


users_router = APIRouter(prefix="/users", tags=["auth"])


@users_router.get("", response_model=list[UserPublic])
def list_users(
    role: str | None = None,
    session: Session = Depends(get_session),
    _: User = Depends(require_roles(Role.admin, Role.qa_lead)),
) -> list[User]:
    q = select(User)
    if role:
        q = q.where(User.role == role)
    return list(session.exec(q.order_by(User.id)))
