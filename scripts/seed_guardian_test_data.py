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
    parser = argparse.ArgumentParser(description="批量生成监护人分页测试数据")
    parser.add_argument(
        "--monitor-username",
        required=True,
        help="监护人用户名（将为该用户创建多条被监护关系）",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=50,
        help="要创建的被监护关系数量，默认 50",
    )
    parser.add_argument(
        "--prefix",
        default="loadtest_ward_",
        help="测试用户名统一前缀，默认 loadtest_ward_",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    db = SessionLocal()
    try:
        monitor = db.query(User).filter(User.username == args.monitor_username).first()
        if not monitor:
            raise SystemExit(f"未找到监护人账号: {args.monitor_username}")

        created = 0
        for i in range(1, args.count + 1):
            username = f"{args.prefix}{i:03d}"
            exists = db.query(User).filter(User.username == username).first()
            if exists:
                continue

            ward = User(
                username=username,
                hashed_password=hash_password("12345678"),
            )
            db.add(ward)
            db.flush()

            profile = UserProfile(
                user_id=ward.id,
                phone=f"139{(10000000 + i):08d}",
            )
            db.add(profile)

            relation = Guardian(
                monitor_id=monitor.id,
                ward_id=ward.id,
                monitor_note=f"压测用户{i:03d}",
                ward_note=f"监护备注{i:03d}",
                relationship="亲友",
            )
            db.add(relation)
            created += 1

        db.commit()
        print(f"创建完成: {created} 条（monitor={args.monitor_username}）")
    finally:
        db.close()


if __name__ == "__main__":
    main()
