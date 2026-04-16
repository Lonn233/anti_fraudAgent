from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Guardian, GuardianLinkRequest, User, UserProfile
from app.db.session import get_db
from app.schemas import (
    GuardianPageOut,
    GuardianOut,
    GuardianRequestApplyIn,
    GuardianRequestDecisionIn,
    GuardianRequestDecisionOut,
    GuardianRequestOut,
    GuardianUpdateIn,
)
from app.utils.deps import get_current_user


router = APIRouter(prefix="/guardians", tags=["guardians"])


def _to_guardian_out(
    item: Guardian,
    monitor: User,
    ward: User,
    monitor_phone: str | None,
    ward_phone: str | None,
    role: str | None = None,
) -> GuardianOut:
    note = None
    phone = None
    if role == "monitor":
        note = item.monitor_note
        phone = ward_phone
    elif role == "ward":
        note = item.ward_note
        phone = monitor_phone
    return GuardianOut(
        id=item.id,
        monitor_id=item.monitor_id,
        monitor_username=monitor.username,
        monitor_phone=monitor_phone,
        ward_id=item.ward_id,
        ward_username=ward.username,
        ward_phone=ward_phone,
        monitor_note=item.monitor_note,
        ward_note=item.ward_note,
        note=note,
        phone=phone,
        relationship=item.relationship,
        created_at=item.created_at,
    )


def _to_request_out(item: GuardianLinkRequest, monitor: User, ward: User) -> GuardianRequestOut:
    return GuardianRequestOut(
        id=item.id,
        monitor_id=item.monitor_id,
        monitor_username=monitor.username,
        ward_id=item.ward_id,
        ward_username=ward.username,
        name=item.name,
        relationship=item.relationship,
        status=item.status,
        created_at=item.created_at,
        processed_at=item.processed_at,
    )


def _get_users_by_ids(db: Session, ids: set[int]) -> dict[int, User]:
    if not ids:
        return {}
    users = db.query(User).filter(User.id.in_(ids)).all()
    return {u.id: u for u in users}


def _request_target_user_id(req: GuardianLinkRequest) -> int:
    # If requester is monitor -> ward decides; if requester is ward -> monitor decides.
    if req.requester_id == req.monitor_id:
        return req.ward_id
    return req.monitor_id


@router.post("/requests/apply", response_model=GuardianRequestOut)
def apply_request(
    payload: GuardianRequestApplyIn,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    target_username = (payload.target_username or "").strip()
    if not target_username:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名为必填项")

    target = db.query(User).filter(User.username == target_username).first()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="目标用户不存在")
    if target.id == current.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能与自己建立监护关系")

    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="备注为必填项")

    relationship = (payload.relationship or "").strip()
    if not relationship:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="关系为必填项")

    if payload.mode == "monitor":
        monitor = current
        ward = target
    else:
        monitor = target
        ward = current

    exists = (
        db.query(Guardian)
        .filter(Guardian.monitor_id == monitor.id, Guardian.ward_id == ward.id)
        .first()
    )
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="监护关系已存在")

    pending = (
        db.query(GuardianLinkRequest)
        .filter(
            GuardianLinkRequest.monitor_id == monitor.id,
            GuardianLinkRequest.ward_id == ward.id,
            GuardianLinkRequest.status == "pending",
        )
        .first()
    )
    if pending:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="已有待处理申请")

    req = GuardianLinkRequest(
        requester_id=current.id,
        monitor_id=monitor.id,
        ward_id=ward.id,
        name=name,
        relationship=relationship,
        status="pending",
    )
    db.add(req)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="申请创建失败")
    db.refresh(req)
    return _to_request_out(req, monitor=monitor, ward=ward)


