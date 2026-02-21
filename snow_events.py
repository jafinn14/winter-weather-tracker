"""
Snow Event Detection and Tracking Module.

Identifies distinct snow events from forecast data, using actual dates
and multiple data sources. Tracks events over time to show evolution.

Key concepts:
- "As of" date: When the analysis is run (reference point)
- Event: A distinct period of snowfall separated by gaps
- Lead time: Days from "as of" date to event start
"""

import re
import json
import hashlib
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
import sqlite3

from database import DB_PATH


class EventConfidence(Enum):
    """Confidence levels for event occurrence and amounts."""
    VERY_HIGH = "Very High"   # 0-36 hours
    HIGH = "High"             # 36-60 hours
    MODERATE = "Moderate"     # 60-96 hours
    LOW = "Low"               # 96-144 hours (4-6 days)
    VERY_LOW = "Very Low"     # 144+ hours (6+ days)


@dataclass
class SnowPeriod:
    """A single period of snowfall within an event."""
    date: date
    start_hour: int  # 0-23
    end_hour: int    # 0-23
    snow_inches: float
    source: str      # 'gridpoint', 'forecast_text', 'wpc'


@dataclass
class SnowEvent:
    """A distinct snow event (one or more consecutive snowy periods)."""
    event_id: str                    # Unique ID for tracking
    start_date: date
    end_date: date
    start_datetime: datetime
    end_datetime: datetime

    # Snow amounts from different sources
    snow_total_low: float            # Low estimate
    snow_total_high: float           # High estimate
    snow_total_best: float           # Best estimate

    # Breakdown by date
    snow_by_date: Dict[str, float] = field(default_factory=dict)

    # Event characteristics
    duration_hours: int = 0
    peak_rate_inches_per_hour: float = 0.0
    has_ice: bool = False
    has_wind: bool = False

    # Sources used
    sources: List[str] = field(default_factory=list)
    source_details: Dict[str, Any] = field(default_factory=dict)

    # Confidence
    confidence: EventConfidence = EventConfidence.MODERATE
    lead_time_hours: int = 0

    # Tracking
    first_detected: str = ""         # ISO datetime when first seen
    detection_count: int = 0         # How many times we've detected this

    # Raw periods
    periods: List[SnowPeriod] = field(default_factory=list)

    # Forecast text
    key_details: str = ""


def generate_event_id(start_date: date, end_date: date, location_id: int) -> str:
    """
    Generate a stable ID for an event based on dates and location.
    This allows tracking the same event across multiple fetches.
    """
    key = f"{location_id}-{start_date.isoformat()}-{end_date.isoformat()}"
    return hashlib.md5(key.encode()).hexdigest()[:12]


