# Winter Weather Tracker - Improvement Plan

## Overview
This plan outlines enhancements to transform the tracker from a manual forecast viewer into a comprehensive storm analysis platform with verification, historical comparison, and proactive alerting.

---

## Current Capabilities (Baseline)
- NWS forecast data (7-day, hourly, gridpoint quantitative)
- Area Forecast Discussions archive
- Forecast evolution visualization
- NWS graphics display
- SQLite storage with 30-day retention

---

## Implementation Status

### Completed (Phase 1 & 2)
- [x] **Automated data fetching** (`auto_fetch.py`) - Standalone script for Task Scheduler
- [x] **Change detection** (`change_detection.py`) - Detects significant forecast changes
- [x] **Desktop notifications** (`notify.py`) - Windows toast alerts
- [x] **Manual observations** (`pages/observations.py`) - Log your own snow measurements
- [x] **Database updates** - Added `user_observations` and `alert_history` tables

### Completed (Data Sources Expansion)
- [x] **WPC Products** (`wpc_api.py`) - Probabilistic snow/ice maps, WSSI, discussions
- [x] **Historical Data** (`historical_data.py`) - xmACIS integration for past storms
- [x] **NBM/Model Comparison** (`nbm_api.py`) - Links to model viewers and comparison tools
- [x] **NOHRSC Observed Snowfall** - Verification maps
- [x] **Data Sources Page** (`pages/data_sources.py`) - Unified interface for all sources

### Completed (Storm Intelligence)
- [x] **Storm Detection** (`storm_analysis.py`) - Automatically detects storms in forecast
- [x] **Storm Dashboard** (`pages/storm_dashboard.py`) - Primary landing page with:
  - Automatic storm detection and headline generation
  - Confidence levels based on lead time (research-backed reliability %)
  - Forecast trend tracking with interactive charts
  - Historical comparison (percentile ranking vs past storms)
  - Key uncertainties identification
  - Impact assessment by threshold (travel, schools, plowing, power)
  - "What to watch" guidance for each lead time

### Pending
- [ ] Radar visualization (embedded or linked)
- [ ] State DOT road conditions
- [ ] NWS Alerts integration
- [ ] Extended verification dashboard

---

## Proposed Enhancements

### 1. Data Sources Expansion

#### 1.1 Actual Observations (for Verification)
| Source | Data Type | Access |
|--------|-----------|--------|
| **NWS Observation Stations** | Hourly temp, precip, snow depth | Free API (api.weather.gov/stations) |
| **CoCoRaHS** | Daily snow/precip reports from trained observers | Free data export |
| **NOAA LCD (Local Climatological Data)** | Quality-controlled daily summaries | Free CSV download |
| **Personal Weather Stations (PWS)** | Real-time local conditions | Weather Underground API (limited free tier) |

**Questions to resolve:**
- Which observation station(s) are closest to your location?
- Do you want to manually enter your own backyard measurements?

#### 1.2 Enhanced Timing Data
| Source | Data Type | Access |
|--------|-----------|--------|
| **NWS Hourly Forecast** | Already captured - precipitation probability by hour | ✓ Exists |
| **HRRR Model** | High-resolution hourly precipitation type/rate | Free via NOMADS or AWS Open Data |
| **NWS Radar (NEXRAD)** | Real-time precipitation location/movement | Free via AWS Open Data |

**Questions to resolve:**
- Do you want embedded radar visualization or links to external viewers?
- How granular should timing predictions be (hourly vs 15-min)?

#### 1.3 Multi-Source Forecast Comparison
| Source | Data Type | Access |
|--------|-----------|--------|
| **NWS Official** | Already captured | ✓ Exists |
| **NWS NBM (National Blend of Models)** | Probabilistic blend of multiple models | Free API |
| **GFS Model** | Global model, 3-hourly | Free via NOMADS |
| **NAM Model** | Regional model, hourly | Free via NOMADS |
| **European (ECMWF)** | Often most accurate for storms | Paid subscription required |

**Questions to resolve:**
- How important is European model data? (cost vs value)
- Do you want raw model output or pre-processed summaries?

#### 1.4 Impact Data Sources
| Source | Data Type | Access |
|--------|-----------|--------|
| **NWS Alerts API** | Winter storm warnings/watches/advisories | Free API (already accessible) |
| **State DOT APIs** | Road conditions, plow status | Varies by state (many free) |
| **FAA Weather** | Airport conditions, delays | Free API |
| **Power Outage Trackers** | Utility outage maps | Web scraping or APIs vary |