@router.get("/requests", response_model=list[GuardianRequestOut])
def list_requests(
    box: str = Query(default="incoming", pattern="^(incoming|outgoing|all)$"),
    status_filter: str = Query(default="pending", alias="status", pattern="^(pending|accepted|rejected|all)$"),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    q = db.query(GuardianLinkRequest)
    if status_filter != "all":
        q = q.filter(GuardianLinkRequest.status == status_filter)

    if box == "outgoing":
        q = q.filter(GuardianLinkRequest.requester_id == current.id)
    elif box == "incoming":
        q = q.filter(
            (
                (GuardianLinkRequest.requester_id == GuardianLinkRequest.monitor_id)
                & (GuardianLinkRequest.ward_id == current.id)
            )
            | (
                (GuardianLinkRequest.requester_id == GuardianLinkRequest.ward_id)
                & (GuardianLinkRequest.monitor_id == current.id)
            )
        )
    else:
        q = q.filter(
            (GuardianLinkRequest.requester_id == current.id)
            | (
                (
                    (GuardianLinkRequest.requester_id == GuardianLinkRequest.monitor_id)
                    & (GuardianLinkRequest.ward_id == current.id)
                )
                | (
                    (GuardianLinkRequest.requester_id == GuardianLinkRequest.ward_id)
                    & (GuardianLinkRequest.monitor_id == current.id)
                )
            )
        )

    rows = q.order_by(GuardianLinkRequest.created_at.desc()).all()
    ids = {r.monitor_id for r in rows} | {r.ward_id for r in rows}
    user_map = _get_users_by_ids(db, ids)
    out: list[GuardianRequestOut] = []
    for r in rows:
        monitor = user_map.get(r.monitor_id)
        ward = user_map.get(r.ward_id)
        if not monitor or not ward:
            continue
        out.append(_to_request_out(item=r, monitor=monitor, ward=ward))
    return out


@router.post("/requests/{request_id}/decision", response_model=GuardianRequestDecisionOut)
def decide_request(
    request_id: int,
    payload: GuardianRequestDecisionIn,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    req = db.query(GuardianLinkRequest).filter(GuardianLinkRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="申请不存在")
    if req.status != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="申请已处理")

    if _request_target_user_id(req) != current.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限处理该申请")

    monitor = db.query(User).filter(User.id == req.monitor_id).first()
    ward = db.query(User).filter(User.id == req.ward_id).first()
    if not monitor or not ward:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    guardian: Guardian | None = None
    if payload.decision == "accept":
        decision_note = (payload.note or "").strip()
        if not decision_note:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="备注为必填项")

        duplicate_same_status = (
            db.query(GuardianLinkRequest)
            .filter(
                GuardianLinkRequest.id != req.id,
                GuardianLinkRequest.monitor_id == req.monitor_id,
                GuardianLinkRequest.ward_id == req.ward_id,
                GuardianLinkRequest.status == "accepted",
            )
            .all()
        )
        for dup in duplicate_same_status:
            db.delete(dup)

        guardian = (
            db.query(Guardian)
            .filter(Guardian.monitor_id == req.monitor_id, Guardian.ward_id == req.ward_id)
            .first()
        )
        if not guardian:
            guardian = Guardian(
                monitor_id=req.monitor_id,
                ward_id=req.ward_id,
                monitor_note=req.name if req.requester_id == req.monitor_id else decision_note,
                ward_note=req.name if req.requester_id == req.ward_id else decision_note,
                relationship=req.relationship,
            )
            db.add(guardian)
        else:
            if req.requester_id == req.monitor_id:
                guardian.monitor_note = req.name
                guardian.ward_note = decision_note
            else:
                guardian.ward_note = req.name
                guardian.monitor_note = decision_note
        req.status = "accepted"
        req.processed_at = datetime.utcnow()
        db.add(req)
        db.commit()
        db.refresh(req)
        if guardian.id is None:
            db.refresh(guardian)
    else:
        duplicate_same_status = (
            db.query(GuardianLinkRequest)
            .filter(
                GuardianLinkRequest.id != req.id,
                GuardianLinkRequest.monitor_id == req.monitor_id,
                GuardianLinkRequest.ward_id == req.ward_id,
                GuardianLinkRequest.status == "rejected",
            )
            .all()
        )
        for dup in duplicate_same_status:
            db.delete(dup)

        req.status = "rejected"
        req.processed_at = datetime.utcnow()
        db.add(req)
        db.commit()
        db.refresh(req)

    req_out = _to_request_out(item=req, monitor=monitor, ward=ward)
    monitor_phone = monitor.profile.phone if monitor.profile else None
    ward_phone = ward.profile.phone if ward.profile else None
    guardian_out = (
        _to_guardian_out(
            guardian,
            monitor=monitor,
            ward=ward,
            monitor_phone=monitor_phone,
            ward_phone=ward_phone,
            role="monitor" if current.id == guardian.monitor_id else "ward",
        )
        if guardian
        else None
    )
    return GuardianRequestDecisionOut(request=req_out, guardian=guardian_out)


