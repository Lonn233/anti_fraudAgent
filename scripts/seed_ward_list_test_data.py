from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.models import Guardian, User, UserProfile
from app.db.session import SessionLocal
from app.utils.security import hash_password


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="批量生成被监护人列表分页测试数据")
    parser.add_argument(
        "--ward-username",
        required=True,
        help="被监护人用户名（将为该用户创建多条监护关系）",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=50,
        help="要创建的监护关系数量，默认 50",
    )
    parser.add_argument(
        "--prefix",
        default="loadtest_monitor_",
        help="测试监护人用户名统一前缀，默认 loadtest_monitor_",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    db = SessionLocal()
    try:
        ward = db.query(User).filter(User.username == args.ward_username).first()
        if not ward:
            raise SystemExit(f"未找到被监护人账号: {args.ward_username}")

        created = 0
        for i in range(1, args.count + 1):
            username = f"{args.prefix}{i:03d}"
            monitor = db.query(User).filter(User.username == username).first()
            if not monitor:
                monitor = User(
                    username=username,
                    hashed_password=hash_password("12345678"),
                )
                db.add(monitor)
                db.flush()
                profile = UserProfile(
                    user_id=monitor.id,
                    phone=f"137{(10000000 + i):08d}",
                )
                db.add(profile)

            exists = (
                db.query(Guardian)
                .filter(Guardian.monitor_id == monitor.id, Guardian.ward_id == ward.id)
                .first()
            )
            if exists:
                continue

            relation = Guardian(
                monitor_id=monitor.id,
                ward_id=ward.id,
                monitor_note=f"监护人{i:03d}",
                ward_note=f"被监护备注{i:03d}",
                relationship="亲友",
            )
            db.add(relation)
            created += 1

        db.commit()
        print(f"创建完成: {created} 条（ward={args.ward_username}）")
    finally:
        db.close()


if __name__ == "__main__":
    main()
