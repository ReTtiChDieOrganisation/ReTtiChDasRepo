"""Per-rider statistics export for 'Die Rettiche' page.

Computes for each rider:
- Total/30d: km, elevation, time, activities
- Explorer score (all-time + 30d)
- Personal Feld (largest connected area of tiles they've visited)
"""

import json
import math
import os
from collections import defaultdict, deque
from datetime import datetime, timedelta
from backend import database as db


DEFAULT_ZOOM = 16


def lat_lon_to_tile(lat, lon, zoom):
    n = 2 ** zoom
    x = int((lon + 180.0) / 360.0 * n)
    lat_rad = math.radians(lat)
    y = int((1.0 - math.log(math.tan(lat_rad) + 1.0 / math.cos(lat_rad)) / math.pi) / 2.0 * n)
    return x, y


def find_largest_connected(tile_set):
    if not tile_set:
        return set()
    visited = set()
    largest = set()
    neighbors = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
    for start in tile_set:
        if start in visited:
            continue
        component = set()
        queue = deque([start])
        while queue:
            node = queue.popleft()
            if node in visited:
                continue
            visited.add(node)
            component.add(node)
            for dx, dy in neighbors:
                nb = (node[0] + dx, node[1] + dy)
                if nb in tile_set and nb not in visited:
                    queue.append(nb)
        if len(component) > len(largest):
            largest = component
    return largest


def harmonic(n):
    return sum(1.0 / k for k in range(1, n + 1))


def export_rider_stats(conn, output_dir, config=None):
    """Export per-rider statistics."""
    config = config or {}
    zoom = config.get('zoom', DEFAULT_ZOOM)

    thirty_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

    # Get all riders
    riders = db.get_all_riders(conn)

    # Get all non-virtual activities
    all_activities = conn.execute("""
        SELECT a.id, a.rider_name, a.date, a.elapsed_time, a.moving_time,
               a.distance, a.total_elevation_gain, a.activity_type
        FROM activities a
        WHERE a.activity_type != 'VirtualRide'
        ORDER BY a.start_epoch ASC
    """).fetchall()

    # Per-rider accumulators
    rider_data = {}
    for r in riders:
        rider_data[r['name']] = {
            'name': r['name'],
            'frame': r['frame'] or 'default',
            'total_km': 0, 'total_elev': 0, 'total_time_s': 0, 'total_acts': 0,
            'km_30d': 0, 'elev_30d': 0, 'time_30d_s': 0, 'acts_30d': 0,
        }

    # Per-rider tile tracking
    rider_tiles = defaultdict(set)  # rider -> set of (x,y)
    rider_tile_visits = defaultdict(lambda: defaultdict(int))  # rider -> {(x,y): count}
    rider_tile_visits_old = defaultdict(lambda: defaultdict(int))

    for act in all_activities:
        rn = act['rider_name']
        if rn not in rider_data:
            continue

        dist = act['distance'] or 0
        elev = act['total_elevation_gain'] or 0
        elapsed = act['elapsed_time'] or 0
        date = act['date']

        rd = rider_data[rn]
        rd['total_km'] += dist / 1000
        rd['total_elev'] += elev
        rd['total_time_s'] += elapsed
        rd['total_acts'] += 1

        if date >= thirty_ago:
            rd['km_30d'] += dist / 1000
            rd['elev_30d'] += elev
            rd['time_30d_s'] += elapsed
            rd['acts_30d'] += 1

        # Tile tracking
        stream = db.get_stream(conn, act['id'])
        if not stream or not stream['latlng_data']:
            continue
        latlng = json.loads(stream['latlng_data'])
        if not latlng:
            continue

        act_tiles = set()
        for point in latlng:
            act_tiles.add(lat_lon_to_tile(point[0], point[1], zoom))

        for key in act_tiles:
            rider_tiles[rn].add(key)
            rider_tile_visits[rn][key] += 1
            if date < thirty_ago:
                rider_tile_visits_old[rn][key] += 1

    # Compute per-rider explorer score and personal feld
    rider_stats_list = []
    for rn, rd in rider_data.items():
        # Explorer score: harmonic of personal visit counts
        score = sum(harmonic(v) for v in rider_tile_visits[rn].values())
        score_old = sum(harmonic(v) for v in rider_tile_visits_old[rn].values())
        score_30d = score - score_old

        # Personal feld (all-time and old for delta)
        personal_feld = find_largest_connected(rider_tiles[rn])
        old_tiles = {k for k in rider_tiles[rn] if rider_tile_visits_old[rn].get(k, 0) > 0}
        personal_feld_old = find_largest_connected(old_tiles)

        rider_stats_list.append({
            'name': rn,
            'frame': rd['frame'],
            'total_km': round(rd['total_km'], 1),
            'total_elev': round(rd['total_elev'], 0),
            'total_hours': round(rd['total_time_s'] / 3600, 1),
            'total_acts': rd['total_acts'],
            'total_tiles': len(rider_tiles[rn]),
            'rettiche': round(score, 1),
            'rettiche_30d': round(score_30d, 1),
            'feld_size': len(personal_feld),
            'feld_size_30d': len(personal_feld) - len(personal_feld_old),
            'km_30d': round(rd['km_30d'], 1),
            'elev_30d': round(rd['elev_30d'], 0),
            'hours_30d': round(rd['time_30d_s'] / 3600, 1),
            'acts_30d': rd['acts_30d'],
            'tiles_30d': sum(1 for k in rider_tiles[rn]
                           if rider_tile_visits_old[rn].get(k, 0) == 0),
        })

    # Sort by explorer score
    rider_stats_list.sort(key=lambda x: -x['rettiche'])

    data = {
        'riders': rider_stats_list,
    }

    js_path = os.path.join(output_dir, 'rider_stats.js')
    json_str = json.dumps(data, separators=(',', ':'))
    with open(js_path, 'w', encoding='utf-8') as f:
        f.write(f'window.RETTICH_RIDERS={json_str};')

    print(f"  Rider stats: {len(rider_stats_list)} riders")
    return data