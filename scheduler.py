"""
Autonomous Scheduler: Runs daily collection and evolutionary recalibration.
Operates automatically in the background with zero user intervention.
"""

import threading
import time
from datetime import datetime
from typing import Dict, Any

from db import get_connection, set_state, get_state
from collector import fetch_live_producthunt


class AutonomousScheduler:
    def __init__(self, check_interval_seconds: int = 3600):
        self.check_interval_seconds = check_interval_seconds
        self.running = False
        self.thread: threading.Thread = None
        self.last_run_time: str = None
        self.last_run_status: str = "Initialized"

    def start(self):
        if self.running:
            return
        self.running = True
        set_state("autonomous_mode", True)
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        print("[Scheduler] Autonomous daily tracker started in background.")

    def stop(self):
        self.running = False
        set_state("autonomous_mode", False)
        print("[Scheduler] Autonomous daily tracker paused.")

    def _run_loop(self):
        while self.running:
            try:
                today_str = datetime.utcnow().strftime("%Y-%m-%d")
                
                # Check if today is already processed
                conn = get_connection()
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) as cnt FROM launches WHERE date = ?", (today_str,))
                row = cur.fetchone()
                already_collected = (row["cnt"] > 0) if row else False
                conn.close()

                if not already_collected:
                    print(f"[Scheduler] Waking up to track Product Hunt for {today_str}...")
                    res = fetch_live_producthunt(today_str)
                    self.last_run_time = datetime.utcnow().isoformat()
                    self.last_run_status = f"Completed run for {today_str}. Winner: {res.get('winner', 'N/A')}"
                    set_state("last_run_time", self.last_run_time)
                    set_state("last_run_status", self.last_run_status)
                    print(f"[Scheduler] {self.last_run_status}")
                else:
                    self.last_run_status = f"Up to date for {today_str}. Waiting for next daily reset."
            except Exception as e:
                self.last_run_status = f"Error during daily cycle: {str(e)}"
                print(f"[Scheduler] Error: {e}")

            # Sleep in increments so we can exit cleanly if stopped
            slept = 0
            while slept < self.check_interval_seconds and self.running:
                time.sleep(5)
                slept += 5

    def trigger_now(self) -> Dict[str, Any]:
        """Manually triggers today's collection and calibration cycle immediately."""
        today_str = datetime.utcnow().strftime("%Y-%m-%d")
        res = fetch_live_producthunt(today_str)
        self.last_run_time = datetime.utcnow().isoformat()
        self.last_run_status = f"Manual run completed for {today_str}. Winner: {res.get('winner', 'N/A')}"
        set_state("last_run_time", self.last_run_time)
        set_state("last_run_status", self.last_run_status)
        return res

    def get_status(self) -> Dict[str, Any]:
        return {
            "autonomous_running": self.running,
            "last_run_time": self.last_run_time or get_state("last_run_time", "Not yet run"),
            "last_run_status": self.last_run_status,
            "check_interval_seconds": self.check_interval_seconds
        }


# Singleton scheduler instance
scheduler = AutonomousScheduler(check_interval_seconds=1800)
