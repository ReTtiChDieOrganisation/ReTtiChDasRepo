"""Explorer: compute collected map tiles from GPS tracks.

Tiles at zoom 16 (~600m at 50°N). Virtual rides excluded.

Rettich Score: harmonic scoring per tile (1 + 1/2 + 1/3 + ...).
Per-rider Explorer Score: when N riders discover a tile on the same day,
each gets 1/N credit for that discovery. Revisit scoring is personal.

Rettich Revier: largest 8-connected component of collected tiles.
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


def tile_to_bounds(x, y, zoom):
    n = 2 ** zoom
    west = x / n * 360.0 - 180.0
    east = (x + 1) / n * 360.0 - 180.0
    north_rad = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
    south_rad = math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n)))
    return [math.degrees(south_rad), west, math.degrees(north_rad), east]


def harmonic(n):
    return sum(1.0 / k for k in range(1, n + 1))


def find_largest_connected(tile_set):
    """BFS with 8-connectivity."""
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


def export_explorer_data(conn, output_dir, config=None):
    config = config or {}
    zoom = config.get('zoom', DEFAULT_ZOOM)

    today_str = datetime.now().strftime('%Y-%m-%d')
    week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')

    # tiles: (x,y) -> { visits: int, first_date }
    tiles = {}
    # Per-rider visits per tile: {(x,y): {rider: visit_count}}
    rider_tile_visits = defaultdict(lambda: defaultdict(int))
    # Same but only visits BEFORE 30 days ago (for delta computation)
    rider_tile_visits_old = defaultdict(lambda: defaultdict(int))
    # Track first discovery: {(x,y): {date: set(riders)}} - who discovered on which day
    tile_discovery = defaultdict(lambda: defaultdict(set))

    thirty_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

    all_activities = conn.execute("""
        SELECT a.id, a.rider_name, a.date, a.elapsed_time, a.moving_time,
               a.distance, a.activity_type
        FROM activities a
        WHERE a.activity_type != 'VirtualRide'
        ORDER BY a.start_epoch ASC
    """).fetchall()

    total_km = 0
    total_time_s = 0
    total_activities = 0
    week_km = 0
    week_time_s = 0
    week_activities = 0

    new_tiles_by_date = defaultdict(int)

    for act in all_activities:
        dist = act['distance'] or 0
        elapsed = act['elapsed_time'] or 0
        date = act['date']
        rider = act['rider_name']

        total_km += dist / 1000
        total_time_s += elapsed
        total_activities += 1

        if date >= week_ago:
            week_km += dist / 1000
            week_time_s += elapsed
            week_activities += 1

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
            rider_tile_visits[key][rider] += 1
            if date < thirty_ago:
                rider_tile_visits_old[key][rider] += 1

            if key not in tiles:
                tiles[key] = {'visits': 1, 'first_date': date}
                new_tiles_by_date[date] += 1
                tile_discovery[key][date].add(rider)
            else:
                tiles[key]['visits'] += 1
                if date == tiles[key]['first_date']:
                    tile_discovery[key][date].add(rider)

    # Largest connected area (Rettich Revier)
    tile_coords = set(tiles.keys())
    revier = find_largest_connected(tile_coords)

    # Track revier new tiles
    new_revier_today = 0
    new_revier_week = 0
    for key in revier:
        fd = tiles[key]['first_date']
        if fd == today_str:
            new_revier_today += 1
        if fd >= week_ago:
            new_revier_week += 1

    # Global Rettich Score
    rettich_score = sum(harmonic(t['visits']) for t in tiles.values())

    # Per-rider Explorer Score:
    # First visit to a tile: if N riders discovered it on the same day, each gets 1/N
    # Subsequent personal visits: +1/(personal_visit_number)
    rider_scores = defaultdict(float)
    rider_scores_old = defaultdict(float)  # score from visits before 30 days ago
    all_rider_names = set()

    for key, info in tiles.items():
        first_date = info['first_date']
        discoverers = tile_discovery[key].get(first_date, set())
        n_discoverers = max(1, len(discoverers))

        for rider, visit_count in rider_tile_visits[key].items():
            all_rider_names.add(rider)
            old_count = rider_tile_visits_old.get(key, {}).get(rider, 0)

            # All-time score
            if rider in discoverers:
                rider_scores[rider] += 1.0 / n_discoverers
                for k in range(2, visit_count + 1):
                    rider_scores[rider] += 1.0 / k
            else:
                for k in range(1, visit_count + 1):
                    rider_scores[rider] += 1.0 / k

            # Old score (same logic, but with old visit counts)
            if old_count > 0:
                if rider in discoverers and first_date < thirty_ago:
                    rider_scores_old[rider] += 1.0 / n_discoverers
                    for k in range(2, old_count + 1):
                        rider_scores_old[rider] += 1.0 / k
                elif rider not in discoverers:
                    for k in range(1, old_count + 1):
                        rider_scores_old[rider] += 1.0 / k
                else:
                    # Rider was discoverer but discovery was within 30 days
                    # All old visits are non-discovery visits
                    for k in range(1, old_count + 1):
                        rider_scores_old[rider] += 1.0 / k

    # Find max visits for normalization
    max_visits = max((t['visits'] for t in tiles.values()), default=1)

    # Build export
    tiles_list = []
    for (tx, ty), info in tiles.items():
        bounds = tile_to_bounds(tx, ty, zoom)
        is_new = info['first_date'] >= week_ago
        in_revier = (tx, ty) in revier
        tile_riders = list(rider_tile_visits[(tx, ty)].keys())

        tiles_list.append({
            'x': tx, 'y': ty,
            'b': bounds,
            'v': info['visits'],
            'n': is_new,
            'r': in_revier,
            'd': info['first_date'],
            'p': tile_riders,  # riders who visited this tile
        })

    new_today = new_tiles_by_date.get(today_str, 0)
    new_week = sum(v for d, v in new_tiles_by_date.items() if d >= week_ago)

    daily_new = [{'date': d, 'count': c}
                 for d, c in sorted(new_tiles_by_date.items()) if d >= thirty_ago]

    rider_score_list = [{
        'rider': r,
        'score': round(rider_scores[r], 1),
        'score_30d': round(rider_scores[r] - rider_scores_old.get(r, 0), 1),
    } for r in sorted(all_rider_names)]
    rider_score_list.sort(key=lambda x: -x['score'])

    data = {
        'zoom': zoom,
        'tiles': tiles_list,
        'max_visits': max_visits,
        'stats': {
            'total_tiles': len(tiles_list),
            'new_today': new_today,
            'new_week': new_week,
            'revier_size': len(revier),
            'revier_new_today': new_revier_today,
            'revier_new_week': new_revier_week,
            'rettich_score': round(rettich_score, 1),
            'total_km': round(total_km, 1),
            'total_time_hours': round(total_time_s / 3600, 1),
            'total_activities': total_activities,
            'week_km': round(week_km, 1),
            'week_time_hours': round(week_time_s / 3600, 1),
            'week_activities': week_activities,
        },
        'daily_new': daily_new,
        'rider_scores': rider_score_list,
    }

    js_path = os.path.join(output_dir, 'explorer_data.js')
    json_str = json.dumps(data, separators=(',', ':'))
    with open(js_path, 'w', encoding='utf-8') as f:
        f.write(f'window.RETTICH_EXPLORER={json_str};')

    print(f"  Explorer: {len(tiles_list)} tiles (zoom {zoom}), "
          f"Score {rettich_score:.1f}, Revier {len(revier)} tiles, "
          f"from {total_activities} activities")
    return data