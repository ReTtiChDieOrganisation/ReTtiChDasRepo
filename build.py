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
                        <div class="pb-timeline-wrap">
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