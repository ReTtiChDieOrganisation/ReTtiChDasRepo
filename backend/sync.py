"""Main sync orchestrator: fetch new activities from Strava for all riders."""

import time
from backend import database as db
from backend import strava_client as strava


def sync_rider(conn, client_id, client_secret, rider_name):
    """Sync all new activities for a single rider."""
    rider = db.get_rider(conn, rider_name)
    if not rider:
        print(f"  [!] Rider {rider_name} not found in DB")
        return 0

    # Refresh access token if needed
    now = int(time.time())
    if rider['token_expires_at'] < now + 60:
        print(f"  Refreshing token for {rider_name}...")
        access_token, expires_at, new_refresh = strava.refresh_access_token(
            client_id, client_secret, rider['refresh_token']
        )
        db.update_token(conn, rider_name, access_token, expires_at)
    else:
        access_token = rider['access_token']

    # Fetch activities incrementally (only after last sync)
    last_epoch = db.get_last_sync_epoch(conn, rider_name)

    # Only fetch from 2025 onwards (epoch 1735689600 = 2025-01-01T00:00:00Z)
    MIN_EPOCH = 1735689600
    if last_epoch < MIN_EPOCH:
        last_epoch = MIN_EPOCH

    print(f"  Fetching activities for {rider_name} after epoch {last_epoch}...")

    max_epoch = last_epoch
    total_new = 0
    page = 1

    while True:
        activities = strava.get_activities(access_token, after_epoch=last_epoch, page=page)
        if not activities:
            break

        for act_json in activities:
            # Include rides, runs, walks — but not virtual rides
            act_type = act_json.get('type', '')
            if act_type == 'VirtualRide':
                continue
            if act_type not in ('Ride', 'Run', 'Walk'):
                continue

            act = strava.parse_activity_summary(rider_name, act_json)

            if db.activity_exists(conn, act['id']):
                continue

            # Insert activity
            db.insert_activity(conn, act)
            total_new += 1

            # Fetch detailed activity for segment efforts
            print(f"    Fetching details for activity {act['id']} ({act['name']})...")
            try:
                detail = strava.get_activity_detail(access_token, act['id'])
                efforts = strava.parse_segment_efforts(rider_name, act['id'], detail)
                for effort in efforts:
                    db.insert_segment_effort(conn, effort)

                # Fetch streams
                streams = strava.get_activity_streams(access_token, act['id'])
                if streams:
                    db.insert_stream(
                        conn, act['id'],
                        streams.get('time'),
                        streams.get('latlng'),
                        streams.get('distance'),
                        streams.get('altitude'),
                        streams.get('watts')
                    )
            except strava.StravaRateLimitError:
                raise  # Let caller handle
            except Exception as e:
                print(f"    [!] Error fetching details for {act['id']}: {e}")

            if act['start_epoch'] > max_epoch:
                max_epoch = act['start_epoch']

        page += 1

    if max_epoch > last_epoch:
        db.update_last_sync_epoch(conn, rider_name, max_epoch)

    return total_new


def sync_all(config):
    """Sync all riders from config."""
    conn = db.get_connection()
    db.init_db()

    client_id = config['client_id']
    client_secret = config['client_secret']
    riders_config = config['riders']

    # Upsert riders
    for name, info in riders_config.items():
        db.upsert_rider(conn, name, info['refresh_token'], info.get('icon_url', ''), info.get('frame', 'default'))

    total = 0
    for rider_name in riders_config:
        try:
            n = sync_rider(conn, client_id, client_secret, rider_name)
            total += n
            print(f"  {rider_name}: {n} new activities")
        except strava.StravaRateLimitError as e:
            print(f"  [!] Rate limit hit: {e}")
            print(f"  Stopping sync. Run again later to continue.")
            break
        except Exception as e:
            print(f"  [!] Error syncing {rider_name}: {e}")

    conn.close()
    return total
