from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.db.models import User, UserProfile
from app.db.session import get_db
from app.schemas import LoginIn, RegisterCheckIn, RegisterCheckOut, RegisterIn, TokenOut, UserOut
from app.utils.security import create_access_token, hash_password, verify_password


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/check", response_model=RegisterCheckOut)
def check_register(payload: RegisterCheckIn, db: Session = Depends(get_db)):
    username_exists = False
    phone_exists = False
    if payload.username:
        username_exists = (
            db.query(User).filter(User.username == payload.username).first() is not None
        )
    if payload.phone:
        phone_exists = (
            db.query(UserProfile).filter(UserProfile.phone == payload.phone).first()
            is not None
        )
    return RegisterCheckOut(username_exists=username_exists, phone_exists=phone_exists)


def _calc_age_from_birth_date(birth_date: str | None) -> int | None:
    if not birth_date:
        return None
    try:
        parts = str(birth_date).split("-")
        year = int(parts[0])
        month = int(parts[1])
        day = int(parts[2])
    except (TypeError, ValueError, IndexError):
        return None

    now = datetime.utcnow()
    age = now.year - year
    if (now.month, now.day) < (month, day):
        age -= 1
    return max(age, 0)


def _to_user_out(user: User) -> UserOut:
    profile = user.profile
    combined_job = None
    combined_region = None
    resolved_age = user.age
    if profile:
        if profile.occupation_category and profile.occupation_subcategory:
            combined_job = f"{profile.occupation_category} / {profile.occupation_subcategory}"
        else:
            combined_job = profile.occupation_category or profile.occupation_subcategory
        if profile.region_province and profile.region_city:
            combined_region = f"{profile.region_province} / {profile.region_city}"
        else:
            combined_region = profile.region_province or profile.region_city
        birth_age = _calc_age_from_birth_date(profile.birth_date)
        if birth_age is not None:
            resolved_age = birth_age

    return UserOut(
        id=user.id,
        username=user.username,
        phone=profile.phone if profile else None,
        birth_date=profile.birth_date if profile else None,
        occupation_category=profile.occupation_category if profile else None,
        occupation_subcategory=profile.occupation_subcategory if profile else None,
        region_province=profile.region_province if profile else None,
        region_city=profile.region_city if profile else None,
        age=resolved_age,
        job=combined_job or user.job,
        region=combined_region or user.region,
        created_at=user.created_at,
    )


@router.post("/register", response_model=UserOut)
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    exists = db.query(User).filter(User.username == payload.username).first()
    if exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="用户名已存在"
        )
    phone_exists = db.query(UserProfile).filter(UserProfile.phone == payload.phone).first()
    if phone_exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="手机号已存在"
        )
    user = User(
        username=payload.username,
        hashed_password=hash_password(payload.password),
        age=_calc_age_from_birth_date(payload.birth_date),
    )
    db.add(user)
    db.flush()
    profile = UserProfile(
        user_id=user.id,
        phone=payload.phone,
        birth_date=payload.birth_date,
        occupation_category=payload.occupation_category,
        occupation_subcategory=payload.occupation_subcategory,
        region_province=payload.region_province,
        region_city=payload.region_city,
    )
    db.add(profile)
    db.commit()
    db.refresh(user)
    return _to_user_out(user)


def _issue_token(db: Session, username: str, password: str) -> TokenOut:
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )
    token = create_access_token(
        subject=user.username,
        secret_key=settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
        expires_minutes=settings.access_token_expire_minutes,
    )
    return TokenOut(access_token=token)


@router.post("/login", response_model=TokenOut)
def login_form(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    return _issue_token(db, form_data.username, form_data.password)


@router.post("/login/json", response_model=TokenOut)
def login_json(payload: LoginIn, db: Session = Depends(get_db)):
    return _issue_token(db, payload.username, payload.password)

