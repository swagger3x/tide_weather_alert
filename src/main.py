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
from email_sender import send_email

CONFIG_FILE_SRC = os.path.join(os.path.dirname(__file__), "config.json")
CONFIG_FILE = "/tmp/config.json"


def load_config():
    # Lambda /var/task is read-only — copy config to writable /tmp on first run
    if not os.path.exists(CONFIG_FILE):
        import shutil
        shutil.copy2(CONFIG_FILE_SRC, CONFIG_FILE)
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
                lines.append(f"\U0001F7E2 {label} \u2014 Conditions Met {start_t} - {end_t}")
            else:
                _, reason = result
                if reason == "No Data":
                    lines.append(f"\u2b1c {label} \u2014 No Forecast Yet")
                else:
                    reason_icons = {
                        "Too Windy":     "\U0001f4a8 Too Windy",
                        "Too Cloudy":    "\u2601\ufe0f Too Cloudy",
                        "Windy, Cloudy": "\U0001f4a8\u2601\ufe0f Windy, Cloudy",
                    }
                    display_reason = reason_icons.get(reason, reason)
                    lines.append(f"\u274c {label} \u2014 {display_reason}")
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
        print("\nntfy notification sent.")
    except Exception as e:
        print(f"\nERROR sending ntfy notification: {e}")

    # Send HTML email via Resend
    api_key = config.get("resend_api_key")
    recipient = config.get("recipient_email")
    if api_key and recipient:
        try:
            send_email(api_key, recipient, all_results, weekdays)
            print(f"Email sent to {recipient}.")
        except Exception as e:
            print(f"ERROR sending email: {e}")
    else:
        print("Email skipped — resend_api_key or recipient_email not set in config.")


# ----------------------------------------------------------------
# EMAIL UPDATE ENDPOINT — currently disabled
# Requires further discussion on persistent storage approach
# since Lambda /var/task is read-only and /tmp resets on cold start.
# To re-enable: uncomment the functions below and restore
# the HTTP request handler block in lambda_handler.
# ----------------------------------------------------------------

# def update_recipient_email(config, new_email, token):
#     """
#     Updates recipient_email in config.json on Lambda.
#     Only proceeds if the provided token matches api_secret in config.
#     """
#     expected_token = config.get("api_secret", "")
#
#     if not expected_token:
#         return {"statusCode": 500, "body": "api_secret not configured"}
#
#     if token != expected_token:
#         return {"statusCode": 401, "body": "Invalid token"}
#
#     if not new_email or "@" not in new_email:
#         return {"statusCode": 400, "body": "Invalid email address"}
#
#     # Update config file in place
#     with open(CONFIG_FILE, "r") as f:
#         raw = json.load(f)
#
#     old_email = raw.get("recipient_email", "")
#     raw["recipient_email"] = new_email
#
#     with open(CONFIG_FILE, "w") as f:
#         json.dump(raw, f, indent=2)
#
#     print(f"Email updated: {old_email} -> {new_email}")
#     return {
#         "statusCode": 200,
#         "body": json.dumps({
#             "message": "Email updated successfully",
#             "old_email": old_email,
#             "new_email": new_email,
#         })
#     }
#
#
# CORS_HEADERS = {
#     "Access-Control-Allow-Origin": "*",
#     "Access-Control-Allow-Methods": "POST",
# }
#
#
# def cors_response(status_code, body):
#     """Wraps a response with CORS headers."""
#     return {
#         "statusCode": status_code,
#         "headers": CORS_HEADERS,
#         "body": body if isinstance(body, str) else __import__('json').dumps(body),
#     }


def lambda_handler(event, context):
    """
    AWS Lambda entry point.
    Called automatically by EventBridge on the configured schedule.
    Email update endpoint is currently disabled — see comments above.
    """
    config = load_config()

    # HTTP request handler (disabled — uncomment when email update is re-enabled)
    # if event.get("requestContext", {}).get("http"):
    #     method = event.get("requestContext", {}).get("http", {}).get("method", "")
    #     if method == "OPTIONS":
    #         return cors_response(200, "OK")
    #     try:
    #         body = json.loads(event.get("body") or "{}")
    #     except json.JSONDecodeError:
    #         return cors_response(400, "Invalid JSON body")
    #     action = body.get("action")
    #     token = body.get("token", "")
    #     new_email = body.get("email", "")
    #     if action == "update_email":
    #         result = update_recipient_email(config, new_email, token)
    #         result["headers"] = CORS_HEADERS
    #         return result
    #     return cors_response(400, "Unknown action")

    # EventBridge scheduled trigger -> run weather check
    run_check(config)
    return {"statusCode": 200, "body": "Check complete"}


if __name__ == "__main__":
    config = load_config()
    if "--test" in sys.argv:
        run_test(config)
    else:
        run_check(config)