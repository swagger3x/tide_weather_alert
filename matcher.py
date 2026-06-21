"""
Core rule engine: finds forecast hours where wind, cloud cover,
and high tide timing all satisfy the configured thresholds.
"""

from datetime import timedelta


def find_matches(forecast, high_tides, thresholds, window_hours=1):
    """
    forecast: list of {"time", "wind_mph", "cloud_pct"} from weather.py
    high_tides: list of datetimes from tides.py
    thresholds: {"max_wind_mph": ..., "max_cloud_pct": ...}
    window_hours: how close a high tide must be to the forecast hour
                  to count as "during this period"

    Returns a list of match dicts ready for notification.
    """
    max_wind = thresholds["max_wind_mph"]
    max_cloud = thresholds["max_cloud_pct"]
    window = timedelta(hours=window_hours)

    matches = []
    for hour in forecast:
        if hour["wind_mph"] > max_wind:
            continue
        if hour["cloud_pct"] >= max_cloud:
            continue

        # is there a high tide within `window` of this forecast hour?
        nearby_tide = next(
            (t for t in high_tides if abs(t - hour["time"]) <= window),
            None,
        )
        if nearby_tide is None:
            continue

        matches.append({
            "time": hour["time"],
            "wind_mph": hour["wind_mph"],
            "cloud_pct": hour["cloud_pct"],
            "high_tide_time": nearby_tide,
        })

    return matches