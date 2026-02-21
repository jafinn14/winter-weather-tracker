"""
Event Visualization Module.

Creates charts and visualizations for snow events including:
- Snow accumulation timeline
- Temperature profile during event
- Hourly snow rate
- Threshold exceedance probabilities
"""

import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Any, Tuple
import re


def parse_nws_datetime(time_str: str) -> Optional[datetime]:
    """Parse NWS API datetime format."""
    if not time_str:
        return None
    try:
        if '/' in time_str:
            time_str = time_str.split('/')[0]
        if '+' in time_str:
            time_str = time_str.rsplit('+', 1)[0]
        elif time_str.count('-') > 2:
            parts = time_str.rsplit('-', 1)
            if ':' in parts[-1] and len(parts[-1]) == 5:
                time_str = parts[0]
        return datetime.fromisoformat(time_str)
    except (ValueError, IndexError):
        return None


def extract_hourly_snow_data(
    gridpoint_data: Dict,
    event_start: date,
    event_end: date
) -> pd.DataFrame:
    """
    Extract hourly snowfall data for an event from gridpoint data.

    Returns DataFrame with columns: datetime, snow_inches, cumulative_snow
    """
    data = []

    try:
        properties = gridpoint_data.get('properties', {})
        snow_amount = properties.get('snowfallAmount', {})
        values = snow_amount.get('values', [])

        for entry in values:
            valid_time = entry.get('validTime', '')
            value = entry.get('value')

            dt = parse_nws_datetime(valid_time)
            if not dt:
                continue

            # Filter to event dates
            if dt.date() < event_start or dt.date() > event_end:
                continue

            # Convert mm to inches
            inches = (value / 25.4) if value else 0

            data.append({
                'datetime': dt,
                'snow_inches': inches
            })

    except (KeyError, TypeError):
        pass

    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data)
    df = df.sort_values('datetime')
    df['cumulative_snow'] = df['snow_inches'].cumsum()

    return df


def extract_hourly_temperature_data(
    gridpoint_data: Dict,
    event_start: date,
    event_end: date
) -> pd.DataFrame:
    """
    Extract hourly temperature data for an event.

    Returns DataFrame with columns: datetime, temperature_f
    """
    data = []

    try:
        properties = gridpoint_data.get('properties', {})
        temperature = properties.get('temperature', {})
        values = temperature.get('values', [])

        for entry in values:
            valid_time = entry.get('validTime', '')
            value = entry.get('value')

            dt = parse_nws_datetime(valid_time)
            if not dt:
                continue

            # Filter to event dates (with buffer)
            if dt.date() < event_start - timedelta(days=1) or dt.date() > event_end + timedelta(days=1):
                continue

            # Convert C to F
            temp_f = (value * 9/5 + 32) if value is not None else None

            if temp_f is not None:
                data.append({
                    'datetime': dt,
                    'temperature_f': temp_f
                })

    except (KeyError, TypeError):
        pass

    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data)
    df = df.sort_values('datetime')

    return df


def extract_wind_data(
    gridpoint_data: Dict,
    event_start: date,
    event_end: date
) -> pd.DataFrame:
    """Extract wind speed data for an event."""
    data = []

    try:
        properties = gridpoint_data.get('properties', {})
        wind_speed = properties.get('windSpeed', {})
        values = wind_speed.get('values', [])

        for entry in values:
            valid_time = entry.get('validTime', '')
            value = entry.get('value')

            dt = parse_nws_datetime(valid_time)
            if not dt:
                continue

            if dt.date() < event_start or dt.date() > event_end:
                continue

            # Convert km/h to mph
            mph = (value * 0.621371) if value else 0

            data.append({
                'datetime': dt,
                'wind_mph': mph
            })

    except (KeyError, TypeError):
        pass

    if not data:
        return pd.DataFrame()

    return pd.DataFrame(data).sort_values('datetime')


