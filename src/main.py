"""
main.py
Orchestrates a single check across all configured locations:
fetch forecast -> fetch tides -> build reasons -> notify.

Run manually:
    python main.py

Run a test notification:
    python main.py --test

Intended to be scheduled via AWS EventBridge once per day.
"""

import json
import sys
import os

from weather import get_wind_cloud_forecast
from tides import get_high_tides
from matcher import get_next_5_weekdays
from reasons import get_day_reason
from notifier import send_alert

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")


def load_config():
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


def build_ntfy_message(all_results, weekdays):
    """
    Builds a single combined vertical plain text message
    covering all locations x 5 weekdays.
    Uses emojis for instant visual scanning on mobile.

    all_results: {location_name: {date: (type, ...)}, ...}
    """
    from datetime import date as date_type

    # Header with date range
    start = weekdays[0].strftime("%b %d")
    end = weekdays[-1].strftime("%b %d")
    lines = [f"\U0001f30a Tide & Weather \u2014 {start} to {end}", ""]

    for location_name, day_results in all_results.items():
        lines.append(f"\U0001f4cd {location_name}")
        for day in weekdays:
            result = day_results.get(day)
            label = day.strftime("%a %b %d").replace(" 0", " ")
            if result is None:
                lines.append(f"\u2b1c {label} \u2014 No Forecast Yet")
            elif result[0] == "match":
                _, block_start, block_end = result
                start_t = block_start.strftime("%I%p").lstrip("0")
                end_t = block_end.strftime("%I%p").lstrip("0")
                lines.append(f"\U0001F7E2 {label} \u2014 {start_t} - {end_t}")
            else:
                _, reason = result
                if reason == "No Data":
                    lines.append(f"\u2b1c {label} \u2014 No Forecast Yet")
                else:
                    lines.append(f"\u274c {label} \u2014 {reason}")
        lines.append("")

    return "\n".join(lines).strip()


def run_test(config):
    print("Sending test notification...")
    send_alert(
        topic=config["ntfy_topic"],
        title="Test Alert - Tide & Weather Tool",
        message=(
            "Tide & Weather - Weekly Forecast\n\n"
            "[ Poquoson, VA ]\n"
            "  Mon Jun 23  OK  10am - 2pm\n"
            "  Tue Jun 24  X  Too Windy\n"
            "  Wed Jun 25  X  Cloudy, No Tide\n"
            "  Thu Jun 26  OK  2pm - 6pm\n"
            "  Fri Jun 27  X  No High Tide\n\n"
            "[ Swan Quarter, NC ]\n"
            "  Mon Jun 23  X  Too Cloudy\n"
            "  Tue Jun 24  OK  11am - 3pm\n"
            "  Wed Jun 25  X  Too Windy\n"
            "  Thu Jun 26  OK  8am - 12pm\n"
            "  Fri Jun 27  X  Too Cloudy"
        ),
    )
    print("Test notification sent. Check your ntfy app.")


def run_check(config):
    thresholds = config["thresholds"]
    topic = config["ntfy_topic"]
    weekdays = get_next_5_weekdays()

    all_results = {}

    for location in config["locations"]:
        name = location["name"]
        check_tide = location.get("check_tide", True)
        print(f"Checking {name}...")

        try:
            forecast = get_wind_cloud_forecast(location["lat"], location["lon"])
            high_tides = get_high_tides(location["noaa_station_id"]) if check_tide else []
        except Exception as e:
            print(f"  ERROR fetching data for {name}: {e}")
            all_results[name] = {day: ("no_match", "No Data") for day in weekdays}
            continue

        day_results = {}
        for day in weekdays:
            result = get_day_reason(forecast, high_tides, thresholds, location, day)
            day_results[day] = result
            status = f"OK  {result[1].strftime('%I%p')}-{result[2].strftime('%I%p')}" if result[0] == "match" else f"X  {result[1]}"
            print(f"  {day.strftime('%a %b %d')}  {status}")

        all_results[name] = day_results

    # Build and send single combined ntfy notification
    message = build_ntfy_message(all_results, weekdays)
    try:
        send_alert(topic, title="Tide & Weather — Weekly Forecast", message=message)
        print("\nCombined notification sent.")
    except Exception as e:
        print(f"\nERROR sending notification: {e}")


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