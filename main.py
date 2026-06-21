"""
Orchestrates a single check across all configured locations:
fetch forecast -> fetch tides -> find matches -> dedupe -> notify.

Run manually:
    python main.py

Run a test notification (sends immediately, skips the real check):
    python main.py --test

Intended to be scheduled via cron (see README.md) to run periodically,
since forecasts update over time.
"""

import json
import sys
import os

from weather import get_wind_cloud_forecast
from tides import get_high_tides
from matcher import find_matches
from notifier import send_alert
from state import load_alerted_keys, save_alerted_keys, make_match_key

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")


def load_config():
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


def format_message(location_name, match):
    return (
        f"Wind: {match['wind_mph']:.0f} mph | "
        f"Clouds: {match['cloud_pct']:.0f}% | "
        f"High tide: {match['high_tide_time'].strftime('%I:%M %p')}\n"
        f"Forecast hour: {match['time'].strftime('%a %I:%M %p')}"
    )


def format_no_match_message(forecast, high_tides, thresholds, window_hours):
    from datetime import timedelta

    max_wind = thresholds["max_wind_mph"]
    max_cloud = thresholds["max_cloud_pct"]
    window = timedelta(hours=window_hours)

    if not high_tides:
        return "No high tides found in the next 2 days."

    lines = []
    for tide in high_tides:
        nearby = [h for h in forecast if abs(h["time"] - tide) <= window]
        if not nearby:
            lines.append(f"High tide {tide.strftime('%a %I:%M %p')}: no forecast data in window.")
            continue

        # pick the hour closest to meeting both thresholds
        best = min(nearby, key=lambda h: (h["wind_mph"] > max_wind, h["cloud_pct"] >= max_cloud))
        issues = []
        if best["wind_mph"] > max_wind:
            issues.append(f"wind {best['wind_mph']:.0f} mph (limit {max_wind})")
        if best["cloud_pct"] >= max_cloud:
            issues.append(f"cloud {best['cloud_pct']:.0f}% (limit <{max_cloud}%)")

        lines.append(
            f"High tide {tide.strftime('%a %I:%M %p')} — NOT MET\n"
            f"  Wind: {best['wind_mph']:.0f} mph | Cloud: {best['cloud_pct']:.0f}%\n"
            f"  Issues: {', '.join(issues)}"
        )

    return "\n\n".join(lines)


def run_test(config):
    print("Sending test notification...")
    send_alert(
        topic=config["ntfy_topic"],
        title="Test Alert - Tide & Weather Tool",
        message="This is a test notification. If you received this, setup is working correctly.",
    )
    print("Test notification sent. Check your ntfy app/subscription.")


def _print_debug(forecast, high_tides, thresholds, window_hours):
    from datetime import timedelta

    print(f"  High tides ({len(high_tides)}):")
    for t in high_tides:
        print(f"    {t.strftime('%a %Y-%m-%d %I:%M %p')}")

    max_wind = thresholds["max_wind_mph"]
    max_cloud = thresholds["max_cloud_pct"]
    window = timedelta(hours=window_hours)

    print(f"  Forecast near high tides (wind<={max_wind} mph, cloud<{max_cloud}%):")
    for hour in forecast:
        nearby = any(abs(t - hour["time"]) <= window for t in high_tides)
        if not nearby:
            continue
        wind_ok = hour["wind_mph"] <= max_wind
        cloud_ok = hour["cloud_pct"] < max_cloud
        status = "MATCH" if (wind_ok and cloud_ok) else "blocked"
        reasons = []
        if not wind_ok:
            reasons.append(f"wind {hour['wind_mph']:.0f}>{max_wind}")
        if not cloud_ok:
            reasons.append(f"cloud {hour['cloud_pct']:.0f}>={max_cloud}")
        detail = " | ".join(reasons) if reasons else ""
        print(
            f"    {hour['time'].strftime('%a %I:%M %p')}  "
            f"wind={hour['wind_mph']:.0f}mph  cloud={hour['cloud_pct']:.0f}%"
            f"  [{status}{': ' + detail if detail else ''}]"
        )


def run_check(config, debug=False):
    thresholds = config["thresholds"]
    window_hours = config.get("match_window_hours", 1)
    topic = config["ntfy_topic"]

    alerted_keys = load_alerted_keys()
    new_alerted_keys = set(alerted_keys)

    for location in config["locations"]:
        name = location["name"]
        print(f"Checking {name}...")

        try:
            forecast = get_wind_cloud_forecast(location["lat"], location["lon"])
            high_tides = get_high_tides(location["noaa_station_id"])
        except Exception as e:
            print(f"  ERROR fetching data for {name}: {e}")
            continue

        if debug:
            _print_debug(forecast, high_tides, thresholds, window_hours)

        matches = find_matches(forecast, high_tides, thresholds, window_hours)

        if not matches:
            print(f"  No matching windows found for {name}. Sending conditions-not-met notification.")
            message = format_no_match_message(forecast, high_tides, thresholds, window_hours)
            try:
                send_alert(topic, title=f"Conditions not met: {name}", message=message)
            except Exception as e:
                print(f"  ERROR sending notification for {name}: {e}")
            continue

        for match in matches:
            key = make_match_key(name, match)
            if key in alerted_keys:
                continue  # already alerted for this exact hour

            message = format_message(name, match)
            try:
                send_alert(topic, title=f"Good conditions: {name}", message=message)
                print(f"  ALERT SENT for {name} at {match['time']}")
                new_alerted_keys.add(key)
            except Exception as e:
                print(f"  ERROR sending alert for {name}: {e}")

    save_alerted_keys(new_alerted_keys)


if __name__ == "__main__":
    config = load_config()

    if "--test" in sys.argv:
        run_test(config)
    else:
        run_check(config, debug="--debug" in sys.argv)