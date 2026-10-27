from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import LoginRequest, TokenResponse
from app.security import create_access_token, verify_password

router = APIRouter(tags=["autenticacion"])


@router.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    row = (
        db.execute(
            text(
                "SELECT email, password_hash, role FROM app.users WHERE lower(email) = lower(:email)"
            ),
            {"email": payload.email},
        )
        .mappings()
        .first()
    )
    if row is None or not verify_password(payload.password, row["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales invalidas",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(row["email"], row["role"])
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": row["role"],
        "email": row["email"],
    }
