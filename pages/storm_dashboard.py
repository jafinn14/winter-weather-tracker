import streamlit as st
from datetime import datetime, timedelta, date
import pandas as pd
import plotly.graph_objects as go
import os

from database import get_location_by_zip, get_forecasts_for_location
from snow_events import (
    identify_snow_events, save_detected_events, get_event_history,
    get_event_trend, format_event_date_range, get_event_headline,
    SnowEvent, EventConfidence
)
from historical_data import find_stations_near_location, compare_to_historical
from discussion_analysis import (
    get_event_discussion_insight, get_discussion_excerpt_only,
    highlight_winter_terms
)
from event_visualizations import (
    extract_hourly_snow_data, extract_hourly_temperature_data,
    create_accumulation_chart, create_daily_accumulation_chart,
    create_temperature_profile, create_snow_rate_chart,
    create_threshold_probability_chart, create_combined_event_chart
)


def show():
    st.title("Storm Dashboard")

    # As-of datetime (when this analysis is running)
    as_of_datetime = datetime.now()
    as_of_date = as_of_datetime.date()

    st.caption(f"**As of:** {as_of_datetime.strftime('%A, %B %d, %Y at %I:%M %p')}")

    # Check if location is set
    if "current_zip" not in st.session_state:
        st.warning("Please set up a location on the **Setup & Fetch Data** page to see your storm dashboard.")
        st.info("The Storm Dashboard automatically detects snow events in your forecast, shows confidence levels, tracks trends, and provides historical context.")
        return

    location = get_location_by_zip(st.session_state.current_zip)
    if not location:
        st.warning("Location not found. Please set up a location on the Setup page.")
        return

    # Get forecast data
    forecasts = get_forecasts_for_location(location['id'], days_back=7)

    if not forecasts:
        st.warning("No forecast data available. Fetch data on the **Setup & Fetch Data** page first.")
        return

    last_fetch = forecasts[0]['fetched_at'][:16].replace('T', ' ')
    st.markdown(f"**{location['city']}, {location['state']}** | Last fetch: {last_fetch}")

    # Detect snow events in the latest forecast
    latest_forecast = forecasts[0]['forecast_data']
    events = identify_snow_events(latest_forecast, as_of_datetime, location['id'])

    # Save detected events for tracking
    if events:
        save_detected_events(location['id'], events, as_of_datetime)

    if not events:
        show_no_events_view(location, forecasts, as_of_date)
    else:
        show_events_view(events, location, forecasts, as_of_datetime)


def show_no_events_view(location, forecasts, as_of_date):
    """Show view when no snow events are detected."""
    st.success("No significant snow events detected in the 7-day forecast.")

    st.markdown("### Current Forecast")

    # Show next few periods
    try:
        periods = forecasts[0]['forecast_data'].get('forecast', {}).get('properties', {}).get('periods', [])
        for period in periods[:6]:
            col1, col2 = st.columns([1, 3])
            with col1:
                st.markdown(f"**{period.get('name', '')}**")
                temp = period.get('temperature', '')
                unit = period.get('temperatureUnit', 'F')
                st.markdown(f"🌡️ {temp}°{unit}")
            with col2:
                st.markdown(period.get('shortForecast', ''))
            st.markdown("---")
    except (KeyError, TypeError, IndexError):
        pass

    st.info("Check the **Data Sources** page to view WPC extended forecasts for potential storms beyond Day 7.")


def show_events_view(events: list, location, forecasts, as_of_datetime: datetime):
    """Show comprehensive view of detected snow events."""

    as_of_date = as_of_datetime.date()

    # Summary header
    if len(events) == 1:
        st.markdown("## ❄️ 1 Snow Event Detected")
    else:
        st.markdown(f"## ❄️ {len(events)} Snow Events Detected")

    # Quick summary of all events
    summary_data = []
    for event in events:
        date_range = format_event_date_range(event, as_of_date)
        lead_days = event.lead_time_hours // 24

        summary_data.append({
            "Event": get_event_headline(event),
            "When": date_range,
            "Snow": f"{event.snow_total_low:.0f}-{event.snow_total_high:.0f}\"",
            "Confidence": f"{get_confidence_emoji(event.confidence)} {event.confidence.value}",
            "Lead Time": f"{lead_days} days"
        })

    st.dataframe(
        pd.DataFrame(summary_data),
        use_container_width=True,
        hide_index=True
    )

    st.markdown("---")

    # Detailed view of each event
    for i, event in enumerate(events):
        show_event_detail(event, location, forecasts, as_of_datetime, is_primary=(i == 0))
        if i < len(events) - 1:
            st.markdown("---")


