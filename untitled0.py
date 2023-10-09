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
    felix_time = [a['elapsed_time'] for a in segments[0]['segment_efforts'] if a['name']==segment_name][0]
    flo_time = [a['elapsed_time'] for a in segments[2]['segment_efforts'] if a['name']==segment_name][0]
    philipp_time = [a['elapsed_time'] for a in segments[1]['segment_efforts'] if a['name']==segment_name][0]
    
    times = [felix_time, philipp_time, flo_time]
    ranks = sstat.rankdata(times,).astype(int)-1 
    
    segment_efforts[segment_name] = {'Felix':felix_time, 'Philipp':philipp_time, 'Flo':flo_time}
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