def create_daily_accumulation_chart(
    snow_by_date: Dict[str, float],
    event_headline: str
) -> go.Figure:
    """
    Create a daily snow accumulation chart from event snow_by_date.

    This is a fallback when hourly gridpoint data is incomplete.
    Shows daily snowfall bars and cumulative accumulation line.
    """
    if not snow_by_date:
        return None

    # Convert to sorted list of (date, amount) tuples
    sorted_data = sorted(snow_by_date.items())
    dates = [date.fromisoformat(d) for d, _ in sorted_data]
    amounts = [amt for _, amt in sorted_data]

    # Calculate cumulative
    cumulative = []
    total = 0
    for amt in amounts:
        total += amt
        cumulative.append(total)

    # Format dates for display
    date_labels = [d.strftime('%a %b %d') for d in dates]

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Daily snowfall bars
    fig.add_trace(
        go.Bar(
            x=date_labels,
            y=amounts,
            name='Daily Snow',
            marker_color='lightblue',
            opacity=0.7,
            text=[f'{a:.1f}"' for a in amounts],
            textposition='outside'
        ),
        secondary_y=False
    )

    # Cumulative line
    fig.add_trace(
        go.Scatter(
            x=date_labels,
            y=cumulative,
            name='Total Accumulation',
            line=dict(color='darkblue', width=3),
            mode='lines+markers',
            marker=dict(size=10)
        ),
        secondary_y=True
    )

    # Add threshold lines
    max_snow = max(cumulative) if cumulative else 0
    thresholds = [2, 4, 6, 8, 12]

    for thresh in thresholds:
        if thresh <= max_snow * 1.2:
            fig.add_hline(
                y=thresh,
                line_dash="dash",
                line_color="gray",
                opacity=0.5,
                annotation_text=f'{thresh}"',
                annotation_position="right",
                secondary_y=True
            )

    fig.update_layout(
        title='Snow Accumulation by Day',
        xaxis_title='Date',
        height=400,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=20, r=20, t=60, b=20)
    )

    fig.update_yaxes(title_text="Daily Snow (inches)", secondary_y=False)
    fig.update_yaxes(title_text="Total Accumulation (inches)", secondary_y=True)

    return fig


def create_accumulation_chart(
    snow_df: pd.DataFrame,
    event_headline: str
) -> go.Figure:
    """
    Create a snow accumulation timeline chart.

    Shows both hourly snowfall (bars) and cumulative accumulation (line).
    """
    if snow_df.empty:
        return None

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Hourly snowfall bars
    fig.add_trace(
        go.Bar(
            x=snow_df['datetime'],
            y=snow_df['snow_inches'],
            name='Hourly Snow',
            marker_color='lightblue',
            opacity=0.7
        ),
        secondary_y=False
    )

    # Cumulative line
    fig.add_trace(
        go.Scatter(
            x=snow_df['datetime'],
            y=snow_df['cumulative_snow'],
            name='Total Accumulation',
            line=dict(color='darkblue', width=3),
            mode='lines'
        ),
        secondary_y=True
    )

    # Add threshold lines
    max_snow = snow_df['cumulative_snow'].max()
    thresholds = [2, 4, 6, 8, 12]

    for thresh in thresholds:
        if thresh <= max_snow * 1.2:  # Only show relevant thresholds
            fig.add_hline(
                y=thresh,
                line_dash="dash",
                line_color="gray",
                opacity=0.5,
                annotation_text=f'{thresh}"',
                annotation_position="right",
                secondary_y=True
            )

    fig.update_layout(
        title=f'Snow Accumulation Timeline',
        xaxis_title='Time',
        height=400,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=20, r=20, t=60, b=20)
    )

    fig.update_yaxes(title_text="Hourly Snow (inches)", secondary_y=False)
    fig.update_yaxes(title_text="Total Accumulation (inches)", secondary_y=True)

    return fig