def get_confidence_emoji(confidence: EventConfidence) -> str:
    """Get emoji for confidence level."""
    return {
        EventConfidence.VERY_HIGH: "🟢",
        EventConfidence.HIGH: "🟢",
        EventConfidence.MODERATE: "🟡",
        EventConfidence.LOW: "🟠",
        EventConfidence.VERY_LOW: "🔴"
    }.get(confidence, "⚪")


def show_event_detail(event: SnowEvent, location, forecasts, as_of_datetime: datetime, is_primary: bool = True):
    """Show detailed analysis for a single event."""

    as_of_date = as_of_datetime.date()
    lead_days = event.lead_time_hours // 24

    # Header
    headline = get_event_headline(event)
    date_range = format_event_date_range(event, as_of_date)

    if is_primary:
        st.markdown(f"## {headline}")
    else:
        st.markdown(f"### {headline}")

    st.markdown(f"**{date_range}**")

    # Key metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Expected Snow",
            f"{event.snow_total_low:.0f}-{event.snow_total_high:.0f}\"",
            help=f"Best estimate: {event.snow_total_best:.1f}\""
        )

    with col2:
        st.metric(
            "Lead Time",
            f"{lead_days} day{'s' if lead_days != 1 else ''}",
            help="Days until event starts"
        )

    with col3:
        emoji = get_confidence_emoji(event.confidence)
        st.metric(
            "Confidence",
            f"{emoji} {event.confidence.value}",
            help="Based on forecast lead time"
        )

    with col4:
        duration_days = (event.end_date - event.start_date).days + 1
        st.metric(
            "Duration",
            f"{duration_days} day{'s' if duration_days != 1 else ''}",
            help="Number of days with snow"
        )

    # Confidence explanation
    show_confidence_message(event.confidence, lead_days)

    # Snow by date breakdown
    if event.snow_by_date and len(event.snow_by_date) > 1:
        st.markdown("### Snow by Date")
        breakdown_data = []
        for date_str, amount in sorted(event.snow_by_date.items()):
            d = date.fromisoformat(date_str)
            day_name = d.strftime('%A')
            date_fmt = d.strftime('%b %d')
            breakdown_data.append({
                "Date": f"{day_name}, {date_fmt}",
                "Expected Snow": f"{amount:.1f}\""
            })

        st.dataframe(pd.DataFrame(breakdown_data), use_container_width=True, hide_index=True)

    # Expandable sections
    with st.expander("📈 Storm Visualizations", expanded=True):
        show_event_visualizations(event, forecasts)

    with st.expander("🧠 Meteorologist Analysis (AI Summary)", expanded=False):
        show_discussion_insight(event, location)

    with st.expander("📊 Forecast Trend", expanded=(lead_days >= 3)):
        show_event_trend(event, location)

    with st.expander("📅 Historical Context", expanded=False):
        show_historical_context(event, location)

    with st.expander("⚠️ Key Factors & Uncertainties", expanded=(lead_days >= 4)):
        show_uncertainties(event, lead_days)

    with st.expander("🎯 Potential Impacts", expanded=False):
        show_impacts(event)

    # Additional characteristics
    tags = []
    if event.has_ice:
        tags.append("⚠️ Ice/Freezing Rain Possible")
    if event.has_wind:
        tags.append("💨 Windy Conditions")
    if tags:
        st.markdown(" | ".join(tags))


def show_confidence_message(confidence: EventConfidence, lead_days: int):
    """Show confidence explanation message."""
    messages = {
        EventConfidence.VERY_HIGH: "High confidence in this forecast. Timing and amounts are well-established.",
        EventConfidence.HIGH: "Good confidence. Details may shift slightly but the event is certain.",
        EventConfidence.MODERATE: "Moderate confidence. Event is likely but amounts and timing could change.",
        EventConfidence.LOW: f"At {lead_days} days out, the storm signal is present but amounts are unreliable. Focus on whether it happens, not exact totals.",
        EventConfidence.VERY_LOW: f"At {lead_days}+ days out, this is a storm to WATCH. Amounts could change dramatically. Track trends over the next few days."
    }

    msg = messages.get(confidence, "")

    if confidence in [EventConfidence.LOW, EventConfidence.VERY_LOW]:
        st.warning(msg)
    elif confidence == EventConfidence.MODERATE:
        st.info(msg)
    else:
        st.success(msg)


