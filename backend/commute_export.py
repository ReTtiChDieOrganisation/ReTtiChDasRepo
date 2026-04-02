"""Identify commute rides and export analysis data.

A commute is detected by checking if the ride starts or ends within
configurable bounding boxes (work location). Direction is inferred
from time of day. Only Ride activities are considered.
"""

import json
import os
from backend import database as db


# Default work location bounds (can be overridden in config.json)
DEFAULT_WORK_BOUNDS = {
    "lat": [50.846, 50.865],
    "lon": [7.094, 7.138]
}

DEFAULT_COMMUTE_RIDERS = ["Felix", "Flo", "Philipp"]

# Rettich nutrition facts
RETTICH_KCAL_PER_100G = 15
RETTICH_AVG_WEIGHT_G = 400  # average white radish

# Human cycling efficiency (~25%) — metabolic cost = mechanical work / 0.25
CYCLING_EFFICIENCY = 0.25


def _in_bounds(lat, lon, lat_bounds, lon_bounds):
    return (lat_bounds[0] <= lat <= lat_bounds[1] and
            lon_bounds[0] <= lon <= lon_bounds[1])


def export_commute_data(conn, output_dir, config=None):
    """Export commute analysis data as a .js file."""
    config = config or {}

    work_bounds = config.get('work_bounds', DEFAULT_WORK_BOUNDS)
    lat_bounds = work_bounds['lat']
    lon_bounds = work_bounds['lon']
    commute_riders = config.get('riders', DEFAULT_COMMUTE_RIDERS)

    riders = db.get_all_riders(conn)
    rider_names = {r['name'] for r in riders}
    commute_riders = [r for r in commute_riders if r in rider_names]

    if not commute_riders:
        print("  No commute riders found in DB")
        return None

    # Get only Ride activities for commute riders
    all_activities = []
    for rider_name in commute_riders:
        rows = conn.execute(
            "SELECT * FROM activities WHERE rider_name=? AND activity_type='Ride' ORDER BY start_epoch",
            (rider_name,)
        ).fetchall()
        all_activities.extend(rows)

    # --- First pass: identify commutes, compute kcal where we have watts ---
    commutes_raw = []

    for act in all_activities:
        stream = db.get_stream(conn, act['id'])
        if not stream or not stream['latlng_data']:
            continue

        latlng = json.loads(stream['latlng_data'])
        if not latlng or len(latlng) < 2:
            continue

        start_lat, start_lon = latlng[0]
        end_lat, end_lon = latlng[-1]

        starts_at_work = _in_bounds(start_lat, start_lon, lat_bounds, lon_bounds)
        ends_at_work = _in_bounds(end_lat, end_lon, lat_bounds, lon_bounds)

        start_hour = _parse_start_hour(act['start_date_local'])
        if start_hour is None:
            continue

        direction = None
        if ends_at_work and start_hour < 12:
            direction = "To Work"
        elif starts_at_work and start_hour > 12:
            direction = "From Work"

        if direction is None:
            continue

        elapsed_s = act['elapsed_time'] or 0
        moving_s = act['moving_time'] or elapsed_s
        standing_s = max(0, elapsed_s - moving_s)
        distance_m = act['distance'] or 0
        distance_km = distance_m / 1000

        avg_speed = (distance_m / elapsed_s * 3.6) if elapsed_s > 0 else 0

        # Energy from watts: mechanical work / efficiency
        # watts * seconds = Joules (mechanical)
        # kcal = Joules / 4184 (mechanical) / efficiency (to get metabolic cost)
        energy_kcal = None
        has_watts = act['average_watts'] and act['average_watts'] > 0 and moving_s > 0
        if has_watts:
            mechanical_joules = act['average_watts'] * moving_s
            energy_kcal = mechanical_joules / 4184 / CYCLING_EFFICIENCY

        commutes_raw.append({
            'rider': act['rider_name'],
            'date': act['date'],
            'direction': direction,
            'start_hour': round(start_hour, 3),
            'elapsed_minutes': round(elapsed_s / 60, 2),
            'moving_minutes': round(moving_s / 60, 2),
            'standing_minutes': round(standing_s / 60, 2),
            'average_speed': round(avg_speed, 2),
            'distance_km': round(distance_km, 2),
            'average_watts': round(act['average_watts'], 1) if has_watts else None,
            'energy_kcal': round(energy_kcal, 1) if energy_kcal is not None else None,
            '_distance_km_raw': distance_km,  # for proxy calculation
        })

    # --- Second pass: compute kcal proxy for rides without watts ---
    # Use average kcal/km from all rides that DO have watts data
    rides_with_kcal = [c for c in commutes_raw if c['energy_kcal'] is not None and c['_distance_km_raw'] > 0]
    if rides_with_kcal:
        total_kcal_known = sum(c['energy_kcal'] for c in rides_with_kcal)
        total_km_known = sum(c['_distance_km_raw'] for c in rides_with_kcal)
        kcal_per_km = total_kcal_known / total_km_known if total_km_known > 0 else 25
    else:
        kcal_per_km = 25  # rough fallback: ~25 kcal/km

    print(f"  Energy proxy: {kcal_per_km:.1f} kcal/km (from {len(rides_with_kcal)} rides with power data)")

    commutes = []
    for c in commutes_raw:
        if c['energy_kcal'] is None:
            c['energy_kcal'] = round(c['_distance_km_raw'] * kcal_per_km, 1)
        del c['_distance_km_raw']
        commutes.append(c)

    # --- Aggregate stats ---
    total_km = sum(c['distance_km'] for c in commutes)
    total_kcal = sum(c['energy_kcal'] for c in commutes)
    rettich_kcal = RETTICH_KCAL_PER_100G * RETTICH_AVG_WEIGHT_G / 100  # 60 kcal per rettich
    rettich_count = total_kcal / rettich_kcal if rettich_kcal > 0 else 0
    rettich_kg = rettich_count * RETTICH_AVG_WEIGHT_G / 1000

    per_rider = {}
    for rn in commute_riders:
        rc = [c for c in commutes if c['rider'] == rn]
        per_rider[rn] = {
            'rides': len(rc),
            'total_km': round(sum(c['distance_km'] for c in rc), 1),
            'total_kcal': round(sum(c['energy_kcal'] for c in rc), 0),
        }

    data = {
        'commutes': commutes,
        'riders': commute_riders,
        'stats': {
            'total_rides': len(commutes),
            'total_km': round(total_km, 1),
            'total_energy_kcal': round(total_kcal, 0),
            'rettich_count': round(rettich_count, 1),
            'rettich_kg': round(rettich_kg, 1),
            'kcal_per_km': round(kcal_per_km, 1),
            'per_rider': per_rider,
        }
    }

    # Write as .js
    js_path = os.path.join(output_dir, 'commute_data.js')
    json_str = json.dumps(data, separators=(',', ':'))
    with open(js_path, 'w', encoding='utf-8') as f:
        f.write(f'window.RETTICH_COMMUTE={json_str};')

    print(f"  Commutes: {len(commutes)} rides from {len(commute_riders)} riders")
    return data


def _parse_start_hour(start_date_local):
    """Extract decimal hour from start_date_local string."""
    if not start_date_local:
        return None
    try:
        time_part = start_date_local.split('T')[1] if 'T' in start_date_local else None
        if not time_part:
            return None
        parts = time_part.split(':')
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0
        s = int(parts[2].split('+')[0].split('Z')[0]) if len(parts) > 2 else 0
        return h + m / 60 + s / 3600
    except (ValueError, IndexError):
        return None