def find_matching_event_id(
    location_id: int,
    start_date: date,
    end_date: date,
    days_back: int = 7
) -> Optional[str]:
    """
    Find an existing event that overlaps with the given date range.

    This allows tracking the same storm even if its dates shift slightly
    between forecast updates. Returns the existing event_id if found.

    Matching criteria:
    - Events must overlap by at least 1 day
    - Only considers events detected within the last N days
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cutoff = (datetime.now() - timedelta(days=days_back)).isoformat()

    # Get recent events for this location
    cursor.execute("""
        SELECT DISTINCT event_id, start_date, end_date
        FROM detected_events
        WHERE location_id = ? AND detected_at >= ?
        ORDER BY detected_at DESC
    """, (location_id, cutoff))

    rows = cursor.fetchall()
    conn.close()

    # Check each for overlap
    for row in rows:
        existing_start = date.fromisoformat(row['start_date'])
        existing_end = date.fromisoformat(row['end_date'])

        # Calculate overlap
        overlap_start = max(start_date, existing_start)
        overlap_end = min(end_date, existing_end)
        overlap_days = (overlap_end - overlap_start).days + 1

        if overlap_days >= 1:
            # Found overlapping event - return its ID
            return row['event_id']

    return None


def parse_nws_datetime(time_str: str) -> Optional[datetime]:
    """Parse NWS API datetime format."""
    if not time_str:
        return None

    # Handle format: 2026-01-25T06:00:00-05:00
    # Or: 2026-01-25T06:00:00+00:00/PT6H
    try:
        # Remove duration suffix if present
        if '/' in time_str:
            time_str = time_str.split('/')[0]

        # Handle timezone
        if '+' in time_str or time_str.count('-') > 2:
            # Has timezone info
            if '+' in time_str:
                time_str = time_str.rsplit('+', 1)[0]
            else:
                # Handle negative timezone like -05:00
                parts = time_str.rsplit('-', 1)
                if ':' in parts[-1] and len(parts[-1]) == 5:
                    time_str = parts[0]

        return datetime.fromisoformat(time_str)
    except (ValueError, IndexError):
        return None


def extract_date_from_period_name(period_name: str, as_of_date: date) -> Optional[date]:
    """
    Extract actual date from NWS period names like "Saturday", "Saturday Night".

    Args:
        period_name: e.g., "Saturday", "Saturday Night", "This Afternoon"
        as_of_date: Reference date for calculating actual dates
    """
    name = period_name.lower().strip()

    # Map day names to weekday numbers (Monday=0)
    day_map = {
        'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
        'friday': 4, 'saturday': 5, 'sunday': 6
    }

    # Handle "today", "tonight", "this afternoon"
    if any(x in name for x in ['today', 'tonight', 'this afternoon', 'this morning']):
        return as_of_date

    # Handle day names
    for day_name, weekday in day_map.items():
        if day_name in name:
            # Find next occurrence of this weekday
            current_weekday = as_of_date.weekday()
            days_ahead = weekday - current_weekday
            if days_ahead <= 0:  # Target day already passed this week
                days_ahead += 7
            return as_of_date + timedelta(days=days_ahead)

    return None


def get_confidence_for_lead_time(hours: int) -> EventConfidence:
    """Determine confidence based on lead time in hours."""
    if hours <= 36:
        return EventConfidence.VERY_HIGH
    elif hours <= 60:
        return EventConfidence.HIGH
    elif hours <= 96:
        return EventConfidence.MODERATE
    elif hours <= 144:
        return EventConfidence.LOW
    else:
        return EventConfidence.VERY_LOW


def extract_snow_from_gridpoint_by_date(
    gridpoint_data: Dict,
    as_of_datetime: datetime
) -> Dict[date, Dict[str, Any]]:
    """
    Extract snow amounts from gridpoint data, organized by date.

    Returns dict keyed by date with 'total', 'periods' list.
    """
    snow_by_date = {}

    try:
        properties = gridpoint_data.get('properties', {})
        snow_amount = properties.get('snowfallAmount', {})
        values = snow_amount.get('values', [])

        for entry in values:
            valid_time = entry.get('validTime', '')
            value = entry.get('value')

            if value is None or value <= 0:
                continue

            dt = parse_nws_datetime(valid_time)
            if not dt:
                continue

            # Convert mm to inches
            inches = value / 25.4
            event_date = dt.date()

            if event_date not in snow_by_date:
                snow_by_date[event_date] = {
                    'total': 0,
                    'periods': [],
                    'min_hour': 24,
                    'max_hour': 0
                }

            snow_by_date[event_date]['total'] += inches
            snow_by_date[event_date]['periods'].append({
                'datetime': dt,
                'amount': inches,
                'hour': dt.hour
            })
            snow_by_date[event_date]['min_hour'] = min(
                snow_by_date[event_date]['min_hour'], dt.hour
            )
            snow_by_date[event_date]['max_hour'] = max(
                snow_by_date[event_date]['max_hour'], dt.hour
            )

    except (KeyError, TypeError, AttributeError):
        pass

    return snow_by_date


def extract_snow_from_forecast_text(
    forecast_data: Dict,
    as_of_date: date
) -> Dict[date, Dict[str, Any]]:
    """
    Extract snow mentions and amounts from forecast text periods.
    """
    snow_by_date = {}

    try:
        periods = forecast_data.get('forecast', {}).get('properties', {}).get('periods', [])

        for period in periods:
            name = period.get('name', '')
            detailed = period.get('detailedForecast', '')
            short = period.get('shortForecast', '')

            # Skip if no snow mentioned
            if not any(w in detailed.lower() for w in ['snow', 'flurries', 'wintry']):
                continue

            # Get date for this period
            # First try startTime from API
            start_time = period.get('startTime', '')
            dt = parse_nws_datetime(start_time)

            if dt:
                period_date = dt.date()
            else:
                # Fall back to parsing period name
                period_date = extract_date_from_period_name(name, as_of_date)

            if not period_date:
                continue

            # Extract snow amounts from text
            low, high = extract_snow_amounts_from_text(detailed)

            if period_date not in snow_by_date:
                snow_by_date[period_date] = {
                    'total': 0,
                    'low': 0,
                    'high': 0,
                    'text': [],
                    'has_ice': False,
                    'has_wind': False
                }

            if low and high:
                snow_by_date[period_date]['low'] = max(snow_by_date[period_date]['low'], low)
                snow_by_date[period_date]['high'] = max(snow_by_date[period_date]['high'], high)
                snow_by_date[period_date]['total'] = max(
                    snow_by_date[period_date]['total'],
                    (low + high) / 2
                )

            snow_by_date[period_date]['text'].append({
                'period': name,
                'forecast': detailed
            })

            # Check for ice/wind
            if any(w in detailed.lower() for w in ['ice', 'freezing rain', 'sleet']):
                snow_by_date[period_date]['has_ice'] = True
            if any(w in detailed.lower() for w in ['wind', 'gusts', 'blustery', 'blowing']):
                snow_by_date[period_date]['has_wind'] = True

    except (KeyError, TypeError, AttributeError):
        pass

    return snow_by_date


def extract_snow_amounts_from_text(text: str) -> Tuple[Optional[float], Optional[float]]:
    """Extract snow amounts from forecast text. Returns (low, high)."""
    if not text:
        return None, None

    text = text.lower()

    patterns = [
        # "6 to 10 inches"
        r'(\d+(?:\.\d+)?)\s*(?:to|-)\s*(\d+(?:\.\d+)?)\s*inch',
        # "around 8 inches"
        r'(?:around|about|near)\s*(\d+(?:\.\d+)?)\s*inch',
        # "8 inches"
        r'(\d+(?:\.\d+)?)\s*inch',
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            groups = match.groups()
            if len(groups) == 2:
                return float(groups[0]), float(groups[1])
            elif len(groups) == 1:
                amt = float(groups[0])
                return amt * 0.8, amt * 1.2  # +/- 20% for single values

    # Check for qualitative descriptions
    if 'heavy snow' in text or 'significant snow' in text:
        return 6.0, 12.0
    elif 'moderate snow' in text:
        return 3.0, 6.0
    elif 'light snow' in text or 'flurries' in text:
        return 0.5, 2.0
    elif 'snow' in text:
        return 1.0, 4.0

    return None, None


def identify_snow_events(
    forecast_data: Dict,
    as_of_datetime: datetime,
    location_id: int,
    min_snow_threshold: float = 0.5
) -> List[SnowEvent]:
    """
    Identify distinct snow events from forecast data.

    Events are separated by gaps of 12+ hours with no snow.
    """
    as_of_date = as_of_datetime.date()

    # Get snow data from multiple sources
    gridpoint_snow = extract_snow_from_gridpoint_by_date(
        forecast_data.get('gridpoint', {}),
        as_of_datetime
    )

    text_snow = extract_snow_from_forecast_text(forecast_data, as_of_date)

    # Merge sources, preferring gridpoint for amounts but text for context
    all_dates = set(gridpoint_snow.keys()) | set(text_snow.keys())

    # Build daily snow data
    daily_data = {}
    for d in sorted(all_dates):
        if d < as_of_date:
            continue  # Skip past dates

        gp = gridpoint_snow.get(d, {})
        tx = text_snow.get(d, {})

        # Use gridpoint total if available, otherwise text
        snow_total = gp.get('total', 0) or tx.get('total', 0)
        snow_low = tx.get('low', snow_total * 0.7)
        snow_high = tx.get('high', snow_total * 1.3)

        if snow_total >= min_snow_threshold or snow_low:
            daily_data[d] = {
                'total': snow_total,
                'low': snow_low or snow_total * 0.7,
                'high': snow_high or snow_total * 1.3,
                'gridpoint': gp,
                'text': tx,
                'has_ice': tx.get('has_ice', False),
                'has_wind': tx.get('has_wind', False),
                'sources': []
            }
            if gp:
                daily_data[d]['sources'].append('gridpoint')
            if tx:
                daily_data[d]['sources'].append('forecast_text')

    # Group consecutive days into events
    events = []
    current_event_dates = []

    sorted_dates = sorted(daily_data.keys())
    for i, d in enumerate(sorted_dates):
        if not current_event_dates:
            current_event_dates = [d]
        else:
            # Check if this date is consecutive
            prev_date = current_event_dates[-1]
            if (d - prev_date).days <= 1:
                current_event_dates.append(d)
            else:
                # Gap found - close current event and start new one
                event = create_event_from_dates(
                    current_event_dates, daily_data, as_of_datetime, location_id
                )
                if event:
                    events.append(event)
                current_event_dates = [d]

    # Don't forget the last event
    if current_event_dates:
        event = create_event_from_dates(
            current_event_dates, daily_data, as_of_datetime, location_id
        )
        if event:
            events.append(event)

    return events


def create_event_from_dates(
    event_dates: List[date],
    daily_data: Dict[date, Dict],
    as_of_datetime: datetime,
    location_id: int
) -> Optional[SnowEvent]:
    """Create a SnowEvent from a list of consecutive dates."""
    if not event_dates:
        return None

    start_date = min(event_dates)
    end_date = max(event_dates)

    # Calculate totals
    snow_total = sum(daily_data[d]['total'] for d in event_dates)
    snow_low = sum(daily_data[d]['low'] for d in event_dates)
    snow_high = sum(daily_data[d]['high'] for d in event_dates)

    # Skip trivial events
    if snow_total < 0.5 and snow_high < 1.0:
        return None

    # Build snow by date dict
    snow_by_date = {d.isoformat(): daily_data[d]['total'] for d in event_dates}

    # Get characteristics
    has_ice = any(daily_data[d].get('has_ice', False) for d in event_dates)
    has_wind = any(daily_data[d].get('has_wind', False) for d in event_dates)

    # Collect sources
    all_sources = set()
    for d in event_dates:
        all_sources.update(daily_data[d].get('sources', []))

    # Calculate lead time
    start_datetime = datetime.combine(start_date, datetime.min.time())
    lead_time_hours = int((start_datetime - as_of_datetime).total_seconds() / 3600)
    lead_time_hours = max(0, lead_time_hours)

    # Get confidence
    confidence = get_confidence_for_lead_time(lead_time_hours)

    # Estimate duration
    duration_hours = (len(event_dates)) * 18  # Assume 18 hours of snow per day avg

    # Get key details from text
    key_details = ""
    for d in event_dates:
        texts = daily_data[d].get('text', {}).get('text', [])
        for t in texts:
            if len(t.get('forecast', '')) > len(key_details):
                key_details = t.get('forecast', '')

    # Find existing event ID if this storm was already detected (with possibly different dates)
    # This allows tracking even when storm dates shift between forecasts
    event_id = find_matching_event_id(location_id, start_date, end_date)
    if not event_id:
        # New event - generate fresh ID
        event_id = generate_event_id(start_date, end_date, location_id)

    return SnowEvent(
        event_id=event_id,
        start_date=start_date,
        end_date=end_date,
        start_datetime=start_datetime,
        end_datetime=datetime.combine(end_date, datetime.max.time().replace(microsecond=0)),
        snow_total_low=round(snow_low, 1),
        snow_total_high=round(snow_high, 1),
        snow_total_best=round(snow_total, 1),
        snow_by_date=snow_by_date,
        duration_hours=duration_hours,
        has_ice=has_ice,
        has_wind=has_wind,
        sources=list(all_sources),
        confidence=confidence,
        lead_time_hours=lead_time_hours,
        first_detected=as_of_datetime.isoformat(),
        detection_count=1,
        key_details=key_details[:500] if key_details else ""
    )


def format_event_date_range(event: SnowEvent, as_of_date: date) -> str:
    """Format event date range in human-readable form."""
    start = event.start_date
    end = event.end_date

    # Day names
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

    start_day = days[start.weekday()]
    end_day = days[end.weekday()]

    # Calculate days from now
    days_until = (start - as_of_date).days

    if start == end:
        if days_until == 0:
            return f"Today ({start.strftime('%b %d')})"
        elif days_until == 1:
            return f"Tomorrow ({start.strftime('%b %d')})"
        else:
            return f"{start_day} ({start.strftime('%b %d')})"
    else:
        if days_until == 0:
            return f"Today through {end_day} ({start.strftime('%b %d')} - {end.strftime('%b %d')})"
        elif days_until == 1:
            return f"Tomorrow through {end_day} ({start.strftime('%b %d')} - {end.strftime('%b %d')})"
        else:
            return f"{start_day} through {end_day} ({start.strftime('%b %d')} - {end.strftime('%b %d')})"


def get_event_headline(event: SnowEvent) -> str:
    """Generate a headline for the event."""
    # Categorize by amount
    best = event.snow_total_best

    if best >= 18:
        severity = "Major Winter Storm"
    elif best >= 12:
        severity = "Significant Snowstorm"
    elif best >= 6:
        severity = "Moderate Snowstorm"
    elif best >= 3:
        severity = "Light to Moderate Snow"
    else:
        severity = "Light Snow"

    if event.has_ice:
        severity += " with Ice"

    return severity


def save_detected_events(location_id: int, events: List[SnowEvent], as_of: datetime):
    """Save detected events to database for tracking over time."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create events table if not exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS detected_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location_id INTEGER NOT NULL,
            event_id TEXT NOT NULL,
            detected_at TIMESTAMP NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            snow_low REAL,
            snow_high REAL,
            snow_best REAL,
            snow_by_date TEXT,
            confidence TEXT,
            lead_time_hours INTEGER,
            has_ice INTEGER,
            has_wind INTEGER,
            sources TEXT,
            key_details TEXT,
            FOREIGN KEY (location_id) REFERENCES locations (id)
        )
    """)

    # Insert events
    for event in events:
        cursor.execute("""
            INSERT INTO detected_events (
                location_id, event_id, detected_at, start_date, end_date,
                snow_low, snow_high, snow_best, snow_by_date, confidence,
                lead_time_hours, has_ice, has_wind, sources, key_details
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            location_id,
            event.event_id,
            as_of.isoformat(),
            event.start_date.isoformat(),
            event.end_date.isoformat(),
            event.snow_total_low,
            event.snow_total_high,
            event.snow_total_best,
            json.dumps(event.snow_by_date),
            event.confidence.value,
            event.lead_time_hours,
            1 if event.has_ice else 0,
            1 if event.has_wind else 0,
            json.dumps(event.sources),
            event.key_details
        ))

    conn.commit()
    conn.close()