def show_discussion_insight(event: SnowEvent, location):
    """Show AI-generated insight from the forecast discussion."""

    # Check if Gemini API key is configured
    gemini_key = os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')

    if not gemini_key:
        # No API key - show raw excerpt instead
        st.info("Set `GEMINI_API_KEY` in your .env file for free AI summaries. Get a key at [aistudio.google.com](https://aistudio.google.com/app/apikey)")

        excerpt = get_discussion_excerpt_only(
            location['id'],
            event.start_date,
            event.end_date
        )

        if excerpt:
            st.markdown("**Relevant Discussion Excerpt:**")
            # Highlight key terms
            highlighted = highlight_winter_terms(excerpt[:1500])
            st.markdown(highlighted)
        else:
            st.warning("No forecast discussion available. Fetch data on the Setup page.")
        return

    # Generate AI insight
    with st.spinner("Analyzing forecast discussion..."):
        insight = get_event_discussion_insight(
            location['id'],
            event.start_date,
            event.end_date,
            event.snow_total_low,
            event.snow_total_high
        )

    if not insight:
        # Fallback to raw excerpt
        excerpt = get_discussion_excerpt_only(
            location['id'],
            event.start_date,
            event.end_date
        )
        if excerpt:
            st.markdown("**Relevant Discussion Excerpt:**")
            highlighted = highlight_winter_terms(excerpt[:1500])
            st.markdown(highlighted)
        else:
            st.warning("No forecast discussion available for this event.")
        return

    # Display the AI-generated insight
    st.markdown("### Summary")
    st.markdown(insight.summary)

    # Confidence assessment
    st.markdown("### Forecaster Confidence")
    st.markdown(insight.confidence_assessment)

    # Key factors in columns
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Key Factors")
        if insight.key_factors:
            for factor in insight.key_factors:
                st.markdown(f"• {factor}")
        else:
            st.markdown("*Not specified*")

    with col2:
        st.markdown("### Concerns")
        if insight.meteorologist_concerns:
            for concern in insight.meteorologist_concerns:
                st.markdown(f"• {concern}")
        else:
            st.markdown("*None noted*")

    # Timing and amounts
    if insight.timing_details or insight.amount_details:
        st.markdown("### Details")
        if insight.timing_details:
            st.markdown(f"**Timing:** {insight.timing_details}")
        if insight.amount_details:
            st.markdown(f"**Amounts:** {insight.amount_details}")

    # Show raw excerpt in collapsed section
    if insight.raw_excerpt:
        with st.expander("View Raw Discussion Excerpt"):
            st.text(insight.raw_excerpt)


def show_event_trend(event: SnowEvent, location):
    """Show how this event's forecast has trended over time."""

    history = get_event_history(location['id'], event.event_id, days_back=7)

    if len(history) < 2:
        st.info("Fetch more forecast snapshots to see trends. Each fetch captures the forecast at that moment.")
        st.markdown("**Tip:** Fetch data every 6-12 hours to track how forecasts evolve.")
        return

    trend = get_event_trend(history)

    # Trend message
    if trend['direction'] == 'increasing':
        st.warning(f"📈 **Trending Up** - {trend['message']}")
    elif trend['direction'] == 'decreasing':
        st.success(f"📉 **Trending Down** - {trend['message']}")
    else:
        st.info(f"➡️ **Steady** - {trend['message']}")

    # Trend chart
    df = pd.DataFrame(trend['history'])
    df['time'] = pd.to_datetime(df['time'])
    df['time_str'] = df['time'].dt.strftime('%m/%d %H:%M')

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df['time_str'],
        y=df['snow'],
        mode='lines+markers',
        name='Forecast Snow',
        line=dict(color='royalblue', width=3),
        marker=dict(size=10)
    ))

    fig.update_layout(
        title='Forecast Evolution',
        xaxis_title='Fetch Time',
        yaxis_title='Expected Snow (inches)',
        height=300,
        margin=dict(l=20, r=20, t=40, b=20)
    )

    st.plotly_chart(fig, width='stretch')

    # Summary stats
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("First Forecast", f"{trend['first_amount']:.1f}\"")
    with col2:
        st.metric("Latest Forecast", f"{trend['latest_amount']:.1f}\"")
    with col3:
        change = trend['change']
        st.metric("Change", f"{change:+.1f}\"", delta=f"{change:+.1f}\"" if change != 0 else None)


