import sqlite3
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from pathlib import Path

# Store database in the same directory as this file (project directory)
DB_PATH = Path(__file__).parent / "weather_tracker.db"

def init_db():
    """Initialize the SQLite database with required tables."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Locations table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            zip_code TEXT UNIQUE NOT NULL,
            lat REAL NOT NULL,
            lon REAL NOT NULL,
            grid_x INTEGER NOT NULL,
            grid_y INTEGER NOT NULL,
            forecast_office TEXT NOT NULL,
            city TEXT,
            state TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Forecasts table - stores each forecast snapshot
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS forecasts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location_id INTEGER NOT NULL,
            fetched_at TIMESTAMP NOT NULL,
            forecast_data TEXT NOT NULL,
            FOREIGN KEY (location_id) REFERENCES locations (id)
        )
    """)

    # Discussions table - stores Area Forecast Discussions
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS discussions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location_id INTEGER NOT NULL,
            fetched_at TIMESTAMP NOT NULL,
            issued_at TIMESTAMP,
            discussion_text TEXT NOT NULL,
            FOREIGN KEY (location_id) REFERENCES locations (id)
        )
    """)

    # User observations table - stores manual snow/weather measurements
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location_id INTEGER NOT NULL,
            observed_at TIMESTAMP NOT NULL,
            snow_depth_inches REAL,
            new_snow_inches REAL,
            temperature_f REAL,
            conditions_notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (location_id) REFERENCES locations (id)
        )
    """)

    # Alert history table - tracks sent notifications
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alert_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location_id INTEGER NOT NULL,
            alert_type TEXT NOT NULL,
            alert_summary TEXT NOT NULL,
            alert_details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (location_id) REFERENCES locations (id)
        )
    """)

    # Detected events table - tracks snow events over time
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

    conn.commit()
    conn.close()

def add_location(zip_code: str, lat: float, lon: float, grid_x: int, grid_y: int,
                 forecast_office: str, city: str = None, state: str = None) -> int:
    """Add or update a location in the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR REPLACE INTO locations
        (zip_code, lat, lon, grid_x, grid_y, forecast_office, city, state)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (zip_code, lat, lon, grid_x, grid_y, forecast_office, city, state))

    location_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return location_id

def get_location_by_zip(zip_code: str) -> Optional[Dict[str, Any]]:
    """Get location data by zip code."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM locations WHERE zip_code = ?", (zip_code,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return dict(row)
    return None

def save_forecast(location_id: int, forecast_data: Dict[str, Any]) -> int:
    """Save a forecast snapshot."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO forecasts (location_id, fetched_at, forecast_data)
        VALUES (?, ?, ?)
    """, (location_id, datetime.now().isoformat(), json.dumps(forecast_data)))

    forecast_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return forecast_id

def save_discussion(location_id: int, discussion_text: str, issued_at: Optional[str] = None) -> int:
    """Save an Area Forecast Discussion."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO discussions (location_id, fetched_at, issued_at, discussion_text)
        VALUES (?, ?, ?, ?)
    """, (location_id, datetime.now().isoformat(), issued_at, discussion_text))

    discussion_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return discussion_id

def get_forecasts_for_location(location_id: int, days_back: int = 30) -> List[Dict[str, Any]]:
    """Get all forecasts for a location within the specified time window."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cutoff_date = datetime.now() - timedelta(days=days_back)

    cursor.execute("""
        SELECT * FROM forecasts
        WHERE location_id = ? AND fetched_at >= ?
        ORDER BY fetched_at DESC
    """, (location_id, cutoff_date.isoformat()))

    rows = cursor.fetchall()
    conn.close()

    forecasts = []
    for row in rows:
        forecast = dict(row)
        forecast['forecast_data'] = json.loads(forecast['forecast_data'])
        forecasts.append(forecast)

    return forecasts

def get_discussions_for_location(location_id: int, days_back: int = 30) -> List[Dict[str, Any]]:
    """Get all discussions for a location within the specified time window."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cutoff_date = datetime.now() - timedelta(days=days_back)

    cursor.execute("""
        SELECT * FROM discussions
        WHERE location_id = ? AND fetched_at >= ?
        ORDER BY fetched_at DESC
    """, (location_id, cutoff_date.isoformat()))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]

def cleanup_old_data(days_to_keep: int = 60):
    """Delete forecast, discussion, and event tracking data older than specified days."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cutoff_date = datetime.now() - timedelta(days=days_to_keep)

    cursor.execute("DELETE FROM forecasts WHERE fetched_at < ?", (cutoff_date.isoformat(),))
    cursor.execute("DELETE FROM discussions WHERE fetched_at < ?", (cutoff_date.isoformat(),))
    cursor.execute("DELETE FROM detected_events WHERE detected_at < ?", (cutoff_date.isoformat(),))

    deleted_forecasts = cursor.rowcount
    conn.commit()
    conn.close()

    return deleted_forecasts


# ============================================================================
# User Observations Functions
# ============================================================================

def save_observation(
    location_id: int,
    observed_at: str,
    snow_depth_inches: Optional[float] = None,
    new_snow_inches: Optional[float] = None,
    temperature_f: Optional[float] = None,
    conditions_notes: Optional[str] = None
) -> int:
    """Save a user observation/measurement."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO user_observations
        (location_id, observed_at, snow_depth_inches, new_snow_inches, temperature_f, conditions_notes)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (location_id, observed_at, snow_depth_inches, new_snow_inches, temperature_f, conditions_notes))

    observation_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return observation_id


def get_observations_for_location(location_id: int, days_back: int = 30) -> List[Dict[str, Any]]:
    """Get all observations for a location within the specified time window."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cutoff_date = datetime.now() - timedelta(days=days_back)

    cursor.execute("""
        SELECT * FROM user_observations
        WHERE location_id = ? AND observed_at >= ?
        ORDER BY observed_at DESC
    """, (location_id, cutoff_date.isoformat()))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def delete_observation(observation_id: int) -> bool:
    """Delete a user observation."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("DELETE FROM user_observations WHERE id = ?", (observation_id,))
    deleted = cursor.rowcount > 0

    conn.commit()
    conn.close()

    return deleted


# ============================================================================
# Alert History Functions
# ============================================================================

def save_alert(
    location_id: int,
    alert_type: str,
    alert_summary: str,
    alert_details: Optional[str] = None
) -> int:
    """Save an alert to history."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO alert_history (location_id, alert_type, alert_summary, alert_details)
        VALUES (?, ?, ?, ?)
    """, (location_id, alert_type, alert_summary, alert_details))

    alert_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return alert_id


def get_alerts_for_location(location_id: int, days_back: int = 7) -> List[Dict[str, Any]]:
    """Get alert history for a location."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cutoff_date = datetime.now() - timedelta(days=days_back)

    cursor.execute("""
        SELECT * FROM alert_history
        WHERE location_id = ? AND created_at >= ?
        ORDER BY created_at DESC
    """, (location_id, cutoff_date.isoformat()))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_all_locations() -> List[Dict[str, Any]]:
    """Get all saved locations."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM locations ORDER BY city")
    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]
