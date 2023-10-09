import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import numpy as np
import matplotlib.pyplot as plt
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
    f.write("'\n")
