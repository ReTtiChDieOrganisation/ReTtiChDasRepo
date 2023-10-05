

import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)



import pandas as pd
import matplotlib.pyplot as plt
import time
import random




felix_id = '68579963'

auth_url = "https://www.strava.com/oauth/token"
# segments_url = "https://www.strava.com/api/v3/segments/14581228"
# segments_url = "https://www.strava.com/api/v3/segments/14581228/leaderboard?"#?gender=male"#"&following=1"
# segments_url = "https://www.strava.com/api/v3/athletes/68579963"
# segments_url = 'https://www.strava.com/api/v3/activities/9921823048?include_all_efforts=True'
# segments_url = "https://www.strava.com/api/v3/activities/9921823048"
# segments_url = "https://www.strava.com/api/v3/activities/1"
# segments_url ="https://www.strava.com/activities/9921823048"
# segments_url ="https://www.strava.com/activities/9973161774"
payload = {
    'client_id': "114307",
    'client_secret': '2731411b1af539de9847632c978f376b92aa3ea5',
    'refresh_token': '',

    'grant_type': "refresh_token",
    'f': 'json'
}

# =============================================================================
# Insert refresh tokens here
# =============================================================================
refresh_tokens = ['']


payload['refresh_token']=refresh_token_FB
print("Requesting Token...\n")
res = requests.post(auth_url, data=payload, verify=False)
access_token = res.json()['access_token']
print("Access Token = {}\n".format(access_token))

header = {'Authorization': 'Bearer ' + access_token}
param = {'per_page': 20, 'page': 1}

# =============================================================================
# year to day stats
# =============================================================================

# y2d_stats_url = 'https://www.strava.com/api/v3/athletes/'+felix_id+'/stats?access_token='+access_token
# year_to_day_stats_ret = requests.get(y2d_stats_url, headers=header, params=param).json()

# # =============================================================================
# # profile information
# # =============================================================================

# profile_url = "https://www.strava.com/api/v3/athletes/"+felix_id
# profile_ret = requests.get(profile_url, headers=header, params=param).json()


# =============================================================================
# activity information
# =============================================================================

activites_url = "https://www.strava.com/api/v3/athlete/activities"
my_dataset = requests.get(activites_url, headers=header, params=param).json()

id_last_tour = my_dataset[0]['id']
segments_url = 'https://www.strava.com/api/v3/activities/'+str(id_last_tour)+'?include_all_efforts=True'
my_segments = requests.get(segments_url, headers=header, params=param).json()


# segment_url = "https://www.strava.com/api/v3/segments/14581228"
# segment = requests.get(segment_url, headers=header).json()


