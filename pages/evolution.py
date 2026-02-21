import streamlit as st
from database import get_location_by_zip, get_forecasts_for_location
from datetime import datetime, timedelta
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from dateutil import parser
import re

def extract_snow_amounts(forecast_text):
    """Extract snow amount from forecast text."""
    snow_pattern = r'(\d+(?:\.\d+)?)\s*(?:to\s*(\d+(?:\.\d+)?))?\s*(?:inch(?:es)?|")'
    matches = re.findall(snow_pattern, forecast_text, re.IGNORECASE)
    if matches:
        if matches[0][1]:  # Range
            return (float(matches[0][0]) + float(matches[0][1])) / 2
        else:  # Single value
            return float(matches[0][0])
    return None

def show():
    st.title("Forecast Evolution")

    # Check if location is set
    if "current_zip" not in st.session_state:
        st.warning("Please set up your location first in the 'Setup & Fetch Data' page.")
        return

    location = get_location_by_zip(st.session_state.current_zip)
    if not location:
        st.error("Location not found. Please set up your location again.")
        return

    st.markdown(f"### 📍 {location['city']}, {location['state']}")
    st.markdown("See how forecasts have changed over time")

    # Get all forecasts
    forecasts = get_forecasts_for_location(location['id'], days_back=30)
    if len(forecasts) < 2:
        st.warning("Not enough forecast data to show evolution. Please fetch data multiple times over several days.")
        st.info(f"Current snapshots: {len(forecasts)}. Fetch data regularly to build up history!")
        return

    st.success(f"Found {len(forecasts)} forecast snapshots")

    # Let user select what to visualize
    viz_option = st.selectbox(
        "What would you like to visualize?",
        ["Temperature Forecast Evolution", "Snow Forecast Evolution", "Precipitation Probability Evolution", "Snow Exceedance Probability"]
    )

    if viz_option == "Temperature Forecast Evolution":
        show_temperature_evolution(forecasts)
    elif viz_option == "Snow Forecast Evolution":
        show_snow_evolution(forecasts)
    elif viz_option == "Precipitation Probability Evolution":
        show_precipitation_evolution(forecasts)
    elif viz_option == "Snow Exceedance Probability":
        show_snow_exceedance_probability(forecasts)

    # Forecast comparison table
    st.markdown("---")
    st.markdown("### 📊 Forecast Snapshots Comparison")

    comparison_data = []
    for forecast in forecasts[:10]:  # Show last 10 fetches
        fetched_at = datetime.fromisoformat(forecast['fetched_at'])
        forecast_periods = forecast['forecast_data'].get('forecast', {}).get('properties', {}).get('periods', [])

        if forecast_periods:
            first_period = forecast_periods[0]
            comparison_data.append({
                "Fetched": fetched_at.strftime('%m/%d %I:%M %p'),
                "First Period": first_period.get('name', 'N/A'),
                "Temp": f"{first_period.get('temperature', 'N/A')}°{first_period.get('temperatureUnit', '')}",
                "Forecast": first_period.get('shortForecast', 'N/A')[:50] + "..."
            })

    if comparison_data:
        df = pd.DataFrame(comparison_data)
        st.dataframe(df, use_container_width=True)

def show_temperature_evolution(forecasts):
    """Show how temperature forecasts have evolved."""
    st.markdown("#### Temperature Forecast Evolution (Spaghetti Plot)")
    st.caption("Each line represents a different forecast fetch, showing how temperature predictions changed over time")

    fig = go.Figure()

    colors = px.colors.sequential.Blues_r

    for idx, forecast in enumerate(forecasts[:10]):  # Limit to 10 most recent
        fetched_at = datetime.fromisoformat(forecast['fetched_at'])
        periods = forecast['forecast_data'].get('forecast', {}).get('properties', {}).get('periods', [])

        if not periods:
            continue

        # Extract temperature data
        x_labels = []
        y_temps = []

        for i, period in enumerate(periods[:14]):  # 7 days
            x_labels.append(period.get('name', f'Period {i}'))
            y_temps.append(period.get('temperature'))

        # Add line to plot
        color_idx = min(idx, len(colors) - 1)
        fig.add_trace(go.Scatter(
            x=x_labels,
            y=y_temps,
            mode='lines+markers',
            name=fetched_at.strftime('%m/%d %I:%M %p'),
            line=dict(color=colors[color_idx], width=2),
            hovertemplate='%{x}<br>%{y}°F<extra></extra>'
        ))

    fig.update_layout(
        xaxis_title="Forecast Period",
        yaxis_title="Temperature (°F)",
        hovermode='x unified',
        height=500,
        legend=dict(
            orientation="v",
            yanchor="top",
            y=1,
            xanchor="left",
            x=1.02
        )
    )

    st.plotly_chart(fig, use_container_width=True)

