"""
weather.py
Fetches hourly wind speed (mph) and cloud cover (%) forecasts from Open-Meteo.
No API key required.
"""

import requests
from datetime import datetime

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


def get_wind_cloud_forecast(lat, lon, forecast_days=6):
    """
    Returns a list of dicts, one per forecast hour:
    [{"time": datetime, "wind_mph": float, "cloud_pct": float}, ...]

    forecast_days=6 covers today + 5 weekdays ahead (accounts for
    weekends being skipped when finding the next 5 weekdays).
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "windspeed_10m,cloudcover",
        "windspeed_unit": "mph",
        "forecast_days": forecast_days,
        "timezone": "auto",
    }

    response = requests.get(OPEN_METEO_URL, params=params, timeout=15)
    response.raise_for_status()
    data = response.json()

    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    winds = hourly.get("windspeed_10m", [])
    clouds = hourly.get("cloudcover", [])

    forecast = []
    for t, w, c in zip(times, winds, clouds):
        # ensure t is a string before parsing (guards against bytes on Windows)
        if isinstance(t, bytes):
            t = t.decode("utf-8")
        forecast.append({
            "time": datetime.fromisoformat(str(t)),
            "wind_mph": float(w),
            "cloud_pct": float(c),
        })

    return forecast