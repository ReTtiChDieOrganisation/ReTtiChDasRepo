import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import numpy as np
import matplotlib.pyplot as plt
import scipy.stats as sstat
import json

from etc import rettich_encrypt

auth_url = "https://www.strava.com/oauth/token"

password = rettich_encrypt.get_access()

payload = {
    'client_id': "114307",
    'client_secret': rettich_encrypt.decode(password, rettich_encrypt.get_client_secret()),
    'refresh_token': '',
    'grant_type': "refresh_token",
    'f': 'json'
}

# =============================================================================
# Insert refresh tokens here
# =============================================================================

with open('./data/unique_identifier.json','r') as f:
    unique_identifier = json.load(f)
names = list(unique_identifier.keys())

# TODO: remove magic number 3 and make more general
names = [names[i] for i in range(3)]

refresh_tokens = [rettich_encrypt.decode(password, bytes(unique_identifier[name],  'utf-8'))for name in names]

streams = []
segments = []
for refresh_token in refresh_tokens:

    payload['refresh_token']=refresh_token
    print("Requesting Token...\n")
    res = requests.post(auth_url, data=payload, verify=False)
    access_token = res.json()['access_token']
    print("Access Token = {}\n".format(access_token))
    
    header = {'Authorization': 'Bearer ' + access_token}
    param = {'per_page': 20, 'page': 1}
    
    
    # =============================================================================
    # activity information
    # =============================================================================
    
    activites_url = "https://www.strava.com/api/v3/athlete/activities"
    my_dataset = requests.get(activites_url, headers=header, params=param).json()
    
    id_last_tour = my_dataset[0]['id']
    segments_url = 'https://www.strava.com/api/v3/activities/'+str(id_last_tour)+'?include_all_efforts=True'
    my_segments = requests.get(segments_url, headers=header, params=param).json()
    
    # stream_url = 'https://www.strava.com/api/v3/activities/'+str(id_last_tour)+'/streams'
    # my_stream =  requests.get(stream_url, headers=header, params=param).json()
    
    
    stream_url = 'https://www.strava.com/api/v3/activities/'+str(id_last_tour)+'/streams?keys=time,distance,latlng,altitude,heartrate&key_by_type=true'
    all_stream =  requests.get(stream_url, headers=header, params=param).json()
    
    streams.append(all_stream)
    segments.append(my_segments)


with open('./frontend/data/data.js', 'w') as f:
    for i, name in enumerate(names):
        
        f.write(name.lower()+"_json = '")
        json.dump(streams[i],f)
        f.write("'\n")


def intersection(lst1, lst2):
    lst3 = [value for value in lst1 if value in lst2]
    return lst3

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



with open('./frontend/data/stats.js', 'w') as f:
    f.write("medals = '")
    json.dump(medals,f)
    f.write("'\n")
    f.write("segment_efforts = '")
    json.dump(segment_efforts,f)
    f.write("'")