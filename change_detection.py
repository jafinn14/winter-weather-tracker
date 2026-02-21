"""
Change detection module for comparing weather forecasts.
Identifies significant changes between forecast snapshots.
"""

import re
from typing import Dict, Any, List, Optional
from datetime import datetime

# Thresholds for significant changes
SNOW_CHANGE_THRESHOLD = 2.0  # inches
TEMP_CHANGE_THRESHOLD = 5    # degrees F
TIMING_CHANGE_THRESHOLD = 6  # hours
PRECIP_PROB_CHANGE_THRESHOLD = 30  # percentage points


def extract_snow_amount(text: str) -> Optional[float]:
    """Extract snow amount from forecast text. Returns midpoint of range if given."""
    if not text:
        return None

    # Pattern: "2 to 4 inches" or "3 inches" or "2-4 inches"
    patterns = [
        r'(\d+(?:\.\d+)?)\s*(?:to|-)\s*(\d+(?:\.\d+)?)\s*(?:inch|")',
        r'(\d+(?:\.\d+)?)\s*(?:inch|")',
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            groups = match.groups()
            if len(groups) == 2 and groups[1]:
                # Range: return midpoint
                return (float(groups[0]) + float(groups[1])) / 2
            else:
                return float(groups[0])

    return None


def extract_snow_from_gridpoint(gridpoint_data: dict) -> Dict[str, float]:
    """Extract snow accumulation data from gridpoint response."""
    snow_totals = {}

    try:
        properties = gridpoint_data.get('properties', {})
        snow_amount = properties.get('snowfallAmount', {})
        values = snow_amount.get('values', [])

        for entry in values[:24]:  # First 24 periods (roughly 3 days)
            valid_time = entry.get('validTime', '')
            value = entry.get('value')

            if value is not None and value > 0:
                # Convert mm to inches
                inches = value / 25.4
                # Extract date from validTime
                date_match = re.match(r'(\d{4}-\d{2}-\d{2})', valid_time)
                if date_match:
                    date_key = date_match.group(1)
                    snow_totals[date_key] = snow_totals.get(date_key, 0) + inches

    except (KeyError, TypeError):
        pass

    return snow_totals


def get_first_period_temp(forecast_data: dict) -> Optional[int]:
    """Get temperature from the first forecast period."""
    try:
        periods = forecast_data.get('forecast', {}).get('properties', {}).get('periods', [])
        if periods:
            return periods[0].get('temperature')
    except (KeyError, TypeError):
        pass
    return None


def get_first_period_precip_prob(forecast_data: dict) -> Optional[int]:
    """Get precipitation probability from the first forecast period."""
    try:
        periods = forecast_data.get('forecast', {}).get('properties', {}).get('periods', [])
        if periods:
            pop = periods[0].get('probabilityOfPrecipitation', {})
            return pop.get('value')
    except (KeyError, TypeError):
        pass
    return None


def get_first_period_text(forecast_data: dict) -> str:
    """Get detailed forecast text from the first period."""
    try:
        periods = forecast_data.get('forecast', {}).get('properties', {}).get('periods', [])
        if periods:
            return periods[0].get('detailedForecast', '')
    except (KeyError, TypeError):
        pass
    return ''


def has_winter_keywords(text: str) -> bool:
    """Check if text contains winter weather keywords."""
    keywords = ['snow', 'ice', 'freezing', 'sleet', 'wintry', 'blizzard', 'frost']
    text_lower = text.lower()
    return any(kw in text_lower for kw in keywords)


def detect_changes(previous: dict, current: dict) -> List[Dict[str, Any]]:
    """
    Compare two forecast snapshots and identify significant changes.

    Args:
        previous: Earlier forecast snapshot (from database)
        current: More recent forecast snapshot (from database)

    Returns:
        List of change dictionaries with type, summary, and details
    """
    changes = []

    prev_data = previous.get('forecast_data', {})
    curr_data = current.get('forecast_data', {})

    # 1. Check temperature change
    prev_temp = get_first_period_temp(prev_data)
    curr_temp = get_first_period_temp(curr_data)

    if prev_temp is not None and curr_temp is not None:
        temp_diff = curr_temp - prev_temp
        if abs(temp_diff) >= TEMP_CHANGE_THRESHOLD:
            direction = "warmer" if temp_diff > 0 else "colder"
            changes.append({
                'type': 'temperature',
                'summary': f"Temperature forecast changed: {prev_temp}°F → {curr_temp}°F ({direction})",
                'previous_value': prev_temp,
                'current_value': curr_temp,
                'difference': temp_diff,
                'severity': 'medium' if abs(temp_diff) < 10 else 'high'
            })

    # 2. Check snow total change
    prev_gridpoint = prev_data.get('gridpoint', {})
    curr_gridpoint = curr_data.get('gridpoint', {})

    prev_snow = extract_snow_from_gridpoint(prev_gridpoint)
    curr_snow = extract_snow_from_gridpoint(curr_gridpoint)

    # Compare total snow over next few days
    prev_total = sum(prev_snow.values())
    curr_total = sum(curr_snow.values())
    snow_diff = curr_total - prev_total

    if abs(snow_diff) >= SNOW_CHANGE_THRESHOLD:
        direction = "increased" if snow_diff > 0 else "decreased"
        changes.append({
            'type': 'snow_total',
            'summary': f"Snow forecast {direction}: {prev_total:.1f}\" → {curr_total:.1f}\"",
            'previous_value': prev_total,
            'current_value': curr_total,
            'difference': snow_diff,
            'severity': 'high' if abs(snow_diff) >= 4 else 'medium'
        })

    # 3. Check precipitation probability change
    prev_prob = get_first_period_precip_prob(prev_data)
    curr_prob = get_first_period_precip_prob(curr_data)

    if prev_prob is not None and curr_prob is not None:
        prob_diff = curr_prob - prev_prob
        if abs(prob_diff) >= PRECIP_PROB_CHANGE_THRESHOLD:
            direction = "increased" if prob_diff > 0 else "decreased"
            changes.append({
                'type': 'precip_probability',
                'summary': f"Precipitation chance {direction}: {prev_prob}% → {curr_prob}%",
                'previous_value': prev_prob,
                'current_value': curr_prob,
                'difference': prob_diff,
                'severity': 'medium'
            })

    # 4. Check for new winter weather mentions
    prev_text = get_first_period_text(prev_data)
    curr_text = get_first_period_text(curr_data)

    prev_has_winter = has_winter_keywords(prev_text)
    curr_has_winter = has_winter_keywords(curr_text)

    if curr_has_winter and not prev_has_winter:
        changes.append({
            'type': 'winter_weather_added',
            'summary': "Winter weather now mentioned in forecast",
            'previous_value': prev_text[:100],
            'current_value': curr_text[:100],
            'severity': 'high'
        })
    elif prev_has_winter and not curr_has_winter:
        changes.append({
            'type': 'winter_weather_removed',
            'summary': "Winter weather no longer mentioned in forecast",
            'previous_value': prev_text[:100],
            'current_value': curr_text[:100],
            'severity': 'medium'
        })

    # 5. Extract and compare snow amounts from text
    prev_text_snow = extract_snow_amount(prev_text)
    curr_text_snow = extract_snow_amount(curr_text)

    if prev_text_snow is not None and curr_text_snow is not None:
        text_snow_diff = curr_text_snow - prev_text_snow
        if abs(text_snow_diff) >= SNOW_CHANGE_THRESHOLD:
            direction = "increased" if text_snow_diff > 0 else "decreased"
            changes.append({
                'type': 'snow_text',
                'summary': f"Forecast text snow amounts {direction}: {prev_text_snow:.1f}\" → {curr_text_snow:.1f}\"",
                'previous_value': prev_text_snow,
                'current_value': curr_text_snow,
                'difference': text_snow_diff,
                'severity': 'high' if abs(text_snow_diff) >= 4 else 'medium'
            })

    return changes


def format_changes(changes: List[Dict[str, Any]]) -> str:
    """Format a list of changes into a human-readable notification string."""
    if not changes:
        return "No significant changes detected."

    lines = []

    # Group by location if present
    locations = {}
    for change in changes:
        loc = change.get('location', {})
        loc_key = loc.get('zip_code', 'Unknown')
        loc_name = f"{loc.get('city', '')}, {loc.get('state', '')}" if loc else loc_key

        if loc_key not in locations:
            locations[loc_key] = {'name': loc_name, 'changes': []}
        locations[loc_key]['changes'].append(change)

    for loc_key, loc_data in locations.items():
        if len(locations) > 1:
            lines.append(f"\n{loc_data['name']}:")

        for change in loc_data['changes']:
            severity_icon = "🔴" if change.get('severity') == 'high' else "🟡"
            lines.append(f"{severity_icon} {change['summary']}")

    return "\n".join(lines)


def get_change_summary(changes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Get a summary of all changes for logging/display."""
    if not changes:
        return {'total': 0, 'high_severity': 0, 'types': []}

    return {
        'total': len(changes),
        'high_severity': sum(1 for c in changes if c.get('severity') == 'high'),
        'types': list(set(c['type'] for c in changes)),
        'changes': changes
    }
