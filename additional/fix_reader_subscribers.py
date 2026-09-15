import re

file = r'F:\invo-system\utility_billing\controllers\utility_reader_api.py'

with open(file, 'r', encoding='utf-8') as f:
    content = f.read()

# إيجاد الدالة وحذفها واستبدالها
pattern = r'(    def reader_subscribers\(self, \*\*kwargs\):.*?)(    @http\.route|    def |\Z)'

new_func = '''    def reader_subscribers(self, **kwargs):
        """جلب المشتركين المخصصين للكاشف عبر utility.route.user_ids"""
        user = request.env.user

        # البحث عبر utility.route.user_ids مباشرة
        routes = request.env['utility.route'].sudo().search([
            ('user_ids', 'in', [user.id]),
            ('active', '=', True),
        ])
        route_ids = routes.ids

        # fallback عبر utility.meter.reader
        try:
            mr = request.env['utility.meter.reader'].sudo().search(
                [('user_id', '=', user.id)], limit=1
            )
            if mr:
                route_ids = list(set(route_ids + mr.route_ids.ids))
        except Exception:
            pass

        if not route_ids:
            return {
                'success': True,
                'subscribers': [],
                'count': 0,
                'debug': f'No routes for user {user.login}',
            }

        customers = request.env['utility.customer'].sudo().search([
            ('route_id', 'in', route_ids),
            ('active', '=', True),
        ])

        result = []
        for c in customers:
            meter = c.meter_id
            address = ''
            try:
                address = c.partner_id.contact_address if c.partner_id else ''
            except Exception:
                pass
            result.append({
                'id': c.id,
                'customer_number': c.customer_number or '',
                'name': c.partner_id.name if c.partner_id else c.display_name or '',
                'address': address or '',
                'route_id': c.route_id.id if c.route_id else None,
                'route_name': c.route_id.name if c.route_id else '',
                'meter_id': meter.id if meter else None,
                'meter_number': meter.meter_number if meter else '',
                'last_reading_value': getattr(meter, 'last_reading_value', 0) if meter else 0,
            })

        return {
            'success': True,
            'count': len(result),
            'subscribers': result,
        }

'''

match = re.search(pattern, content, re.DOTALL)
if match:
    old_func = match.group(1)
    next_part = match.group(2)
    content = content.replace(old_func, new_func)
    with open(file, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'SUCCESS - replaced {len(old_func)} chars with {len(new_func)} chars')
    # تحقق
    with open(file, 'r', encoding='utf-8') as f:
        check = f.read()
    if 'utility.route' in check and "('user_ids', 'in'" in check:
        print('VERIFIED - new code is in file')
    else:
        print('WARNING - verification failed')
else:
    print('NOT FOUND - function not matched by regex')
    idx = content.find('def reader_subscribers')
    print(f'Function at char: {idx}')
    print(repr(content[idx:idx+200]))
