"""
Storm Watch page — tracks how a specific storm's forecast evolves over time.

Shows every detected snapshot of a given event so you can watch the forecast
change fetch-by-fetch as the storm approaches.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sqlite3
import json
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional

from database import get_location_by_zip, DB_PATH


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_distinct_events(location_id: int, days_back: int = 14) -> List[Dict]:
    """Return one row per event_id — the most recent detection for each."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cutoff = (datetime.now() - timedelta(days=days_back)).isoformat()

    cursor.execute("""
        SELECT event_id, start_date, end_date,
               MAX(detected_at) AS last_detected,
               COUNT(*) AS detection_count,
               snow_best, snow_low, snow_high, confidence
        FROM detected_events
        WHERE location_id = ? AND detected_at >= ?
        GROUP BY event_id
        ORDER BY start_date ASC
    """, (location_id, cutoff))

    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_event_snapshots(location_id: int, event_id: str) -> List[Dict]:
    """Return every detection of one event, oldest first."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT detected_at, start_date, end_date,
               snow_low, snow_best, snow_high,
               confidence, lead_time_hours, key_details
        FROM detected_events
        WHERE location_id = ? AND event_id = ?
        ORDER BY detected_at ASC
    """, (location_id, event_id))

    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_forecast_texts_for_event(location_id: int, start_date: str, end_date: str) -> List[Dict]:
    """
    Pull the forecast period text from stored raw forecast blobs that overlap
    with the event's date range, to show how forecast language has changed.
    Returns a list of {fetched_at, periods_text} dicts.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get all forecasts for this location from the past 14 days
    cutoff = (datetime.now() - timedelta(days=14)).isoformat()
    cursor.execute("""
        SELECT fetched_at, forecast_data
        FROM forecasts
        WHERE location_id = ? AND fetched_at >= ?
        ORDER BY fetched_at ASC
    """, (location_id, cutoff))

    rows = cursor.fetchall()
    conn.close()

    event_start = date.fromisoformat(start_date)
    event_end = date.fromisoformat(end_date)

    results = []
    for row in rows:
        try:
            forecast_data = json.loads(row['forecast_data'])
            periods = forecast_data.get('forecast', {}).get('properties', {}).get('periods', [])

            relevant_texts = []
            for p in periods:
                start_time = p.get('startTime', '')
                if not start_time:
                    continue
                try:
                    period_date = date.fromisoformat(start_time[:10])
                except ValueError:
                    continue
                # Include periods that overlap with or are just before the event
                if event_start - timedelta(days=1) <= period_date <= event_end + timedelta(days=1):
                    detailed = p.get('detailedForecast', '')
                    short = p.get('shortForecast', '')
                    if any(w in detailed.lower() for w in ['snow', 'wintry', 'ice', 'sleet', 'flurr']):
                        relevant_texts.append(f"**{p.get('name', '')}:** {detailed}")

            if relevant_texts:
                results.append({
                    'fetched_at': row['fetched_at'],
                    'texts': relevant_texts
                })
        except (json.JSONDecodeError, KeyError, TypeError):
            continue

    return results


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def format_event_label(event: Dict) -> str:
    start = date.fromisoformat(event['start_date'])
    end = date.fromisoformat(event['end_date'])
    days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    start_day = days[start.weekday()]
    end_day = days[end.weekday()]
    if start == end:
        label = f"{start_day} {start.strftime('%b %d')}"
    else:
        label = f"{start_day}–{end_day} {start.strftime('%b %d')}–{end.strftime('%b %d')}"
    return f"{label}  ({event['snow_best']:.1f}\" best est. | {event['detection_count']} snapshots)"


def confidence_color(conf: str) -> str:
    return {
        'Very High': '🟢',
        'High': '🟢',
        'Moderate': '🟡',
        'Low': '🟠',
        'Very Low': '🔴',
    }.get(conf, '⚪')


# ---------------------------------------------------------------------------
# Main page
# ---------------------------------------------------------------------------

def show():
    st.title("Storm Watch")
    st.caption("Track how a specific storm's forecast changes over time, fetch by fetch.")

    if 'current_zip' not in st.session_state:
        st.warning("Set up a location on the **Setup & Fetch Data** page first.")
        return

    location = get_location_by_zip(st.session_state.current_zip)
    if not location:
        st.warning("Location not found. Go to Setup & Fetch Data.")
        return

    st.markdown(f"**{location['city']}, {location['state']}**")

    # --- Event picker ---
    events = get_distinct_events(location['id'], days_back=14)

    if not events:
        st.info("No storm events detected yet. Auto-fetch needs to run at least once.")
        return

    event_labels = [format_event_label(e) for e in events]
    selected_idx = st.selectbox(
        "Select event to watch",
        range(len(events)),
        format_func=lambda i: event_labels[i]
    )

    event = events[selected_idx]
    event_id = event['event_id']
    start_date = event['start_date']
    end_date = event['end_date']

    st.markdown("---")

    # --- Snapshot history ---
    snapshots = get_event_snapshots(location['id'], event_id)

    if len(snapshots) < 2:
        st.info(f"Only {len(snapshots)} snapshot(s) so far. Each hourly fetch adds a data point. Check back soon.")
        if snapshots:
            s = snapshots[0]
            st.metric("Current forecast", f"{s['snow_low']:.0f}–{s['snow_high']:.0f}\"",
                      help=f"Best estimate: {s['snow_best']:.1f}\"")
        return

    # Header metrics
    first = snapshots[0]
    latest = snapshots[-1]
    change = latest['snow_best'] - first['snow_best']
    n = len(snapshots)
    first_time = first['detected_at'][:16].replace('T', ' ')
    latest_time = latest['detected_at'][:16].replace('T', ' ')

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("First forecast", f"{first['snow_best']:.1f}\"",
                help=f"First seen {first_time}")
    col2.metric("Latest forecast", f"{latest['snow_best']:.1f}\"",
                help=f"As of {latest_time}")
    col3.metric("Change", f"{change:+.1f}\"",
                delta=f"{change:+.1f}\"" if change != 0 else None)
    col4.metric("Snapshots", str(n),
                help=f"Since {first_time}")

    # Trend message
    if change > 1.0:
        st.warning(f"📈 Forecast trending **up** {change:+.1f}\" since first detection")
    elif change < -1.0:
        st.success(f"📉 Forecast trending **down** {change:+.1f}\" since first detection")
    else:
        st.info("➡️ Forecast has been relatively **steady**")

    # --- Evolution chart ---
    st.markdown("### Forecast Evolution")

    df = pd.DataFrame(snapshots)
    df['detected_at'] = pd.to_datetime(df['detected_at'])
    df['time_label'] = df['detected_at'].dt.strftime('%m/%d %H:%M')

    fig = go.Figure()

    # Shaded uncertainty band
    fig.add_trace(go.Scatter(
        x=pd.concat([df['time_label'], df['time_label'].iloc[::-1]]).tolist(),
        y=pd.concat([df['snow_high'], df['snow_low'].iloc[::-1]]).tolist(),
        fill='toself',
        fillcolor='rgba(100,149,237,0.15)',
        line=dict(color='rgba(255,255,255,0)'),
        name='Forecast range',
        hoverinfo='skip'
    ))

    # Best estimate line
    fig.add_trace(go.Scatter(
        x=df['time_label'],
        y=df['snow_best'],
        mode='lines+markers',
        name='Best estimate',
        line=dict(color='royalblue', width=3),
        marker=dict(size=8),
        hovertemplate='%{x}<br>Best: %{y:.1f}"<extra></extra>'
    ))

    fig.update_layout(
        xaxis_title='Fetch time',
        yaxis_title='Snow (inches)',
        height=350,
        margin=dict(l=20, r=20, t=20, b=20),
        legend=dict(orientation='h', yanchor='bottom', y=1.0, xanchor='right', x=1)
    )

    st.plotly_chart(fig, use_container_width=True)

    # --- Snapshot table ---
    st.markdown("### All Snapshots")

    table_rows = []
    for i, s in enumerate(reversed(snapshots)):  # newest first
        dt = datetime.fromisoformat(s['detected_at'])
        lead_h = s.get('lead_time_hours', 0)
        lead_label = f"{lead_h // 24}d {lead_h % 24}h" if lead_h else "—"
        conf = s.get('confidence', '')
        table_rows.append({
            'Fetched': dt.strftime('%a %m/%d %H:%M'),
            'Snow low': f"{s['snow_low']:.1f}\"",
            'Best est.': f"{s['snow_best']:.1f}\"",
            'Snow high': f"{s['snow_high']:.1f}\"",
            'Lead time': lead_label,
            'Confidence': f"{confidence_color(conf)} {conf}",
        })

    st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)

    # --- Forecast language evolution ---
    st.markdown("### How the Forecast Text Has Changed")
    st.caption("NWS forecast language for periods overlapping this storm, from stored snapshots.")

    text_history = get_forecast_texts_for_event(location['id'], start_date, end_date)

    if not text_history:
        st.info("No forecast text history found for this event's date range.")
    else:
        # Show last 5 snapshots that had relevant text, newest first
        for entry in reversed(text_history[-5:]):
            fetch_dt = datetime.fromisoformat(entry['fetched_at'])
            with st.expander(f"Fetched {fetch_dt.strftime('%a %b %d at %H:%M')}"):
                for line in entry['texts']:
                    st.markdown(line)
                    st.markdown("")
