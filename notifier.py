"""
Sends push notifications via ntfy.sh.
Free, no account or API key required.
Setup: install the ntfy app (iOS/Android) or visit ntfy.sh/<your-topic>
       in a browser, then subscribe to the topic configured in config.json.
"""

import requests

NTFY_URL = "https://ntfy.sh"


def send_alert(topic, title, message):
    """
    Sends a push notification to the given ntfy topic.
    """
    response = requests.post(
        f"{NTFY_URL}/{topic}",
        data=message.encode("utf-8"),
        headers={
            "Title": title,
            "Priority": "default",
            "Tags": "ocean,sunny",
        },
        timeout=10,
    )
    response.raise_for_status()
    return response