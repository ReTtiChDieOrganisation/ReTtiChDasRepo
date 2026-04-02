# 🥕 ReTtiCh — Ride Tracking & Comparison Hub

A cycling visualization tool for friends who commute by bike and track rides on Strava.

## Features

- **Strava Sync**: Incremental data download with rate-limit handling
- **Ride Groups**: Auto-groups rides by shared segments (≥10) on the same day
- **Map Visualization**: Leaflet-based map with rider positions
- **Time-Sync Playback**: Watch rides unfold in real time with video-like controls
- **Segment Comparison**: Compare riders on shared segments as if starting together
- **Gold/Silver/Bronze**: Stats on who's fastest on shared segments

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure
```bash
cp config/config.example.json config/config.json
# Edit config/config.json with your Strava credentials and rider info
```

### 3. Sync data from Strava
```bash
python sync.py
```

### 4. Build frontend
```bash
python build.py
```

### 5. View
Open `frontend/index.html` in your browser, or serve it:
```bash
python -m http.server 8000 --directory frontend
```

## Project Structure

```
rettich/
├── config/             # Configuration files
├── backend/            # Python: Strava sync, DB, grouping, export
├── frontend/           # Static HTML/JS/CSS frontend
│   ├── css/
│   ├── js/
│   ├── data/           # Exported JSON (generated)
│   └── icons/
├── sync.py             # Entry: sync Strava data
├── build.py            # Entry: export data & build frontend
└── requirements.txt
```

## Security

The frontend has an optional simple password gate (configured in `config.json`).
This is NOT real security — just a deterrent for casual access.

## Future

- Raspberry Pi deployment with auto-sync cron job
- Flask/FastAPI server for dynamic data
- Detailed commute analysis page with Plotly charts
