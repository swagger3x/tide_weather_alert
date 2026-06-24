"""
Tracks which matches have already triggered an alert, so re-running
the script (e.g. via cron) doesn't spam duplicate notifications for
the same qualifying day.
"""

import json
import os

STATE_FILE = os.path.join(os.path.dirname(__file__), "alert_state.json")


def load_alerted_keys():
    if not os.path.exists(STATE_FILE):
        return set()
    with open(STATE_FILE, "r") as f:
        try:
            return set(json.load(f))
        except json.JSONDecodeError:
            return set()


def save_alerted_keys(keys):
    with open(STATE_FILE, "w") as f:
        json.dump(sorted(keys), f, indent=2)


def make_match_key(location_name, match):
    """
    Unique key per location + qualifying day, so the same
    day isn't alerted twice even across multiple script runs.
    """
    return f"{location_name}|{match['date'].isoformat()}"