def create_temperature_profile(
    temp_df: pd.DataFrame,
    snow_df: pd.DataFrame,
    event_start: date,
    event_end: date
) -> go.Figure:
    """
    Create temperature profile chart with freezing line highlighted.

    Shows when temperatures are above/below freezing during the event.
    """
    if temp_df.empty:
        return None

    fig = go.Figure()

    # Temperature line
    fig.add_trace(
        go.Scatter(
            x=temp_df['datetime'],
            y=temp_df['temperature_f'],
            name='Temperature',
            line=dict(color='red', width=2),
            mode='lines'
        )
    )

    # Freezing line
    fig.add_hline(
        y=32,
        line_dash="dash",
        line_color="blue",
        annotation_text="32°F (Freezing)",
        annotation_position="right"
    )

    # Shade the snow period if we have snow data
    if not snow_df.empty:
        snow_start = snow_df['datetime'].min()
        snow_end = snow_df['datetime'].max()

        fig.add_vrect(
            x0=snow_start,
            x1=snow_end,
            fillcolor="lightblue",
            opacity=0.2,
            layer="below",
            line_width=0,
            annotation_text="Snow Period",
            annotation_position="top left"
        )

    # Color regions above/below freezing
    fig.add_hrect(
        y0=32, y1=temp_df['temperature_f'].max() + 5,
        fillcolor="lightyellow",
        opacity=0.1,
        layer="below",
        line_width=0
    )

    fig.add_hrect(
        y0=temp_df['temperature_f'].min() - 5, y1=32,
        fillcolor="lightcyan",
        opacity=0.1,
        layer="below",
        line_width=0
    )

    fig.update_layout(
        title='Temperature Profile During Event',
        xaxis_title='Time',
        yaxis_title='Temperature (°F)',
        height=350,
        margin=dict(l=20, r=20, t=60, b=20)
    )

    return fig


def create_snow_rate_chart(snow_df: pd.DataFrame) -> go.Figure:
    """
    Create chart showing snow intensity over time.

    Categorizes into light/moderate/heavy snow rates.
    """
    if snow_df.empty:
        return None

    # Calculate hourly rate (assuming 6-hour periods in NWS data)
    df = snow_df.copy()

    # Categorize intensity
    def get_intensity(rate):
        if rate >= 1.0:
            return 'Heavy'
        elif rate >= 0.5:
            return 'Moderate'
        elif rate > 0:
            return 'Light'
        return 'None'

    def get_color(rate):
        if rate >= 1.0:
            return '#1e3a5f'  # Dark blue
        elif rate >= 0.5:
            return '#4a90d9'  # Medium blue
        elif rate > 0:
            return '#a8d5ff'  # Light blue
        return '#f0f0f0'  # Gray

    df['intensity'] = df['snow_inches'].apply(get_intensity)
    df['color'] = df['snow_inches'].apply(get_color)

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=df['datetime'],
            y=df['snow_inches'],
            marker_color=df['color'],
            name='Snow Rate',
            hovertemplate='%{x}<br>%{y:.2f}" per period<extra></extra>'
        )
    )

    # Add intensity legend
    fig.add_annotation(
        x=0.02, y=0.98,
        xref="paper", yref="paper",
        text="<b>Intensity:</b> Light (<0.5\") | Moderate (0.5-1\") | Heavy (>1\")",
        showarrow=False,
        font=dict(size=10),
        bgcolor="white",
        bordercolor="gray",
        borderwidth=1
    )

    fig.update_layout(
        title='Snow Intensity Over Time',
        xaxis_title='Time',
        yaxis_title='Snow per Period (inches)',
        height=300,
        margin=dict(l=20, r=20, t=60, b=20),
        showlegend=False
    )

    return fig


def create_threshold_probability_chart(
    snow_low: float,
    snow_high: float,
    snow_best: float
) -> go.Figure:
    """
    Create chart showing probability of exceeding various snow thresholds.

    Uses a simple normal distribution approximation based on the forecast range.
    """
    import numpy as np
    from scipy import stats

    # Estimate standard deviation from range
    # Assuming low-high covers roughly 80% of distribution (±1.28 sigma)
    if snow_high > snow_low:
        std_dev = (snow_high - snow_low) / 2.56
    else:
        std_dev = snow_best * 0.25  # Default 25% uncertainty

    mean = snow_best

    thresholds = [1, 2, 4, 6, 8, 12, 18]
    probabilities = []

    for thresh in thresholds:
        # Probability of exceeding threshold
        prob = 1 - stats.norm.cdf(thresh, loc=mean, scale=std_dev)
        probabilities.append(prob * 100)

    # Color based on probability
    colors = []
    for prob in probabilities:
        if prob >= 75:
            colors.append('#2ecc71')  # Green - likely
        elif prob >= 50:
            colors.append('#f1c40f')  # Yellow - possible
        elif prob >= 25:
            colors.append('#e67e22')  # Orange - uncertain
        else:
            colors.append('#e74c3c')  # Red - unlikely

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=[f'{t}"' for t in thresholds],
            y=probabilities,
            marker_color=colors,
            text=[f'{p:.0f}%' for p in probabilities],
            textposition='outside',
            hovertemplate='%{x}: %{y:.0f}% chance<extra></extra>'
        )
    )

    # Add reference lines
    fig.add_hline(y=50, line_dash="dash", line_color="gray", opacity=0.5)

    fig.update_layout(
        title='Probability of Exceeding Snow Thresholds',
        xaxis_title='Snow Amount',
        yaxis_title='Probability (%)',
        yaxis_range=[0, 105],
        height=350,
        margin=dict(l=20, r=20, t=60, b=20)
    )

    return fig