def show_historical_context(event: SnowEvent, location):
    """Show how this event compares to historical data."""

    stations = find_stations_near_location(location['lat'], location['lon'])

    if not stations:
        st.info("No nearby weather stations found for historical comparison.")
        return

    station = stations[0]

    try:
        comparison = compare_to_historical(
            event.snow_total_best,
            station['id'],
            event.start_date.isoformat()
        )

        if comparison and comparison.get('percentile') is not None:
            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric("This Event", f"{event.snow_total_best:.1f}\"")

            with col2:
                st.metric("Historical Avg", f"{comparison['historical_avg']:.1f}\"",
                          help="Average snow for same week historically")

            with col3:
                pct = comparison['percentile']
                if pct >= 90:
                    st.metric("Percentile", f"{pct:.0f}th", delta="Unusually large")
                elif pct >= 75:
                    st.metric("Percentile", f"{pct:.0f}th", delta="Above average")
                elif pct <= 25:
                    st.metric("Percentile", f"{pct:.0f}th", delta="Below average", delta_color="inverse")
                else:
                    st.metric("Percentile", f"{pct:.0f}th")

            if pct >= 90:
                month_name = event.start_date.strftime('%B')
                st.error(f"This would be an unusually large storm for late {month_name}. Only {100-pct:.0f}% of similar periods have had more snow.")
            elif pct >= 75:
                st.warning("Above average snowfall for this time of year.")
        else:
            st.info("Historical comparison data unavailable.")

    except Exception as e:
        st.info("Could not load historical comparison.")


def show_uncertainties(event: SnowEvent, lead_days: int):
    """Show key uncertainties for this event."""

    uncertainties = []

    # Lead time based
    if lead_days >= 6:
        uncertainties.append("🔴 At 6+ days, storm track could shift dramatically affecting totals")
        uncertainties.append("🔴 Amount forecasts are unreliable - could be 50% higher or lower")
    elif lead_days >= 4:
        uncertainties.append("🟠 Storm track still uncertain - could shift totals by several inches")
        uncertainties.append("🟠 Timing may shift by 6-12 hours")
    elif lead_days >= 2:
        uncertainties.append("🟡 Minor adjustments to timing and amounts still possible")

    # Amount range
    spread = event.snow_total_high - event.snow_total_low
    if spread >= 8:
        uncertainties.append(f"🔴 Wide range of outcomes: {event.snow_total_low:.0f}\" to {event.snow_total_high:.0f}\"")
    elif spread >= 4:
        uncertainties.append(f"🟠 Moderate uncertainty in totals: {event.snow_total_low:.0f}\" to {event.snow_total_high:.0f}\"")

    # Ice/mixing
    if event.has_ice:
        uncertainties.append("⚠️ Rain/snow line is a key factor - small temp changes affect totals")

    if not uncertainties:
        st.success("No major uncertainties at this lead time.")
    else:
        for u in uncertainties:
            st.markdown(f"• {u}")

    # What to watch
    st.markdown("### What to Watch")

    if lead_days >= 4:
        st.markdown("• **Model trends** - Are forecasts converging or diverging?")
        st.markdown("• **Storm track** - North = more snow, South = less snow")
    if lead_days >= 2:
        st.markdown("• **Timing** - When exactly does snow start?")
        st.markdown("• **Precip type** - Will it start as rain?")
    st.markdown("• **NWS Discussion** - Read meteorologist reasoning on the Discussion Archive page")