**Questions to resolve:**
- Which state(s) do you need road condition data for?
- Is power outage tracking a priority?

#### 1.5 Historical Storm Data
| Source | Data Type | Access |
|--------|-----------|--------|
| **NOAA Storm Events Database** | Historical storm reports, damage | Free CSV download |
| **NOAA Regional Snowfall Index (RSI)** | Storm severity rankings | Free API |
| **xmACIS (Applied Climate Information System)** | Historical daily snow/temp data | Free web service |
| **Your own archive** | Past forecasts stored in app | ✓ Exists (30 days) |

**Questions to resolve:**
- How far back should historical data go? (10 years? 30 years?)
- What makes storms "comparable"? (total accumulation? timing? storm track?)

---

### 2. Storage Architecture

#### 2.1 Extended Schema
```
Current tables:
  - locations
  - forecasts
  - discussions

New tables needed:
  - observations        (actual weather that occurred)
  - alerts              (NWS warnings/watches with timestamps)
  - verification        (forecast vs actual comparison records)
  - historical_storms   (archived notable storms for comparison)
  - model_forecasts     (if adding GFS/NAM/HRRR data)
```

#### 2.2 Data Retention Policy
| Data Type | Current | Proposed |
|-----------|---------|----------|
| Forecasts | 30 days | 30 days (or per-storm archive) |
| Discussions | 30 days | 30 days |
| Observations | N/A | 1 year rolling |
| Historical storms | N/A | Permanent |
| Verification records | N/A | Permanent |

#### 2.3 Storage Options
- **Keep SQLite**: Simple, no setup, good for personal use
- **Upgrade to PostgreSQL**: Better for larger datasets, concurrent access
- **Add time-series DB (InfluxDB)**: Optimized for weather data patterns

**Recommendation:** Keep SQLite for now, add tables. Migrate later if needed.

---

### 3. Key Questions to Answer

#### 3.1 Forecast Evolution (Enhanced)
- How has the snow total forecast changed over the past 24/48/72 hours?
- When did forecasters first mention this storm?
- How does forecast confidence (spread) change as storm approaches?

#### 3.2 Verification Questions
- How accurate was the forecast vs what actually happened?
- Which forecast source was most accurate for this storm?
- Is there a systematic bias (always over/under predicting)?

#### 3.3 Timing Questions
- When exactly will precipitation start at my location?
- When will rain change to snow (or vice versa)?
- When will the heaviest snow rates occur?
- When will it end?

