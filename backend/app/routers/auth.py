from fastapi import APIRouter, HTTPException, Response, status

from backend.app.auth import (
    AuthSessionRead,
    CurrentUser,
    LoginRequest,
    clear_auth_cookie,
    set_auth_cookie,
    verify_login,
)


router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)


@router.post("/login", response_model=AuthSessionRead)
def login(credentials: LoginRequest, response: Response) -> AuthSessionRead:
    user = verify_login(credentials.name, credentials.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid name or password.",
        )

    set_auth_cookie(response, user)
    return AuthSessionRead(name=user.name, role=user.role)


@router.get("/me", response_model=AuthSessionRead)
def me(user: CurrentUser) -> AuthSessionRead:
    return AuthSessionRead(name=user.name, role=user.role)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> None:
    clear_auth_cookie(response)
