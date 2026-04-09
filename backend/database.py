"""SQLite database for storing Strava ride data."""

import sqlite3
import json
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "rettich.db")


def get_connection(db_path=None):
    conn = sqlite3.connect(db_path or DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path=None):
    """Create all tables if they don't exist."""
    conn = get_connection(db_path)
    c = conn.cursor()

    c.executescript("""
        CREATE TABLE IF NOT EXISTS riders (
            name TEXT PRIMARY KEY,
            refresh_token TEXT NOT NULL,
            access_token TEXT,
            token_expires_at INTEGER DEFAULT 0,
            icon_url TEXT,
            frame TEXT DEFAULT 'default'
        );

        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY,
            rider_name TEXT NOT NULL REFERENCES riders(name),
            name TEXT,
            activity_type TEXT DEFAULT 'Ride',
            date TEXT NOT NULL,
            start_date_local TEXT NOT NULL,
            start_epoch INTEGER NOT NULL,
            elapsed_time INTEGER NOT NULL,
            moving_time INTEGER,
            distance REAL,
            total_elevation_gain REAL,
            average_speed REAL,
            max_speed REAL,
            average_watts REAL,
            summary_polyline TEXT
        );

        CREATE TABLE IF NOT EXISTS streams (
            activity_id INTEGER PRIMARY KEY REFERENCES activities(id),
            time_data TEXT,
            latlng_data TEXT,
            distance_data TEXT,
            altitude_data TEXT,
            watts_data TEXT
        );

        CREATE TABLE IF NOT EXISTS segment_efforts (
            id INTEGER PRIMARY KEY,
            activity_id INTEGER NOT NULL REFERENCES activities(id),
            segment_id INTEGER NOT NULL,
            segment_name TEXT,
            rider_name TEXT NOT NULL,
            elapsed_time INTEGER NOT NULL,
            distance REAL,
            avg_grade REAL,
            start_index INTEGER,
            end_index INTEGER,
            average_watts REAL
        );

        CREATE TABLE IF NOT EXISTS groups_table (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            date TEXT NOT NULL,
            group_type TEXT NOT NULL DEFAULT 'segment',
            shared_segment_count INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS group_activities (
            group_id INTEGER NOT NULL REFERENCES groups_table(id) ON DELETE CASCADE,
            activity_id INTEGER NOT NULL REFERENCES activities(id),
            PRIMARY KEY (group_id, activity_id)
        );

        CREATE TABLE IF NOT EXISTS sync_state (
            rider_name TEXT PRIMARY KEY REFERENCES riders(name),
            last_activity_epoch INTEGER DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_activities_date ON activities(date);
        CREATE INDEX IF NOT EXISTS idx_activities_rider ON activities(rider_name);
        CREATE INDEX IF NOT EXISTS idx_segment_efforts_activity ON segment_efforts(activity_id);
        CREATE INDEX IF NOT EXISTS idx_segment_efforts_segment ON segment_efforts(segment_id);
    """)

    conn.commit()
    conn.close()


# --- Rider operations ---

def upsert_rider(conn, name, refresh_token, icon_url, frame):
    conn.execute("""
        INSERT INTO riders (name, refresh_token, icon_url, frame)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(name) DO UPDATE SET
            refresh_token=excluded.refresh_token,
            icon_url=excluded.icon_url,
            frame=excluded.frame
    """, (name, refresh_token, icon_url, frame))
    conn.execute("""
        INSERT INTO sync_state (rider_name, last_activity_epoch)
        VALUES (?, 0)
        ON CONFLICT(rider_name) DO NOTHING
    """, (name,))
    conn.commit()


def update_token(conn, rider_name, access_token, expires_at, refresh_token=None):
    conn.execute("""
        UPDATE riders
        SET access_token=?,
            token_expires_at=?,
            refresh_token=COALESCE(?, refresh_token)
        WHERE name=?
    """, (access_token, expires_at, refresh_token, rider_name))
    conn.commit()


def get_rider(conn, name):
    return conn.execute("SELECT * FROM riders WHERE name=?", (name,)).fetchone()


def get_all_riders(conn):
    return conn.execute("SELECT * FROM riders").fetchall()


# --- Activity operations ---

def activity_exists(conn, activity_id):
    row = conn.execute("SELECT 1 FROM activities WHERE id=?", (activity_id,)).fetchone()
    return row is not None


