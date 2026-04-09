#!/usr/bin/env python3
"""Build frontend: compute groups, export data, and produce index.html.

Usage:
    python build.py          Incremental build (only new activities exported)
    python build.py --full   Full rebuild (re-export all activities)
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from backend import database as db
from backend.grouping import compute_groups, compute_groups_for_dates
from backend.export import export_all

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, 'frontend')
DATA_DIR = os.path.join(FRONTEND_DIR, 'data')


def main():
    full = '--full' in sys.argv
    db_path = None
    for arg in sys.argv[1:]:
        if arg.startswith('--db='):
            db_path = arg.split('=', 1)[1]
    if db_path is None:
        db_path = os.path.join(BASE_DIR, 'rettich.db')
    if not os.path.exists(db_path):
        print("Error: rettich.db not found. Run sync.py first.")
        sys.exit(1)

    conn = db.get_connection(db_path)

    config_path = os.path.join(BASE_DIR, 'config', 'config.json')
    config = {}
    if os.path.exists(config_path):
        with open(config_path) as f:
            config = json.load(f)
    commute_config = config.get('commute', {})
    explorer_config = config.get('explorer', {})

    print("=== ReTtiCh Build ===")
    if full:
        print("  Mode: FULL rebuild")
    else:
        print("  Mode: incremental (use --full to rebuild all)")

    # Detect new activity IDs (in DB but no .js file exported yet)
    new_ids = _get_new_activity_ids(conn, DATA_DIR)
    if not new_ids and not full:
        print("No new activities. Nothing to do.")
        conn.close()
        return

    if new_ids:
        print(f"  {len(new_ids)} new activity/activities to process")

    # Step 1: Compute groups
    print("Computing ride groups...")
    if full:
        compute_groups(conn)
    else:
        new_dates = _get_dates_for_ids(conn, new_ids)
        compute_groups_for_dates(conn, new_dates)

    # Step 2: Export data (activities as .js files, metadata as .json)
    print("Exporting data for frontend...")
    export_all(conn, DATA_DIR, full=full)

    # Step 2b: Export commute data (skip if no new Ride-type activities)
    from backend.commute_export import export_commute_data
    if full or _has_new_rides(conn, new_ids):
        print("Exporting commute data...")
        commute_data = export_commute_data(conn, DATA_DIR, commute_config)
    else:
        print("  Skipping commute export (no new ride activities)")
        commute_data = _load_js_data(os.path.join(DATA_DIR, 'commute_data.js'), 'RETTICH_COMMUTE')

    # Step 2c: Compute tile data once for both explorer and rider stats
    print("Computing tile data...")
    from backend.tile_engine import compute_tile_data
    tile_data = compute_tile_data(conn, explorer_config)

    # Step 2d: Export explorer tile data
    print("Exporting explorer data...")
    from backend.explorer_export import export_explorer_data
    explorer_data = export_explorer_data(conn, DATA_DIR, tile_data, explorer_config)

    # Step 2e: Export per-rider statistics (reuses tile_data — no second stream pass)
    print("Exporting rider statistics...")
    from backend.rider_stats_export import export_rider_stats
    rider_stats_data = export_rider_stats(conn, DATA_DIR, tile_data, explorer_config)

    conn.close()

    # Step 3: Read site password from config
    site_password = config.get('site_password', 'rettich')

    site_config = {'password_hash': _simple_hash(site_password)}

    # Step 4: Build index.html (only metadata embedded, activities loaded on demand)
    print("Building index.html...")
    build_html(site_config, explorer_data)

    # Step 5: Build commutes.html
    print("Building commutes.html...")
    build_commutes_html(commute_data, site_config)

    # Step 6: Build explorer.html
    print("Building explorer.html...")
    build_explorer_html(explorer_data, site_config)

    # Step 7: Build riders.html
    print("Building riders.html...")
    build_riders_html(rider_stats_data, site_config, explorer_data)

    print(f"\nDone! Open {os.path.join(FRONTEND_DIR, 'index.html')} in your browser.")


def build_html(site_config, explorer_data=None):
    """Build index.html with only lightweight metadata embedded."""

    # Load metadata (small)
    riders = _read_json(os.path.join(DATA_DIR, 'riders.json'))
    groups = _read_json(os.path.join(DATA_DIR, 'groups.json'))
    activities_index = _read_json(os.path.join(DATA_DIR, 'activities_index.json'))
    shared_segments = _read_json(os.path.join(DATA_DIR, 'shared_segments.json'))

    # Merge per-activity rettiche scores from explorer data
    if explorer_data and 'activity_rettiche' in explorer_data:
        act_rettiche = explorer_data['activity_rettiche']
        for act in activities_index:
            info = act_rettiche.get(act['id'], act_rettiche.get(str(act['id']), {}))
            if isinstance(info, dict):
                act['new_tiles'] = info.get('new', 0)
                act['total_tiles'] = info.get('total', 0)
                act['rettiche_score'] = info.get('score', 0.0)
            else:
                act['new_tiles'] = 0
                act['total_tiles'] = 0

    embedded_data = {
        'riders': riders,
        'groups': groups,
        'activities_index': activities_index,
        'shared_segments': shared_segments,
        'site_config': site_config,
    }
    embedded_json = json.dumps(embedded_data, separators=(',', ':'))

    # Load CSS and JS source files
    css = _read_text(os.path.join(FRONTEND_DIR, 'css', 'style.css'))

    js_files = ['icons.js', 'map.js', 'timeline.js', 'segments.js', 'stats.js', 'app.js']
    js_parts = []
    for name in js_files:
        js_parts.append(f'// === {name} ===')
        js_parts.append(_read_text(os.path.join(FRONTEND_DIR, 'js', name)))
    js_all = '\n'.join(js_parts)

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
    <title>ReTtiCh — Ride Tracking & Comparison Hub</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
{css}
    </style>
</head>
<body>
    <!-- Password Gate -->
    <div id="password-gate" class="gate hidden">
        <div class="gate-card">
            <div class="gate-icon">🥕</div>
            <h1>ReTtiCh</h1>
            <p>Enter password to continue</p>
            <input type="password" id="gate-password" placeholder="Password" autofocus />
            <button id="gate-submit">Enter</button>
        </div>
    </div>

    <!-- Main App -->
    <div id="app">
{_topnav_html('map')}

        <!-- Mobile sidebar overlay -->
        <div id="sidebar-overlay" class="sidebar-overlay"></div>

        <!-- Main Layout -->
        <div class="main-layout">
            <!-- Left Sidebar -->
            <aside class="sidebar" id="sidebar">
                <div class="sidebar-section">
                    <h3 class="section-title">Date</h3>
                    <select id="date-select" class="date-select"></select>
                </div>

                <div class="sidebar-section">
                    <h3 class="section-title">Groups</h3>
                    <div id="group-list" class="group-list"></div>
                </div>

                <div class="sidebar-section" id="stats-section" style="display:none;">
                    <h3 class="section-title">Stats</h3>
                    <div id="stats-content"></div>
                </div>

                <div class="sidebar-section" id="activities-section" style="display:none;">
                    <h3 class="section-title">Activities</h3>
                    <div id="activities-list" class="activities-list"></div>
                </div>

                <div class="sidebar-section" id="riders-section">
                    <h3 class="section-title">Riders</h3>
                    <div id="riders-list" class="riders-list"></div>
                </div>
            </aside>

            <!-- Map + Controls -->
            <div class="map-area">
                <!-- Mobile sidebar toggle -->
                <button id="sidebar-toggle-btn" class="sidebar-toggle-btn" title="Open/close sidebar">☰</button>
                <div id="map"></div>

                <!-- Mode Toggle -->
                <div class="mode-toggle" id="mode-toggle" style="display:none;">
                    <button class="mode-btn active" data-mode="time-sync">
                        <span class="mode-icon">⏱</span> Time Sync
                    </button>
                    <button class="mode-btn" data-mode="segment-compare">
                        <span class="mode-icon">🏁</span> Segment Compare
                    </button>
                </div>

                <!-- Timeline Controls (Time Sync mode) -->
                <div class="playback-controls" id="playback-controls" style="display:none;">
                    <div class="pb-clock" id="pb-clock">--:--</div>
                    <div class="playback-bar">
                        <button class="pb-btn" id="pb-play" title="Play/Pause">▶</button>
                        <span class="pb-time" id="pb-current-time">00:00:00</span>
                        <div class="pb-timeline-wrap" id="pb-timeline-wrap">
                            <input type="range" id="pb-timeline" class="pb-timeline" min="0" max="1000" value="0" step="1" />
                        </div>
                        <span class="pb-time" id="pb-end-time">00:00:00</span>
                        <div class="pb-speed">
                            <button class="pb-speed-btn" id="pb-speed-btn">1×</button>
                        </div>
                    </div>
                </div>

                <!-- Segment Compare Panel -->
                <div class="segment-panel" id="segment-panel" style="display:none;">
                    <div class="segment-selector">
                        <h4>Shared Segments</h4>
                        <select id="segment-select" class="segment-select">
                            <option value="">Choose a segment...</option>
                        </select>
                    </div>
                    <div id="segment-info" class="segment-info"></div>
                    <div id="segment-table" class="segment-table"></div>
                    <div class="playback-bar segment-playback" id="segment-playback" style="display:none;">
                        <button class="pb-btn" id="seg-pb-play">▶</button>
                        <span class="pb-time" id="seg-pb-current-time">00:00</span>
                        <div class="pb-timeline-wrap">
                            <input type="range" id="seg-pb-timeline" class="pb-timeline" min="0" max="1000" value="0" step="1" />
                        </div>
                        <span class="pb-time" id="seg-pb-end-time">00:00</span>
                        <button class="pb-speed-btn" id="seg-pb-speed-btn">1×</button>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Metadata only (lightweight). Activity data loaded on demand. -->
    <script>
    window.RETTICH_DATA = {embedded_json};
    window.RETTICH_ACT = {{}};
    </script>

    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script>
{js_all}
    </script>
{_shared_mobile_js()}
</body>
</html>'''

    out_path = os.path.join(FRONTEND_DIR, 'index.html')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)
    size_kb = os.path.getsize(out_path) / 1024
    print(f"  Written {out_path} ({size_kb:.0f} KB)")


def build_commutes_html(commute_data, site_config):
    """Build the commute analysis page with Plotly charts."""
    if not commute_data:
        commute_data = {'commutes': [], 'riders': [], 'stats': {}}

    css = _read_text(os.path.join(FRONTEND_DIR, 'css', 'style.css'))
    commute_json = json.dumps(commute_data, separators=(',', ':'))

    # Rider colors matching the user's palette
    rider_colors_json = json.dumps({
        "Felix": "#298c8c",
        "Flo": "#a00000",
        "Philipp": "#f1a226",
    })

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
    <title>ReTtiCh — Commute Analysis</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <script src="https://cdn.plot.ly/plotly-2.35.0.min.js"></script>
    <style>
{css}
/* Commute-specific overrides */
.commute-page {{
    padding: 24px 32px;
    overflow-y: auto;
    height: calc(100vh - var(--topnav-height));
}}
.commute-header {{
    display: flex;
    align-items: baseline;
    gap: 24px;
    margin-bottom: 24px;
}}
.commute-header h1 {{
    font-size: 26px;
    font-weight: 800;
    letter-spacing: -0.5px;
}}
.controls-row {{
    display: flex;
    gap: 12px;
    margin-bottom: 20px;
    flex-wrap: wrap;
    align-items: center;
}}
.control-group {{
    display: flex;
    align-items: center;
    gap: 6px;
}}
.control-label {{
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: var(--text-muted);
}}
.control-select {{
    padding: 8px 12px;
    background: var(--bg-tertiary);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    color: var(--text-primary);
    font-family: var(--font-display);
    font-size: 13px;
    cursor: pointer;
    outline: none;
}}
.control-select:focus {{ border-color: var(--accent); }}
.control-select option {{ background: var(--bg-tertiary); color: var(--text-primary); }}

.chart-container {{
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    padding: 16px;
    margin-bottom: 24px;
}}
#plotly-chart {{
    width: 100%;
    height: 420px;
}}

.stats-row {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 12px;
    margin-bottom: 24px;
}}
.stat-big {{
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    padding: 20px;
    text-align: center;
}}
.stat-big .stat-icon {{ font-size: 28px; margin-bottom: 6px; }}
.stat-big .stat-value {{
    font-family: var(--font-mono);
    font-size: 24px;
    font-weight: 700;
    color: var(--accent);
}}
.stat-big .stat-label {{
    font-size: 11px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.8px;
    margin-top: 4px;
}}
.stat-big.rettich .stat-value {{ color: var(--success); }}

.rider-stats-row {{
    display: flex;
    gap: 12px;
    margin-bottom: 24px;
    flex-wrap: wrap;
}}
.rider-stat-card {{
    flex: 1;
    min-width: 200px;
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    padding: 16px;
    display: flex;
    align-items: center;
    gap: 14px;
}}
.rider-stat-color {{
    width: 6px;
    height: 48px;
    border-radius: 3px;
    flex-shrink: 0;
}}
.rider-stat-name {{
    font-size: 15px;
    font-weight: 600;
    margin-bottom: 4px;
}}
.rider-stat-detail {{
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--text-secondary);
    line-height: 1.5;
}}
    </style>
</head>
<body>
    <div id="app">
{_topnav_html('commutes')}

        <div class="commute-page">
            <!-- Stats Banner -->
            <div class="stats-row" id="stats-row"></div>

            <!-- Rider breakdown -->
            <div class="rider-stats-row" id="rider-stats"></div>

            <!-- Chart Controls -->
            <div class="controls-row">
                <div class="control-group">
                    <span class="control-label">Parameter</span>
                    <select id="param-select" class="control-select">
                        <option value="start_hour">Start Time</option>
                        <option value="elapsed_minutes" selected>Elapsed Time</option>
                        <option value="moving_minutes">Moving Time</option>
                        <option value="standing_minutes">Standing Time</option>
                        <option value="average_speed">Average Speed</option>
                        <option value="distance_km">Distance</option>
                    </select>
                </div>
                <div class="control-group">
                    <span class="control-label">Direction</span>
                    <select id="dir-select" class="control-select">
                        <option value="To Work">To Work</option>
                        <option value="From Work">From Work</option>
                        <option value="All">All</option>
                    </select>
                </div>
                <div class="control-group">
                    <span class="control-label">Rolling Window</span>
                    <select id="window-select" class="control-select">
                        <option value="15">15 days</option>
                        <option value="30" selected>30 days</option>
                        <option value="60">60 days</option>
                        <option value="90">90 days</option>
                    </select>
                </div>
            </div>

            <!-- Plotly Chart -->
            <div class="chart-container">
                <div id="plotly-chart"></div>
            </div>
        </div>
    </div>

    <script>
    const COMMUTE = {commute_json};
    const RIDER_COLORS = {rider_colors_json};

    const PARAM_CONFIG = {{
        start_hour:       {{ label: 'Start Time', unit: '', format: v => {{ const h=Math.floor(v); const m=Math.round((v-h)*60); return h+':'+(m<10?'0':'')+m; }} }},
        elapsed_minutes:  {{ label: 'Elapsed Time', unit: 'min', format: v => v.toFixed(1) }},
        moving_minutes:   {{ label: 'Moving Time', unit: 'min', format: v => v.toFixed(1) }},
        standing_minutes: {{ label: 'Standing Time', unit: 'min', format: v => v.toFixed(1) }},
        average_speed:    {{ label: 'Average Speed', unit: 'km/h', format: v => v.toFixed(1) }},
        distance_km:      {{ label: 'Distance', unit: 'km', format: v => v.toFixed(2) }},
    }};

    // --- Stats rendering ---
    function renderStats() {{
        const s = COMMUTE.stats;
        document.getElementById('stats-row').innerHTML = `
            <div class="stat-big">
                <div class="stat-icon">🚴</div>
                <div class="stat-value">${{s.total_rides}}</div>
                <div class="stat-label">Total Commutes</div>
            </div>
            <div class="stat-big">
                <div class="stat-icon">📏</div>
                <div class="stat-value">${{s.total_km.toLocaleString()}} km</div>
                <div class="stat-label">Total Distance</div>
            </div>
            <div class="stat-big rettich">
                <div class="stat-icon">🥕</div>
                <div class="stat-value">${{s.rettich_kg.toLocaleString()}} kg Rettiche</div>
            </div>
        `;

        let riderHtml = '';
        for (const rn of COMMUTE.riders) {{
            const rs = s.per_rider[rn] || {{}};
            const color = RIDER_COLORS[rn] || '#888';
            riderHtml += `
                <div class="rider-stat-card">
                    <div class="rider-stat-color" style="background:${{color}}"></div>
                    <div>
                        <div class="rider-stat-name">${{rn}}</div>
                        <div class="rider-stat-detail">
                            ${{rs.rides || 0}} rides · ${{(rs.total_km || 0).toLocaleString()}} km
                        </div>
                    </div>
                </div>
            `;
        }}
        document.getElementById('rider-stats').innerHTML = riderHtml;
    }}

    // --- Rolling statistics ---
    function rollingStats(values, dates, windowDays, minPeriods) {{
        minPeriods = minPeriods || 3;
        const n = values.length;
        const means = new Array(n);
        const stds = new Array(n);
        const windowMs = windowDays * 86400000;

        for (let i = 0; i < n; i++) {{
            const tMax = dates[i].getTime();
            const tMin = tMax - windowMs;
            const windowVals = [];
            for (let j = 0; j <= i; j++) {{
                if (dates[j].getTime() >= tMin && values[j] != null) {{
                    windowVals.push(values[j]);
                }}
            }}
            if (windowVals.length >= minPeriods) {{
                const mean = windowVals.reduce((a, b) => a + b, 0) / windowVals.length;
                const variance = windowVals.reduce((a, b) => a + (b - mean) ** 2, 0) / windowVals.length;
                means[i] = mean;
                stds[i] = Math.sqrt(variance);
            }} else {{
                means[i] = null;
                stds[i] = null;
            }}
        }}
        return {{ means, stds }};
    }}

    // --- KDE computation ---
    function gaussianKDE(values, gridMin, gridMax, bandwidth, nGrid) {{
        nGrid = nGrid || 100;
        if (!bandwidth) {{
            const std = Math.sqrt(values.reduce((a, b) => a + (b - values.reduce((x, y) => x + y, 0) / values.length) ** 2, 0) / values.length);
            bandwidth = 1.06 * std * Math.pow(values.length, -0.2);
        }}
        if (bandwidth <= 0) bandwidth = 1;
        const grid = [];
        const density = [];
        const step = (gridMax - gridMin) / (nGrid - 1);
        for (let i = 0; i < nGrid; i++) {{
            const x = gridMin + i * step;
            grid.push(x);
            let d = 0;
            for (const v of values) {{
                const z = (x - v) / bandwidth;
                d += Math.exp(-0.5 * z * z) / (bandwidth * Math.sqrt(2 * Math.PI));
            }}
            density.push(d / values.length);
        }}
        return {{ grid, density }};
    }}

    // --- Main chart ---
    function updateChart() {{
        const param = document.getElementById('param-select').value;
        const dir = document.getElementById('dir-select').value;
        const windowDays = parseInt(document.getElementById('window-select').value);
        const cfg = PARAM_CONFIG[param];

        let data = COMMUTE.commutes;
        if (dir !== 'All') {{
            data = data.filter(c => c.direction === dir);
        }}

        const traces = [];
        const riders = COMMUTE.riders;

        // Collect all y-values for KDE range
        let allY = [];

        for (const rider of riders) {{
            const rc = data.filter(c => c.rider === rider).sort((a, b) => a.date.localeCompare(b.date));
            if (rc.length === 0) continue;

            const dates = rc.map(c => new Date(c.date));
            const yVals = rc.map(c => c[param]);
            const color = RIDER_COLORS[rider] || '#888';

            allY.push(...yVals.filter(v => v != null));

            // Scatter points
            traces.push({{
                x: dates,
                y: yVals,
                mode: 'markers',
                type: 'scatter',
                name: rider,
                marker: {{ color: color, size: 5, opacity: 0.45 }},
                legendgroup: rider,
                xaxis: 'x',
                yaxis: 'y',
                hovertemplate: '%{{x|%Y-%m-%d}}<br>' + cfg.label + ': %{{y:.2f}} ' + cfg.unit + '<extra>' + rider + '</extra>',
            }});

            // Rolling mean + std
            const validIdx = [];
            const validDates = [];
            const validVals = [];
            for (let i = 0; i < yVals.length; i++) {{
                if (yVals[i] != null) {{
                    validIdx.push(i);
                    validDates.push(dates[i]);
                    validVals.push(yVals[i]);
                }}
            }}

            if (validVals.length >= 3) {{
                const {{ means, stds }} = rollingStats(validVals, validDates, windowDays, 3);

                // Split into continuous segments (break where gap > window)
                const windowMs = windowDays * 86400000;
                const segments = [];
                let seg = {{ dates: [], means: [], upper: [], lower: [] }};

                for (let i = 0; i < means.length; i++) {{
                    if (means[i] == null || stds[i] == null) continue;

                    // Start new segment if gap too large
                    if (seg.dates.length > 0) {{
                        const gap = validDates[i].getTime() - seg.dates[seg.dates.length - 1].getTime();
                        if (gap > windowMs) {{
                            if (seg.dates.length >= 2) segments.push(seg);
                            seg = {{ dates: [], means: [], upper: [], lower: [] }};
                        }}
                    }}
                    seg.dates.push(validDates[i]);
                    seg.means.push(means[i]);
                    seg.upper.push(means[i] + stds[i]);
                    seg.lower.push(means[i] - stds[i]);
                }}
                if (seg.dates.length >= 2) segments.push(seg);

                // Create traces for each continuous segment
                segments.forEach((s, si) => {{
                    // Upper bound (invisible)
                    traces.push({{
                        x: s.dates,
                        y: s.upper,
                        mode: 'lines',
                        line: {{ width: 0, color: 'transparent' }},
                        showlegend: false,
                        legendgroup: rider,
                        xaxis: 'x',
                        yaxis: 'y',
                        hoverinfo: 'skip',
                    }});
                    // Lower bound with fill to upper
                    traces.push({{
                        x: s.dates,
                        y: s.lower,
                        mode: 'lines',
                        line: {{ width: 0, color: 'transparent' }},
                        fill: 'tonexty',
                        fillcolor: color + '25',
                        showlegend: false,
                        legendgroup: rider,
                        xaxis: 'x',
                        yaxis: 'y',
                        hoverinfo: 'skip',
                    }});
                    // Mean line
                    traces.push({{
                        x: s.dates,
                        y: s.means,
                        mode: 'lines',
                        line: {{ color: color, width: 2.5 }},
                        showlegend: false,
                        legendgroup: rider,
                        xaxis: 'x',
                        yaxis: 'y',
                        hovertemplate: '%{{x|%Y-%m-%d}}<br>Mean: %{{y:.2f}} ' + cfg.unit + '<extra>' + rider + ' (rolling)</extra>',
                    }});
                }});
            }}

            // KDE on x2 axis
            if (validVals.length >= 2) {{
                const yMin = Math.min(...validVals);
                const yMax = Math.max(...validVals);
                const pad = (yMax - yMin) * 0.1 || 1;
                const kde = gaussianKDE(validVals, yMin - pad, yMax + pad);

                traces.push({{
                    x: kde.density,
                    y: kde.grid,
                    mode: 'lines',
                    fill: 'tozerox',
                    fillcolor: color + '30',
                    line: {{ color: color, width: 1.5 }},
                    showlegend: false,
                    legendgroup: rider,
                    xaxis: 'x2',
                    yaxis: 'y',
                    hoverinfo: 'skip',
                }});
            }}
        }}

        const layout = {{
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: '#151821',
            font: {{ family: 'Outfit, sans-serif', color: '#e8eaf0', size: 12 }},
            margin: {{ l: 60, r: 20, t: 10, b: 50 }},
            legend: {{ x: 0, y: 1.12, orientation: 'h', font: {{ size: 12 }} }},
            xaxis: {{
                domain: [0, 0.82],
                gridcolor: '#2a2f45',
                zerolinecolor: '#2a2f45',
                title: {{ text: 'Date', font: {{ size: 12 }} }},
            }},
            xaxis2: {{
                domain: [0.85, 1.0],
                gridcolor: '#2a2f45',
                zerolinecolor: '#2a2f45',
                title: {{ text: 'Density', font: {{ size: 11 }} }},
                showticklabels: false,
            }},
            yaxis: {{
                gridcolor: '#2a2f45',
                zerolinecolor: '#2a2f45',
                title: {{ text: cfg.label + (cfg.unit ? ' (' + cfg.unit + ')' : ''), font: {{ size: 12 }} }},
            }},
            hovermode: 'closest',
        }};

        // Custom y-axis tick format for start_hour
        if (param === 'start_hour') {{
            layout.yaxis.tickvals = [6, 7, 8, 9, 10, 14, 15, 16, 17, 18, 19, 20];
            layout.yaxis.ticktext = ['6:00','7:00','8:00','9:00','10:00','14:00','15:00','16:00','17:00','18:00','19:00','20:00'];
            layout.yaxis.title.text = 'Start Time';
        }}

        Plotly.react('plotly-chart', traces, layout, {{
            responsive: true,
            displayModeBar: true,
            modeBarButtonsToRemove: ['lasso2d', 'select2d'],
            displaylogo: false,
        }});
    }}

    // --- Init ---
    document.addEventListener('DOMContentLoaded', () => {{
        renderStats();
        updateChart();
        document.getElementById('param-select').addEventListener('change', updateChart);
        document.getElementById('dir-select').addEventListener('change', updateChart);
        document.getElementById('window-select').addEventListener('change', updateChart);
    }});
    </script>
{_shared_mobile_js()}
</body>
</html>'''

    out_path = os.path.join(FRONTEND_DIR, 'commutes.html')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)
    size_kb = os.path.getsize(out_path) / 1024
    print(f"  Written {out_path} ({size_kb:.0f} KB)")


def build_explorer_html(explorer_data, site_config):
    """Build the tile explorer page with heatmap, Acker, per-rider scores."""
    if not explorer_data:
        explorer_data = {'tiles': [], 'stats': {}, 'daily_new': [], 'rider_scores': [], 'zoom': 16, 'max_visits': 1}

    css = _read_text(os.path.join(FRONTEND_DIR, 'css', 'style.css'))
    explorer_json = json.dumps(explorer_data, separators=(',', ':'))

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
    <title>ReTtiCh — Explorer</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
{css}
.explorer-layout {{ display: flex; height: calc(var(--app-vh, 100dvh) - var(--topnav-height)); }}
.explorer-sidebar {{
    width: 360px; background: var(--bg-secondary); border-right: 1px solid var(--border);
    overflow-y: auto; flex-shrink: 0; padding: 20px 16px;
}}
.explorer-map {{ flex: 1; position: relative; }}
#explorer-map {{ width: 100%; height: 100%; }}
.exp-section {{ margin-bottom: 18px; }}
.exp-section-title {{
    font-size: 11px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 1.2px; color: var(--text-muted); margin-bottom: 10px;
}}
.exp-stats-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }}
.exp-stat {{
    background: var(--bg-tertiary); border: 1px solid var(--border);
    border-radius: var(--radius-sm); padding: 10px; text-align: center;
}}
.exp-stat.wide {{ grid-column: span 2; }}
.exp-stat.highlight {{ border-color: var(--accent); background: rgba(255,102,0,0.08); }}
.exp-stat .exp-val {{
    font-family: var(--font-mono); font-size: 20px; font-weight: 700; color: var(--accent);
}}
.exp-stat .exp-val.teal {{ color: #00d4aa; }}
.exp-stat .exp-lbl {{
    font-size: 10px; color: var(--text-muted); text-transform: uppercase;
    letter-spacing: 0.5px; margin-top: 2px;
}}
.exp-divider {{ height: 1px; background: var(--border); margin: 14px 0; }}
.daily-bar-chart {{ display: flex; align-items: flex-end; gap: 2px; height: 70px; }}
.daily-bar {{
    flex: 1; background: #00d4aa; border-radius: 2px 2px 0 0; min-width: 3px;
    position: relative; cursor: pointer; opacity: 0.7; transition: opacity 0.15s;
}}
.daily-bar:hover {{ opacity: 1; }}
.daily-bar.active {{ opacity: 1; background: #fff; }}
.daily-bar-tooltip {{
    display: none; position: absolute; bottom: 100%; left: 50%; transform: translateX(-50%);
    background: var(--bg-secondary); border: 1px solid var(--border); border-radius: var(--radius-sm);
    padding: 4px 8px; font-size: 11px; white-space: nowrap; z-index: 10;
    pointer-events: none; color: var(--text-primary);
}}
.daily-bar:hover .daily-bar-tooltip {{ display: block; }}
.mode-switch {{
    display: flex; gap: 2px; background: var(--bg-tertiary); border: 1px solid var(--border);
    border-radius: var(--radius-sm); padding: 3px; margin-bottom: 14px;
}}
.mode-switch button {{
    flex: 1; padding: 7px 10px; background: transparent; border: none; border-radius: 4px;
    color: var(--text-secondary); font-family: var(--font-display); font-size: 12px;
    font-weight: 600; cursor: pointer; transition: all 0.15s; white-space: nowrap;
}}
.mode-switch button:hover {{ color: var(--text-primary); }}
.mode-switch button.active {{ background: var(--accent); color: #fff; }}
.colormap-legend {{
    display: flex; align-items: center; gap: 6px; margin-top: 8px;
    font-size: 10px; color: var(--text-muted);
}}
.colormap-bar {{
    flex: 1; height: 10px; border-radius: 3px;
    background: linear-gradient(to right, #ffffb2, #fecc5c, #fd8d3c, #f03b20, #bd0026, #800026);
}}
.colormap-new {{
    display: inline-block; width: 14px; height: 10px; background: #00d4aa;
    border-radius: 2px; margin-left: 8px;
}}
.rider-score-row {{
    display: flex; align-items: center; gap: 10px; padding: 6px 8px;
    border-radius: var(--radius-sm); margin-bottom: 4px;
    background: var(--bg-tertiary); border: 1px solid var(--border);
    transition: border-color 0.15s, background 0.15s;
}}
.rider-score-row:hover {{
    border-color: var(--border-light); background: var(--bg-hover);
}}
.rider-score-row.active {{
    border-color: #00d4aa; background: rgba(0, 212, 170, 0.1);
}}
.rider-score-row .rs-name {{ flex: 1; font-size: 13px; font-weight: 500; }}
.rider-score-row .rs-score {{
    font-family: var(--font-mono); font-size: 14px; font-weight: 700; color: var(--accent);
}}
.rider-score-row .rs-rank {{ font-size: 14px; width: 22px; text-align: center; }}
    </style>
</head>
<body>
    <div id="app">
{_topnav_html('explorer')}

        <div class="explorer-layout">
            <aside class="explorer-sidebar" id="explorer-sidebar">
                <div class="mode-switch">
                    <button class="active" data-mode="heatmap">Beete</button>
                    <button data-mode="feld">Acker</button>
                </div>

                <div class="exp-section">
                    <div class="exp-section-title">Scores</div>
                    <div class="exp-stats-grid">
                        <div class="exp-stat wide highlight">
                            <div class="exp-val" id="rettiche-id">0</div>
                            <div class="exp-lbl">🥕 Rettiche</div>
                        </div>
                    </div>
                </div>

                <div class="exp-section">
                    <div class="exp-section-title">Tiles</div>
                    <div class="exp-stats-grid">
                        <div class="exp-stat">
                            <div class="exp-val" id="total-tiles">0</div>
                            <div class="exp-lbl">Beete</div>
                        </div>
                        <div class="exp-stat">
                            <div class="exp-val teal" id="feld-size">0</div>
                            <div class="exp-lbl">🏠 Acker Größe</div>
                        </div>
                        <div class="exp-stat">
                            <div class="exp-val teal" id="new-today">0</div>
                            <div class="exp-lbl">New Today</div>
                        </div>
                        <div class="exp-stat">
                            <div class="exp-val teal" id="new-week">0</div>
                            <div class="exp-lbl">New This Week</div>
                        </div>
                        <div class="exp-stat">
                            <div class="exp-val teal" id="feld-new-today">0</div>
                            <div class="exp-lbl">Acker + Today</div>
                        </div>
                        <div class="exp-stat">
                            <div class="exp-val teal" id="feld-new-week">0</div>
                            <div class="exp-lbl">Acker + Week</div>
                        </div>
                    </div>
                </div>

                <div class="exp-divider"></div>

                <div class="exp-section">
                    <div class="exp-section-title">All Time</div>
                    <div class="exp-stats-grid">
                        <div class="exp-stat"><div class="exp-val" id="total-km">0</div><div class="exp-lbl">Kilometers</div></div>
                        <div class="exp-stat"><div class="exp-val" id="total-hours">0</div><div class="exp-lbl">Hours</div></div>
                        <div class="exp-stat wide"><div class="exp-val" id="total-acts">0</div><div class="exp-lbl">Activities</div></div>
                    </div>
                </div>

                <div class="exp-divider"></div>

                <div class="exp-section">
                    <div class="exp-section-title">Last 7 Days</div>
                    <div class="exp-stats-grid">
                        <div class="exp-stat"><div class="exp-val" id="week-km">0</div><div class="exp-lbl">Kilometers</div></div>
                        <div class="exp-stat"><div class="exp-val" id="week-hours">0</div><div class="exp-lbl">Hours</div></div>
                        <div class="exp-stat wide"><div class="exp-val" id="week-acts">0</div><div class="exp-lbl">Activities</div></div>
                    </div>
                </div>

                <div class="exp-divider"></div>

                <div class="exp-section">
                    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">
                        <div class="exp-section-title" style="margin-bottom:0">Rettiche</div>
                        <div class="mode-switch" style="margin-bottom:0;padding:2px;">
                            <button class="active" data-score="alltime" style="padding:4px 8px;font-size:11px;">All Time</button>
                            <button data-score="30d" style="padding:4px 8px;font-size:11px;">30 Days</button>
                        </div>
                    </div>
                    <div id="rider-scores"></div>
                </div>

                <div class="exp-divider"></div>

                <div class="exp-section">
                    <div class="exp-section-title">New Tiles (30 Days)</div>
                    <div class="daily-bar-chart" id="daily-chart"></div>
                </div>

                <div class="exp-section">
                    <div class="exp-section-title">Legend</div>
                    <div class="colormap-legend">
                        <span>1×</span><div class="colormap-bar"></div><span>many</span>
                        <span class="colormap-new"></span><span>new</span>
                    </div>
                </div>
            </aside>

            <div class="explorer-map">
                <button id="explorer-sidebar-toggle-btn" class="sidebar-toggle-btn" aria-label="Open explorer panel">☰</button>
                <div id="explorer-sidebar-overlay" class="sidebar-overlay"></div>
                <div id="explorer-map"></div>
            </div>
        </div>
    </div>

    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script>
    const EXP = {explorer_json};
    let currentMode = 'heatmap';
    let selectedDate = null;
    let selectedRider = null;
    let map;
    const tileLayers = [];
    let feldBorderLayer = null;

    // Colormap: cool-to-warm with good contrast at both ends
    const CMAP = [
        [1,   '#ffffb2'],
        [3,   '#fecc5c'],
        [10,  '#fd8d3c'],
        [30,  '#f03b20'],
        [80,  '#bd0026'],
        [200, '#800026'],
    ];
    const TEAL = '#00d4aa';
    const MUTED = '#f6d365';

    function visitColor(v) {{
        for (let i = CMAP.length - 1; i >= 0; i--)
            if (v >= CMAP[i][0]) return CMAP[i][1];
        return CMAP[0][1];
    }}

    function initExplorer() {{
        const s = EXP.stats || {{}};
        document.getElementById('rettiche-id').textContent = (s.rettiche || 0).toLocaleString();
        document.getElementById('total-tiles').textContent = (s.total_tiles || 0).toLocaleString();
        document.getElementById('feld-size').textContent = (s.feld_size || 0).toLocaleString();
        document.getElementById('new-today').textContent = s.new_today || 0;
        document.getElementById('new-week').textContent = s.new_week || 0;
        document.getElementById('feld-new-today').textContent = s.feld_new_today || 0;
        document.getElementById('feld-new-week').textContent = s.feld_new_week || 0;
        document.getElementById('total-km').textContent = Math.round(s.total_km || 0).toLocaleString();
        document.getElementById('total-hours').textContent = Math.round(s.total_time_hours || 0).toLocaleString();
        document.getElementById('total-acts').textContent = (s.total_activities || 0).toLocaleString();
        document.getElementById('week-km').textContent = Math.round(s.week_km || 0).toLocaleString();
        document.getElementById('week-hours').textContent = Math.round(s.week_time_hours || 0).toLocaleString();
        document.getElementById('week-acts').textContent = s.week_activities || 0;

        // Rider scores with toggle
        let scoreMode = 'alltime';
        function renderRiderScores() {{
            const rsEl = document.getElementById('rider-scores');
            const rs = EXP.rider_scores || [];
            const medals = ['🥇', '🥈', '🥉'];

            // Sort by current mode's score
            const sorted = [...rs].sort((a, b) => {{
                const sa = scoreMode === '30d' ? (b.score_30d || 0) : b.score;
                const sb = scoreMode === '30d' ? (a.score_30d || 0) : a.score;
                return sa - sb;
            }});

            rsEl.innerHTML = sorted.map((r, i) => {{
                const val = scoreMode === '30d' ? (r.score_30d || 0) : r.score;
                const prefix = scoreMode === '30d' && val > 0 ? '+' : '';
                const active = selectedRider === r.rider ? 'active' : '';
                return `<div class="rider-score-row ${{active}}" data-rider="${{r.rider}}" style="cursor:pointer;">
                    <span class="rs-rank">${{medals[i] || (i+1)}}</span>
                    <span class="rs-name">${{r.rider}}</span>
                    <span class="rs-score">${{prefix}}${{val.toLocaleString(undefined, {{minimumFractionDigits: 1, maximumFractionDigits: 1}})}}</span>
                </div>`;
            }}).join('');

            rsEl.querySelectorAll('.rider-score-row').forEach(row => {{
                row.addEventListener('click', () => {{
                    const rider = row.dataset.rider;
                    if (selectedRider === rider) {{
                        selectedRider = null;
                    }} else {{
                        selectedRider = rider;
                        selectedDate = null;
                        document.querySelectorAll('.daily-bar').forEach(b => b.classList.remove('active'));
                    }}
                    renderRiderScores();
                    drawTiles();
                }});
            }});
        }}
        renderRiderScores();

        document.querySelectorAll('[data-score]').forEach(btn => {{
            btn.addEventListener('click', () => {{
                document.querySelectorAll('[data-score]').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                scoreMode = btn.dataset.score;
                renderRiderScores();
            }});
        }});

        // Daily chart — clickable to highlight tiles from that day
        const dailyEl = document.getElementById('daily-chart');
        const daily = EXP.daily_new || [];
        if (daily.length > 0) {{
            const mx = Math.max(...daily.map(d => d.count), 1);
            dailyEl.innerHTML = daily.map((d, i) => {{
                const h = Math.max(2, (d.count / mx) * 100);
                return `<div class="daily-bar" style="height:${{h}}%" data-date="${{d.date}}" data-idx="${{i}}">
                    <div class="daily-bar-tooltip">${{d.date}}: ${{d.count}} tiles</div></div>`;
            }}).join('');

            dailyEl.querySelectorAll('.daily-bar').forEach(bar => {{
                bar.addEventListener('click', () => {{
                    const date = bar.dataset.date;
                    selectedRider = null;
                    renderRiderScores();
                    if (selectedDate === date) {{
                        selectedDate = null;
                        dailyEl.querySelectorAll('.daily-bar').forEach(b => b.classList.remove('active'));
                    }} else {{
                        selectedDate = date;
                        dailyEl.querySelectorAll('.daily-bar').forEach(b => b.classList.remove('active'));
                        bar.classList.add('active');
                    }}
                    drawTiles();
                }});
            }});
        }}

        // Map
        map = L.map('explorer-map', {{ center: [50.35, 8.5], zoom: 10, zoomControl: true }});
        L.tileLayer('https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
            attribution: '&copy; OSM &copy; CARTO', subdomains: 'abcd', maxZoom: 19,
        }}).addTo(map);

        drawTiles();

        document.querySelectorAll('.mode-switch button').forEach(btn => {{
            btn.addEventListener('click', () => {{
                document.querySelectorAll('.mode-switch button').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                currentMode = btn.dataset.mode;
                selectedDate = null;
                selectedRider = null;
                document.querySelectorAll('.daily-bar').forEach(b => b.classList.remove('active'));
                renderRiderScores();
                drawTiles();
            }});
        }});

        setTimeout(() => map.invalidateSize(), 200);
        window.addEventListener('resize', () => setTimeout(() => map.invalidateSize(), 100));
    }}

    function computeFeldBorder() {{
        // Find feld tiles that have a neighbor NOT in the feld
        const feldSet = new Set();
        const tiles = EXP.tiles || [];
        const tileMap = {{}};
        for (const t of tiles) {{
            const k = t.x + ',' + t.y;
            tileMap[k] = t;
            if (t.r) feldSet.add(k);
        }}

        const edges = []; // array of [[lat1,lng1],[lat2,lng2]]
        const nb = [[-1,0],[1,0],[0,-1],[0,1]];
        const zoom = EXP.zoom || 16;
        const n = 2 ** zoom;

        for (const t of tiles) {{
            if (!t.r) continue;
            for (const [dx, dy] of nb) {{
                const nk = (t.x+dx)+','+(t.y+dy);
                if (!feldSet.has(nk)) {{
                    // This edge is a border
                    const b = t.b; // [south, west, north, east]
                    if (dx === -1) edges.push([[b[0],b[1]],[b[2],b[1]]]); // left: west edge
                    if (dx === 1) edges.push([[b[0],b[3]],[b[2],b[3]]]); // right: east edge
                    if (dy === -1) edges.push([[b[2],b[1]],[b[2],b[3]]]); // north neighbor missing: north edge
                    if (dy === 1) edges.push([[b[0],b[1]],[b[0],b[3]]]); // south neighbor missing: south edge
                }}
            }}
        }}
        return edges;
    }}

    function drawTiles() {{
        tileLayers.forEach(l => map.removeLayer(l));
        tileLayers.length = 0;
        if (feldBorderLayer) {{ map.removeLayer(feldBorderLayer); feldBorderLayer = null; }}

        const tiles = EXP.tiles || [];
        if (tiles.length === 0) return;

        const renderer = L.canvas({{ padding: 0.5 }});
        const allBounds = [];
        const highlightBounds = [];

        for (const t of tiles) {{
            const bounds = [[t.b[0], t.b[1]], [t.b[2], t.b[3]]];
            let color, fillOpacity, weight, opacity;

            if (selectedRider) {{
                // Rider highlight mode: tiles this rider visited pop
                if (t.p && t.p.includes(selectedRider)) {{
                    color = TEAL; fillOpacity = 0.55; weight = 1.2; opacity = 0.8;
                }} else {{
                    color = '#333350'; fillOpacity = 0.15; weight = 0.3; opacity = 0.25;
                }}
            }} else if (selectedDate) {{
                // Date highlight mode: tiles discovered on selectedDate pop
                if (t.d === selectedDate) {{
                    color = TEAL; fillOpacity = 0.65; weight = 1.5; opacity = 0.9;
                }} else {{
                    color = '#333350'; fillOpacity = 0.15; weight = 0.3; opacity = 0.25;
                }}
            }} else if (currentMode === 'feld') {{
                if (t.r) {{
                    color = TEAL; fillOpacity = 0.4; weight = 0.8; opacity = 0.6;
                }} else {{
                    color = MUTED; fillOpacity = 0.5; weight = 0.5; opacity = 0.4;
                }}
            }} else {{
                if (t.n) {{
                    color = TEAL; fillOpacity = 0.55; weight = 1.5; opacity = 0.9;
                }} else {{
                    color = visitColor(t.v); fillOpacity = 0.4; weight = 0.5; opacity = 0.5;
                }}
            }}

            const rect = L.rectangle(bounds, {{
                color, fillColor: color, fillOpacity, weight, opacity, renderer,
            }}).addTo(map);

            let tooltipText = `${{t.v}}× visited`;
            if (selectedRider && t.p && t.p.includes(selectedRider)) {{
                tooltipText = `${{selectedRider}}'s tile (${{t.v}}× total)`;
            }} else if (selectedDate && t.d === selectedDate) {{
                tooltipText = `New on ${{t.d}} (${{t.v}}× total)`;
            }}

            rect.bindTooltip(tooltipText, {{
                sticky: true, className: 'rider-marker-label',
                direction: 'top', offset: [0, -5],
            }});

            tileLayers.push(rect);
            allBounds.push(bounds[0], bounds[1]);
            if ((selectedDate && t.d === selectedDate) ||
                (selectedRider && t.p && t.p.includes(selectedRider))) {{
                highlightBounds.push(bounds[0], bounds[1]);
            }}
        }}

        // Draw feld border only in feld mode
        if (!selectedDate && !selectedRider && currentMode === 'feld') {{
            const edges = computeFeldBorder();
            if (edges.length > 0) {{
                feldBorderLayer = L.layerGroup();
                for (const e of edges) {{
                    L.polyline(e, {{
                        color: TEAL, weight: 2.5, opacity: 0.8,
                    }}).addTo(feldBorderLayer);
                }}
                feldBorderLayer.addTo(map);
            }}
        }}

        // Fit to highlighted tiles, or all tiles on first load
        if (highlightBounds.length > 0) {{
            map.fitBounds(L.latLngBounds(highlightBounds), {{ padding: [40, 40] }});
        }} else if (allBounds.length > 0 && !selectedDate && !selectedRider) {{
            map.fitBounds(L.latLngBounds(allBounds), {{ padding: [30, 30] }});
        }}
    }}

    document.addEventListener('DOMContentLoaded', initExplorer);
    </script>
    <script>
    (function () {{
        function setupExplorerSidebar() {{
            const sidebar = document.getElementById('explorer-sidebar');
            const overlay = document.getElementById('explorer-sidebar-overlay');
            const btn = document.getElementById('explorer-sidebar-toggle-btn');
            if (!btn || !overlay || !sidebar) return;
            btn.addEventListener('click', function () {{
                sidebar.classList.toggle('open');
                overlay.classList.toggle('active');
            }});
            overlay.addEventListener('click', function () {{
                sidebar.classList.remove('open');
                overlay.classList.remove('active');
            }});
        }}
        document.addEventListener('DOMContentLoaded', setupExplorerSidebar);
    }})();
    </script>
{_shared_mobile_js()}
</body>
</html>'''

    out_path = os.path.join(FRONTEND_DIR, 'explorer.html')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)
    size_kb = os.path.getsize(out_path) / 1024
    print(f"  Written {out_path} ({size_kb:.0f} KB)")


def build_riders_html(rider_stats_data, site_config, explorer_data=None):
    """Build the Die Rettiche page: pivot table + bar chart."""
    if not rider_stats_data:
        rider_stats_data = {'riders': []}

    # Override rider rettiche scores with explorer's scores for consistency
    if explorer_data and 'rider_scores' in explorer_data:
        explorer_scores = {s['rider']: s for s in explorer_data['rider_scores']}
        for r in rider_stats_data['riders']:
            es = explorer_scores.get(r['name'], {})
            r['rettiche'] = es.get('score', r.get('rettiche', 0))
            r['rettiche_30d'] = es.get('score_30d', r.get('rettiche_30d', 0))

    css = _read_text(os.path.join(FRONTEND_DIR, 'css', 'style.css'))
    riders_json = json.dumps(rider_stats_data, separators=(',', ':'))

    frame_colors = {
        'cinelli': '#ff6600', 'orbea': '#cfb53b', 'speedster': '#888888',
        'red': '#8b0000', 'blue': '#00387b', 'green': '#065000',
        'purple': '#7030a0', 'orange': '#843c0c', 'navyblue': '#203864',
        'black': '#333333', 'default': '#646464',
    }
    frame_colors_json = json.dumps(frame_colors)

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
    <title>ReTtiCh — Die Rettiche</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <script src="https://cdn.plot.ly/plotly-2.35.0.min.js"></script>
    <style>
{css}
.riders-page {{
    padding: 24px 32px;
    overflow-y: auto;
    height: calc(100vh - var(--topnav-height));
}}
.riders-header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 20px;
}}
.riders-header h1 {{
    font-size: 26px; font-weight: 800; letter-spacing: -0.5px;
}}
.riders-toggle {{
    display: flex; gap: 2px; background: var(--bg-tertiary);
    border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 3px;
}}
.riders-toggle button {{
    padding: 7px 14px; background: transparent; border: none; border-radius: 4px;
    color: var(--text-secondary); font-family: var(--font-display); font-size: 12px;
    font-weight: 600; cursor: pointer; transition: all 0.15s;
}}
.riders-toggle button:hover {{ color: var(--text-primary); }}
.riders-toggle button.active {{ background: var(--accent); color: #fff; }}

.riders-content {{
    display: flex;
    gap: 20px;
    align-items: flex-start;
}}
.riders-table-wrap {{
    flex: 1;
    min-width: 0;
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    overflow: hidden;
}}
.riders-chart-wrap {{
    width: 400px;
    flex-shrink: 0;
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    padding: 12px;
}}
#riders-chart {{
    width: 100%;
    height: 360px;
}}

.riders-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
}}
.riders-table th {{
    text-align: right;
    font-weight: 600;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--text-muted);
    padding: 10px 12px;
    border-bottom: 1px solid var(--border);
    cursor: pointer;
    transition: color 0.15s;
    white-space: nowrap;
    user-select: none;
}}
.riders-table th:first-child {{
    text-align: left;
}}
.riders-table th:hover {{
    color: var(--text-primary);
}}
.riders-table th.active {{
    color: var(--accent);
    border-bottom: 2px solid var(--accent);
}}
.riders-table th .sort-arrow {{
    font-size: 9px;
    margin-left: 3px;
    opacity: 0.5;
}}
.riders-table th.active .sort-arrow {{
    opacity: 1;
}}
.riders-table td {{
    padding: 10px 12px;
    border-bottom: 1px solid rgba(42, 47, 69, 0.4);
    text-align: right;
    font-family: var(--font-mono);
    font-size: 13px;
}}
.riders-table td:first-child {{
    text-align: left;
    font-family: var(--font-display);
    font-weight: 600;
}}
.riders-table tr:hover {{
    background: var(--bg-hover);
}}
.rider-name-cell {{
    display: flex;
    align-items: center;
    gap: 8px;
}}
.rider-dot {{
    width: 10px;
    height: 10px;
    border-radius: 50%;
    flex-shrink: 0;
}}
    </style>
</head>
<body>
    <div id="app">
{_topnav_html('riders')}

        <div class="riders-page">
            <div class="riders-header">
                <h1>🥕 Die Rettiche</h1>
                <div class="riders-toggle">
                    <button class="active" data-period="alltime">All Time</button>
                    <button data-period="30d">Last 30 Days</button>
                </div>
            </div>
            <div class="riders-content">
                <div class="riders-table-wrap">
                    <table class="riders-table" id="riders-table">
                        <thead><tr id="table-header"></tr></thead>
                        <tbody id="table-body"></tbody>
                    </table>
                </div>
                <div class="riders-chart-wrap">
                    <div id="riders-chart"></div>
                </div>
            </div>
        </div>
    </div>

    <script>
    const DATA = {riders_json};
    const FRAME_COLORS = {frame_colors_json};
    let period = 'alltime';
    let selectedCol = 'rettiche';
    let sortDir = -1; // -1 = desc

const COLUMNS = {{
        rettiche:   {{ label: 'Rettiche',      unit: '',   allKey: 'rettiche',   thirtyKey: 'rettiche_30d',   fmt: v => v.toLocaleString(undefined, {{minimumFractionDigits: 1, maximumFractionDigits: 1}}) }},
        tiles:      {{ label: 'Beete',          unit: '',   allKey: 'total_tiles', thirtyKey: 'tiles_30d',     fmt: v => v.toLocaleString() }},
        feld_size:  {{ label: 'Acker Größe',    unit: '',   allKey: 'feld_size',   thirtyKey: 'feld_size_30d', fmt: v => v.toLocaleString(), prefix30d: true }},
        km:         {{ label: 'km',             unit: 'km', allKey: 'total_km',    thirtyKey: 'km_30d',        fmt: v => Math.round(v).toLocaleString() }},
        elev:       {{ label: 'Elevation',      unit: 'm',  allKey: 'total_elev',  thirtyKey: 'elev_30d',      fmt: v => Math.round(v).toLocaleString() }},
        hours:      {{ label: 'Hours',          unit: 'h',  allKey: 'total_hours', thirtyKey: 'hours_30d',     fmt: v => v.toLocaleString(undefined, {{minimumFractionDigits: 1, maximumFractionDigits: 1}}) }},
        acts:       {{ label: 'Activities',     unit: '',   allKey: 'total_acts',  thirtyKey: 'acts_30d',      fmt: v => v.toLocaleString() }},
    }};

    function getVal(rider, colKey) {{
        const col = COLUMNS[colKey];
        const key = period === '30d' ? col.thirtyKey : col.allKey;
        return rider[key] || 0;
    }}

    function render() {{
        const riders = DATA.riders || [];

        // Sort
        const sorted = [...riders].sort((a, b) => sortDir * (getVal(a, selectedCol) - getVal(b, selectedCol)));

        // Header
        const headerEl = document.getElementById('table-header');
        headerEl.innerHTML = '<th>Rider</th>' + Object.entries(COLUMNS).map(([key, col]) => {{
            const active = key === selectedCol ? 'active' : '';
            const arrow = key === selectedCol ? (sortDir < 0 ? '▼' : '▲') : '';
            return `<th class="${{active}}" data-col="${{key}}">${{col.label}} <span class="sort-arrow">${{arrow}}</span></th>`;
        }}).join('');

        // Body
        const bodyEl = document.getElementById('table-body');
        bodyEl.innerHTML = sorted.map(r => {{
            const color = FRAME_COLORS[r.frame] || FRAME_COLORS['default'];
            let cells = `<td><div class="rider-name-cell"><div class="rider-dot" style="background:${{color}}"></div>${{r.name}}</div></td>`;
            for (const [key, col] of Object.entries(COLUMNS)) {{
                const val = getVal(r, key);
                let display = col.fmt(Math.abs(val));
                if (period === '30d' && col.prefix30d && val > 0) display = '+' + display;
                if (period === '30d' && col.prefix30d && val < 0) display = '-' + display;
                cells += `<td>${{display}}</td>`;
            }}
            return `<tr>${{cells}}</tr>`;
        }}).join('');

        // Header click handlers
        headerEl.querySelectorAll('th[data-col]').forEach(th => {{
            th.addEventListener('click', () => {{
                const col = th.dataset.col;
                if (col === selectedCol) {{
                    sortDir *= -1;
                }} else {{
                    selectedCol = col;
                    sortDir = -1;
                }}
                render();
            }});
        }});

        // Bar chart
        const col = COLUMNS[selectedCol];
        const chartRiders = sorted;
        const names = chartRiders.map(r => r.name);
        const values = chartRiders.map(r => getVal(r, selectedCol));
        const colors = chartRiders.map(r => FRAME_COLORS[r.frame] || FRAME_COLORS['default']);

        Plotly.react('riders-chart', [{{
            x: names,
            y: values,
            type: 'bar',
            marker: {{ color: colors, opacity: 0.8 }},
            hovertemplate: '%{{x}}: %{{y:.1f}}<extra></extra>',
        }}], {{
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: '#151821',
            font: {{ family: 'Outfit, sans-serif', color: '#e8eaf0', size: 12 }},
            margin: {{ l: 50, r: 16, t: 32, b: 40 }},
            title: {{
                text: col.label + (period === '30d' ? ' (30d)' : ''),
                font: {{ size: 14 }},
            }},
            yaxis: {{
                gridcolor: '#2a2f45',
                zerolinecolor: '#2a2f45',
            }},
            xaxis: {{
                gridcolor: '#2a2f45',
            }},
        }}, {{
            responsive: true,
            displayModeBar: false,
        }});
    }}

    document.addEventListener('DOMContentLoaded', () => {{
        render();
        document.querySelectorAll('.riders-toggle button').forEach(btn => {{
            btn.addEventListener('click', () => {{
                document.querySelectorAll('.riders-toggle button').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                period = btn.dataset.period;
                render();
            }});
        }});
    }});
    </script>
{_shared_mobile_js()}
</body>
</html>'''

    out_path = os.path.join(FRONTEND_DIR, 'riders.html')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)
    size_kb = os.path.getsize(out_path) / 1024
    print(f"  Written {out_path} ({size_kb:.0f} KB)")



# --- Mobile helpers ---

def _topnav_html(active_tab):
    """Return the shared topnav HTML with view-toggle button.
    active_tab: 'map' | 'commutes' | 'explorer' | 'riders'
    """
    def _tab(href, full, short, key):
        cls = 'tab active' if key == active_tab else 'tab'
        return (f'<a href="{href}" class="{cls}">'
                f'<span class="tab-full">{full}</span>'
                f'<span class="tab-short">{short}</span>'
                f'</a>')

    tabs = (
        _tab('index.html', 'Map',          'Map',   'map')
        + _tab('commutes.html', 'Commutes', 'Rides', 'commutes')
        + _tab('explorer.html', 'Explorer', 'Tiles', 'explorer')
        + _tab('riders.html',   'Die Rettiche', 'Stats', 'riders')
    )
    return f'''        <nav class="topnav">
            <div class="topnav-brand">
                <span class="brand-icon">🥕</span>
                <span class="brand-name">ReTtiCh</span>
            </div>
            <div class="topnav-tabs">{tabs}</div>
            <div class="topnav-spacer"></div>
            <button class="view-toggle-btn" id="view-toggle-btn" title="Toggle mobile/desktop view">📱</button>
        </nav>'''


def _shared_mobile_js():
    """Return an inline <script> block for view-mode detection + toggle button."""
    return '''<script>
(function () {
    var KEY = 'rettich-view';
    var btn = document.getElementById('view-toggle-btn');
    function isMobileScreen() { return window.innerWidth <= 768; }
    function getMode() { return localStorage.getItem(KEY); }
    function isEffectiveMobile() {
        var m = getMode();
        if (m === 'desktop') return false;
        if (m === 'mobile')  return true;
        return isMobileScreen();
    }
    function applyView() {
        if (isEffectiveMobile()) {
            document.body.classList.add('mobile-view');
        } else {
            document.body.classList.remove('mobile-view');
        }
        if (btn) {
            var m = getMode();
            btn.textContent = (m === 'desktop') ? '📱' : (m === 'mobile') ? '🖥' : (isMobileScreen() ? '🖥' : '📱');
            btn.title = isEffectiveMobile() ? 'Switch to desktop view' : 'Switch to mobile view';
        }
    }
    if (btn) {
        btn.addEventListener('click', function () {
            var m = getMode();
            if (!m)            { localStorage.setItem(KEY, isMobileScreen() ? 'desktop' : 'mobile'); }
            else if (m === 'mobile')  { localStorage.setItem(KEY, 'desktop'); }
            else               { localStorage.removeItem(KEY); }
            applyView();
        });
    }
    applyView();
    window.addEventListener('resize', applyView);
    window.applyRettichView = applyView;

    // Set --app-vh so CSS can use actual visible viewport height on all browsers
    // (100dvh is unreliable on older Android Chrome; window.innerHeight always correct)
    function setAppVh() {
        document.documentElement.style.setProperty('--app-vh', window.innerHeight + 'px');
    }
    setAppVh();
    window.addEventListener('resize', setAppVh);
})();
</script>'''


# --- Helpers ---

def _get_new_activity_ids(conn, data_dir):
    """Return IDs of activities in the DB that have no exported .js file yet."""
    acts_dir = os.path.join(data_dir, 'activities')
    existing = set()
    if os.path.exists(acts_dir):
        for fname in os.listdir(acts_dir):
            if fname.endswith('.js'):
                try:
                    existing.add(int(fname[:-3]))
                except ValueError:
                    pass
    all_ids = {row['id'] for row in conn.execute("SELECT id FROM activities").fetchall()}
    return all_ids - existing


def _get_dates_for_ids(conn, activity_ids):
    """Return the unique dates for a set of activity IDs."""
    if not activity_ids:
        return []
    placeholders = ','.join('?' * len(activity_ids))
    rows = conn.execute(
        f"SELECT DISTINCT date FROM activities WHERE id IN ({placeholders})",
        list(activity_ids)
    ).fetchall()
    return [r['date'] for r in rows]


def _has_new_rides(conn, activity_ids):
    """Return True if any of the given IDs is a Ride activity."""
    if not activity_ids:
        return False
    placeholders = ','.join('?' * len(activity_ids))
    return conn.execute(
        f"SELECT 1 FROM activities WHERE id IN ({placeholders}) AND activity_type='Ride' LIMIT 1",
        list(activity_ids)
    ).fetchone() is not None


def _load_js_data(js_path, var_name):
    """Load data previously written as window.VAR_NAME = {...};  Returns dict or None."""
    if not os.path.exists(js_path):
        return None
    try:
        text = _read_text(js_path)
        prefix = f'window.{var_name}='
        if text.startswith(prefix):
            return json.loads(text[len(prefix):].rstrip(';'))
    except Exception:
        pass
    return None


def _simple_hash(s):
    h = 0
    for c in s:
        h = ((h << 5) - h + ord(c)) & 0xFFFFFFFF
    return h


def _read_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _read_text(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


if __name__ == '__main__':
    main()