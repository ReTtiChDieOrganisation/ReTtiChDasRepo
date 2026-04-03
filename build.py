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
from backend.grouping import compute_groups
from backend.export import export_all

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, 'frontend')
DATA_DIR = os.path.join(FRONTEND_DIR, 'data')


def main():
    full = '--full' in sys.argv

    db_path = os.path.join(BASE_DIR, 'rettich.db')
    if not os.path.exists(db_path):
        print("Error: rettich.db not found. Run sync.py first.")
        sys.exit(1)

    conn = db.get_connection()

    print("=== ReTtiCh Build ===")
    if full:
        print("  Mode: FULL rebuild")
    else:
        print("  Mode: incremental (use --full to rebuild all)")

    # Step 1: Compute groups
    print("Computing ride groups...")
    compute_groups(conn)

    # Step 2: Export data (activities as .js files, metadata as .json)
    print("Exporting data for frontend...")
    export_all(conn, DATA_DIR, full=full)

    # Step 2b: Export commute data
    print("Exporting commute data...")
    from backend.commute_export import export_commute_data
    config_path = os.path.join(BASE_DIR, 'config', 'config.json')
    config = {}
    if os.path.exists(config_path):
        with open(config_path) as f:
            config = json.load(f)
    commute_config = config.get('commute', {})
    commute_data = export_commute_data(conn, DATA_DIR, commute_config)

    # Step 2c: Export explorer tile data
    print("Exporting explorer data...")
    from backend.explorer_export import export_explorer_data
    explorer_config = config.get('explorer', {})
    explorer_data = export_explorer_data(conn, DATA_DIR, explorer_config)

    # Step 2d: Export per-rider statistics
    print("Exporting rider statistics...")
    from backend.rider_stats_export import export_rider_stats
    rider_stats_data = export_rider_stats(conn, DATA_DIR, explorer_config)

    conn.close()

    # Step 3: Read site password from config
    site_password = config.get('site_password', 'rettich')

    site_config = {'password_hash': _simple_hash(site_password)}

    # Step 4: Build index.html (only metadata embedded, activities loaded on demand)
    print("Building index.html...")
    build_html(site_config)

    # Step 5: Build commutes.html
    print("Building commutes.html...")
    build_commutes_html(commute_data, site_config)

    # Step 6: Build explorer.html
    print("Building explorer.html...")
    build_explorer_html(explorer_data, site_config)

    # Step 7: Build riders.html
    print("Building riders.html...")
    build_riders_html(rider_stats_data, site_config)

    print(f"\nDone! Open {os.path.join(FRONTEND_DIR, 'index.html')} in your browser.")


