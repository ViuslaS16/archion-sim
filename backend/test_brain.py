import requests
BRAIN_API_URL = "http://127.0.0.1:8001/act_batch"
states = [
    [5.0, 5.0, 5.0, 0.0, 0.0], # open space
    [0.2, 5.0, 5.0, 0.0, 0.0], # wall in front
    [0.2, 0.2, 0.2, 0.0, 0.0], # boxed in
]
res = requests.post(BRAIN_API_URL, json={"states": states})
print(res.json())
