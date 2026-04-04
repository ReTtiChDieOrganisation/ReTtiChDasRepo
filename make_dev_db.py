#!/usr/bin/env python3
"""Create a dev database with only the last 6 months of activities.

Usage:
    python make_dev_db.py
    
Produces rettich_dev.db. Then run:
    python build.py --db rettich_dev.db
"""

import os
import shutil
import sqlite3
from datetime import datetime, timedelta

SRC = 'rettich.db'
DST = 'rettich_dev.db'

cutoff = (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d')

print(f"Copying {SRC} -> {DST} and pruning before {cutoff}...")

shutil.copy2(SRC, DST)

conn = sqlite3.connect(DST)
conn.execute("PRAGMA foreign_keys=OFF")

conn.execute("DELETE FROM activities WHERE date < ?", (cutoff,))
deleted = conn.execute("SELECT changes()").fetchone()[0]

# Cascade manually since foreign_keys is off
conn.execute("""
    DELETE FROM streams WHERE activity_id NOT IN (SELECT id FROM activities)
""")
conn.execute("""
    DELETE FROM segment_efforts WHERE activity_id NOT IN (SELECT id FROM activities)
""")
conn.execute("""
    DELETE FROM group_activities WHERE activity_id NOT IN (SELECT id FROM activities)
""")
conn.execute("""
    DELETE FROM groups_table WHERE id NOT IN (
        SELECT group_id FROM group_activities
    )
""")

conn.commit()
conn.execute("VACUUM")
conn.close()

src_mb = os.path.getsize(SRC) / 1024 / 1024
dst_mb = os.path.getsize(DST) / 1024 / 1024
print(f"Done. Removed {deleted} activities.")
print(f"  {SRC}: {src_mb:.1f} MB  ->  {DST}: {dst_mb:.1f} MB")