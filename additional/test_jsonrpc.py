import json
import urllib.request
import urllib.error

# Authenticate
auth_data = json.dumps({
    "jsonrpc": "2.0",
    "method": "call",
    "params": {
        "db": "invoice_utility_erp",
        "login": "admin",
        "password": "1"
    }
}).encode('utf-8')

auth_req = urllib.request.Request(
    'http://127.0.0.1:8170/web/session/authenticate',
    data=auth_data,
    headers={'Content-Type': 'application/json'}
)
try:
    auth_resp = urllib.request.urlopen(auth_req)
    auth_resp.read()
    session_id = None
    for k, v in auth_resp.getheaders():
        if k.lower() == 'set-cookie':
            session_id = v.split(';')[0]
            break
except urllib.error.URLError as e:
    print(f"Auth Error: {e}")
    exit(1)

# Lookup
lookup_data = json.dumps({
    "jsonrpc": "2.0",
    "method": "call",
    "params": {"meter_number": "12/008657"}
}).encode('utf-8')

req = urllib.request.Request(
    'http://127.0.0.1:8170/api/v1/utility/reading/meter/lookup',
    data=lookup_data,
    headers={'Content-Type': 'application/json', 'Cookie': session_id}
)

try:
    response = urllib.request.urlopen(req)
    print("STATUS:", response.status)
    body = response.read().decode('utf-8')
    print("BODY:", body)
except urllib.error.URLError as e:
    print(f"Error: {e}")
    if hasattr(e, 'read'):
        print(e.read().decode('utf-8'))
