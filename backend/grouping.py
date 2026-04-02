"""
Group detection: find rides done on the same day that share segments.

A group is a set of rides from the same day sharing ≥10 Strava segments.
We also create "daily overview" groups for all rides on a given day.
"""

from collections import defaultdict
from backend import database as db


MIN_SHARED_SEGMENTS = 10


def compute_groups(conn):
    """Recompute all groups from scratch."""
    db.clear_groups(conn)

    dates = db.get_all_dates(conn)

    for date in dates:
        activities = db.get_activities_by_date(conn, date)
        if not activities:
            continue

        activity_ids = [a['id'] for a in activities]
        rider_names = [a['rider_name'] for a in activities]

        # --- Daily overview group (all rides of this day) ---
        unique_riders = sorted(set(rider_names))
        daily_name = f"{date} — All ({', '.join(unique_riders)})"
        db.insert_group(conn, daily_name, date, 'daily', 0, activity_ids)

        # --- Segment-based groups ---
        if len(activity_ids) < 2:
            continue

        # Build segment sets per activity
        activity_segments = {}
        for aid in activity_ids:
            efforts = db.get_segment_efforts_for_activity(conn, aid)
            activity_segments[aid] = set(e['segment_id'] for e in efforts)

        # Find clusters of activities sharing ≥ MIN_SHARED_SEGMENTS
        # Use a greedy approach: for each pair, check overlap, then expand
        found_groups = []
        used = set()

        # Sort by number of segments descending for better grouping
        sorted_aids = sorted(activity_ids, key=lambda a: len(activity_segments.get(a, set())), reverse=True)

        for i, aid1 in enumerate(sorted_aids):
            for j in range(i + 1, len(sorted_aids)):
                aid2 = sorted_aids[j]
                segs1 = activity_segments.get(aid1, set())
                segs2 = activity_segments.get(aid2, set())
                shared = segs1 & segs2

                if len(shared) >= MIN_SHARED_SEGMENTS:
                    # Try to expand this pair into a larger group
                    group_aids = {aid1, aid2}
                    group_shared = shared.copy()

                    for k, aid3 in enumerate(sorted_aids):
                        if aid3 in group_aids:
                            continue
                        segs3 = activity_segments.get(aid3, set())
                        # Check if aid3 shares enough segments with the group
                        overlap_with_group = segs3 & group_shared
                        if len(overlap_with_group) >= MIN_SHARED_SEGMENTS:
                            group_aids.add(aid3)
                            group_shared = group_shared & segs3  # narrow shared segs

                    # Check if this group is a subset of an existing one
                    group_key = frozenset(group_aids)
                    already_exists = any(group_key == fg for fg in found_groups)
                    if not already_exists:
                        # Also check if it's a subset
                        is_subset = any(group_key < fg for fg in found_groups)
                        if not is_subset:
                            # Remove any existing groups that are subsets of this one
                            found_groups = [fg for fg in found_groups if not fg < group_key]
                            found_groups.append(group_key)

        # Insert segment-based groups
        for group_aids_frozen in found_groups:
            group_aids = list(group_aids_frozen)

            # Compute shared segments for this specific group
            shared_segs = None
            for aid in group_aids:
                segs = activity_segments.get(aid, set())
                if shared_segs is None:
                    shared_segs = segs.copy()
                else:
                    shared_segs &= segs
            shared_count = len(shared_segs) if shared_segs else 0

            # Name the group
            group_riders = set()
            for a in activities:
                if a['id'] in group_aids:
                    group_riders.add(a['rider_name'])
            riders_str = ', '.join(sorted(group_riders))
            group_name = f"{date} — {riders_str} ({shared_count} seg)"

            db.insert_group(conn, group_name, date, 'segment', shared_count, group_aids)

    print(f"  Computed groups for {len(dates)} dates")