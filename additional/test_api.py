
import requests
import json
session = requests.Session()
login_res = session.post('http://127.0.0.1:8170/web/session/authenticate', json={'jsonrpc': '2.0', 'params': {'db': 'invoice_utility_erp', 'login': 'saleem@gmail.com', 'password': '1'}})
print('Login:', login_res.json())
res = session.post('http://127.0.0.1:8170/api/v1/utility/reader/subscribers', json={'jsonrpc': '2.0', 'params': {}})
print('Subs:', res.json())
