"""
recalculate_coach_scores.py — Updates rolling_score/rolling_band on all active staff.

Usage:
    UFIT_SECRET_KEY=<key> python scripts/recalculate_coach_scores.py

Run nightly via cron or Render cron job.
"""

import sys
import os
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import create_app
from app.database import get_db
from app.routes._coach_scoring import calculate_coach_score, rolling_period
from app.routes._helpers import now_utc


def run():
    app = create_app()
    with app.app_context():
        db = get_db()
        period_start, period_end = rolling_period()

        rows = db.execute(
            "SELECT sa.staff_id, sa.school_id FROM staff_assignments sa"
            " JOIN staff_profiles sp ON sp.staff_id = sa.staff_id"
            " WHERE sa.active_status=1 AND sp.deleted_at IS NULL"
            " ORDER BY sa.staff_id, sa.school_id"
        ).fetchall()

        # Group by staff_id — if a coach has multiple active schools, use the first.
        staff_schools: dict = defaultdict(list)
        for row in rows:
            staff_schools[row["staff_id"]].append(row["school_id"])

        updated = 0
        errors = 0
        for staff_id, school_ids in staff_schools.items():
            if len(school_ids) > 1:
                print(f"  WARN staff_id={staff_id} has {len(school_ids)} active schools {school_ids} — scoring first only")
            school_id = school_ids[0]
            try:
                sc = calculate_coach_score(
                    db, staff_id, school_id, period_start, period_end
                )
                db.execute(
                    "UPDATE staff_profiles SET rolling_score=?, rolling_band=?, score_last_updated=?"
                    " WHERE staff_id=?",
                    (sc["overall_score"], sc["performance_band"], now_utc(), staff_id),
                )
                db.commit()
                updated += 1
            except Exception as exc:
                print(f"  ERROR staff_id={staff_id}: {exc}")
                try:
                    db.rollback()
                except Exception:
                    pass
                errors += 1
        print(f"Recalculated: {updated} updated, {errors} errors ({period_start} to {period_end})")


if __name__ == "__main__":
    run()
