"""Strava API client with rate-limit handling and incremental sync."""

import time
import requests
from datetime import datetime

STRAVA_AUTH_URL = "https://www.strava.com/oauth/token"
STRAVA_API_BASE = "https://www.strava.com/api/v3"


class StravaRateLimitError(Exception):
    """Raised when Strava API rate limit is hit."""
    def __init__(self, usage_15m, limit_15m, usage_daily, limit_daily):
        self.usage_15m = usage_15m
        self.limit_15m = limit_15m
        self.usage_daily = usage_daily
        self.limit_daily = limit_daily
        super().__init__(
            f"Rate limited: 15min {usage_15m}/{limit_15m}, daily {usage_daily}/{limit_daily}"
        )


def _check_rate_limit(response):
    """Check Strava rate limit headers and raise if exceeded."""
    limit_15m = response.headers.get('X-RateLimit-Limit', '100,1000').split(',')
    usage = response.headers.get('X-RateLimit-Usage', '0,0').split(',')
    usage_15m = int(usage[0])
    usage_daily = int(usage[1])
    limit_15m_val = int(limit_15m[0])
    limit_daily_val = int(limit_15m[1]) if len(limit_15m) > 1 else 1000

    if response.status_code == 429 or usage_15m >= limit_15m_val or usage_daily >= limit_daily_val:
        raise StravaRateLimitError(usage_15m, limit_15m_val, usage_daily, limit_daily_val)

    return usage_15m, usage_daily


def refresh_access_token(client_id, client_secret, refresh_token):
    """Get a fresh access token using the refresh token."""
    resp = requests.post(STRAVA_AUTH_URL, data={
        'client_id': client_id,
        'client_secret': client_secret,
        'refresh_token': refresh_token,
        'grant_type': 'refresh_token'
    })
    resp.raise_for_status()
    data = resp.json()
    return data['access_token'], data['expires_at'], data.get('refresh_token', refresh_token)


def get_activities(access_token, after_epoch=0, page=1, per_page=50):
    """Fetch activities list, only those after the given epoch."""
    resp = requests.get(f"{STRAVA_API_BASE}/athlete/activities", headers={
        'Authorization': f'Bearer {access_token}'
    }, params={
        'after': after_epoch,
        'page': page,
        'per_page': per_page
    })
    _check_rate_limit(resp)
    resp.raise_for_status()
    return resp.json()


def get_activity_detail(access_token, activity_id):
    """Fetch detailed activity including segment efforts."""
    resp = requests.get(f"{STRAVA_API_BASE}/activities/{activity_id}", headers={
        'Authorization': f'Bearer {access_token}'
    }, params={
        'include_all_efforts': 'true'
    })
    _check_rate_limit(resp)
    resp.raise_for_status()
    return resp.json()


def get_activity_streams(access_token, activity_id):
    """Fetch activity streams (time, latlng, distance, altitude, watts)."""
    keys = 'time,latlng,distance,altitude,watts'
    resp = requests.get(f"{STRAVA_API_BASE}/activities/{activity_id}/streams", headers={
        'Authorization': f'Bearer {access_token}'
    }, params={
        'keys': keys,
        'key_type': 'distance'
    })
    _check_rate_limit(resp)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()

    streams = {}
    for s in resp.json():
        streams[s['type']] = s['data']
    return streams


def parse_activity_summary(rider_name, act_json):
    """Parse a Strava activity summary into our DB format."""
    start_date = act_json.get('start_date_local', act_json.get('start_date', ''))
    dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))

    return {
        'id': act_json['id'],
        'rider_name': rider_name,
        'name': act_json.get('name', ''),
        'type': act_json.get('type', 'Ride'),
        'date': dt.strftime('%Y-%m-%d'),
        'start_date_local': start_date,
        'start_epoch': int(dt.timestamp()),
        'elapsed_time': act_json.get('elapsed_time', 0),
        'moving_time': act_json.get('moving_time'),
        'distance': act_json.get('distance'),
        'total_elevation_gain': act_json.get('total_elevation_gain'),
        'average_speed': act_json.get('average_speed'),
        'max_speed': act_json.get('max_speed'),
        'average_watts': act_json.get('average_watts'),
        'summary_polyline': act_json.get('map', {}).get('summary_polyline')
    }


def parse_segment_efforts(rider_name, activity_id, detail_json):
    """Extract segment efforts from detailed activity."""
    efforts = []
    for se in detail_json.get('segment_efforts', []):
        seg = se.get('segment', {})
        efforts.append({
            'id': se['id'],
            'activity_id': activity_id,
            'segment_id': seg.get('id', se.get('segment', {}).get('id')),
            'segment_name': se.get('name', seg.get('name', '')),
            'rider_name': rider_name,
            'elapsed_time': se.get('elapsed_time', 0),
            'distance': seg.get('distance'),
            'avg_grade': seg.get('average_grade'),
            'start_index': se.get('start_index'),
            'end_index': se.get('end_index'),
            'average_watts': se.get('average_watts')
        })
    return efforts
