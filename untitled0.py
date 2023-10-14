import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


import itertools
import datetime
import iso8601
import numpy as np

import scipy.stats as sstat
import json
import os

from etc import rettich_encrypt


NO_DAYS = 7 # number of days which are saved and displayed
activity_path = './frontend/data/raw_data/'
SHARED_SEGS = 10 #number of share segments such that it counts as a group
# =============================================================================
#               Check for new data and load/save all data
# =============================================================================
password = rettich_encrypt.get_access()

payload = {
    'client_id': "114307",
    'client_secret': rettich_encrypt.decode(password, rettich_encrypt.get_client_secret()),
    'refresh_token': '',
    'grant_type': "refresh_token",
    'f': 'json'
}



with open('./data/riders.json','r') as f:
    riders = json.load(f)
names = list(riders.keys())

refresh_tokens = [rettich_encrypt.decode(password, bytes(riders[name]['refresh_token'],  'utf-8'))for name in names]


if not os.path.exists(activity_path):
    os.mkdir(activity_path)
remove_activities = os.listdir(activity_path) # get all saved activities to delete those which are not needed anymore


our_id = 0
all_rides = {}
for rider_idx, refresh_token in enumerate(refresh_tokens):

    payload['refresh_token']=refresh_token
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
        if today-act_date>datetime.timedelta(days=NO_DAYS):
            break
        
        
        act_id = activity['id']
        if not os.path.exists(activity_path+str(act_id)+'.json') and (activity['sport_type'] in ['Ride','Run']):
            detailed_url = 'https://www.strava.com/api/v3/activities/'+str(act_id)+'?include_all_efforts=True'
            detailed_act = requests.get(detailed_url, headers=header, params=param).json()
            
            stream_url = 'https://www.strava.com/api/v3/activities/'+str(act_id)+'/streams?keys=time,distance,latlng,altitude,heartrate&key_by_type=true'
            full_act =  requests.get(stream_url, headers=header, params=param).json()
            full_act['strava_id'] = act_id
            full_act['rider'] = names[rider_idx]
            full_act['start_date'] = str(iso8601.parse_date(activity['start_date']))
            full_act['segment_efforts'] = detailed_act['segment_efforts']
            
            with open(activity_path+str(act_id)+'.json', 'w') as f:
                json.dump(full_act,f)
        elif str(act_id)+'.json' in remove_activities:
            remove_activities.remove(str(act_id)+'.json')
            
            with open(activity_path+str(act_id)+'.json', 'r') as f:
                full_act = json.load(f)
                
        all_rides[our_id]=full_act
        our_id += 1
        
            
            
for file in remove_activities:
    os.remove(activity_path+file)
                    
            
with open('./frontend/data/data.js', 'w') as f:
    json.dump(all_rides,f)
            
            
# =============================================================================
#         Find groups, calculate stats, save groups and stats
# =============================================================================
def intersection(lst1, lst2):
    lst3 = [value for value in lst1 if value in lst2]
    return lst3
groups = []
           
# find groups which share more than shared_segs = 15 segments (only from the same day)

for day_del in range(NO_DAYS):
    today = datetime.date.today()

    
    #get all indices from i days ago
    day_idcs = []
    for i in range(len(all_rides)):
        act_date = datetime.datetime.date(iso8601.parse_date(all_rides[i]['start_date']))
        if today-act_date==datetime.timedelta(days=day_del):
            day_idcs.append(i)
        
    # TODO now we have all indices from this day and have to check all possible subsets for intersection of segments
    for L in range(len(day_idcs)-1):
        for subset in itertools.combinations(day_idcs, L+2): # TODO this gets big if the sets get large
            for i in range(len(subset)):
                if not i:
                    segments = [seg['name'] for seg in all_rides[subset[i]]['segment_efforts']]
                else:
                    segments =  intersection(segments, [seg['name'] for seg in all_rides[subset[i]]['segment_efforts']])
                if len(segments) < SHARED_SEGS:
                    break
            if len(segments) > SHARED_SEGS:
                groups.append(list(subset))
                
            
# TODO alle subsets rausschmeißen
# also wenn (1,2,3) dann (1,2) und (1,3) und (2,3) rausschmeißen
# Sort bei length longest first and then use itertools.combinations und groups.remove to remove subsets


# one group for each rider consisting of all of their rides

groups.append(list(np.arange(len(all_rides))))


       

# TODO calculate groups
# TODO save group stats with group id in frontend/data/stats.json
#       - groups should be collection of ids and it is probably easiest if ids correspond to idcs in the data.json /all_reides
#       - there should also be one group for each rider consisting of all activities from this rider we have to figure out 
#           what to show in the stats then first use dummys
# TODO make chapters into functions and then add a if __name__ == "__main__": which consecutively calls both functions

        

    
    
if False:    
    


    
    

    
    segment_list = intersection([a['name'] for a in segments[2]['segment_efforts']],intersection([a['name'] for a in segments[0]['segment_efforts']],[a['name'] for a in segments[1]['segment_efforts']]))
    
    segment_efforts = {}
    medal_arr = np.zeros((len(names),3))
    
    for segment_name in segment_list:
    
        for idx_rider, seg_stream in enumerate(segments):
            personal_se = {}
            for i in range(len(seg_stream['segment_efforts'])):
                if seg_stream['segment_efforts'][i]['name']==segment_name:
                    seg_eff = seg_stream['segment_efforts'][i]
                    personal_se['time'] = seg_eff['elapsed_time']
                    personal_se['speed'] = seg_eff['distance']*60*60/(1000*seg_eff['elapsed_time'])
                    personal_se['start_index'] = seg_eff['start_index']
                    personal_se['end_index'] = seg_eff['end_index']
                    
                    if 'average_watts' in seg_eff.keys():
                        personal_se['power'] = seg_eff['average_watts']
            segment_name_clean = segment_name.replace("'","")
            segment_name_clean = segment_name_clean.replace(',','')
            if not idx_rider:
                segment_info = {'start_latlng':seg_eff['segment']['start_latlng'], 'end_latlng':seg_eff['segment']['end_latlng']}
                segment_efforts[segment_name_clean] = {names[idx_rider]:personal_se, 'Segment':segment_info}
            else:
                segment_efforts[segment_name_clean][names[idx_rider]] = personal_se
    
    
    
        times = [segment_efforts[segment_name_clean][name]['time'] for name in names]
        ranks = sstat.rankdata(times,).astype(int)-1 
        
        for idx_rider in range(len(names)):
            medal_arr[idx_rider,ranks[idx_rider]] +=1
    
        
    medals = {names[i]: list(medal_arr[i,:]) for i in range(len(names))} 
    
    
    
    # with open('./frontend/data/stats.js', 'w') as f:
    #     f.write("medals = '")
    #     json.dump(medals,f)
    #     f.write("'\n")
    #     f.write("segment_efforts = '")
    #     json.dump(segment_efforts,f)
    #     f.write("'")
