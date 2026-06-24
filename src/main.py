"""
main.py
Orchestrates a single check across all configured locations:
fetch forecast -> fetch tides -> find matches -> notify.

Run manually:
    python main.py

Run a test notification (sends immediately, skips the real check):
    python main.py --test

Intended to be scheduled via AWS EventBridge (Lambda) or cron once per day.
"""

import json
import sys
import os

from src.weather import get_wind_cloud_forecast
from src.tides import get_high_tides
from src.matcher import find_matches
from src.notifier import send_alert

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")


def load_config():
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


def format_match_message(match):
    """
    Formats a single qualifying day into a notification message.
    Shows worst-case (max) wind and cloud across the 4-hour block
    so the client knows the ceiling of what to expect.
    """
    tide_line = (
        f"High tide: {match['high_tide_time'].strftime('%I:%M %p')}\n"
        if match.get("high_tide_time")
        else ""
    )
    return (
        f"Date: {match['date'].strftime('%A, %b %d')}\n"
        f"Window: {match['block_start'].strftime('%I:%M %p')} - "
        f"{match['block_end'].strftime('%I:%M %p')}\n"
        f"Max wind: {match['wind_mph']:.0f} mph | Max cloud: {match['cloud_pct']:.0f}%\n"
        f"{tide_line}"
    )


def run_test(config):
    print("Sending test notification...")
    send_alert(
        topic=config["ntfy_topic"],
        title="Test Alert - Tide & Weather Tool",
        message=(
            "This is a test notification.\n"
            "If you received this, setup is working correctly.\n\n"
            "Example alert format:\n"
            "Date: Tuesday, Jun 23\n"
            "Window: 10:00 AM - 02:00 PM\n"
            "Max wind: 8 mph | Max cloud: 12%\n"
            "High tide: 11:30 AM"
        ),
    )
    print("Test notification sent. Check your ntfy app/subscription.")


def run_check(config):
    thresholds = config["thresholds"]
    topic = config["ntfy_topic"]

    for location in config["locations"]:
        name = location["name"]
        check_tide = location.get("check_tide", True)
        print(f"Checking {name}...")

        try:
            forecast = get_wind_cloud_forecast(location["lat"], location["lon"])
            high_tides = get_high_tides(location["noaa_station_id"]) if check_tide else []
        except Exception as e:
            print(f"  ERROR fetching data for {name}: {e}")
            continue

        matches = find_matches(forecast, high_tides, thresholds, location)

        if not matches:
            print(f"  No qualifying windows found for {name} in the next 5 weekdays.")
            continue

        for match in matches:
            message = format_match_message(match)
            try:
                send_alert(topic, title=f"Match conditions: {name}", message=message)
                print(f"  ALERT SENT for {name} on {match['date']} "
                      f"({match['block_start'].strftime('%I%p')}-"
                      f"{match['block_end'].strftime('%I%p')})")
            except Exception as e:
                print(f"  ERROR sending alert for {name}: {e}")


def lambda_handler(event, context):
    """
    AWS Lambda entry point.
    Called automatically by EventBridge on the configured schedule.
    """
    config = load_config()
    run_check(config)
    return {"statusCode": 200, "body": "Check complete"}


if __name__ == "__main__":
    config = load_config()

    if "--test" in sys.argv:
        run_test(config)
    else:
        run_check(config)