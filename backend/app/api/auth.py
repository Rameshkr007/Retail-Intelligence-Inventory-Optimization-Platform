from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.core.auth import create_access_token, get_current_user, hash_password, verify_password
from app.core.database import get_db
from app.models.orm import AuditLog, User

router = APIRouter(prefix="/api/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)

VALID_ROLES = {"admin", "analyst", "manager"}


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    role: str = "analyst"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@router.post("/register")
@limiter.limit("10/minute")
async def register(request: Request, req: RegisterRequest, db: Session = Depends(get_db)):
    if req.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Role must be one of {sorted(VALID_ROLES)}.")
    if db.query(User).filter(User.email == req.email).first():
        raise HTTPException(status_code=409, detail="A user with this email already exists.")
    if len(req.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")

    user = User(email=req.email, password_hash=hash_password(req.password), role=req.role)
    db.add(user)
    db.add(AuditLog(user_email=req.email, action="register", entity="user"))
    db.commit()
    return {"email": user.email, "role": user.role}


@router.post("/login")
@limiter.limit("5/minute")  # brute-force protection (spec §59)
async def login(request: Request, req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if user is None or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password.")
    token = create_access_token(subject=user.email, role=user.role)
    db.add(AuditLog(user_email=user.email, action="login", entity="user"))
    db.commit()
    return {"access_token": token, "token_type": "bearer", "role": user.role}


@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    return {"email": user.email, "role": user.role}
