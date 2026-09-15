meters = env['utility.meter'].search([('meter_number', '=', '12/008657')])
with open('F:/invo-system/meter_check.txt', 'w', encoding='utf-8') as f:
    f.write(f"Found exactly '12/008657': {len(meters)}\n")
    for m in meters:
        f.write(f"ID: {m.id}, Num: '{m.meter_number}'\n")

all_meters = env['utility.meter'].search([])
matched = [m for m in all_meters if m.meter_number and '008657' in m.meter_number]
with open('F:/invo-system/meter_check.txt', 'a', encoding='utf-8') as f:
    f.write(f"\nLike '008657': {len(matched)}\n")
    for m in matched:
        f.write(f"ID: {m.id}, Num: '{m.meter_number}'\n")
