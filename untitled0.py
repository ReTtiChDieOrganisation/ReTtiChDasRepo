

import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)



import pandas as pd
import matplotlib.pyplot as plt
import time
import random


auth_url = "https://www.strava.com/oauth/token"

payload = {
    'client_id': "114307",
    'client_secret':'XXXXXXXXXX',
    'refresh_token': '',

    'grant_type': "refresh_token",
    'f': 'json'
}

# =============================================================================
# Insert refresh tokens here
# =============================================================================
refresh_tokens = ['']


payload['refresh_token']=refresh_tokens[0]
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



