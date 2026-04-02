"""Export database data to JSON files for the static frontend."""

import json
import os
from backend import database as db

FRAMES = {
    "blue": {"line_color": "rgba(0, 56, 123, 1)"},
    "green": {"line_color": "rgba(6, 80, 0, 1)"},
    "orbea": {"line_color": "rgba(207, 181, 59, 1)"},
    "ulle": {"line_color": "rgba(227, 0, 126, 1)"},
    "cinelli": {"line_color": "rgba(255, 102, 0, 1)"},
    "speedster": {"line_color": "rgba(24, 23, 23, 1)"},
    "navyblue": {"line_color": "rgba(32, 56, 100, 1)"},
    "neutral": {"line_color": "rgba(208, 206, 206, 1)"},
    "purple": {"line_color": "rgba(112, 48, 160, 1)"},
    "red": {"line_color": "rgba(139, 0, 0, 1)"},
    "orange": {"line_color": "rgba(132, 60, 12, 1)"},
    "yellow": {"line_color": "rgba(255, 238, 21, 1)"},
    "gold": {"line_color": "rgba(207, 181, 59, 1)"},
    "silver": {"line_color": "rgba(170, 169, 173, 1)"},
    "bronze": {"line_color": "rgba(191, 137, 112, 1)"},
    "black": {"line_color": "rgba(0, 0, 0, 1)"},
    "white": {"line_color": "rgba(255, 255, 255, 1)"},
    "default": {"line_color": "rgba(100, 100, 100, 1)"},
}


def export_all(conn, output_dir):
    """Export all data needed by the frontend."""
    os.makedirs(output_dir, exist_ok=True)

    # 1. Riders
    riders = db.get_all_riders(conn)
    riders_data = {}
    for r in riders:
        frame = r['frame'] or 'default'
        frame_info = FRAMES.get(frame, FRAMES['default'])
        riders_data[r['name']] = {
            'name': r['name'],
            'icon_url': r['icon_url'] or '',
            'frame': frame,
            'line_color': frame_info['line_color']
        }
    _write_json(os.path.join(output_dir, 'riders.json'), riders_data)

    # 2. Groups
    groups = db.get_all_groups(conn)
    groups_data = []
    for g in groups:
        aid_str = g['activity_ids'] or ''
        activity_ids = [int(x) for x in aid_str.split(',') if x]
        groups_data.append({
            'id': g['id'],
            'name': g['name'],
            'date': g['date'],
            'type': g['group_type'],
            'shared_segment_count': g['shared_segment_count'],
            'activity_ids': activity_ids
        })
    _write_json(os.path.join(output_dir, 'groups.json'), groups_data)

    # 3. Activities + streams (one file per activity for performance)
    activities_dir = os.path.join(output_dir, 'activities')
    os.makedirs(activities_dir, exist_ok=True)

    # Collect all activity IDs referenced by groups
    all_aids = set()
    for g in groups_data:
        all_aids.update(g['activity_ids'])

    activities_index = []
    for aid in all_aids:
        act = db.get_activity(conn, aid)
        if not act:
            continue

        act_data = {
            'id': act['id'],
            'rider_name': act['rider_name'],
            'name': act['name'],
            'date': act['date'],
            'start_date_local': act['start_date_local'],
            'start_epoch': act['start_epoch'],
            'elapsed_time': act['elapsed_time'],
            'moving_time': act['moving_time'],
            'distance': act['distance'],
            'total_elevation_gain': act['total_elevation_gain'],
            'average_speed': act['average_speed'],
            'max_speed': act['max_speed'],
            'average_watts': act['average_watts'],
            'summary_polyline': act['summary_polyline']
        }

        # Add stream data
        stream = db.get_stream(conn, aid)
        if stream:
            act_data['streams'] = {
                'time': json.loads(stream['time_data']) if stream['time_data'] else None,
                'latlng': json.loads(stream['latlng_data']) if stream['latlng_data'] else None,
                'distance': json.loads(stream['distance_data']) if stream['distance_data'] else None,
                'altitude': json.loads(stream['altitude_data']) if stream['altitude_data'] else None,
                'watts': json.loads(stream['watts_data']) if stream['watts_data'] else None,
            }

        # Add segment efforts
        efforts = db.get_segment_efforts_for_activity(conn, aid)
        act_data['segment_efforts'] = [{
            'id': e['id'],
            'segment_id': e['segment_id'],
            'segment_name': e['segment_name'],
            'elapsed_time': e['elapsed_time'],
            'distance': e['distance'],
            'avg_grade': e['avg_grade'],
            'start_index': e['start_index'],
            'end_index': e['end_index'],
            'average_watts': e['average_watts']
        } for e in efforts]

        _write_json(os.path.join(activities_dir, f'{aid}.json'), act_data)

        activities_index.append({
            'id': act['id'],
            'rider_name': act['rider_name'],
            'name': act['name'],
            'date': act['date'],
            'start_epoch': act['start_epoch'],
            'elapsed_time': act['elapsed_time'],
            'distance': act['distance']
        })

    _write_json(os.path.join(output_dir, 'activities_index.json'), activities_index)

    # 4. Shared segments per group
    segments_data = {}
    for g in groups_data:
        if g['type'] == 'segment' and len(g['activity_ids']) >= 2:
            shared = db.get_shared_segments_for_activities(conn, g['activity_ids'])
            segments_data[str(g['id'])] = [{
                'segment_id': s['segment_id'],
                'segment_name': s['segment_name'],
                'distance': s['distance'],
                'avg_grade': s['avg_grade'],
                'ride_count': s['ride_count']
            } for s in shared]
    _write_json(os.path.join(output_dir, 'shared_segments.json'), segments_data)

    print(f"  Exported {len(riders_data)} riders, {len(groups_data)} groups, {len(activities_index)} activities")


def _write_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, separators=(',', ':'))
