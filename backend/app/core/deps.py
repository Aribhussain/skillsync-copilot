"""Request dependencies: current user and role-based access control."""

from __future__ import annotations

from collections.abc import Callable

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session, select

from app.core.db import get_session
from app.core.security import decode_access_token
from app.models.user import Role, User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)


def get_current_user(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    session: Session = Depends(get_session),
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise unauthorized
    try:
        payload = decode_access_token(token, request.app.state.settings.jwt_secret)
    except jwt.PyJWTError as exc:
        raise unauthorized from exc
    user = session.exec(select(User).where(User.username == payload.get("sub"))).first()
    if not user or not user.is_active:
        raise unauthorized
    return user


def require_roles(*roles: Role | str) -> Callable[..., User]:
    allowed = {str(r) for r in roles}

    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role: {', '.join(sorted(allowed))}",
            )
        return user

    return checker