def insert_activity(conn, act):
    conn.execute("""
        INSERT OR IGNORE INTO activities
        (id, rider_name, name, activity_type, date, start_date_local, start_epoch,
         elapsed_time, moving_time, distance, total_elevation_gain,
         average_speed, max_speed, average_watts, summary_polyline)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        act['id'], act['rider_name'], act.get('name', ''),
        act.get('type', 'Ride'),
        act['date'], act['start_date_local'], act['start_epoch'],
        act['elapsed_time'], act.get('moving_time'),
        act.get('distance'), act.get('total_elevation_gain'),
        act.get('average_speed'), act.get('max_speed'),
        act.get('average_watts'), act.get('summary_polyline')
    ))
    conn.commit()


def insert_stream(conn, activity_id, time_data, latlng_data, distance_data, altitude_data, watts_data=None):
    conn.execute("""
        INSERT OR REPLACE INTO streams
        (activity_id, time_data, latlng_data, distance_data, altitude_data, watts_data)
        VALUES (?,?,?,?,?,?)
    """, (
        activity_id,
        json.dumps(time_data),
        json.dumps(latlng_data),
        json.dumps(distance_data),
        json.dumps(altitude_data),
        json.dumps(watts_data) if watts_data else None
    ))
    conn.commit()


def stream_exists(conn, activity_id):
    row = conn.execute("SELECT 1 FROM streams WHERE activity_id=?", (activity_id,)).fetchone()
    return row is not None


def insert_segment_effort(conn, effort):
    conn.execute("""
        INSERT OR IGNORE INTO segment_efforts
        (id, activity_id, segment_id, segment_name, rider_name,
         elapsed_time, distance, avg_grade, start_index, end_index, average_watts)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, (
        effort['id'], effort['activity_id'], effort['segment_id'],
        effort.get('segment_name', ''), effort['rider_name'],
        effort['elapsed_time'], effort.get('distance'),
        effort.get('avg_grade'), effort.get('start_index'),
        effort.get('end_index'), effort.get('average_watts')
    ))
    conn.commit()


# --- Sync state ---

def get_last_sync_epoch(conn, rider_name):
    row = conn.execute("SELECT last_activity_epoch FROM sync_state WHERE rider_name=?",
                       (rider_name,)).fetchone()
    return row['last_activity_epoch'] if row else 0


def update_last_sync_epoch(conn, rider_name, epoch):
    conn.execute("UPDATE sync_state SET last_activity_epoch=? WHERE rider_name=?",
                 (epoch, rider_name))
    conn.commit()


# --- Group operations ---

def clear_groups(conn):
    conn.execute("DELETE FROM group_activities")
    conn.execute("DELETE FROM groups_table")
    conn.commit()


def clear_groups_for_dates(conn, dates):
    if not dates:
        return
    placeholders = ','.join('?' * len(dates))
    group_ids = [r[0] for r in conn.execute(
        f"SELECT id FROM groups_table WHERE date IN ({placeholders})", list(dates)
    ).fetchall()]
    if group_ids:
        ph = ','.join('?' * len(group_ids))
        conn.execute(f"DELETE FROM group_activities WHERE group_id IN ({ph})", group_ids)
        conn.execute(f"DELETE FROM groups_table WHERE id IN ({ph})", group_ids)
    conn.commit()


def insert_group(conn, name, date, group_type, shared_segment_count, activity_ids):
    c = conn.cursor()
    c.execute("""
        INSERT INTO groups_table (name, date, group_type, shared_segment_count)
        VALUES (?,?,?,?)
    """, (name, date, group_type, shared_segment_count))
    group_id = c.lastrowid
    for aid in activity_ids:
        c.execute("INSERT OR IGNORE INTO group_activities (group_id, activity_id) VALUES (?,?)",
                  (group_id, aid))
    conn.commit()
    return group_id


# --- Query helpers ---

def get_activities_by_date(conn, date):
    return conn.execute("SELECT * FROM activities WHERE date=? ORDER BY start_epoch",
                        (date,)).fetchall()


def get_all_dates(conn):
    rows = conn.execute("SELECT DISTINCT date FROM activities ORDER BY date DESC").fetchall()
    return [r['date'] for r in rows]


def get_segment_efforts_for_activity(conn, activity_id):
    return conn.execute(
        "SELECT * FROM segment_efforts WHERE activity_id=?", (activity_id,)
    ).fetchall()


def get_all_groups(conn):
    rows = conn.execute("""
        SELECT g.*, GROUP_CONCAT(ga.activity_id) as activity_ids
        FROM groups_table g
        JOIN group_activities ga ON g.id = ga.group_id
        GROUP BY g.id
        ORDER BY g.date DESC, g.shared_segment_count DESC
    """).fetchall()
    return rows


def get_stream(conn, activity_id):
    return conn.execute("SELECT * FROM streams WHERE activity_id=?", (activity_id,)).fetchone()


def get_activity(conn, activity_id):
    return conn.execute("SELECT * FROM activities WHERE id=?", (activity_id,)).fetchone()


def get_shared_segments_for_activities(conn, activity_ids):
    """Get segments shared by all activities in the list."""
    if not activity_ids:
        return []
    placeholders = ','.join('?' * len(activity_ids))
    rows = conn.execute(f"""
        SELECT segment_id, segment_name, distance, avg_grade,
               COUNT(DISTINCT activity_id) as ride_count
        FROM segment_efforts
        WHERE activity_id IN ({placeholders})
        GROUP BY segment_id
        HAVING ride_count >= 2
        ORDER BY segment_name
    """, activity_ids).fetchall()
    return rows
