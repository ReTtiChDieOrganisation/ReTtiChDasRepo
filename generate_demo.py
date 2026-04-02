#!/usr/bin/env python3
"""Generate demo data for frontend testing without Strava access."""

import json
import os
import sys
import random
import math

sys.path.insert(0, os.path.dirname(__file__))

from backend import database as db
from backend.grouping import compute_groups
from backend.export import export_all

# Frankfurt area coordinates for demo
FRANKFURT_CENTER = (50.1109, 8.6821)
OFFENBACH = (50.0956, 8.7761)
DARMSTADT = (49.8728, 8.6512)

DEMO_RIDERS = {
    'Felix': {'frame': 'cinelli', 'icon_url': './icons/profile_pictures/felix.png'},
    'Philipp': {'frame': 'orbea', 'icon_url': './icons/profile_pictures/philipp.png'},
    'Flo': {'frame': 'speedster', 'icon_url': './icons/profile_pictures/flo.png'},
    'David': {'frame': 'red', 'icon_url': './icons/profile_pictures/david.png'},
}

# Define some "routes" as waypoint lists (lat, lng)
ROUTE_COMMUTE_1 = [
    (50.1109, 8.6821), (50.1085, 8.6890), (50.1050, 8.6950),
    (50.1020, 8.7020), (50.0990, 8.7100), (50.0970, 8.7200),
    (50.0960, 8.7350), (50.0955, 8.7500), (50.0956, 8.7650),
    (50.0956, 8.7761)
]

ROUTE_COMMUTE_2 = [
    (50.1109, 8.6821), (50.1090, 8.6900), (50.1060, 8.6960),
    (50.1030, 8.7030), (50.1000, 8.7120), (50.0975, 8.7230),
    (50.0965, 8.7380), (50.0958, 8.7520), (50.0956, 8.7670),
    (50.0956, 8.7761)
]

ROUTE_WEEKEND = [
    (50.1109, 8.6821), (50.1000, 8.6700), (50.0900, 8.6600),
    (50.0800, 8.6550), (50.0700, 8.6520), (50.0500, 8.6500),
    (50.0300, 8.6510), (50.0100, 8.6520), (49.9900, 8.6530),
    (49.9500, 8.6540), (49.9200, 8.6550), (49.8900, 8.6530),
    (49.8728, 8.6512)
]

# Define shared segment IDs (commute routes share many)
COMMUTE_SEGMENTS = list(range(1000, 1025))  # 25 segments
WEEKEND_SEGMENTS = list(range(2000, 2015))   # 15 segments


def interpolate_route(waypoints, num_points=200):
    """Interpolate waypoints into a smooth route with num_points."""
    if len(waypoints) < 2:
        return waypoints

    # Calculate cumulative distances
    dists = [0]
    for i in range(1, len(waypoints)):
        d = _haversine(waypoints[i - 1], waypoints[i])
        dists.append(dists[-1] + d)

    total_dist = dists[-1]
    points = []

    for i in range(num_points):
        target = total_dist * i / (num_points - 1)
        # Find segment
        for j in range(1, len(dists)):
            if dists[j] >= target:
                frac = (target - dists[j - 1]) / (dists[j] - dists[j - 1]) if dists[j] > dists[j - 1] else 0
                lat = waypoints[j - 1][0] + frac * (waypoints[j][0] - waypoints[j - 1][0])
                lng = waypoints[j - 1][1] + frac * (waypoints[j][1] - waypoints[j - 1][1])
                # Add slight randomness for variation between riders
                lat += random.gauss(0, 0.0003)
                lng += random.gauss(0, 0.0003)
                points.append([round(lat, 6), round(lng, 6)])
                break

    return points


def _haversine(p1, p2):
    R = 6371000
    lat1, lat2 = math.radians(p1[0]), math.radians(p2[0])
    dlat = math.radians(p2[0] - p1[0])
    dlng = math.radians(p2[1] - p1[1])
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def generate_time_series(num_points, total_time, variation=0.1):
    """Generate realistic time series for a ride."""
    times = []
    t = 0
    avg_dt = total_time / num_points
    for i in range(num_points):
        times.append(int(t))
        # Variable speed
        speed_factor = 1 + variation * math.sin(i / num_points * math.pi * 4) + random.gauss(0, variation * 0.3)
        t += avg_dt * max(0.3, speed_factor)
    return times


def generate_altitude(latlng, base=100, amplitude=30):
    """Generate altitude data with hills."""
    n = len(latlng)
    return [round(base + amplitude * math.sin(i / n * math.pi * 3) + random.gauss(0, 2), 1) for i in range(n)]


def generate_distance(latlng):
    """Generate cumulative distance from latlng."""
    dists = [0]
    for i in range(1, len(latlng)):
        d = _haversine(latlng[i - 1], latlng[i])
        dists.append(round(dists[-1] + d, 1))
    return dists