#### 3.4 Impact Questions
- Will accumulation exceed thresholds that matter? (2" for travel, 6" for plowing, 12" for major impact)
- What's the probability of school closure?
- When will roads become hazardous?

#### 3.5 Historical Comparison
- How does this forecast compare to similar past storms?
- What actually happened in comparable situations?
- Is this storm unusual for the time of year?

---

### 4. Automation & Alerting

#### 4.1 Automatic Data Fetching
| Approach | Pros | Cons |
|----------|------|------|
| **Background thread in Streamlit** | Simple to add | Only runs when app is open |
| **Scheduled task (cron/Task Scheduler)** | Runs independently | Separate script needed |
| **Cloud function (AWS Lambda)** | Reliable, scalable | More complex setup |

**Recommendation:** Start with scheduled task (Windows Task Scheduler) running a fetch script every 1-2 hours.

#### 4.2 Alert Triggers
- Forecast snow total changes by >2 inches
- New NWS watch/warning/advisory issued
- Storm timing shifts by >6 hours
- Precipitation type change (rain→snow or vice versa)

#### 4.3 Notification Methods
- Desktop notification (Windows toast)
- Email alert
- SMS via Twilio (requires account)
- Discord/Slack webhook

---

### 5. Implementation Phases

#### Phase 1: Foundation (Current Storm)
**Goal:** Get verification working for this storm
- [ ] Add observations table to database
- [ ] Integrate NWS observation station data for your location
- [ ] Create verification page comparing forecast vs actual
- [ ] Extend data retention for storm events

#### Phase 2: Automation
**Goal:** Stop manual refreshing
- [ ] Create standalone fetch script
- [ ] Set up Windows Task Scheduler for hourly fetches
- [ ] Add desktop notifications for significant changes

#### Phase 3: Enhanced Timing
**Goal:** Know exactly when snow starts/stops
- [ ] Add precipitation type to hourly tracking
- [ ] Create timeline visualization showing precip phases
- [ ] Integrate HRRR model data for high-resolution timing

#### Phase 4: Historical Context
**Goal:** Compare to past storms
- [ ] Import historical storm data (10+ years)
- [ ] Build storm similarity algorithm
- [ ] Create comparison views ("storms like this one")

#### Phase 5: Multi-Source Comparison
**Goal:** See how different forecasts compare
- [ ] Add NBM (National Blend of Models) data
- [ ] Track which source is most accurate over time
- [ ] Visualization comparing forecast sources

#### Phase 6: Impact Assessment
**Goal:** Understand real-world consequences
- [ ] Integrate state DOT road conditions
- [ ] Add threshold-based impact indicators
- [ ] Historical correlation (X inches = Y% chance of school closing)

---

## Decisions Made

- **Priority for current storm:** Automation (scheduled fetches + alerts)
- **Manual measurements:** Yes, add manual snow depth logging
- **Remaining open questions:**
  - Geographic scope (single vs multiple locations)
  - Model data complexity
  - Historical depth

---

## Implementation Plan: Automation + Manual Logging

### Priority A: Automated Data Fetching

**Goal:** Fetch new forecast data on a schedule without opening the app

**Components:**
1. **Standalone fetch script** (`auto_fetch.py`)
   - Runs independently of Streamlit
   - Fetches forecast data for all saved locations
   - Stores in existing database

2. **Windows Task Scheduler setup**
   - Run every 1-2 hours during active weather
   - Can be adjusted based on storm proximity

3. **Logging**
   - Track fetch success/failure
   - Log data for troubleshooting

### Priority B: Change Detection & Alerts

**Goal:** Get notified when forecasts change significantly

**Components:**
1. **Change detection logic**
   - Compare new fetch to previous fetch
   - Detect significant changes:
     - Snow total changes by ≥2 inches
     - Temperature changes by ≥5°F
     - Timing shifts by ≥6 hours
     - New winter weather keywords appear

2. **Alert triggers table** (new)
   - Store detected changes with timestamps
   - Track which changes have been notified

3. **Desktop notifications**
   - Windows toast notifications via `win10toast` or `plyer`
   - Summary of what changed

4. **Optional: Alert history page**
   - View past alerts in the Streamlit app

### Priority C: Manual Snow Measurements

**Goal:** Log your own observations for ground truth

**Components:**
1. **User observations table** (new)
   ```sql
   user_observations (
     id, location_id, observed_at,
     snow_depth_inches, new_snow_inches,
     temperature_f, conditions_notes
   )
   ```

2. **Observation entry page** (new Streamlit page)
   - Simple form: date/time, snow depth, new snow, temp, notes
   - View history of your measurements

3. **Integration with verification**
   - Compare your measurements to forecast
   - Calculate forecast error

---

## Detailed Implementation Steps

### Step 1: Create auto_fetch.py
- Reuse existing `nws_api.py` and `database.py`
- Add logging
- Accept command-line args (--location, --all)

### Step 2: Add change detection
- Query last two forecasts
- Compare key metrics
- Return list of significant changes

### Step 3: Add notification system
- Install notification library
- Create `notify.py` module
- Integrate with change detection

### Step 4: Set up Task Scheduler
- Create batch file wrapper
- Configure scheduled task
- Test automation

### Step 5: Add user_observations table
- Update `database.py` schema
- Add CRUD functions

### Step 6: Create observation entry page
- New page in `pages/` folder
- Form for entering measurements
- History view

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `auto_fetch.py` | Create | Standalone fetch script |
| `change_detection.py` | Create | Compare forecasts, detect changes |
| `notify.py` | Create | Send desktop notifications |
| `run_fetch.bat` | Create | Batch wrapper for Task Scheduler |
| `database.py` | Modify | Add user_observations table, alert_triggers table |
| `pages/observations.py` | Create | UI for manual snow logging |
| `requirements.txt` | Modify | Add notification library |

---

## Next Steps

1. **Review this refined plan** - any adjustments needed?
2. **Begin implementation** - start with auto_fetch.py
3. **Test with current storm** - validate automation works

---

*Plan created: January 21, 2026*
*Updated: January 21, 2026 - Prioritized automation + manual logging*
