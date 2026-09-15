
import json
users = env['res.users'].search([])
res_users = [{'id': u.id, 'login': u.login, 'name': u.name, 'route_ids': u.assigned_route_ids.ids} for u in users]
readers = env['utility.meter.reader'].search([])
res_readers = [{'id': r.id, 'user': r.user_id.login, 'name': r.name, 'routes': r.route_ids.ids} for r in readers]
with open('F:/invo-system/users_dump.json', 'w', encoding='utf-8') as f:
    json.dump({'users': res_users, 'readers': res_readers}, f, ensure_ascii=False, indent=2)
