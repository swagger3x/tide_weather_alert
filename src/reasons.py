"""
reasons.py
Determines the display reason for each location/day combination.
Uses window-level reasoning:
- Too Windy: no 4hr block where all hours have wind <= threshold
- Too Cloudy: no 4hr block where all hours have cloud < threshold
- Windy, Cloudy: neither wind nor cloud has a qualifying 4hr block
- No Window: wind 4hr block exists AND cloud 4hr block exists but never overlap
- No High Tide: combined wind+cloud 4hr block exists but no tide aligns
- No Data: no forecast data for that day
"""

from datetime import timedelta


def has_4hr_block_wind(hours, max_wind):
    """Check if any 4 consecutive hours all have wind <= max_wind"""
    for i in range(len(hours) - 3):
        block = hours[i:i + 4]
        times = [b["time"] for b in block]
        gaps = [(times[j+1] - times[j]).seconds // 3600 for j in range(3)]
        if any(g != 1 for g in gaps):
            continue
        if all(h["wind_mph"] <= max_wind for h in block):
            return True
    return False


def has_4hr_block_cloud(hours, max_cloud):
    """Check if any 4 consecutive hours all have cloud < max_cloud"""
    for i in range(len(hours) - 3):
        block = hours[i:i + 4]
        times = [b["time"] for b in block]
        gaps = [(times[j+1] - times[j]).seconds // 3600 for j in range(3)]
        if any(g != 1 for g in gaps):
            continue
        if all(h["cloud_pct"] < max_cloud for h in block):
            return True
    return False


def get_day_reason(forecast, high_tides, thresholds, location, target_date):
    """
    For a given location and date, returns either:
    - ("match", block_start, block_end) if conditions are met
    - ("no_match", reason_string) if not met
    """
    from matcher import get_hours_in_window, find_4hr_blocks, block_has_tide

    max_wind = thresholds["max_wind_mph"]
    max_cloud = thresholds["max_cloud_pct"]
    check_tide = location.get("check_tide", True)

    day_hours = get_hours_in_window(forecast, target_date)

    if not day_hours:
        return ("no_match", "No Data")

    # Check wind and cloud independently at window level
    wind_has_block = has_4hr_block_wind(day_hours, max_wind)
    cloud_has_block = has_4hr_block_cloud(day_hours, max_cloud)

    # Both fail — neither has a qualifying 4hr block
    if not wind_has_block and not cloud_has_block:
        return ("no_match", "Windy, Cloudy")

    # Only wind fails
    if not wind_has_block:
        return ("no_match", "Too Windy")

    # Only cloud fails
    if not cloud_has_block:
        return ("no_match", "Too Cloudy")

    # Both wind and cloud have qualifying 4hr blocks independently
    # Now check if they overlap (combined block)
    combined_blocks = find_4hr_blocks(day_hours, thresholds)

    if not combined_blocks:
        return ("no_match", "No Window")

    # Combined block exists — check tide if required
    if not check_tide:
        block = combined_blocks[0]
        return ("match", block[0]["time"], block[-1]["time"])

    for block in combined_blocks:
        tide = block_has_tide(block, high_tides)
        if tide:
            return ("match", block[0]["time"], block[-1]["time"])

    return ("no_match", "No High Tide")