def build_html(site_config):
    """Build index.html with only lightweight metadata embedded.
    
    Activity data lives in separate .js files under data/activities/
    and is loaded on demand via <script> tag injection.
    """

    # Load metadata (small)
    riders = _read_json(os.path.join(DATA_DIR, 'riders.json'))
    groups = _read_json(os.path.join(DATA_DIR, 'groups.json'))
    activities_index = _read_json(os.path.join(DATA_DIR, 'activities_index.json'))
    shared_segments = _read_json(os.path.join(DATA_DIR, 'shared_segments.json'))

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
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
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
        <!-- Top Navigation -->
        <nav class="topnav">
            <div class="topnav-brand">
                <span class="brand-icon">🥕</span>
                <span class="brand-name">ReTtiCh</span>
            </div>
            <div class="topnav-tabs">
                <a href="#" class="tab active" id="tab-map">Map</a>
                <a href="commutes.html" class="tab" id="tab-commutes">Commutes</a>
                <a href="explorer.html" class="tab" id="tab-explorer">Explorer</a>
                <a href="riders.html" class="tab" id="tab-riders">Die Rettiche</a>
            </div>
            <div class="topnav-spacer"></div>
        </nav>

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

                <div class="sidebar-section" id="riders-section">
                    <h3 class="section-title">Riders</h3>
                    <div id="riders-list" class="riders-list"></div>
                </div>
            </aside>

            <!-- Map + Controls -->
            <div class="map-area">
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
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
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
        <nav class="topnav">
            <div class="topnav-brand">
                <span class="brand-icon">🥕</span>
                <span class="brand-name">ReTtiCh</span>
            </div>
            <div class="topnav-tabs">
                <a href="index.html" class="tab">Map</a>
                <a href="commutes.html" class="tab active">Commutes</a>
                <a href="explorer.html" class="tab">Explorer</a>
                <a href="riders.html" class="tab">Die Rettiche</a>
            </div>
            <div class="topnav-spacer"></div>
        </nav>

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
                <div class="stat-value">${{s.rettich_count.toLocaleString()}} Rettiche</div>
                <div class="stat-label">${{s.rettich_kg.toLocaleString()}} kg Rettich</div>
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
</body>
</html>'''

    out_path = os.path.join(FRONTEND_DIR, 'commutes.html')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)
    size_kb = os.path.getsize(out_path) / 1024
    print(f"  Written {out_path} ({size_kb:.0f} KB)")


def build_explorer_html(explorer_data, site_config):
    """Build the tile explorer page with heatmap, Rettich Revier, per-rider scores."""
    if not explorer_data:
        explorer_data = {'tiles': [], 'stats': {}, 'daily_new': [], 'rider_scores': [], 'zoom': 16, 'max_visits': 1}

    css = _read_text(os.path.join(FRONTEND_DIR, 'css', 'style.css'))
    explorer_json = json.dumps(explorer_data, separators=(',', ':'))

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ReTtiCh — Explorer</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
{css}
.explorer-layout {{ display: flex; height: calc(100vh - var(--topnav-height)); }}
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
        <nav class="topnav">
            <div class="topnav-brand">
                <span class="brand-icon">🥕</span>
                <span class="brand-name">ReTtiCh</span>
            </div>
            <div class="topnav-tabs">
                <a href="index.html" class="tab">Map</a>
                <a href="commutes.html" class="tab">Commutes</a>
                <a href="explorer.html" class="tab active">Explorer</a>
                <a href="riders.html" class="tab">Die Rettiche</a>
            </div>
            <div class="topnav-spacer"></div>
        </nav>

        <div class="explorer-layout">
            <aside class="explorer-sidebar">
                <div class="mode-switch">
                    <button class="active" data-mode="heatmap">All Tiles</button>
                    <button data-mode="revier">Rettich Revier</button>
                </div>

                <div class="exp-section">
                    <div class="exp-section-title">Scores</div>
                    <div class="exp-stats-grid">
                        <div class="exp-stat wide highlight">
                            <div class="exp-val" id="rettich-score">0</div>
                            <div class="exp-lbl">🥕 Rettich Score</div>
                        </div>
                    </div>
                </div>

                <div class="exp-section">
                    <div class="exp-section-title">Tiles</div>
                    <div class="exp-stats-grid">
                        <div class="exp-stat">
                            <div class="exp-val" id="total-tiles">0</div>
                            <div class="exp-lbl">Total Tiles</div>
                        </div>
                        <div class="exp-stat">
                            <div class="exp-val teal" id="revier-size">0</div>
                            <div class="exp-lbl">🏠 Revier Size</div>
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
                            <div class="exp-val teal" id="revier-new-today">0</div>
                            <div class="exp-lbl">Revier + Today</div>
                        </div>
                        <div class="exp-stat">
                            <div class="exp-val teal" id="revier-new-week">0</div>
                            <div class="exp-lbl">Revier + Week</div>
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
                        <div class="exp-section-title" style="margin-bottom:0">Explorer Scores</div>
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
    let revierBorderLayer = null;

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
        document.getElementById('rettich-score').textContent = (s.rettich_score || 0).toLocaleString();
        document.getElementById('total-tiles').textContent = (s.total_tiles || 0).toLocaleString();
        document.getElementById('revier-size').textContent = (s.revier_size || 0).toLocaleString();
        document.getElementById('new-today').textContent = s.new_today || 0;
        document.getElementById('new-week').textContent = s.new_week || 0;
        document.getElementById('revier-new-today').textContent = s.revier_new_today || 0;
        document.getElementById('revier-new-week').textContent = s.revier_new_week || 0;
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
                    <span class="rs-score">${{prefix}}${{val.toFixed(1)}}</span>
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

    function computeRevierBorder() {{
        // Find revier tiles that have a neighbor NOT in the revier
        const revierSet = new Set();
        const tiles = EXP.tiles || [];
        const tileMap = {{}};
        for (const t of tiles) {{
            const k = t.x + ',' + t.y;
            tileMap[k] = t;
            if (t.r) revierSet.add(k);
        }}

        const edges = []; // array of [[lat1,lng1],[lat2,lng2]]
        const nb = [[-1,0],[1,0],[0,-1],[0,1]];
        const zoom = EXP.zoom || 16;
        const n = 2 ** zoom;

        for (const t of tiles) {{
            if (!t.r) continue;
            for (const [dx, dy] of nb) {{
                const nk = (t.x+dx)+','+(t.y+dy);
                if (!revierSet.has(nk)) {{
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
        if (revierBorderLayer) {{ map.removeLayer(revierBorderLayer); revierBorderLayer = null; }}

        const tiles = EXP.tiles || [];
        if (tiles.length === 0) return;

        const renderer = L.canvas({{ padding: 0.5 }});
        const allBounds = [];

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
            }} else if (currentMode === 'revier') {{
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
        }}

        // Draw revier border only in revier mode
        if (!selectedDate && !selectedRider && currentMode === 'revier') {{
            const edges = computeRevierBorder();
            if (edges.length > 0) {{
                revierBorderLayer = L.layerGroup();
                for (const e of edges) {{
                    L.polyline(e, {{
                        color: TEAL, weight: 2.5, opacity: 0.8,
                    }}).addTo(revierBorderLayer);
                }}
                revierBorderLayer.addTo(map);
            }}
        }}

        if (allBounds.length > 0 && !selectedDate && !selectedRider) {{
            map.fitBounds(L.latLngBounds(allBounds), {{ padding: [30, 30] }});
        }}
    }}

    document.addEventListener('DOMContentLoaded', initExplorer);
    </script>
</body>
</html>'''

    out_path = os.path.join(FRONTEND_DIR, 'explorer.html')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)
    size_kb = os.path.getsize(out_path) / 1024
    print(f"  Written {out_path} ({size_kb:.0f} KB)")


