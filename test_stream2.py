import requests
print("Getting stream...")
try:
    r = requests.get("http://127.0.0.1:8000/api/simulation/stream?n_standard=2&n_specialist=0", stream=True)
    count = 0
    for line in r.iter_lines():
        if line:
            count += 1
            if count % 100 == 0:
                print(f"Received {count} lines...")
            s = line.decode('utf-8')
            if '"done"' in s:
                print("Received DONE!")
                break
except Exception as e:
    print(f"Stream exception: {e}")

print("Fetching compliance...")
r3 = requests.get('http://127.0.0.1:8000/api/compliance/report')
print(r3.text[:200])
