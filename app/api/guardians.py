from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Guardian, User
from app.db.session import get_db
from app.schemas import GuardianCreateIn, GuardianOut
from app.utils.deps import get_current_user


router = APIRouter(prefix="/guardians", tags=["guardians"])


@router.post("", response_model=GuardianOut)
def create_guardian(
    payload: GuardianCreateIn,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    guardian = Guardian(
        ward_user_id=current.id,
        name=payload.name,
        relation=payload.relation,
        phone=payload.phone,
    )
    db.add(guardian)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Guardian phone already exists"
        )
    db.refresh(guardian)
    return guardian


@router.get("", response_model=list[GuardianOut])
def list_guardians(
    db: Session = Depends(get_db), current: User = Depends(get_current_user)
):
    return (
        db.query(Guardian)
        .filter(Guardian.ward_user_id == current.id)
        .order_by(Guardian.created_at.desc())
        .all()
    )


@router.delete("/{guardian_id}")
def delete_guardian(
    guardian_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    g = (
        db.query(Guardian)
        .filter(Guardian.id == guardian_id, Guardian.ward_user_id == current.id)
        .first()
    )
    if not g:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    db.delete(g)
    db.commit()
    return {"ok": True}

