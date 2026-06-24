"""
matcher.py
Core rule engine: finds 4-consecutive-hour blocks within 8am-8pm
across the next 5 weekdays where wind, cloud cover, and optionally
high tide all satisfy the configured thresholds.
"""

from datetime import datetime, timedelta, date


def get_next_5_weekdays(from_date=None):
    """
    Returns the next 5 weekdays (Mon-Fri) starting from tomorrow
    relative to from_date. Defaults to today if not provided.
    """
    if from_date is None:
        from_date = datetime.now().date()

    days = []
    current = from_date + timedelta(days=1)
    while len(days) < 5:
        if current.weekday() < 5:  # 0=Mon, 4=Fri
            days.append(current)
        current += timedelta(days=1)
    return days


def get_hours_in_window(forecast, target_date, start_hour=8, end_hour=20):
    """
    Filters forecast to hours within start_hour to end_hour (exclusive)
    on the given target_date.
    """
    return [
        h for h in forecast
        if h["time"].date() == target_date
        and start_hour <= h["time"].hour < end_hour
    ]


def find_4hr_blocks(hours, thresholds):
    """
    Slides a 4-hour window across the given hours list.
    Returns qualifying blocks where all 4 consecutive hours pass
    wind + cloud thresholds.
    """
    max_wind = thresholds["max_wind_mph"]
    max_cloud = thresholds["max_cloud_pct"]
    qualifying_blocks = []

    for i in range(len(hours) - 3):
        block = hours[i:i + 4]

        # ensure the 4 hours are actually consecutive (no gaps)
        times = [b["time"] for b in block]
        gaps = [(times[j+1] - times[j]).seconds // 3600 for j in range(3)]
        if any(g != 1 for g in gaps):
            continue

        # check all 4 hours pass wind and cloud thresholds
        if all(
            h["wind_mph"] <= max_wind and h["cloud_pct"] < max_cloud
            for h in block
        ):
            qualifying_blocks.append(block)

    return qualifying_blocks


def block_has_tide(block, high_tides, buffer_hours=1):
    """
    Returns the high tide datetime if one falls within the block window
    plus/minus buffer_hours on either side. Returns None if no tide qualifies.
    """
    block_start = block[0]["time"] - timedelta(hours=buffer_hours)
    block_end = block[-1]["time"] + timedelta(hours=buffer_hours)

    for tide in high_tides:
        if block_start <= tide <= block_end:
            return tide
    return None


def find_matches(forecast, high_tides, thresholds, location, from_date=None):
    """
    Main entry point. Checks the next 5 weekdays for qualifying 4-hour
    blocks between 8am-8pm. Tide check is skipped if location has
    check_tide=False.

    from_date: override today's date (used for testing). Defaults to today.

    Returns a list of match dicts, one per qualifying day:
    [
      {
        "date": date,
        "block_start": datetime,
        "block_end": datetime,
        "wind_mph": float (worst in block),
        "cloud_pct": float (worst in block),
        "high_tide_time": datetime or None,
      },
      ...
    ]
    """
    check_tide = location.get("check_tide", True)
    weekdays = get_next_5_weekdays(from_date)
    matches = []

    for day in weekdays:
        day_hours = get_hours_in_window(forecast, day)
        if not day_hours:
            continue

        blocks = find_4hr_blocks(day_hours, thresholds)
        if not blocks:
            continue

        matched_block = None
        matched_tide = None

        for block in blocks:
            if check_tide:
                tide = block_has_tide(block, high_tides)
                if tide is None:
                    continue  # tide required but not found in this block
                matched_tide = tide
            matched_block = block
            break  # take the first qualifying block of the day

        if matched_block is None:
            continue

        matches.append({
            "date": day,
            "block_start": matched_block[0]["time"],
            "block_end": matched_block[-1]["time"],
            "wind_mph": max(h["wind_mph"] for h in matched_block),
            "cloud_pct": max(h["cloud_pct"] for h in matched_block),
            "high_tide_time": matched_tide,
        })

    return matches