from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import User, UserProfile
from app.db.session import get_db
from app.schemas import ChangePasswordIn, UserOut, UserProfileIn
from app.utils.deps import get_current_user
from app.utils.security import hash_password, verify_password


router = APIRouter(prefix="/users", tags=["users"])


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


@router.get("/me", response_model=UserOut)
def get_me(current: User = Depends(get_current_user)):
    return _to_user_out(current)


@router.put("/me/profile", response_model=UserOut)
def update_profile(
    payload: UserProfileIn,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    if payload.username is not None and payload.username != current.username:
        username_exists = db.query(User).filter(User.username == payload.username).first()
        if username_exists and username_exists.id != current.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="用户名已存在"
            )
        current.username = payload.username

    profile = current.profile
    if profile is None:
        profile = UserProfile(user_id=current.id, phone=payload.phone or "")
        db.add(profile)

    if payload.phone is not None and payload.phone != profile.phone:
        phone_exists = db.query(UserProfile).filter(UserProfile.phone == payload.phone).first()
        if phone_exists and phone_exists.user_id != current.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="手机号已存在"
            )

    if payload.age is not None:
        current.age = payload.age
    if payload.job is not None:
        current.job = payload.job
    if payload.region is not None:
        current.region = payload.region
    if payload.phone is not None:
        profile.phone = payload.phone
    if payload.birth_date is not None:
        profile.birth_date = payload.birth_date
        birth_age = _calc_age_from_birth_date(payload.birth_date)
        if birth_age is not None:
            current.age = birth_age
    if payload.occupation_category is not None:
        profile.occupation_category = payload.occupation_category
    if payload.occupation_subcategory is not None:
        profile.occupation_subcategory = payload.occupation_subcategory
    if payload.region_province is not None:
        profile.region_province = payload.region_province
    if payload.region_city is not None:
        profile.region_city = payload.region_city

    db.add(current)
    db.add(profile)
    db.commit()
    db.refresh(current)
    return _to_user_out(current)


@router.put("/me/password")
def update_password(
    payload: ChangePasswordIn,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    if not verify_password(payload.current_password, current.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="当前密码错误"
        )
    current.hashed_password = hash_password(payload.new_password)
    db.add(current)
    db.commit()
    return {"message": "密码修改成功"}

