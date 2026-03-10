import urllib.request
import json
req = urllib.request.Request("http://127.0.0.1:8000/api/simulation/start", data=json.dumps({"boundaries":[[0,0],[10,0],[10,10],[0,10]], "obstacles":[], "n_standard": 2, "n_specialist": 0}).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
try:
    with urllib.request.urlopen(req) as response:
        print(response.read().decode())
except Exception as e:
    print(e)
