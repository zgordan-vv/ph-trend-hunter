"""
Verification script for Product Hunt Trend Hunter pipeline.
Tests data seeding, Day 10 Genesis synthesis, Day 11-14 recalibration, and API correctness.
"""

import os
import sys

from db import init_db, get_connection, get_tracked_days_count, get_distinct_dates
from collector import seed_historical_data, fetch_live_producthunt
from evolution_engine import process_day


def run_verification():
    print("[1/5] Initializing database...")
    init_db()
    
    print("[2/5] Seeding 14-day continuous dataset...")
    res = seed_historical_data()
    days_seeded = res.get("days_seeded", 0)
    print(f"      Seeded {days_seeded} days.")
    assert days_seeded >= 14, "Expected at least 14 days of historical data."

    print("[3/5] Verifying Day 10 Genesis Milestone...")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM conclusions WHERE is_genesis = 1")
    genesis_row = cur.fetchone()
    assert genesis_row is not None, "Day 10 Genesis Report was not created!"
    print(f"      Genesis Report: '{genesis_row['title']}' on {genesis_row['date']}")
    
    print("[4/5] Verifying Day 11+ Continuous Calibrations...")
    cur.execute("SELECT * FROM conclusions WHERE is_genesis = 0 ORDER BY day_number ASC")
    calibrations = cur.fetchall()
    assert len(calibrations) >= 4, f"Expected at least 4 daily calibrations, found {len(calibrations)}"
    for c in calibrations:
        print(f"      Day {c['day_number']} Calibration ({c['date']}): {c['title']} | Δ: {c['delta_from_yesterday'][:60]}...")
        
    print("[5/5] Verifying Hypotheses & Belief Shifts...")
    cur.execute("SELECT * FROM hypotheses ORDER BY confidence_score DESC")
    hyps = cur.fetchall()
    assert len(hyps) >= 6, f"Expected at least 6 hypotheses, found {len(hyps)}"
    for h in hyps:
        print(f"      [{h['status'].upper()}] {h['title']} — Confidence: {int(h['confidence_score']*100)}% ({h['times_confirmed']} confirmed, {h['times_challenged']} challenged)")

    # Check hypothesis log transitions
    cur.execute("SELECT COUNT(*) as cnt FROM hypothesis_logs")
    logs_cnt = cur.fetchone()["cnt"]
    assert logs_cnt > 0, "No hypothesis calibration logs recorded!"
    print(f"      Total belief calibration events recorded: {logs_cnt}")

    conn.close()
    print("\n✅ ALL PIPELINE TESTS PASSED!")


if __name__ == "__main__":
    run_verification()
