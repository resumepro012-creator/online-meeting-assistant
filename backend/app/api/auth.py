"""Authentication endpoints.

University-email policy in brief (details in `app/services/auth_service.py`):
*   `POST /auth/register` creates an **inactive** account and emails a 6-digit
    code. It returns no token — the account cannot be used yet.
*   `POST /auth/verify-email` confirms the code, activates the account and only
    then issues an access token.
*   `POST /auth/login` refuses unknown domains, wrong credentials and accounts
    that have not been verified.

Errors carry a machine-readable `code` alongside the human message so the
frontend can react to a specific case (for example showing "please login with
institute mail" under the email field) without string matching.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.email import EmailDeliveryError
from app.core.security import OTP_DIGITS, create_access_token
from app.db.session import get_db
from app.models import User
from app.schemas import (
    AuthPolicyOut,
    AuthResponse,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    RegisterResponse,
    ResendVerificationRequest,
    ResendVerificationResponse,
    ResetPasswordRequest,
    StudentOut,
    VerifyEmailRequest,
)
from app.services import auth_service
from app.services.serializers import to_student

router = APIRouter(prefix="/auth", tags=["auth"])

# Deliberately vague for the forgot-password endpoint: it must not reveal
# whether an address is registered.
_RESET_SENT_MESSAGE = (
    "If that email address matches an account, a password-reset link has been sent to it."
)


def _problem(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


def _issue_session(user: User) -> AuthResponse:
    token, expires_in = create_access_token(user.id, user.token_version)
    return AuthResponse(access_token=token, expires_in=expires_in, student=to_student(user))


@router.get("/policy", response_model=AuthPolicyOut)
def policy() -> AuthPolicyOut:
    """The approved university domains and whether dev mode exposes the code."""
    return AuthPolicyOut(
        allowed_email_domains=settings.allowed_email_domains,
        university_email_domains=settings.university_email_domains,
        accept_any_academic_domain=settings.accept_any_academic_domain,
        verification_required=True,
        verification_code_length=OTP_DIGITS,
        resend_cooldown_seconds=settings.verification_resend_cooldown_seconds,
        dev_code_exposed=settings.exposes_verification_code,
    )


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> RegisterResponse:
    try:
        user, code = auth_service.register_user(
            db,
            name=payload.name,
            email=payload.email,
            password=payload.password,
            program=payload.program,
        )
    except auth_service.EmailDomainNotAllowed as exc:
        raise _problem(
            status.HTTP_400_BAD_REQUEST,
            "email_domain_not_allowed",
            "Please register with your institute email address "
            f"(e.g. you@your-institute.edu). '{exc.domain}' is not an institutional domain.",
        ) from exc
    except auth_service.EmailAlreadyRegistered as exc:
        raise _problem(status.HTTP_409_CONFLICT, "email_already_registered", str(exc)) from exc
    except EmailDeliveryError as exc:
        raise _problem(
            status.HTTP_502_BAD_GATEWAY,
            "verification_email_failed",
            "Your account was created but the verification email could not be sent. "
            "Use 'Resend code' to try again.",
        ) from exc

    return RegisterResponse(
        email=user.email,
        verification_required=True,
        message="We have sent a verification code to your institute email address.",
        # Only ever present with the development console email backend.
        dev_verification_code=code if settings.exposes_verification_code else None,
    )


@router.post("/verify-email", response_model=AuthResponse)
def verify_email(payload: VerifyEmailRequest, db: Session = Depends(get_db)) -> AuthResponse:
    try:
        user = auth_service.verify_email(db, payload.email, payload.code)
    except auth_service.VerificationCodeExpired as exc:
        raise _problem(status.HTTP_400_BAD_REQUEST, "code_expired", str(exc)) from exc
    except auth_service.TooManyVerificationAttempts as exc:
        raise _problem(status.HTTP_429_TOO_MANY_REQUESTS, "too_many_attempts", str(exc)) from exc
    except auth_service.InvalidVerificationCode as exc:
        raise _problem(status.HTTP_400_BAD_REQUEST, "invalid_code", str(exc)) from exc

    return _issue_session(user)


@router.post("/resend-verification", response_model=ResendVerificationResponse)
def resend_verification(
    payload: ResendVerificationRequest, db: Session = Depends(get_db)
) -> ResendVerificationResponse:
    try:
        sent, code = auth_service.resend_verification(db, payload.email)
    except auth_service.ResendTooSoon as exc:
        raise _problem(
            status.HTTP_429_TOO_MANY_REQUESTS, "resend_too_soon", str(exc)
        ) from exc
    except EmailDeliveryError as exc:
        raise _problem(
            status.HTTP_502_BAD_GATEWAY,
            "verification_email_failed",
            "The verification email could not be sent. Please try again shortly.",
        ) from exc

    # Same wording whether or not the address exists, to avoid enumeration.
    message = (
        "A new verification code has been sent."
        if sent
        else "If that address needs verification, a new code has been sent."
    )
    return ResendVerificationResponse(
        message=message,
        dev_verification_code=code if settings.exposes_verification_code else None,
    )


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
    # Check the domain before the credentials so a personal address gets the
    # precise "use your institute email" message rather than a generic failure.
    if not auth_service.is_allowed_email(payload.email):
        raise _problem(
            status.HTTP_403_FORBIDDEN,
            "email_domain_not_allowed",
            "Please login with institute mail.",
        )

    user = auth_service.authenticate(db, payload.email, payload.password)
    if user is None:
        raise _problem(
            status.HTTP_401_UNAUTHORIZED, "invalid_credentials", "Incorrect email or password."
        )
    if not user.is_verified:
        raise _problem(
            status.HTTP_403_FORBIDDEN,
            "email_not_verified",
            "Please verify your institute email address before signing in. "
            "Check your inbox for the verification code.",
        )

    return _issue_session(user)


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(
    payload: ForgotPasswordRequest, db: Session = Depends(get_db)
) -> MessageResponse:
    try:
        auth_service.request_password_reset(db, payload.email)
    except EmailDeliveryError:
        # The response stays generic; log-only detail is in the server log.
        pass
    return MessageResponse(message=_RESET_SENT_MESSAGE)


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(
    payload: ResetPasswordRequest, db: Session = Depends(get_db)
) -> MessageResponse:
    try:
        auth_service.reset_password(db, payload.token, payload.password)
    except auth_service.InvalidResetToken as exc:
        raise _problem(status.HTTP_400_BAD_REQUEST, "invalid_reset_token", str(exc)) from exc
    return MessageResponse(
        message="Your password has been reset. You can now sign in with the new password."
    )


@router.get("/me", response_model=StudentOut)
def me(user: User = Depends(get_current_user)) -> StudentOut:
    return to_student(user)