def show_event_visualizations(event: SnowEvent, forecasts):
    """Show charts and visualizations for the snow event."""

    if not forecasts:
        st.info("No forecast data available for visualizations.")
        return

    # Get gridpoint data from the latest forecast
    latest_forecast = forecasts[0].get('forecast_data', {})
    gridpoint_data = latest_forecast.get('gridpoint', {})

    # Extract data for charts (may be incomplete for later dates)
    snow_df = pd.DataFrame()
    temp_df = pd.DataFrame()
    if gridpoint_data:
        snow_df = extract_hourly_snow_data(gridpoint_data, event.start_date, event.end_date)
        temp_df = extract_hourly_temperature_data(gridpoint_data, event.start_date, event.end_date)

    # Check if hourly data covers all event dates
    hourly_dates_covered = set()
    if not snow_df.empty:
        hourly_dates_covered = set(snow_df['datetime'].dt.date.unique())

    event_dates = set(date.fromisoformat(d) for d in event.snow_by_date.keys())
    hourly_data_complete = event_dates.issubset(hourly_dates_covered)

    # Tab layout for different visualizations
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Accumulation", "🌡️ Temperature", "⏱️ Snow Rate", "🎯 Probabilities"
    ])

    with tab1:
        # Use daily chart from event data (always complete)
        # Fall back to hourly if we have complete coverage
        if hourly_data_complete and not snow_df.empty:
            fig = create_accumulation_chart(snow_df, get_event_headline(event))
            if fig:
                st.plotly_chart(fig, width='stretch')
                total = snow_df['cumulative_snow'].max()
                peak_rate = snow_df['snow_inches'].max()
                st.caption(f"**Forecast Total:** {total:.1f}\" | **Peak Rate:** {peak_rate:.2f}\"/period")
        elif event.snow_by_date:
            # Use daily chart from event detection (always has all dates)
            fig = create_daily_accumulation_chart(event.snow_by_date, get_event_headline(event))
            if fig:
                st.plotly_chart(fig, width='stretch')
                total = sum(event.snow_by_date.values())
                st.caption(f"**Forecast Total:** {total:.1f}\" (daily breakdown from forecast)")
                if not hourly_data_complete and not snow_df.empty:
                    st.caption("_Note: Hourly gridpoint data incomplete - showing daily totals_")
        else:
            st.info("No snow data available for accumulation chart.")

    with tab2:
        if not temp_df.empty:
            fig = create_temperature_profile(temp_df, snow_df, event.start_date, event.end_date)
            if fig:
                st.plotly_chart(fig, width='stretch')

                # Show temperature stats during event
                min_temp = temp_df['temperature_f'].min()
                max_temp = temp_df['temperature_f'].max()
                below_freezing = (temp_df['temperature_f'] < 32).sum()
                total_periods = len(temp_df)
                st.caption(f"**Range:** {min_temp:.0f}°F - {max_temp:.0f}°F | **Below Freezing:** {below_freezing}/{total_periods} periods")
        else:
            st.info("No temperature data available for profile chart.")

    with tab3:
        if not snow_df.empty:
            fig = create_snow_rate_chart(snow_df)
            if fig:
                st.plotly_chart(fig, width='stretch')
        else:
            st.info("No hourly snow data available for rate chart.")

    with tab4:
        # Probability chart uses the event totals, not hourly data
        fig = create_threshold_probability_chart(
            event.snow_total_low,
            event.snow_total_high,
            event.snow_total_best
        )
        if fig:
            st.plotly_chart(fig, width='stretch')
            st.caption("Probabilities estimated from forecast range using statistical modeling.")

    # Combined chart option
    with st.expander("View Combined Timeline"):
        if gridpoint_data:
            fig = create_combined_event_chart(
                gridpoint_data,
                event.start_date,
                event.end_date,
                get_event_headline(event)
            )
            if fig:
                st.plotly_chart(fig, width='stretch')
            else:
                st.info("Combined chart unavailable - insufficient hourly data.")
        else:
            st.info("Combined timeline requires gridpoint data. Fetch data on Setup page.")


def show_impacts(event: SnowEvent):
    """Show potential impacts based on snow amounts."""

    best = event.snow_total_best
    high = event.snow_total_high

    st.markdown("### Threshold Analysis")

    thresholds = [
        (2, "Slippery roads, careful driving needed"),
        (4, "Hazardous travel, delays likely"),
        (6, "Plowing operations, school closures likely"),
        (8, "Significant disruption, parking bans possible"),
        (12, "Major storm, widespread closures"),
        (18, "Potentially crippling, multi-day recovery")
    ]

    for thresh, desc in thresholds:
        if high >= thresh:
            if best >= thresh:
                st.markdown(f"✅ **{thresh}\"**: {desc} - *Likely*")
            else:
                st.markdown(f"⚠️ **{thresh}\"**: {desc} - *Possible*")
        else:
            st.markdown(f"⬜ **{thresh}\"**: {desc}")

    # General impact summary
    st.markdown("---")

    if best >= 12:
        st.error("**Major Storm** - Plan for widespread disruption. Avoid travel during the storm.")
    elif best >= 6:
        st.warning("**Significant Snow** - Expect travel delays and possible closures.")
    elif best >= 3:
        st.info("**Moderate Snow** - Allow extra time for travel, be prepared for slippery roads.")
    else:
        st.success("**Light Snow** - Minor impacts expected.")
