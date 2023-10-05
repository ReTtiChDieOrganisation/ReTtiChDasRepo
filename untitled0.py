import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import numpy as np
import matplotlib.pyplot as plt

auth_url = "https://www.strava.com/oauth/token"

payload = {
    'client_id': "114307",
    'client_secret': 'XXXXXXX',
    'refresh_token': '',

    'grant_type': "refresh_token",
    'f': 'json'
}

# =============================================================================
# Insert refresh tokens here
# =============================================================================
refresh_tokens = ['']

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
    
lat_lngs = [a['latlng']['data'] for a in streams]


max_length= max([len(a) for a in lat_lngs])

lat_lngs_arr = np.empty((max_length,2,len(lat_lngs)))
lat_lngs_arr.fill(np.nan)


for i,ll in enumerate(lat_lngs):
    ll_arr = np.array(ll)
    lat_lngs_arr[-len(ll):,:,i]=ll_arr



max_lat = np.nanmax(lat_lngs_arr[:,0,:])
min_lat = np.nanmin(lat_lngs_arr[:,0,:])

max_lng = np.nanmax(lat_lngs_arr[:,1,:])
min_lng = np.nanmin(lat_lngs_arr[:,1,:])


for i in range(65):
    for rider in range(len(names)):
        plt.scatter(lat_lngs_arr[i*60,0,rider],lat_lngs_arr[i*60,1,rider],label=names[rider])
    plt.xlim([min_lat,max_lat])
    plt.ylim([min_lng,max_lng])
    plt.legend()
    plt.show()

segment_name = 'Ab nach Porz'
for seg_eff in my_segments['segment_efforts']:
    if seg_eff['name']==segment_name:
        break
