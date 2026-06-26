"""
email_sender.py
Sends HTML email notifications via Resend API.
Builds a weekly forecast table covering all locations x 5 weekdays.
"""

import json
import urllib.request
import urllib.error


RESEND_API_URL = "https://api.resend.com/emails"
SENDER = "Tide & Weather Alert <alerts@createlogs.com>"


def build_html_table(all_results, weekdays):
    """
    Builds a full HTML email with a forecast table.
    Rows = locations, Columns = weekdays.
    """
    # Colors
    COLOR_MATCH = "#d4edda"
    COLOR_NO_MATCH = "#f8d7da"
    COLOR_NO_DATA = "#f5f5f5"
    COLOR_HEADER_BG = "#1F4E79"
    COLOR_HEADER_TEXT = "#ffffff"
    COLOR_LOCATION_BG = "#2E75B6"

    # Build column headers
    date_headers = ""
    for day in weekdays:
        date_headers += f"""
            <th style="background:{COLOR_HEADER_BG}; color:{COLOR_HEADER_TEXT};
                padding:10px 14px; font-size:13px; font-weight:600;
                border:1px solid #ccc; white-space:nowrap;">
                {day.strftime("%a")}<br>{day.strftime("%b %d")}
            </th>"""

    # Build rows
    rows = ""
    for location_name, day_results in all_results.items():
        cells = ""
        for day in weekdays:
            result = day_results.get(day)
            if result is None or (result[0] == "no_match" and result[1] == "No Data"):
                bg = COLOR_NO_DATA
                cell_content = "<span style=\"color:#999; font-size:12px;\">No Forecast</span>"
            elif result[0] == "match":
                r_type, blk_start, blk_end, tide_time = result
                start_t = blk_start.strftime("%I%p").lstrip("0")
                end_t = blk_end.strftime("%I%p").lstrip("0")
                bg = COLOR_MATCH
                tide_str = (
                    f"<br><span style=\"font-size:10px; color:#155724;\">"
                    f"🌊 High tide at: {tide_time.strftime('%I:%M %p')}</span>"
                    if tide_time else ""
                )
                cell_content = (
                    "<span style=\"font-size:22px;\">✅</span><br>"
                    f"<span style=\"font-size:12px; font-weight:700; color:#155724;\">"
                    f"{start_t} – {end_t}</span><br>"
                    "<span style=\"font-size:10px; color:#155724;\">Conditions Met</span>"
                    f"{tide_str}"
                )
            else:
                r_type, reason = result
                bg = COLOR_NO_MATCH
                # Icon + label per reason
                reason_icons = {
                    "Too Windy":        ("💨", "Too Windy"),
                    "Too Cloudy":       ("☁️", "Too Cloudy"),
                    "Windy, Cloudy":    ("💨☁️", "Windy, Cloudy"),
                    "No High Tide":     ("🌊", "No High Tide"),
                    "No Window":        ("❌", "No Window"),
                    "Windy, No Tide":   ("💨🌊", "Windy, No Tide"),
                    "Cloudy, No Tide":  ("☁️🌊", "Cloudy, No Tide"),
                    "Windy, Cloudy, No Tide": ("💨☁️🌊", "Windy, Cloudy, No Tide"),
                }
                icon, label = reason_icons.get(reason, ("❌", reason))
                cell_content = (
                    f"<span style=\"font-size:22px;\">{icon}</span><br>"
                    f"<span style=\"font-size:11px; color:#721c24; font-weight:600;\">"
                    f"{label}</span>"
                )

            cells += f"""
                <td style="background:{bg}; padding:10px 8px; text-align:center;
                    border:1px solid #ccc; min-width:90px; vertical-align:middle;">
                    {cell_content}
                </td>"""

        rows += f"""
            <tr>
                <td style="background:{COLOR_LOCATION_BG}; color:white; padding:10px 14px;
                    font-weight:600; font-size:13px; border:1px solid #ccc;
                    white-space:nowrap;">
                    📍 {location_name}
                </td>
                {cells}
            </tr>"""

    # Date range for subject
    start_date = weekdays[0].strftime("%b %d")
    end_date = weekdays[-1].strftime("%b %d")

    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: Arial, sans-serif; padding: 24px; background: #f9f9f9;">

        <h2 style="color:#1F4E79; margin-bottom:4px;">
            🌊 Tide & Weather — Weekly Forecast
        </h2>
        <p style="color:#666; margin-top:0; font-size:14px;">
            {start_date} to {end_date} &nbsp;|&nbsp;
            Conditions: Wind ≤12 mph, Cloud &lt;20%
        </p>

        <table style="border-collapse:collapse; width:100%; margin-top:16px;">
            <thead>
                <tr>
                    <th style="background:{COLOR_HEADER_BG}; color:{COLOR_HEADER_TEXT};
                        padding:10px 14px; font-size:13px; text-align:left;
                        border:1px solid #ccc;">
                        Location
                    </th>
                    {date_headers}
                </tr>
            </thead>
            <tbody>
                {rows}
            </tbody>
        </table>

        <p style="margin-top:20px; font-size:12px; color:#999;">
            ✅ = conditions met &nbsp;|&nbsp;
            🟥 = conditions not met &nbsp;|&nbsp;
            ⬜ = no forecast data yet
        </p>

    </body>
    </html>
    """
    return html, f"🌊 Tide & Weather Forecast — {start_date} to {end_date}"


def send_email(api_key, recipient_email, all_results, weekdays):
    """
    Sends the HTML forecast table via Resend API.
    Uses urllib (no extra dependencies needed).
    """
    html, subject = build_html_table(all_results, weekdays)

    payload = json.dumps({
        "from": SENDER,
        "to": [recipient_email],
        "subject": subject,
        "html": html,
    }).encode("utf-8")

    req = urllib.request.Request(
        RESEND_API_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "tide-weather-alert/1.0",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        raise Exception(f"Resend API error {e.code}: {error_body}")