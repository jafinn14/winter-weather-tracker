# Winter Weather Tracker

A Streamlit application for tracking winter weather forecasts in New England. This app helps you understand how forecasts evolve over time by storing historical forecast data and Area Forecast Discussions from the National Weather Service.

## Features

- **Location-based tracking**: Enter your zip code to track forecasts for your area
- **Historical data**: Stores 30 days of forecast history
- **Official NWS Graphics**: View real-time winter weather maps and visualizations
  - Probabilistic snowfall maps (90%, 50%, 10% scenarios)
  - Snow exceedance probability maps (2", 4", 6", 12" thresholds)
  - Ice accumulation forecasts
  - Animated snowfall and snow rate loops
  - Winter Storm Severity Index
- **Forecast evolution visualization**: See how predictions change over time with interactive charts
  - Temperature trends (spaghetti plots)
  - Snow accumulation predictions
  - Precipitation probability changes
  - Snow exceedance probability analysis based on forecast variance
- **Area Forecast Discussions**: Archive of meteorologist discussions explaining forecast reasoning
- **Winter weather focus**: Tracks snow, ice, temperature, wind chill, and storm timing

## Installation

1. Clone or download this repository

2. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

1. Start the Streamlit app:
```bash
streamlit run app.py
```

2. Enter your zip code in the "Setup & Fetch Data" page

3. Click "Fetch Latest Data" to retrieve the current forecast

4. Return regularly (daily or multiple times during active weather) to fetch updated forecasts

5. Explore the different pages:
   - **Current Forecast**: View the latest forecast and winter weather alerts
   - **NWS Graphics**: View official NWS winter weather maps and visualizations (updated in real-time)
   - **Forecast Evolution**: See how predictions have changed over time with interactive charts
   - **Discussion Archive**: Read meteorologist discussions and compare them

## Data Sources

This app uses two primary data sources from the National Weather Service:

1. **NWS API** (api.weather.gov): Provides structured forecast data including:
   - 7-day forecasts
   - Hourly forecasts
   - Gridpoint data (snowfall, ice accumulation, wind chill)

2. **Area Forecast Discussions (AFD)**: Detailed narratives written by NWS meteorologists explaining forecast reasoning and uncertainties

## How It Works

1. **Location Setup**: Your zip code is converted to coordinates, then mapped to NWS grid points
2. **Data Collection**: On-demand fetching of forecast data and discussions
3. **Storage**: All data stored locally in SQLite database
4. **Visualization**: Multiple charts show how forecasts evolve over time
5. **Auto-cleanup**: Data older than 30 days is automatically removed

## Deployment

### Streamlit Community Cloud

1. Push this repository to GitHub

2. Go to [share.streamlit.io](https://share.streamlit.io)

3. Deploy your app by connecting to your GitHub repository

4. Your friends can access the app via the provided URL

Note: The SQLite database will reset when the app restarts on Community Cloud. For persistent storage across restarts, consider using a cloud database.

## Data Retention

- Forecast snapshots: 30 days
- Area Forecast Discussions: 30 days
- Old data is automatically cleaned up on app startup

## Winter Weather Metrics Tracked

- **Snowfall amounts**: Predicted accumulation over time
- **Temperature**: High/low temperatures and trends
- **Ice accumulation**: Freezing rain and ice predictions
- **Wind chill**: Apparent temperature calculations
- **Storm timing**: When precipitation starts/stops
- **Precipitation probability**: Chance of precipitation

## Tips for Best Results

- Fetch data at least once daily during winter months
- Fetch multiple times per day when winter storms are approaching
- Compare forecasts from 3-5 days out vs. 1 day out to see how predictions change
- Read the Area Forecast Discussions to understand meteorologist uncertainty

## Requirements

- Python 3.8+
- Streamlit
- Requests
- Plotly
- Pandas
- python-dateutil

## License

This project uses data from the National Weather Service, which is in the public domain.

## Credits

Built for tracking New England winter weather using National Weather Service data.