def main():
    db_path = os.path.join(os.path.dirname(__file__), 'rettich.db')
    if os.path.exists(db_path):
        os.remove(db_path)

    db.init_db()
    conn = db.get_connection()

    # Insert riders
    for name, info in DEMO_RIDERS.items():
        db.upsert_rider(conn, name, 'demo_token', info['icon_url'], info['frame'])

    activity_id = 10000
    effort_id = 50000
    riders = list(DEMO_RIDERS.keys())

    dates_to_generate = [
        ('2025-05-19', 'commute'),  # Monday commute
        ('2025-05-20', 'commute'),  # Tuesday commute
        ('2025-05-21', 'commute'),  # Wednesday commute
        ('2025-05-24', 'weekend'),  # Saturday ride
        ('2025-05-26', 'commute'),  # Monday commute
    ]

    for date, ride_type in dates_to_generate:
        # Random subset of riders for this day (at least 2)
        day_riders = random.sample(riders, random.randint(2, len(riders)))

        for rider in day_riders:
            activity_id += 1

            if ride_type == 'commute':
                route = random.choice([ROUTE_COMMUTE_1, ROUTE_COMMUTE_2])
                segments = random.sample(COMMUTE_SEGMENTS, random.randint(15, 22))
                base_time = 1800 + random.randint(-300, 600)  # 25-40 min
                start_hour = 7 + random.randint(0, 2)
                start_min = random.randint(0, 59)
            else:
                route = ROUTE_WEEKEND
                segments = random.sample(WEEKEND_SEGMENTS, random.randint(10, 14))
                base_time = 5400 + random.randint(-600, 1800)  # 80-120 min
                start_hour = 9 + random.randint(0, 2)
                start_min = random.randint(0, 59)

            num_points = 200 if ride_type == 'commute' else 400
            latlng = interpolate_route(route, num_points)
            times = generate_time_series(num_points, base_time)
            altitude = generate_altitude(latlng)
            distance = generate_distance(latlng)
            total_dist = distance[-1]

            start_epoch = int(
                __import__('datetime').datetime.fromisoformat(
                    f"{date}T{start_hour:02d}:{start_min:02d}:00+02:00"
                ).timestamp()
            )

            # Simplified polyline (just store as JSON reference)
            # For demo, we'll use the latlng directly
            act = {
                'id': activity_id,
                'rider_name': rider,
                'name': f"{'Morning Commute' if ride_type == 'commute' else 'Weekend Ride'} - {rider}",
                'type': 'Ride',
                'date': date,
                'start_date_local': f"{date}T{start_hour:02d}:{start_min:02d}:00",
                'start_epoch': start_epoch,
                'elapsed_time': times[-1],
                'moving_time': int(times[-1] * 0.9),
                'distance': total_dist,
                'total_elevation_gain': random.uniform(50, 200),
                'average_speed': total_dist / times[-1] if times[-1] > 0 else 0,
                'max_speed': random.uniform(10, 15),
                'average_watts': random.uniform(150, 250) if random.random() > 0.3 else None,
                'summary_polyline': None  # We'll use streams instead
            }
            db.insert_activity(conn, act)

            # Insert stream
            db.insert_stream(conn, activity_id, times, latlng, distance, altitude,
                             [random.randint(100, 300) for _ in range(num_points)] if act['average_watts'] else None)

            # Insert segment efforts
            for seg_id in segments:
                effort_id += 1
                seg_start = random.randint(0, num_points // 3)
                seg_end = seg_start + random.randint(20, 60)
                seg_end = min(seg_end, num_points - 1)

                effort = {
                    'id': effort_id,
                    'activity_id': activity_id,
                    'segment_id': seg_id,
                    'segment_name': f"Segment {seg_id}",
                    'rider_name': rider,
                    'elapsed_time': random.randint(30, 300),
                    'distance': random.uniform(200, 2000),
                    'avg_grade': random.uniform(-2, 8),
                    'start_index': seg_start,
                    'end_index': seg_end,
                    'average_watts': random.uniform(150, 300) if act['average_watts'] else None
                }
                db.insert_segment_effort(conn, effort)

    # Compute groups
    print("Computing groups...")
    compute_groups(conn)

    # Export
    output_dir = os.path.join(os.path.dirname(__file__), 'frontend', 'data')
    print("Exporting...")
    export_all(conn, output_dir)

    # Write site config
    site_config = {'password_hash': 0}  # No password for demo
    with open(os.path.join(output_dir, 'site_config.json'), 'w') as f:
        json.dump(site_config, f)

    conn.close()
    print("Demo data generated successfully!")


if __name__ == '__main__':
    main()
