from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.models import Guardian, User, UserProfile
from app.db.session import SessionLocal


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="清理监护人分页测试数据")
    parser.add_argument(
        "--prefix",
        default="loadtest_ward_",
        help="要清理的测试用户名前缀，默认 loadtest_ward_",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    db = SessionLocal()
    try:
        users = db.query(User).filter(User.username.like(f"{args.prefix}%")).all()
        user_ids = [u.id for u in users]
        if not user_ids:
            print("未找到可清理的测试数据")
            return

        guardians_deleted = (
            db.query(Guardian).filter(Guardian.ward_id.in_(user_ids)).delete(synchronize_session=False)
        )
        profiles_deleted = (
            db.query(UserProfile).filter(UserProfile.user_id.in_(user_ids)).delete(synchronize_session=False)
        )
        users_deleted = db.query(User).filter(User.id.in_(user_ids)).delete(synchronize_session=False)

        db.commit()
        print(
            f"清理完成: guardians={guardians_deleted}, profiles={profiles_deleted}, users={users_deleted}"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
