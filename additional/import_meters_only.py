import xlrd
import re

file_path = r'C:\Users\TUF\Desktop\بيانات للرفع لنظام الاودو\الخلايا و المحولات يوليو 2026.xls'
output_file = r'F:\invo-system\import_meters_result.txt'

def normalize_ar(text):
    if not text:
        return ''
    text = str(text).strip()
    text = re.sub(r'[أإآٱ]', 'ا', text)
    text = re.sub(r'ى', 'ي', text)
    text = re.sub(r'ة', 'ه', text)
    text = re.sub(r'[\u064B-\u065F]', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def clean_str(val):
    if val is None:
        return ''
    if isinstance(val, float):
        if val.is_integer():
            return str(int(val))
        return str(val)
    return str(val).strip()

def clean_float(val):
    try:
        if val == '' or val is None:
            return 0.0
        return float(val)
    except:
        return 0.0

# Build normalized list for substring matching
db_trans_all = env['utility.transformer'].search([])
db_trans_list = []
for t in db_trans_all:
    rk = normalize_ar(t.region_id.name) if t.region_id else ''
    tk = normalize_ar(t.name)
    db_trans_list.append((rk, tk, t))

def find_transformer(region_name, trans_name):
    """Find transformer using substring match (handles CODE - NAME format in DB)."""
    rk = normalize_ar(region_name)
    tk = normalize_ar(trans_name)
    if not tk or len(tk) < 5:
        return None
    matches = []
    for db_rk, db_tk, t in db_trans_list:
        if db_rk and rk and db_rk != rk:
            continue
        # substring match both directions
        if tk in db_tk or db_tk in tk:
            matches.append(t)
    if len(matches) == 1:
        return matches[0]
    return None

# Find date range
date_range = env['date.range'].search([('name', 'ilike', 'يوليو 2026')], limit=1)
if not date_range:
    date_range = env['date.range'].search([('name', 'ilike', 'يوليو')], limit=1)
if not date_range:
    date_range = env['date.range'].search([], order='date_start desc', limit=1)

# Read Excel
wb = xlrd.open_workbook(file_path)
sheet = wb.sheet_by_index(0)
header_row = -1
for rowx in range(min(10, sheet.nrows)):
    val = str(sheet.cell_value(rowx, 1)).strip()
    if 'المنطقة' in val or 'املنطقة' in val:
        header_row = rowx
        break

stats = {'meter_created': 0, 'reading_created': 0, 'reading_exists': 0,
         'trans_not_found': 0, 'trans_ambiguous': 0, 'no_meter_num': 0,
         'meter_error': 0, 'reading_error': 0}

log_lines = []

for rowx in range(header_row + 1, sheet.nrows):
    region_name = clean_str(sheet.cell_value(rowx, 1))
    transformer_name = clean_str(sheet.cell_value(rowx, 2))
    meter_number = clean_str(sheet.cell_value(rowx, 3))
    curr_reading_val = clean_float(sheet.cell_value(rowx, 5))
    multiplier = clean_float(sheet.cell_value(rowx, 7))

    if not region_name or not transformer_name:
        continue

    transformer = find_transformer(region_name, transformer_name)

    if not transformer:
        stats['trans_not_found'] += 1
        continue

    if not meter_number or meter_number in ('-', '0', '', 'None', '0.0'):
        stats['no_meter_num'] += 1
        continue

    mult = multiplier if multiplier > 0 else 1.0

    # Find or create meter
    meter = env['utility.meter'].search([('meter_number', '=', meter_number)], limit=1)
    if not meter:
        try:
            with env.cr.savepoint():
                meter = env['utility.meter'].create({
                    'meter_number': meter_number,
                    'payment_type': 'postpaid',
                    'connection_type': 'transformer',
                    'linked_transformer_id': transformer.id,
                    'multiplier': mult,
                    'is_coupling_meter': True,
                })
                if not transformer.coupling_meter_id:
                    transformer.coupling_meter_id = meter.id
                stats['meter_created'] += 1
        except Exception as e:
            stats['meter_error'] += 1
            log_lines.append(f"METER_ERR [{meter_number}]: {str(e)[:100]}")
            continue
    else:
        if not meter.linked_transformer_id:
            try:
                with env.cr.savepoint():
                    meter.write({'connection_type': 'transformer',
                                 'linked_transformer_id': transformer.id,
                                 'is_coupling_meter': True})
                    if not transformer.coupling_meter_id:
                        transformer.coupling_meter_id = meter.id
            except Exception:
                pass

    if not meter:
        continue

    # Check for existing reading
    existing = env['utility.reading'].search([
        ('meter_id', '=', meter.id),
        ('date_range_id', '=', date_range.id if date_range else False),
        ('reading_purpose', '=', 'periodic'),
    ], limit=1)

    if existing:
        stats['reading_exists'] += 1
        continue

    try:
        with env.cr.savepoint():
            env['utility.reading'].with_context(_bypass_reading_protection=True).create({
                'meter_id': meter.id,
                'reading_category': 'transformer',
                'reading_purpose': 'periodic',
                'date_range_id': date_range.id if date_range else False,
                'reading_date': '2026-07-31 12:00:00',
                'reading_value': curr_reading_val,
                'meter_multiplier': mult,
                'state': 'approved',
                'image_state': 'clear',
                'reading_source': 'import_july_2026',
            })
            stats['reading_created'] += 1
    except Exception as e:
        stats['reading_error'] += 1
        log_lines.append(f"READING_ERR [{meter_number}]: {str(e)[:100]}")

env.cr.commit()

with open(output_file, 'w', encoding='utf-8') as f:
    f.write("=== METERS & READINGS IMPORT RESULT ===\n")
    f.write(f"date_range: {date_range.name if date_range else 'NONE'}\n")
    f.write(f"DB transformers: {len(db_trans_all)}\n\n")
    for k, v in stats.items():
        f.write(f"  {k}: {v}\n")
    f.write("\n=== ERRORS (first 100) ===\n")
    for line in log_lines[:100]:
        f.write(f"  {line}\n")

print("=== DONE ===")
for k, v in stats.items():
    print(f"  {k}: {v}")
print(f"Report: {output_file}")