def show_snow_evolution(forecasts):
    """Show how snowfall forecasts have evolved."""
    st.markdown("#### Snowfall Forecast Evolution")
    st.caption("Track how predicted snowfall amounts have changed over time")

    # Extract snow data from all forecasts
    snow_data = []

    for forecast in forecasts:
        fetched_at = datetime.fromisoformat(forecast['fetched_at'])
        periods = forecast['forecast_data'].get('forecast', {}).get('properties', {}).get('periods', [])

        for period in periods[:14]:
            period_name = period.get('name', '')
            detailed_forecast = period.get('detailedForecast', '')

            # Check for snow mentions
            if 'snow' in detailed_forecast.lower():
                snow_amount = extract_snow_amounts(detailed_forecast)

                snow_data.append({
                    'Fetched At': fetched_at,
                    'Period': period_name,
                    'Snow Amount (inches)': snow_amount if snow_amount else 'Mentioned',
                    'Forecast': detailed_forecast[:100] + "..."
                })

    if snow_data:
        df = pd.DataFrame(snow_data)
        st.dataframe(df, use_container_width=True)

        # Try to create a visualization if we have quantitative data
        numeric_data = [d for d in snow_data if isinstance(d['Snow Amount (inches)'], (int, float))]

        if numeric_data:
            df_numeric = pd.DataFrame(numeric_data)

            fig = go.Figure()

            for period in df_numeric['Period'].unique():
                period_data = df_numeric[df_numeric['Period'] == period]

                fig.add_trace(go.Scatter(
                    x=period_data['Fetched At'],
                    y=period_data['Snow Amount (inches)'],
                    mode='lines+markers',
                    name=period,
                    hovertemplate='%{y:.1f} inches<extra></extra>'
                ))

            fig.update_layout(
                xaxis_title="Forecast Fetch Time",
                yaxis_title="Predicted Snowfall (inches)",
                hovermode='x unified',
                height=400
            )

            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No specific snow amounts found in forecasts yet (only mentions). Amounts will appear when NWS provides quantitative predictions.")
    else:
        st.info("No snow mentioned in any forecasts yet.")

def show_precipitation_evolution(forecasts):
    """Show how precipitation probability has evolved."""
    st.markdown("#### Precipitation Probability Evolution")
    st.caption("Track how precipitation chances have changed over time")

    fig = go.Figure()
    colors = px.colors.sequential.Greens

    for idx, forecast in enumerate(forecasts[:10]):
        fetched_at = datetime.fromisoformat(forecast['fetched_at'])
        periods = forecast['forecast_data'].get('forecast', {}).get('properties', {}).get('periods', [])

        if not periods:
            continue

        x_labels = []
        y_probs = []

        for period in periods[:14]:
            period_name = period.get('name', '')
            precip_prob = period.get('probabilityOfPrecipitation', {})

            if precip_prob and precip_prob.get('value') is not None:
                x_labels.append(period_name)
                y_probs.append(precip_prob['value'])

        if x_labels and y_probs:
            color_idx = min(idx, len(colors) - 1)
            fig.add_trace(go.Scatter(
                x=x_labels,
                y=y_probs,
                mode='lines+markers',
                name=fetched_at.strftime('%m/%d %I:%M %p'),
                line=dict(color=colors[color_idx], width=2),
                hovertemplate='%{x}<br>%{y}%<extra></extra>'
            ))

    if fig.data:
        fig.update_layout(
            xaxis_title="Forecast Period",
            yaxis_title="Precipitation Probability (%)",
            hovermode='x unified',
            height=500,
            yaxis=dict(range=[0, 100]),
            legend=dict(
                orientation="v",
                yanchor="top",
                y=1,
                xanchor="left",
                x=1.02
            )
        )

        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No precipitation probability data available in forecasts.")