def build_riders_html(rider_stats_data, site_config):
    """Build the Die Rettiche rider stats page."""
    if not rider_stats_data:
        rider_stats_data = {'riders': []}

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
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ReTtiCh — Die Rettiche</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
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
    margin-bottom: 24px;
}}
.riders-header h1 {{
    font-size: 26px;
    font-weight: 800;
    letter-spacing: -0.5px;
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

.rider-cards {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 16px;
}}
.rider-card {{
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    overflow: hidden;
    transition: border-color 0.2s;
}}
.rider-card:hover {{
    border-color: var(--border-light);
}}
.rider-card-header {{
    padding: 20px 20px 14px;
    display: flex;
    align-items: center;
    gap: 14px;
    border-bottom: 1px solid var(--border);
}}
.rider-card-color {{
    width: 8px;
    height: 48px;
    border-radius: 4px;
    flex-shrink: 0;
}}
.rider-card-name {{
    font-size: 20px;
    font-weight: 700;
    letter-spacing: -0.3px;
}}
.rider-card-frame {{
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--text-muted);
    text-transform: uppercase;
    margin-top: 2px;
}}
.rider-card-body {{
    padding: 16px 20px 20px;
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 12px;
}}
.rc-stat {{
    text-align: center;
}}
.rc-stat-val {{
    font-family: var(--font-mono);
    font-size: 18px;
    font-weight: 700;
    color: var(--text-primary);
}}
.rc-stat-val.accent {{ color: var(--accent); }}
.rc-stat-val.teal {{ color: #00d4aa; }}
.rc-stat-lbl {{
    font-size: 10px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-top: 2px;
}}
.rc-divider {{
    grid-column: span 3;
    height: 1px;
    background: var(--border);
}}
    </style>
</head>
<body>
    <div id="app">
        <nav class="topnav">
            <div class="topnav-brand">
                <span class="brand-icon">🥕</span>
                <span class="brand-name">ReTtiCh</span>
            </div>
            <div class="topnav-tabs">
                <a href="index.html" class="tab">Map</a>
                <a href="commutes.html" class="tab">Commutes</a>
                <a href="explorer.html" class="tab">Explorer</a>
                <a href="riders.html" class="tab active">Die Rettiche</a>
            </div>
            <div class="topnav-spacer"></div>
        </nav>

        <div class="riders-page">
            <div class="riders-header">
                <h1>🥕 Die Rettiche</h1>
                <div class="riders-toggle">
                    <button class="active" data-period="alltime">All Time</button>
                    <button data-period="30d">Last 30 Days</button>
                </div>
            </div>
            <div class="rider-cards" id="rider-cards"></div>
        </div>
    </div>

    <script>
    const DATA = {riders_json};
    const FRAME_COLORS = {frame_colors_json};
    let period = 'alltime';

    function renderCards() {{
        const el = document.getElementById('rider-cards');
        const riders = DATA.riders || [];

        // Sort: by explorer score in current period
        const sorted = [...riders].sort((a, b) => {{
            if (period === '30d') return (b.explorer_score_30d || 0) - (a.explorer_score_30d || 0);
            return (b.explorer_score || 0) - (a.explorer_score || 0);
        }});

        el.innerHTML = sorted.map(r => {{
            const color = FRAME_COLORS[r.frame] || FRAME_COLORS['default'];
            const km = period === '30d' ? r.km_30d : r.total_km;
            const elev = period === '30d' ? r.elev_30d : r.total_elev;
            const hours = period === '30d' ? r.hours_30d : r.total_hours;
            const acts = period === '30d' ? r.acts_30d : r.total_acts;
            const score = period === '30d' ? r.explorer_score_30d : r.explorer_score;
            const tiles = period === '30d' ? r.tiles_30d : r.total_tiles;
            const scorePrefix = period === '30d' && score > 0 ? '+' : '';

            return `<div class="rider-card">
                <div class="rider-card-header">
                    <div class="rider-card-color" style="background:${{color}}"></div>
                    <div>
                        <div class="rider-card-name">${{r.name}}</div>
                        <div class="rider-card-frame">${{r.frame}}</div>
                    </div>
                </div>
                <div class="rider-card-body">
                    <div class="rc-stat">
                        <div class="rc-stat-val accent">${{scorePrefix}}${{score.toFixed(1)}}</div>
                        <div class="rc-stat-lbl">Explorer Score</div>
                    </div>
                    <div class="rc-stat">
                        <div class="rc-stat-val teal">${{tiles.toLocaleString()}}</div>
                        <div class="rc-stat-lbl">${{period === '30d' ? 'New Tiles' : 'Tiles'}}</div>
                    </div>
                    <div class="rc-stat">
                        <div class="rc-stat-val">${{r.revier_size.toLocaleString()}}</div>
                        <div class="rc-stat-lbl">Revier</div>
                    </div>
                    <div class="rc-divider"></div>
                    <div class="rc-stat">
                        <div class="rc-stat-val">${{Math.round(km).toLocaleString()}}</div>
                        <div class="rc-stat-lbl">km</div>
                    </div>
                    <div class="rc-stat">
                        <div class="rc-stat-val">${{Math.round(elev).toLocaleString()}} m</div>
                        <div class="rc-stat-lbl">Elevation</div>
                    </div>
                    <div class="rc-stat">
                        <div class="rc-stat-val">${{Math.round(hours)}}</div>
                        <div class="rc-stat-lbl">Hours</div>
                    </div>
                    <div class="rc-divider"></div>
                    <div class="rc-stat" style="grid-column:span 3;">
                        <div class="rc-stat-val">${{acts}}</div>
                        <div class="rc-stat-lbl">Activities</div>
                    </div>
                </div>
            </div>`;
        }}).join('');
    }}

    document.addEventListener('DOMContentLoaded', () => {{
        renderCards();
        document.querySelectorAll('.riders-toggle button').forEach(btn => {{
            btn.addEventListener('click', () => {{
                document.querySelectorAll('.riders-toggle button').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                period = btn.dataset.period;
                renderCards();
            }});
        }});
    }});
    </script>
</body>
</html>'''

    out_path = os.path.join(FRONTEND_DIR, 'riders.html')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)
    size_kb = os.path.getsize(out_path) / 1024
    print(f"  Written {out_path} ({size_kb:.0f} KB)")


# --- Helpers ---

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