import json
import urllib.request

req = urllib.request.Request(
    'http://localhost:8069/api/v1/utility/reading/meter/lookup',
    data=json.dumps({"params": {"meter_number": "12/008657"}}).encode('utf-8'),
    headers={'Content-Type': 'application/json'}
)
try:
    response = urllib.request.urlopen(req)
    print(response.read().decode('utf-8'))
except Exception as e:
    print(f"Error: {e}")
