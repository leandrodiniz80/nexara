"""Alert -> outbound-payload templates (Sprint 258).

Both formatters read `error_rate`/`avg_duration` from `alert["current"]`,
not `alert.get("error_rate")`/`alert.get("avg_duration")` directly (the
original spec's own code): `detect_anomalies()` (loader_metrics.py) never
puts those keys on the alert dict itself — they only exist nested under
`alert["current"]`/`alert["baseline"]` (each shaped like `summary_window()`'s
own return value). Read literally, the spec's version would always see
`None` for both fields, silently showing "Error Rate: None" / "Latency:
None" in every Slack message, no matter how bad the actual anomaly was —
the whole point of these templates. Fixed by reading the nested
`current` window's stats instead, which is what's actually anomalous (the
same values `_severity()`/`_alert_type()` already key off of).

Deliberately not changing `alert`'s own top-level shape to flatten these
fields onto it instead — that's an explicit constraint for this sprint,
and every other alert-consuming caller would need auditing if it changed.
"""


def format_generic(alert: dict) -> dict:
    current = alert.get("current", {})

    return {
        "domain": alert["domain"],
        "severity": alert["severity"],
        "error_rate": current.get("error_rate"),
        "latency": current.get("avg_duration"),
        "type": alert.get("type"),
    }


def format_slack(alert: dict) -> dict:
    current = alert.get("current", {})

    return {
        "text": f"🚨 Alert: {alert['domain']}",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*Domain:* {alert['domain']}\n"
                        f"*Severity:* {alert['severity']}\n"
                        f"*Error Rate:* {current.get('error_rate')}\n"
                        f"*Latency:* {current.get('avg_duration')}"
                    ),
                },
            }
        ],
    }
