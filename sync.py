#!/usr/bin/env python3
"""Sync Strava data for all riders."""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from backend.sync import sync_all


def main():
    config_path = os.path.join(os.path.dirname(__file__), 'config', 'config.json')
    if not os.path.exists(config_path):
        print("Error: config/config.json not found.")
        print("Copy config/config.example.json to config/config.json and fill in your credentials.")
        sys.exit(1)

    with open(config_path) as f:
        config = json.load(f)

    # Handle old config format (riders at top level vs nested)
    if 'riders' not in config:
        # Convert old format: extract riders from top-level keys
        riders = {}
        non_rider_keys = {'client_id', 'client_secret', 'site_password'}
        for key, val in config.items():
            if key not in non_rider_keys and isinstance(val, dict) and 'refresh_token' in val:
                riders[key] = val
        config['riders'] = riders

    print("=== ReTtiCh Strava Sync ===")
    total = sync_all(config)
    print(f"\nDone! {total} new activities synced.")


if __name__ == '__main__':
    main()
