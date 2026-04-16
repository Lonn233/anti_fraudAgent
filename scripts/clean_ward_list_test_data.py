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
    parser = argparse.ArgumentParser(description="清理被监护人列表分页测试数据")
    parser.add_argument(
        "--prefix",
        default="loadtest_monitor_",
        help="要清理的测试监护人用户名前缀，默认 loadtest_monitor_",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    db = SessionLocal()
    try:
        users = db.query(User).filter(User.username.like(f"{args.prefix}%")).all()
        ids = [u.id for u in users]
        if not ids:
            print("未找到可清理的测试监护人数据")
            return

        guardians_deleted = (
            db.query(Guardian)
            .filter(Guardian.monitor_id.in_(ids))
            .delete(synchronize_session=False)
        )
        profiles_deleted = (
            db.query(UserProfile)
            .filter(UserProfile.user_id.in_(ids))
            .delete(synchronize_session=False)
        )
        users_deleted = db.query(User).filter(User.id.in_(ids)).delete(synchronize_session=False)

        db.commit()
        print(
            f"清理完成: guardians={guardians_deleted}, profiles={profiles_deleted}, users={users_deleted}"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
