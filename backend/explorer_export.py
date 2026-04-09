"""Explorer: export collected map tiles from GPS tracks.

Tiles at zoom 16 (~600m at 50°N). Virtual rides excluded.

Rettiche: harmonic scoring per tile (1 + 1/2 + 1/3 + ...).
Per-rider Rettiche: when N riders discover a tile on the same day,
each gets 1/N credit for that discovery. Revisit scoring is personal.

Rettich Feld: largest 8-connected component of collected tiles.

Tile computation is done once in tile_engine.py and passed in as TileData.
"""

import json
import math
import os
from collections import defaultdict
from datetime import datetime, timedelta


def tile_to_bounds(x, y, zoom):
    n = 2 ** zoom
    west = x / n * 360.0 - 180.0
    east = (x + 1) / n * 360.0 - 180.0
    north_rad = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
    south_rad = math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n)))
    return [math.degrees(south_rad), west, math.degrees(north_rad), east]


def export_explorer_data(conn, output_dir, tile_data, config=None):
    """Export explorer tile data.

    Args:
        conn: database connection
        output_dir: path to frontend/data
        tile_data: TileData from tile_engine.compute_tile_data()
        config: explorer config dict
    """
    config = config or {}
    zoom = tile_data.zoom

    today_str = datetime.now().strftime('%Y-%m-%d')
    week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    thirty_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

    tiles = tile_data.tiles
    tile_rider_visits = tile_data.tile_rider_visits
    tile_rider_visits_old = tile_data.tile_rider_visits_old
    tile_discovery = tile_data.tile_discovery
    feld = tile_data.feld
    new_tiles_by_date = tile_data.new_tiles_by_date
    activity_rettiche = tile_data.activity_rettiche

    # Global activity stats (simple aggregate — no stream loading needed here)
    row = conn.execute("""
        SELECT
            COUNT(*) AS total_activities,
            SUM(distance) / 1000.0 AS total_km,
            SUM(elapsed_time) AS total_time_s,
            COUNT(CASE WHEN date >= ? THEN 1 END) AS week_activities,
            SUM(CASE WHEN date >= ? THEN distance ELSE 0 END) / 1000.0 AS week_km,
            SUM(CASE WHEN date >= ? THEN elapsed_time ELSE 0 END) AS week_time_s
        FROM activities
        WHERE activity_type != 'VirtualRide'
    """, (week_ago, week_ago, week_ago)).fetchone()

    total_activities = row['total_activities'] or 0
    total_km = row['total_km'] or 0.0
    total_time_s = row['total_time_s'] or 0
    week_activities = row['week_activities'] or 0
    week_km = row['week_km'] or 0.0
    week_time_s = row['week_time_s'] or 0

    # Feld stats
    new_feld_today = 0
    new_feld_week = 0
    for key in feld:
        fd = tiles[key]['first_date']
        if fd == today_str:
            new_feld_today += 1
        if fd >= week_ago:
            new_feld_week += 1

    # Global Rettiche (harmonic sum over all tile visit counts)
    rettiche = sum(
        sum(1.0 / k for k in range(1, t['visits'] + 1))
        for t in tiles.values()
    )

    # Per-rider Rettiche using discovery model:
    # First visit: if N riders discovered tile on same day, each gets 1/N
    # Subsequent personal visits: +1/(personal_visit_number)
    rider_scores = defaultdict(float)
    rider_scores_old = defaultdict(float)
    all_rider_names = set()

    for key, info in tiles.items():
        first_date = info['first_date']
        discoverers = tile_discovery[key].get(first_date, set())
        n_discoverers = max(1, len(discoverers))

        for rider, visit_count in tile_rider_visits[key].items():
            all_rider_names.add(rider)
            old_count = tile_rider_visits_old.get(key, {}).get(rider, 0)

            if rider in discoverers:
                rider_scores[rider] += 1.0 / n_discoverers
                for k in range(2, visit_count + 1):
                    rider_scores[rider] += 1.0 / k
            else:
                for k in range(1, visit_count + 1):
                    rider_scores[rider] += 1.0 / k

            if old_count > 0:
                if rider in discoverers and first_date < thirty_ago:
                    rider_scores_old[rider] += 1.0 / n_discoverers
                    for k in range(2, old_count + 1):
                        rider_scores_old[rider] += 1.0 / k
                elif rider not in discoverers:
                    for k in range(1, old_count + 1):
                        rider_scores_old[rider] += 1.0 / k
                else:
                    for k in range(1, old_count + 1):
                        rider_scores_old[rider] += 1.0 / k

    max_visits = max((t['visits'] for t in tiles.values()), default=1)

    tiles_list = []
    for (tx, ty), info in tiles.items():
        bounds = tile_to_bounds(tx, ty, zoom)
        is_new = info['first_date'] >= week_ago
        in_feld = (tx, ty) in feld
        tile_riders = list(tile_rider_visits[(tx, ty)].keys())

        tiles_list.append({
            'x': tx, 'y': ty,
            'b': bounds,
            'v': info['visits'],
            'n': is_new,
            'r': in_feld,
            'd': info['first_date'],
            'p': tile_riders,
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
            'feld_size': len(feld),
            'feld_new_today': new_feld_today,
            'feld_new_week': new_feld_week,
            'rettiche': round(rettiche, 1),
            'total_km': round(total_km, 1),
            'total_time_hours': round(total_time_s / 3600, 1),
            'total_activities': total_activities,
            'week_km': round(week_km, 1),
            'week_time_hours': round(week_time_s / 3600, 1),
            'week_activities': week_activities,
        },
        'daily_new': daily_new,
        'rider_scores': rider_score_list,
        'activity_rettiche': activity_rettiche,
    }

    js_path = os.path.join(output_dir, 'explorer_data.js')
    js_data = {k: v for k, v in data.items() if k != 'activity_rettiche'}
    json_str = json.dumps(js_data, separators=(',', ':'))
    with open(js_path, 'w', encoding='utf-8') as f:
        f.write(f'window.RETTICH_EXPLORER={json_str};')

    print(f"  Explorer: {len(tiles_list)} tiles (zoom {zoom}), "
          f"Score {rettiche:.1f}, Feld {len(feld)} tiles, "
          f"from {total_activities} activities")
    return data