def get_event_history(location_id: int, event_id: str, days_back: int = 7) -> List[Dict]:
    """Get historical detections of an event to show trend."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cutoff = (datetime.now() - timedelta(days=days_back)).isoformat()

    cursor.execute("""
        SELECT * FROM detected_events
        WHERE location_id = ? AND event_id = ? AND detected_at >= ?
        ORDER BY detected_at ASC
    """, (location_id, event_id, cutoff))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_event_trend(history: List[Dict]) -> Dict[str, Any]:
    """Analyze how an event's forecast has changed over time."""
    if len(history) < 2:
        return {'direction': 'insufficient_data', 'message': 'Need more data points'}

    first = history[0]
    latest = history[-1]

    first_amt = first['snow_best']
    latest_amt = latest['snow_best']
    change = latest_amt - first_amt

    if change > 1:
        direction = 'increasing'
        msg = f"Snow forecast has INCREASED by {change:.1f}\" since first detected"
    elif change < -1:
        direction = 'decreasing'
        msg = f"Snow forecast has DECREASED by {abs(change):.1f}\" since first detected"
    else:
        direction = 'steady'
        msg = "Forecast has remained relatively steady"

    return {
        'direction': direction,
        'message': msg,
        'first_amount': first_amt,
        'latest_amount': latest_amt,
        'change': change,
        'num_detections': len(history),
        'history': [
            {
                'time': h['detected_at'],
                'snow': h['snow_best'],
                'confidence': h['confidence']
            }
            for h in history
        ]
    }
