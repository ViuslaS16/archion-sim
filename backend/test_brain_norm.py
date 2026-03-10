import requests
BRAIN_API_URL = "http://127.0.0.1:8001/act_batch"
states = [
    [5.0, 5.0, 5.0, 0.0, 0.0],
    [1.0, 1.0, 1.0, 0.0, 0.0],
    [5.0/20, 5.0/20, 5.0/20, 0.0, 0.0],
    [0.0, 0.0, 0.0, 0.0, 0.0],
    [10.0, 10.0, 10.0, 0.0, 0.0]
]
res = requests.post(BRAIN_API_URL, json={"states": states})
print(res.json())
