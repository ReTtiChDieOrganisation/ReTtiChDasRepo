"""Per-rider statistics export for 'Die Rettiche' page.

Computes for each rider:
- Total/30d: km, elevation, time, activities
- Explorer score (all-time + 30d) — harmonic of personal tile visit counts
- Personal Feld (largest connected area of tiles they've visited)

Tile data is provided by tile_engine.compute_tile_data() so that streams
are not re-walked independently here.
"""

import json
import os
from datetime import datetime, timedelta
from backend import database as db


def export_rider_stats(conn, output_dir, tile_data, config=None):
    """Export per-rider statistics.

    Args:
        conn: database connection
        output_dir: path to frontend/data
        tile_data: TileData from tile_engine.compute_tile_data()
        config: explorer config dict (for zoom level)
    """
    thirty_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

    riders = db.get_all_riders(conn)

    all_activities = conn.execute("""
        SELECT a.id, a.rider_name, a.date, a.elapsed_time,
               a.distance, a.total_elevation_gain
        FROM activities a
        WHERE a.activity_type != 'VirtualRide'
        ORDER BY a.start_epoch ASC
    """).fetchall()

    rider_data = {}
    for r in riders:
        rider_data[r['name']] = {
            'name': r['name'],
            'frame': r['frame'] or 'default',
            'total_km': 0, 'total_elev': 0, 'total_time_s': 0, 'total_acts': 0,
            'km_30d': 0, 'elev_30d': 0, 'time_30d_s': 0, 'acts_30d': 0,
        }

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

    rider_tile_visits = tile_data.rider_tile_visits
    rider_tile_visits_old = tile_data.rider_tile_visits_old
    rider_tiles = tile_data.rider_tiles
    rider_felds = tile_data.rider_felds
    rider_felds_old = tile_data.rider_felds_old

    rider_stats_list = []
    for rn, rd in rider_data.items():
        score = sum(
            sum(1.0 / k for k in range(1, v + 1))
            for v in rider_tile_visits[rn].values()
        )
        score_old = sum(
            sum(1.0 / k for k in range(1, v + 1))
            for v in rider_tile_visits_old[rn].values()
        )

        personal_feld = rider_felds.get(rn, set())
        personal_feld_old = rider_felds_old.get(rn, set())

        rider_stats_list.append({
            'name': rn,
            'frame': rd['frame'],
            'total_km': round(rd['total_km'], 1),
            'total_elev': round(rd['total_elev'], 0),
            'total_hours': round(rd['total_time_s'] / 3600, 1),
            'total_acts': rd['total_acts'],
            'total_tiles': len(rider_tiles.get(rn, set())),
            'rettiche': round(score, 1),
            'rettiche_30d': round(score - score_old, 1),
            'feld_size': len(personal_feld),
            'feld_size_30d': len(personal_feld) - len(personal_feld_old),
            'km_30d': round(rd['km_30d'], 1),
            'elev_30d': round(rd['elev_30d'], 0),
            'hours_30d': round(rd['time_30d_s'] / 3600, 1),
            'acts_30d': rd['acts_30d'],
            'tiles_30d': sum(
                1 for k in rider_tiles.get(rn, set())
                if rider_tile_visits_old[rn].get(k, 0) == 0
            ),
        })

    rider_stats_list.sort(key=lambda x: -x['rettiche'])

    data = {'riders': rider_stats_list}

    js_path = os.path.join(output_dir, 'rider_stats.js')
    json_str = json.dumps(data, separators=(',', ':'))
    with open(js_path, 'w', encoding='utf-8') as f:
        f.write(f'window.RETTICH_RIDERS={json_str};')

    print(f"  Rider stats: {len(rider_stats_list)} riders")
    return data
