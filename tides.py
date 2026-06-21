"""
Fetches high tide predictions from NOAA CO-OPS (US coastal stations only).
No API key required. Find station IDs at:
https://tidesandcurrents.noaa.gov/tide_predictions.html
"""

import requests
from datetime import datetime, timedelta

NOAA_URL = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"


def get_high_tides(station_id, days=2):
    """
    Returns a list of datetimes representing high tide events
    over the next `days` days for the given NOAA station.
    """
    begin = datetime.now()
    end = begin + timedelta(days=days)

    params = {
        "station": station_id,
        "product": "predictions",
        "datum": "MLLW",
        "time_zone": "lst_ldt",
        "units": "english",
        "interval": "hilo",
        "format": "json",
        "begin_date": begin.strftime("%Y%m%d %H:%M"),
        "end_date": end.strftime("%Y%m%d %H:%M"),
    }

    response = requests.get(NOAA_URL, params=params, timeout=15)
    response.raise_for_status()
    data = response.json()

    predictions = data.get("predictions", [])

    high_tides = []
    for entry in predictions:
        if entry.get("type") == "H":  # H = High tide, L = Low tide
            high_tides.append(datetime.strptime(entry["t"], "%Y-%m-%d %H:%M"))

    return high_tides