import urllib.request
import json
import time

url_run = "http://localhost:8000/api/v1/model/run"
req = urllib.request.Request(url_run, data=json.dumps({"rainfall_mm": 75.0}).encode('utf-8'), headers={"Content-Type": "application/json"})
res = urllib.request.urlopen(req).read()
run_data = json.loads(res.decode('utf-8'))
run_id = run_data["id"]
print(f"Created Model Run #{run_id}: status={run_data['status']}")

time.sleep(2)

url_status = f"http://localhost:8000/api/v1/model/runs/{run_id}"
res_status = json.loads(urllib.request.urlopen(url_status).read().decode('utf-8'))
print(f"Run #{run_id} status={res_status['status']}, execution_time_ms={res_status['execution_time_ms']}")

url_stats = f"http://localhost:8000/api/v1/model/runs/{run_id}/statistics"
stats = json.loads(urllib.request.urlopen(url_stats).read().decode('utf-8'))
print("Run Statistics:")
print(json.dumps(stats, indent=2))

url_geojson = f"http://localhost:8000/api/v1/model/runs/{run_id}/geojson"
geojson = json.loads(urllib.request.urlopen(url_geojson).read().decode('utf-8'))
print(f"GeoJSON Features count: {len(geojson['features'])}")
if len(geojson['features']) > 0:
    print("Sample feature properties:", geojson['features'][0]['properties'])
