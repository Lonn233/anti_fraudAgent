from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.models import User
from app.db.session import get_db
from app.schemas import UserOut, UserProfileIn
from app.utils.deps import get_current_user


router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
def get_me(current: User = Depends(get_current_user)):
    return current


@router.put("/me/profile", response_model=UserOut)
def update_profile(
    payload: UserProfileIn,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    if payload.age is not None:
        current.age = payload.age
    if payload.job is not None:
        current.job = payload.job
    if payload.region is not None:
        current.region = payload.region

    db.add(current)
    db.commit()
    db.refresh(current)
    return current

