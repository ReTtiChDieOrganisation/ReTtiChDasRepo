#!/usr/bin/env python3
"""Build frontend: compute groups, export JSON, and produce a self-contained index.html."""

import json
import os
import sys
import glob

sys.path.insert(0, os.path.dirname(__file__))

from backend import database as db
from backend.grouping import compute_groups
from backend.export import export_all

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, 'frontend')
DATA_DIR = os.path.join(FRONTEND_DIR, 'data')


def main():
    db_path = os.path.join(BASE_DIR, 'rettich.db')
    if not os.path.exists(db_path):
        print("Error: rettich.db not found. Run sync.py first.")
        sys.exit(1)

    conn = db.get_connection()

    print("=== ReTtiCh Build ===")

    # Step 1: Compute groups
    print("Computing ride groups...")
    compute_groups(conn)

    # Step 2: Export data as JSON files (also used by the server mode later)
    print("Exporting data for frontend...")
    export_all(conn, DATA_DIR)
    conn.close()

    # Step 3: Read site password from config
    config_path = os.path.join(BASE_DIR, 'config', 'config.json')
    site_password = 'rettich'
    if os.path.exists(config_path):
        with open(config_path) as f:
            config = json.load(f)
            site_password = config.get('site_password', site_password)

    site_config = {'password_hash': _simple_hash(site_password)}
    _write_json(os.path.join(DATA_DIR, 'site_config.json'), site_config)

    # Step 4: Build self-contained index.html
    print("Building self-contained index.html...")
    build_self_contained_html(site_config)

    print(f"\nDone! Open {os.path.join(FRONTEND_DIR, 'index.html')} in your browser.")


def build_self_contained_html(site_config):
    """Read all JSON data + JS/CSS and produce a single index.html."""

    # --- Load all exported data ---
    riders = _read_json(os.path.join(DATA_DIR, 'riders.json'))
    groups = _read_json(os.path.join(DATA_DIR, 'groups.json'))
    activities_index = _read_json(os.path.join(DATA_DIR, 'activities_index.json'))
    shared_segments = _read_json(os.path.join(DATA_DIR, 'shared_segments.json'))

    # Load individual activity files
    activities = {}
    activities_dir = os.path.join(DATA_DIR, 'activities')
    if os.path.isdir(activities_dir):
        for fpath in glob.glob(os.path.join(activities_dir, '*.json')):
            aid = os.path.splitext(os.path.basename(fpath))[0]
            activities[aid] = _read_json(fpath)

    embedded_data = {
        'riders': riders,
        'groups': groups,
        'activities_index': activities_index,
        'shared_segments': shared_segments,
        'site_config': site_config,
        'activities': activities,
    }
    embedded_json = json.dumps(embedded_data, separators=(',', ':'))

    # --- Load CSS and JS source files ---
    css = _read_text(os.path.join(FRONTEND_DIR, 'css', 'style.css'))

    js_files = ['icons.js', 'map.js', 'timeline.js', 'segments.js', 'stats.js', 'app.js']
    js_parts = []
    for name in js_files:
        js_parts.append(f'// === {name} ===')
        js_parts.append(_read_text(os.path.join(FRONTEND_DIR, 'js', name)))
    js_all = '\n'.join(js_parts)

    # --- Assemble HTML ---
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
                <a href="#" class="tab" id="tab-commutes" onclick="alert('Commute analysis page — coming soon with Plotly charts')">Commutes</a>
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

    <!-- Embedded data (so file:// works without a server) -->
    <script>
    window.RETTICH_DATA = {embedded_json};
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


# --- Helpers ---

def _simple_hash(s):
    """Very simple hash for the weak password gate. NOT cryptographic."""
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


def _write_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, separators=(',', ':'))


if __name__ == '__main__':
    main()
