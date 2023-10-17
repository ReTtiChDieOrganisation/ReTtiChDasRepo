from etc import rettich_encrypt
import os
import json
import scipy.stats as sstat
import numpy as np
import iso8601
import datetime
import itertools
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


NO_DAYS = 7  # number of days which are saved and displayed
SHARED_SEGS = 10  # number of share segments such that it counts as a group

RAW_PATH = './frontend/data/strava/raw_data/'
DATA_PATH = './frontend/data/strava/'


def load_data():
    '''
    Loads raw data of the last NO_DAYS days into RAW_PATH and clears all old and other files in this folder
    Saves accumulated data in DATA_PATH + 'data.json'
    '''

    #with open('./etc/etc.txt', 'r') as f:
    #    client_sc = f.read()
    client_sc = '290331dcc0fb07054618452f7fc4dde505c77345'
    password = 'pass'
    payload = {
        'client_id': "114307",
        'client_secret': client_sc,
        'refresh_token': '',
        'grant_type': "refresh_token",
        'f': 'json'
    }

    with open('./data/riders.json', 'r') as f:
        riders = json.load(f)
    names = list(riders.keys())

    refresh_tokens = [rettich_encrypt.decode(password, bytes(riders[name]['refresh_token'],  'utf-8'))for name in names]

    if not os.path.exists(RAW_PATH):
        os.mkdir(RAW_PATH)
    remove_activities = os.listdir(RAW_PATH)  # get all saved activities to delete those which are not needed anymore

    our_id = 0
    all_rides = {}
    for rider_idx, refresh_token in enumerate(refresh_tokens):

        payload['refresh_token'] = refresh_token
        print("Requesting Token...\n")
        res = requests.post("https://www.strava.com/oauth/token", data=payload, verify=False)
        access_token = res.json()['access_token']
        header = {'Authorization': 'Bearer ' + access_token}
        param = {'per_page': 50, 'page': 1}

        # =============================================================================
        # activity information
        # =============================================================================
        # retrieve last 50 activities
        activites_url = "https://www.strava.com/api/v3/athlete/activities"
        last_activities = requests.get(activites_url, headers=header, params=param).json()

        for activity in last_activities:
            today = datetime.date.today()
            act_date = datetime.datetime.date(iso8601.parse_date(activity['start_date']))
            if today-act_date > datetime.timedelta(days=NO_DAYS):
                break

            act_id = activity['id']
            if not os.path.exists(RAW_PATH+str(act_id)+'.json') and (activity['sport_type'] in ['Ride', 'Run']):
                detailed_url = 'https://www.strava.com/api/v3/activities/'+str(act_id)+'?include_all_efforts=True'
                detailed_act = requests.get(detailed_url, headers=header, params=param).json()

                stream_url = 'https://www.strava.com/api/v3/activities/' + \
                    str(act_id)+'/streams?keys=time,distance,latlng,altitude,heartrate&key_by_type=true'
                full_act = requests.get(stream_url, headers=header, params=param).json()
                full_act['strava_id'] = act_id
                full_act['rider'] = names[rider_idx]
                full_act['start_date'] = str(iso8601.parse_date(activity['start_date']))
                full_act['segment_efforts'] = detailed_act['segment_efforts']
                for i in range(len(full_act['segment_efforts'])):
                    segment_name = full_act['segment_efforts'][i]['name']
                    segment_name_clean = segment_name.replace("'", "")
                    segment_name_clean = segment_name_clean.replace(',', '')
                    full_act['segment_efforts'][i]['name'] = segment_name_clean
                    full_act['segment_efforts'][i]['segment']['name'] = segment_name_clean

                with open(RAW_PATH+str(act_id)+'.json', 'w') as f:
                    json.dump(full_act, f)
            elif str(act_id)+'.json' in remove_activities:
                remove_activities.remove(str(act_id)+'.json')

                with open(RAW_PATH+str(act_id)+'.json', 'r') as f:
                    full_act = json.load(f)

            all_rides[our_id] = full_act
            our_id += 1

    for file in remove_activities:
        os.remove(RAW_PATH+file)

    with open(DATA_PATH + 'data.json', 'w') as f:
        json.dump(all_rides, f)


