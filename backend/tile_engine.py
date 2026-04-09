"""Shared tile computation for explorer and rider stats exporters.

Computes all tile data in a single pass over activity streams so that
explorer_export and rider_stats_export don't duplicate that work.
"""

import json
import math
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


class TileData:
    """All tile-derived data computed in a single stream pass."""
    __slots__ = (
        'zoom',
        'tiles',               # (x,y) -> {'visits': int, 'first_date': str}
        'tile_discovery',      # (x,y) -> {date: set(riders)}
        'tile_rider_visits',   # (x,y) -> {rider: count}
        'tile_rider_visits_old',
        'rider_tile_visits',   # rider -> {(x,y): count}
        'rider_tile_visits_old',
        'rider_tiles',         # rider -> set of (x,y)
        'new_tiles_by_date',   # date -> int
        'activity_rettiche',   # act_id -> {'new': int, 'total': int, 'score': float}
        'feld',                # set of (x,y) — global largest connected component
        'rider_felds',         # rider -> set of (x,y)
        'rider_felds_old',     # rider -> set of (x,y) (tiles visited before 30 days ago)
    )

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def compute_tile_data(conn, config=None):
    """Walk all non-virtual activity streams once and return a TileData.

    This replaces the independent stream-walking loops that previously existed
    in both explorer_export.py and rider_stats_export.py.
    """
    config = config or {}
    zoom = config.get('zoom', DEFAULT_ZOOM)
    thirty_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

    tiles = {}
    tile_discovery = defaultdict(lambda: defaultdict(set))
    tile_rider_visits = defaultdict(lambda: defaultdict(int))
    tile_rider_visits_old = defaultdict(lambda: defaultdict(int))
    rider_tile_visits = defaultdict(lambda: defaultdict(int))
    rider_tile_visits_old = defaultdict(lambda: defaultdict(int))
    rider_tiles = defaultdict(set)
    new_tiles_by_date = defaultdict(int)
    activity_rettiche = {}

    all_activities = conn.execute("""
        SELECT a.id, a.rider_name, a.date
        FROM activities a
        WHERE a.activity_type != 'VirtualRide'
        ORDER BY a.start_epoch ASC
    """).fetchall()

    for act in all_activities:
        act_id = act['id']
        rider = act['rider_name']
        date = act['date']
        is_old = date < thirty_ago

        stream = db.get_stream(conn, act_id)
        if not stream or not stream['latlng_data']:
            activity_rettiche[act_id] = {'new': 0, 'total': 0, 'score': 0.0}
            continue

        latlng = json.loads(stream['latlng_data'])
        if not latlng:
            activity_rettiche[act_id] = {'new': 0, 'total': 0, 'score': 0.0}
            continue

        act_tiles = set()
        for point in latlng:
            act_tiles.add(lat_lon_to_tile(point[0], point[1], zoom))

        new_tiles_count = 0
        act_score = 0.0

        for key in act_tiles:
            tile_rider_visits[key][rider] += 1
            rider_tile_visits[rider][key] += 1
            rider_tiles[rider].add(key)

            personal_count = tile_rider_visits[key][rider]
            act_score += 1.0 / personal_count

            if is_old:
                tile_rider_visits_old[key][rider] += 1
                rider_tile_visits_old[rider][key] += 1

            if key not in tiles:
                tiles[key] = {'visits': 1, 'first_date': date}
                new_tiles_by_date[date] += 1
                tile_discovery[key][date].add(rider)
                new_tiles_count += 1
            else:
                tiles[key]['visits'] += 1
                if date == tiles[key]['first_date']:
                    tile_discovery[key][date].add(rider)

        activity_rettiche[act_id] = {
            'new': new_tiles_count,
            'total': len(act_tiles),
            'score': round(act_score, 2),
        }

    # Global feld
    feld = find_largest_connected(set(tiles.keys()))

    # Per-rider felds (all-time and pre-30d for delta)
    rider_felds = {}
    rider_felds_old = {}
    for rider, rtiles in rider_tiles.items():
        rider_felds[rider] = find_largest_connected(rtiles)
        old_tiles = {k for k in rtiles if rider_tile_visits_old[rider].get(k, 0) > 0}
        rider_felds_old[rider] = find_largest_connected(old_tiles)

    return TileData(
        zoom=zoom,
        tiles=tiles,
        tile_discovery=tile_discovery,
        tile_rider_visits=tile_rider_visits,
        tile_rider_visits_old=tile_rider_visits_old,
        rider_tile_visits=rider_tile_visits,
        rider_tile_visits_old=rider_tile_visits_old,
        rider_tiles=rider_tiles,
        new_tiles_by_date=new_tiles_by_date,
        activity_rettiche=activity_rettiche,
        feld=feld,
        rider_felds=rider_felds,
        rider_felds_old=rider_felds_old,
    )