def show_snow_exceedance_probability(forecasts):
    """Show probability of exceeding various snow thresholds based on historical forecast variance."""
    st.markdown("#### Snow Exceedance Probability Analysis")
    st.caption("""
    This chart analyzes how snowfall forecasts have varied over time to estimate the probability
    of exceeding different snow amount thresholds. Based on your historical forecast data.
    """)

    # Extract all snow forecasts with amounts
    all_snow_forecasts = []

    for forecast in forecasts:
        fetched_at = datetime.fromisoformat(forecast['fetched_at'])
        periods = forecast['forecast_data'].get('forecast', {}).get('properties', {}).get('periods', [])

        for period in periods[:14]:
            period_name = period.get('name', '')
            detailed_forecast = period.get('detailedForecast', '')

            if 'snow' in detailed_forecast.lower():
                snow_amount = extract_snow_amounts(detailed_forecast)
                if snow_amount:
                    all_snow_forecasts.append({
                        'fetched_at': fetched_at,
                        'period': period_name,
                        'amount': snow_amount
                    })

    if not all_snow_forecasts:
        st.info("No quantitative snow forecasts found in your data yet. This analysis requires numerical snow predictions.")
        return

    # Calculate statistics by period
    df = pd.DataFrame(all_snow_forecasts)

    # Group by period and calculate stats
    period_stats = df.groupby('period')['amount'].agg(['mean', 'std', 'max', 'min', 'count']).reset_index()

    st.markdown("#### Snowfall Statistics by Forecast Period")

    # Display stats table
    stats_display = period_stats.copy()
    stats_display.columns = ['Period', 'Mean (in)', 'Std Dev', 'Max (in)', 'Min (in)', 'Forecasts']
    stats_display['Mean (in)'] = stats_display['Mean (in)'].round(2)
    stats_display['Std Dev'] = stats_display['Std Dev'].round(2)
    stats_display['Max (in)'] = stats_display['Max (in)'].round(2)
    stats_display['Min (in)'] = stats_display['Min (in)'].round(2)

    st.dataframe(stats_display, use_container_width=True)

    st.markdown("---")

    # Create exceedance probability chart
    st.markdown("#### Probability of Exceeding Snow Thresholds")
    st.caption("Based on the variance in your historical forecasts")

    # Define thresholds
    thresholds = [1, 2, 4, 6, 8, 12, 18]

    # Calculate exceedance probabilities for each period
    exceedance_data = []

    for _, row in period_stats.iterrows():
        period = row['period']
        mean = row['mean']
        std = row['std']

        for threshold in thresholds:
            # Simple probability calculation based on normal distribution
            # Higher mean and lower std = higher probability
            if std > 0:
                # Z-score
                z = (threshold - mean) / std
                # Approximate probability (simplified - assumes normal distribution)
                if z <= -2:
                    prob = 95
                elif z <= -1:
                    prob = 84
                elif z <= 0:
                    prob = 50
                elif z <= 1:
                    prob = 16
                elif z <= 2:
                    prob = 5
                else:
                    prob = 1
            else:
                prob = 100 if mean >= threshold else 0

            exceedance_data.append({
                'Period': period,
                'Threshold': f'{threshold}"',
                'Probability': prob,
                'Threshold_Value': threshold
            })

    if exceedance_data:
        df_exceed = pd.DataFrame(exceedance_data)

        # Create grouped bar chart
        fig = go.Figure()

        for threshold in thresholds:
            threshold_data = df_exceed[df_exceed['Threshold_Value'] == threshold]

            fig.add_trace(go.Bar(
                x=threshold_data['Period'],
                y=threshold_data['Probability'],
                name=f'{threshold}" snow',
                hovertemplate='%{y}% chance<extra></extra>'
            ))

        fig.update_layout(
            xaxis_title="Forecast Period",
            yaxis_title="Probability of Exceeding (%)",
            hovermode='x unified',
            height=500,
            barmode='group',
            yaxis=dict(range=[0, 100]),
            legend=dict(
                title="Snow Threshold",
                orientation="v",
                yanchor="top",
                y=1,
                xanchor="left",
                x=1.02
            )
        )

        st.plotly_chart(fig, use_container_width=True)

        # Alternative: Heatmap view
        st.markdown("#### Exceedance Probability Heatmap")

        pivot_data = df_exceed.pivot(index='Threshold', columns='Period', values='Probability')

        fig_heat = go.Figure(data=go.Heatmap(
            z=pivot_data.values,
            x=pivot_data.columns,
            y=pivot_data.index,
            colorscale='RdYlGn_r',
            text=pivot_data.values,
            texttemplate='%{text}%',
            textfont={"size": 10},
            colorbar=dict(title="Probability (%)")
        ))

        fig_heat.update_layout(
            xaxis_title="Forecast Period",
            yaxis_title="Snow Threshold",
            height=400
        )

        st.plotly_chart(fig_heat, use_container_width=True)

        st.info("""
        **Note:** These probabilities are estimated based on the variability in your historical forecast data.
        They represent how forecasts have changed over time, not official NWS probability forecasts.
        For official probabilities, see the NWS Graphics page.
        """)
    else:
        st.warning("Not enough data to calculate exceedance probabilities.")