def create_event_summary_visual(
    event_start: date,
    event_end: date,
    snow_low: float,
    snow_high: float,
    snow_best: float,
    confidence: str,
    has_ice: bool,
    has_wind: bool
) -> go.Figure:
    """
    Create a visual summary card for the event.
    """
    # Create a gauge chart for snow amount
    fig = go.Figure()

    # Determine max for gauge
    gauge_max = max(18, snow_high * 1.2)

    fig.add_trace(go.Indicator(
        mode="gauge+number+delta",
        value=snow_best,
        title={'text': "Expected Snow (inches)", 'font': {'size': 16}},
        delta={'reference': snow_low, 'increasing': {'color': "blue"}},
        gauge={
            'axis': {'range': [0, gauge_max], 'tickwidth': 1},
            'bar': {'color': "darkblue"},
            'bgcolor': "white",
            'borderwidth': 2,
            'bordercolor': "gray",
            'steps': [
                {'range': [0, 2], 'color': '#e8f4f8'},
                {'range': [2, 4], 'color': '#b8e0ec'},
                {'range': [4, 6], 'color': '#7cc8dc'},
                {'range': [6, 12], 'color': '#3bafd4'},
                {'range': [12, gauge_max], 'color': '#1a8cba'}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': snow_high
            }
        }
    ))

    fig.update_layout(
        height=250,
        margin=dict(l=20, r=20, t=40, b=20)
    )

    return fig


def create_combined_event_chart(
    gridpoint_data: Dict,
    event_start: date,
    event_end: date,
    event_headline: str
) -> go.Figure:
    """
    Create a combined chart with snow accumulation and temperature.
    """
    snow_df = extract_hourly_snow_data(gridpoint_data, event_start, event_end)
    temp_df = extract_hourly_temperature_data(gridpoint_data, event_start, event_end)

    if snow_df.empty and temp_df.empty:
        return None

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.1,
        subplot_titles=('Snow Accumulation', 'Temperature'),
        row_heights=[0.6, 0.4]
    )

    # Snow accumulation
    if not snow_df.empty:
        fig.add_trace(
            go.Bar(
                x=snow_df['datetime'],
                y=snow_df['snow_inches'],
                name='Hourly Snow',
                marker_color='lightblue',
                opacity=0.7
            ),
            row=1, col=1
        )

        fig.add_trace(
            go.Scatter(
                x=snow_df['datetime'],
                y=snow_df['cumulative_snow'],
                name='Total',
                line=dict(color='darkblue', width=3),
                mode='lines',
                yaxis='y3'
            ),
            row=1, col=1
        )

    # Temperature
    if not temp_df.empty:
        fig.add_trace(
            go.Scatter(
                x=temp_df['datetime'],
                y=temp_df['temperature_f'],
                name='Temperature',
                line=dict(color='red', width=2),
                mode='lines'
            ),
            row=2, col=1
        )

        # Freezing line
        fig.add_hline(
            y=32,
            line_dash="dash",
            line_color="blue",
            row=2, col=1
        )

    fig.update_layout(
        title=f'{event_headline} - Forecast Timeline',
        height=500,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=20, r=20, t=80, b=20)
    )

    fig.update_yaxes(title_text="Snow (in)", row=1, col=1)
    fig.update_yaxes(title_text="Temp (°F)", row=2, col=1)
    fig.update_xaxes(title_text="Time", row=2, col=1)

    return fig