def calculate_stats():
    '''
    loads data from DATA_PATH +'data.json' calculates the groups and the statistics for each group and saves them to 
    '''
    def intersection(lst1, lst2):
        lst3 = [value for value in lst1 if value in lst2]
        return lst3

    with open(DATA_PATH + 'data.json', 'r') as f:
        all_rides = json.load(f)
    with open('./data/riders.json', 'r') as f:
        riders = json.load(f)
    names = list(riders.keys())
    groups = []

    # find groups which share more than SHARED_SEGS = 10 segments (only from the same day)

    for day_del in range(NO_DAYS):
        today = datetime.date.today()

        # get all indices from i days ago
        day_idcs = []
        for i in range(len(all_rides)):
            act_date = datetime.datetime.date(iso8601.parse_date(all_rides[str(i)]['start_date']))
            if today-act_date == datetime.timedelta(days=day_del):
                day_idcs.append(i)

        # TODO now we have all indices from this day and have to check all possible subsets for intersection of segments
        for L in range(len(day_idcs)-1):
            for subset in itertools.combinations(day_idcs, L+2):  # TODO this gets big if the sets get large
                for i in range(len(subset)):
                    if not i:
                        segments = [seg['name'] for seg in all_rides[str(subset[i])]['segment_efforts']]
                    else:
                        segments = intersection(segments, [seg['name']
                                                for seg in all_rides[str(subset[i])]['segment_efforts']])
                    if len(segments) < SHARED_SEGS:
                        break
                if len(segments) > SHARED_SEGS:
                    groups.append(list(subset))

    groups.sort(key=len, reverse=True)
    for group in groups:
        for L in range(2, len(group)):
            for subset in itertools.combinations(group, L):
                groups.remove(list(subset))

    # one group for each rider consisting of all of their rides
    for name in names:
        id_list_rider = [i for i in range(len(all_rides)) if all_rides[str(i)]['rider'] == name]
        groups.append(id_list_rider)

    # add group of all rides
    groups.append(list(np.arange(len(all_rides))))

    # calculate stats for each group
    all_groups = {}
    group_id = 0
    for group in groups:
        # for some reason there are some int32 and not int and this does not work with json.dump
        group = [int(g) for g in group]
        shared_segments = [seg['name'] for seg in all_rides[str(group[0])]['segment_efforts']]
        for i in range(1, len(group)):
            shared_segments = intersection(shared_segments, [seg['name']
                                           for seg in all_rides[str(group[i])]['segment_efforts']])

        segment_efforts = {}

        medal_arr = np.zeros((len(group), 3))

        for segment_name in shared_segments:
            for idx_in_group, ride_idx in enumerate(group):
                activity_stats = all_rides[str(ride_idx)]
                ride_segment_efforts = {}

                for seg_idx in range(len(activity_stats['segment_efforts'])):
                    seg_eff = activity_stats['segment_efforts'][seg_idx]
                    if seg_eff['name'] == segment_name:
                        ride_segment_efforts['time'] = seg_eff['elapsed_time']
                        ride_segment_efforts['speed'] = seg_eff['distance']*60*60/(1000*seg_eff['elapsed_time'])
                        ride_segment_efforts['start_index'] = seg_eff['start_index']
                        ride_segment_efforts['end_index'] = seg_eff['end_index']
                        if 'average_watts' in seg_eff.keys():
                            ride_segment_efforts['power'] = seg_eff['average_watts']
                segment_name_clean = segment_name.replace("'", "")
                segment_name_clean = segment_name_clean.replace(',', '')
                if not idx_in_group:
                    segment_info = {'start_latlng': seg_eff['segment']
                                    ['start_latlng'], 'end_latlng': seg_eff['segment']['end_latlng']}
                    segment_efforts[segment_name_clean] = {ride_idx: ride_segment_efforts, 'Segment': segment_info}
                else:
                    segment_efforts[segment_name_clean][ride_idx] = ride_segment_efforts

            times = [segment_efforts[segment_name_clean][ride_idx]['time'] for ride_idx in group]
            ranks = sstat.rankdata(times,).astype(int)-1
            for i in range(len(group)):
                if ranks[i] < 3:
                    medal_arr[i, ranks[i]] += 1

        all_groups[str(group_id)] = {'segments': segment_efforts, 'ride_ids': group, 'medals': {group[i]: list(
            medal_arr[i, :]) for i in range(len(group))}, 'riders': [all_rides[str(i)]['rider'] for i in group]}
        group_id += 1

    with open(DATA_PATH+'stats.json', 'w') as f:
        json.dump(all_groups, f)


if __name__ == "__main__":
    load_data()
    calculate_stats()
