import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import numpy as np
import matplotlib.pyplot as plt
import scipy.stats as sstat
import json

from etc import rettich_encrypt

auth_url = "https://www.strava.com/oauth/token"

payload = {
    'client_id': "114307",
    'client_secret': rettich_encrypt.decode(rettich_encrypt.password, rettich_encrypt.encoded_client_secret),
    'refresh_token': '',
    'grant_type': "refresh_token",
    'f': 'json'
}

# =============================================================================
# Insert refresh tokens here
# =============================================================================
refresh_tokens = [rettich_encrypt.decode(rettich_encrypt.password, rettich_encrypt.encoded_refresh_tokens_Felix),
                  rettich_encrypt.decode(rettich_encrypt.password, rettich_encrypt.encoded_refresh_tokens_Philipp),
                  rettich_encrypt.decode(rettich_encrypt.password, rettich_encrypt.encoded_refresh_tokens_Flo)]

names = ['Felix', 'Philipp', 'Flo']

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
    f.write("felix_json = '")
    json.dump(streams[0],f)
    f.write("'\n")
    f.write("flo_json = '")
    json.dump(streams[2],f)
    f.write("'\n")
    f.write("philipp_json = '")
    json.dump(streams[1],f)
    f.write("'")

def intersection(lst1, lst2):
    lst3 = [value for value in lst1 if value in lst2]
    return lst3

segment_list = intersection([a['name'] for a in segments[2]['segment_efforts']],intersection([a['name'] for a in segments[0]['segment_efforts']],[a['name'] for a in segments[1]['segment_efforts']]))


felix = [0,0,0]
philipp = [0,0,0]
flo = [0,0,0]

segment_efforts = {}


for segment_name in segment_list:
    felix_se = {}
    philipp_se = {}
    flo_se = {}
    for i in range(len(segments[0]['segment_efforts'])):
        if segments[0]['segment_efforts'][i]['name']==segment_name:
            seg_eff = segments[0]['segment_efforts'][i]
            felix_se['time'] = seg_eff['elapsed_time']
            felix_se['speed'] = seg_eff['distance']*60*60/(1000*seg_eff['elapsed_time'])
            felix_se['start_index'] = seg_eff['start_index']
            felix_se['end_index'] = seg_eff['end_index']
            
            if 'average_watts' in seg_eff.keys():
                felix_se['power'] = seg_eff['average_watts']

    for i in range(len(segments[1]['segment_efforts'])):
        if segments[1]['segment_efforts'][i]['name']==segment_name:
            seg_eff = segments[1]['segment_efforts'][i]
            philipp_se['time'] = seg_eff['elapsed_time']
            philipp_se['speed'] = seg_eff['distance']*60*60/(1000*seg_eff['elapsed_time'])
            philipp_se['start_index'] = seg_eff['start_index']
            philipp_se['end_index'] = seg_eff['end_index']
            
            if 'average_watts' in seg_eff.keys():
                philipp_se['power'] = seg_eff['average_watts']

    for i in range(len(segments[2]['segment_efforts'])):
        if segments[2]['segment_efforts'][i]['name']==segment_name:
            seg_eff = segments[2]['segment_efforts'][i]
            flo_se['time'] = seg_eff['elapsed_time']
            flo_se['speed'] = seg_eff['distance']*60*60/(1000*seg_eff['elapsed_time'])
            flo_se['start_index'] = seg_eff['start_index']
            flo_se['end_index'] = seg_eff['end_index']
            
            if 'average_watts' in seg_eff.keys():
                flo_se['power'] = seg_eff['average_watts']
            


    
    times = [felix_se['time'], philipp_se['time'], flo_se['time']]
    ranks = sstat.rankdata(times,).astype(int)-1 
    segment_info = {'start_latlng':seg_eff['segment']['start_latlng'], 'end_latlng':seg_eff['segment']['end_latlng']}
    segment_name_clean = segment_name.replace("'","")
    segment_name_clean = segment_name_clean.replace(',','')
    segment_efforts[segment_name_clean] = {'Felix':felix_se, 'Philipp':philipp_se, 'Flo':flo_se, 'Segment':segment_info}
    felix[ranks[0]] = felix[ranks[0]]+1
    philipp[ranks[1]] = philipp[ranks[1]]+1
    flo[ranks[2]] = flo[ranks[2]]+1
    
medals = {"Felix": felix, "Philipp":philipp, "Flo":flo} 






with open('./frontend/data/stats.js', 'w') as f:
    f.write("medals = '")
    json.dump(medals,f)
    f.write("'\n")
    f.write("segment_efforts = '")
    json.dump(segment_efforts,f)
    f.write("'")