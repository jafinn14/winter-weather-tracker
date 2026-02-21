#!/usr/bin/env python3
"""
Standalone script to automatically fetch weather data.
Designed to be run by Windows Task Scheduler.
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

# Set up logging
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / f"auto_fetch_{datetime.now().strftime('%Y%m')}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Import local modules
from database import (
    init_db, get_location_by_zip, save_forecast, save_discussion,
    get_forecasts_for_location
)
from nws_api import (
    get_forecast, get_hourly_forecast, get_gridpoint_data,
    get_area_forecast_discussion, NWSAPIError
)
from change_detection import detect_changes, format_changes
from notify import send_notification
from snow_events import identify_snow_events, save_detected_events


def fetch_for_location(location: dict) -> dict:
    """Fetch all weather data for a single location."""
    grid_id = location['forecast_office']
    grid_x = location['grid_x']
    grid_y = location['grid_y']
    location_id = location['id']

    logger.info(f"Fetching data for {location['city']}, {location['state']} ({location['zip_code']})")

    results = {
        'location': location,
        'success': False,
        'forecast_id': None,
        'discussion_id': None,
        'error': None
    }

    try:
        # Fetch forecast data
        forecast = get_forecast(grid_id, grid_x, grid_y)
        hourly = get_hourly_forecast(grid_id, grid_x, grid_y)
        gridpoint = get_gridpoint_data(grid_id, grid_x, grid_y)

        # Combine into single forecast object
        forecast_data = {
            'forecast': forecast,
            'hourly': hourly,
            'gridpoint': gridpoint
        }

        # Save forecast
        forecast_id = save_forecast(location_id, forecast_data)
        results['forecast_id'] = forecast_id
        logger.info(f"Saved forecast with ID {forecast_id}")

        # Fetch discussion
        try:
            afd = get_area_forecast_discussion(grid_id)
            discussion_id = save_discussion(
                location_id,
                afd['text'],
                afd.get('issued_at')
            )
            results['discussion_id'] = discussion_id
            logger.info(f"Saved discussion with ID {discussion_id}")
        except NWSAPIError as e:
            logger.warning(f"Could not fetch discussion: {e}")

        results['success'] = True

    except NWSAPIError as e:
        results['error'] = str(e)
        logger.error(f"API error for {location['zip_code']}: {e}")
    except Exception as e:
        results['error'] = str(e)
        logger.error(f"Unexpected error for {location['zip_code']}: {e}")

    return results


def check_for_changes(location_id: int) -> list:
    """Check for significant forecast changes and return them."""
    forecasts = get_forecasts_for_location(location_id, days_back=7)

    if len(forecasts) < 2:
        logger.info("Not enough forecasts to compare")
        return []

    # Compare the two most recent forecasts
    current = forecasts[0]
    previous = forecasts[1]

    changes = detect_changes(previous, current)

    if changes:
        logger.info(f"Detected {len(changes)} significant change(s)")
        for change in changes:
            logger.info(f"  - {change['type']}: {change['summary']}")

    return changes


def get_all_locations() -> list:
    """Get all saved locations from the database."""
    import sqlite3
    from database import DB_PATH

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM locations")
    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def main():
    parser = argparse.ArgumentParser(description='Automatically fetch weather data')
    parser.add_argument('--zip', type=str, help='Fetch for specific zip code only')
    parser.add_argument('--all', action='store_true', help='Fetch for all saved locations')
    parser.add_argument('--no-notify', action='store_true', help='Disable notifications')
    parser.add_argument('--dry-run', action='store_true', help='Check changes without fetching new data')
    args = parser.parse_args()

    logger.info("=" * 50)
    logger.info("Starting auto-fetch")

    # Initialize database
    init_db()

    # Determine which locations to fetch
    locations = []

    if args.zip:
        location = get_location_by_zip(args.zip)
        if location:
            locations = [location]
        else:
            logger.error(f"Location not found for zip code: {args.zip}")
            sys.exit(1)
    elif args.all:
        locations = get_all_locations()
        if not locations:
            logger.warning("No saved locations found")
            sys.exit(0)
    else:
        # Default: fetch all locations
        locations = get_all_locations()
        if not locations:
            logger.warning("No saved locations found. Use --zip to specify a location.")
            sys.exit(0)

    logger.info(f"Processing {len(locations)} location(s)")

    all_changes = []

    for location in locations:
        if args.dry_run:
            logger.info(f"Dry run - checking changes for {location['zip_code']}")
        else:
            # Fetch new data
            result = fetch_for_location(location)

            if not result['success']:
                logger.error(f"Failed to fetch for {location['zip_code']}: {result['error']}")
                continue

            # Detect snow events and save for trend tracking
            try:
                forecasts = get_forecasts_for_location(location['id'], days_back=1)
                if forecasts:
                    as_of = datetime.now()
                    events = identify_snow_events(forecasts[0]['forecast_data'], as_of, location['id'])
                    if events:
                        save_detected_events(location['id'], events, as_of)
                        logger.info(f"Saved {len(events)} detected event(s) for trend tracking")
                    else:
                        logger.info("No snow events detected in current forecast")
            except Exception as e:
                logger.warning(f"Event detection failed (non-fatal): {e}")

        # Check for significant changes
        changes = check_for_changes(location['id'])

        if changes:
            for change in changes:
                change['location'] = location
            all_changes.extend(changes)

    # Send notifications if there are changes
    if all_changes and not args.no_notify:
        notification_text = format_changes(all_changes)
        logger.info(f"Sending notification: {notification_text[:100]}...")

        try:
            send_notification(
                title="Weather Forecast Changed",
                message=notification_text
            )
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")

    logger.info(f"Auto-fetch complete. Processed {len(locations)} location(s), {len(all_changes)} change(s) detected.")


if __name__ == "__main__":
    main()
