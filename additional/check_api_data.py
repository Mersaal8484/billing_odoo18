
import json
route_ids = [2]
customers = env['utility.customer'].sudo().search([('route_id', 'in', route_ids)], limit=5)
result = []
for c in customers:
    meter = c.meter_id
    result.append({
        'id': c.id,
        'customer_number': c.customer_number,
        'name': c.partner_id.name if c.partner_id else '',
        'address': c.address or '',
        'route_id': c.route_id.id if c.route_id else None,
        'route_name': c.route_id.name if c.route_id else '',
        'meter_id': meter.id if meter else None,
        'meter_number': meter.meter_number if meter else '',
    })
print(result)