@router.get("/relations", response_model=GuardianPageOut)
def list_relations(
    role: str = Query(default="monitor", pattern="^(monitor|ward)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    q = db.query(Guardian)
    if role == "monitor":
        q = q.filter(Guardian.monitor_id == current.id)
    else:
        q = q.filter(Guardian.ward_id == current.id)
    total = q.count()
    total_pages = max((total + page_size - 1) // page_size, 1)
    safe_page = min(page, total_pages)
    rows = (
        q.order_by(Guardian.created_at.desc())
        .offset((safe_page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    monitor_ids = {r.monitor_id for r in rows}
    ward_ids = {r.ward_id for r in rows}
    users = db.query(User).filter(User.id.in_(monitor_ids | ward_ids)).all() if rows else []
    user_map = {u.id: u for u in users}
    profiles = (
        db.query(UserProfile).filter(UserProfile.user_id.in_(monitor_ids | ward_ids)).all()
        if rows
        else []
    )
    phone_map = {p.user_id: p.phone for p in profiles}
    items = [
        _to_guardian_out(
            item=row,
            monitor=user_map[row.monitor_id],
            ward=user_map[row.ward_id],
            monitor_phone=phone_map.get(row.monitor_id),
            ward_phone=phone_map.get(row.ward_id),
            role=role,
        )
        for row in rows
        if row.monitor_id in user_map and row.ward_id in user_map
    ]
    return GuardianPageOut(
        items=items,
        page=safe_page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
    )





@router.delete("/{guardian_id}")
def delete_guardian(
    guardian_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    g = (
        db.query(Guardian)
        .filter(
            Guardian.id == guardian_id,
            or_(Guardian.monitor_id == current.id, Guardian.ward_id == current.id),
        )
        .first()
    )
    if not g:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到对应监护关系")
    db.delete(g)
    db.commit()
    return {"ok": True}


@router.put("/{guardian_id}", response_model=GuardianOut)
def update_guardian(
    guardian_id: int,
    payload: GuardianUpdateIn,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    g = (
        db.query(Guardian)
        .filter(
            Guardian.id == guardian_id,
            or_(Guardian.monitor_id == current.id, Guardian.ward_id == current.id),
        )
        .first()
    )
    if not g:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到对应监护关系")

    note = (payload.note or "").strip()
    if not note:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="备注为必填项")

    if current.id == g.monitor_id:
        g.monitor_note = note
        role = "monitor"
    else:
        g.ward_note = note
        role = "ward"
    db.add(g)
    db.commit()
    db.refresh(g)

    monitor = db.query(User).filter(User.id == g.monitor_id).first()
    ward = db.query(User).filter(User.id == g.ward_id).first()
    if not monitor or not ward:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    monitor_phone = monitor.profile.phone if monitor.profile else None
    ward_phone = ward.profile.phone if ward.profile else None
    return _to_guardian_out(
        item=g,
        monitor=monitor,
        ward=ward,
        monitor_phone=monitor_phone,
        ward_phone=ward_phone,
        role=role,
    )

