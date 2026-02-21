"""
Notification module for sending desktop alerts.
Supports Windows toast notifications.
"""

import sys
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Track which notification library is available
_notification_backend = None


def _init_notification_backend():
    """Initialize the notification backend."""
    global _notification_backend

    if _notification_backend is not None:
        return _notification_backend

    # Try plyer first (cross-platform)
    try:
        from plyer import notification as plyer_notification
        _notification_backend = 'plyer'
        logger.debug("Using plyer for notifications")
        return _notification_backend
    except ImportError:
        pass

    # Try win10toast (Windows-specific)
    if sys.platform == 'win32':
        try:
            from win10toast import ToastNotifier
            _notification_backend = 'win10toast'
            logger.debug("Using win10toast for notifications")
            return _notification_backend
        except ImportError:
            pass

    # Fallback to console
    _notification_backend = 'console'
    logger.warning("No notification library available, using console output")
    return _notification_backend


def send_notification(
    title: str,
    message: str,
    timeout: int = 10,
    app_name: str = "Winter Weather Tracker"
) -> bool:
    """
    Send a desktop notification.

    Args:
        title: Notification title
        message: Notification body
        timeout: How long to show notification (seconds)
        app_name: Application name to display

    Returns:
        True if notification was sent successfully
    """
    backend = _init_notification_backend()

    # Truncate message if too long for toast notifications
    max_message_len = 250
    if len(message) > max_message_len:
        message = message[:max_message_len - 3] + "..."

    try:
        if backend == 'plyer':
            from plyer import notification as plyer_notification
            plyer_notification.notify(
                title=title,
                message=message,
                app_name=app_name,
                timeout=timeout
            )
            logger.info(f"Sent notification via plyer: {title}")
            return True

        elif backend == 'win10toast':
            from win10toast import ToastNotifier
            toaster = ToastNotifier()
            toaster.show_toast(
                title=title,
                msg=message,
                duration=timeout,
                threaded=True
            )
            logger.info(f"Sent notification via win10toast: {title}")
            return True

        else:
            # Console fallback
            print("\n" + "=" * 50)
            print(f"NOTIFICATION: {title}")
            print("-" * 50)
            print(message)
            print("=" * 50 + "\n")
            return True

    except Exception as e:
        logger.error(f"Failed to send notification: {e}")
        return False


def send_weather_alert(
    changes: list,
    location_name: Optional[str] = None
) -> bool:
    """
    Send a notification about weather forecast changes.

    Args:
        changes: List of change dictionaries from change_detection
        location_name: Optional location name for the title

    Returns:
        True if notification was sent successfully
    """
    if not changes:
        return False

    # Build title
    if location_name:
        title = f"Weather Alert: {location_name}"
    else:
        title = "Weather Forecast Changed"

    # Count high severity changes
    high_severity = sum(1 for c in changes if c.get('severity') == 'high')

    if high_severity > 0:
        title = f"⚠️ {title}"

    # Build message
    lines = []
    for change in changes[:5]:  # Limit to 5 changes for notification
        severity_marker = "!" if change.get('severity') == 'high' else "-"
        lines.append(f"{severity_marker} {change.get('summary', 'Change detected')}")

    if len(changes) > 5:
        lines.append(f"... and {len(changes) - 5} more changes")

    message = "\n".join(lines)

    return send_notification(title=title, message=message)


def test_notification():
    """Send a test notification to verify the system works."""
    return send_notification(
        title="Winter Weather Tracker",
        message="Test notification - your alerts are working!",
        timeout=5
    )


if __name__ == "__main__":
    # Test notifications when run directly
    print("Testing notification system...")
    success = test_notification()
    if success:
        print("Notification sent successfully!")
    else:
        print("Failed to send notification.")
