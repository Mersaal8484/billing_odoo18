import xlrd
import re

file_path = r'C:\Users\TUF\Desktop\بيانات للرفع لنظام الاودو\الخلايا و المحولات يوليو 2026.xls'
output_file = r'F:\invo-system\import_full_result.txt'

def normalize_ar(text):
    """Normalize Arabic text for matching: unify alef, ya, ta marbuta, remove extra spaces."""
    if not text:
        return ''
    text = text.strip()
    # Normalize alef variants
    text = re.sub(r'[أإآٱ]', 'ا', text)
    # Normalize ya
    text = re.sub(r'ى', 'ي', text)
    # Normalize ta marbuta
    text = re.sub(r'ة', 'ه', text)
    # Remove tashkeel
    text = re.sub(r'[\u064B-\u065F]', '', text)
    # Collapse multiple spaces
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

# Build normalized maps of existing DB records
db_regions = env['utility.region'].search([('type', '=', 'region')])
region_norm_map = {}  # normalized_name -> region record
for r in db_regions:
    key = normalize_ar(r.name)
    region_norm_map[key] = r

db_trans = env['utility.transformer'].search([])
trans_norm_map = {}  # (normalized_region_name, normalized_trans_name) -> transformer record
for t in db_trans:
    r_key = normalize_ar(t.region_id.name) if t.region_id else ''
    t_key = normalize_ar(t.name)
    trans_norm_map[(r_key, t_key)] = t

# Read Excel
wb = xlrd.open_workbook(file_path)
sheet = wb.sheet_by_index(0)

header_row = -1
for rowx in range(min(10, sheet.nrows)):
    val = str(sheet.cell_value(rowx, 1)).strip()
    if 'المنطقة' in val or 'املنطقة' in val:
        header_row = rowx
        break

if header_row == -1:
    raise ValueError("Header not found")

# Print headers for reference
headers = [clean_str(sheet.cell_value(header_row, c)) for c in range(sheet.ncols)]

# Find date range for July 2026
date_range = env['date.range'].search([('name', 'ilike', 'يوليو 2026')], limit=1)
if not date_range:
    date_range = env['date.range'].search([('name', 'ilike', 'يوليو')], limit=1)
if not date_range:
    date_range = env['date.range'].search([], order='date_start desc', limit=1)

# Counters
stats = {
    'region_created': 0,
    'trans_created': 0,
    'meter_created': 0,
    'reading_created': 0,
    'reading_exists': 0,
    'no_meter_num': 0,
    'trans_name_empty': 0,
    'errors': 0,
}
log_lines = []

# Process each row
for rowx in range(header_row + 1, sheet.nrows):
    region_name = clean_str(sheet.cell_value(rowx, 1))
    transformer_name = clean_str(sheet.cell_value(rowx, 2))
    meter_number = clean_str(sheet.cell_value(rowx, 3))
    prev_reading_val = clean_float(sheet.cell_value(rowx, 4))
    curr_reading_val = clean_float(sheet.cell_value(rowx, 5))
    multiplier = clean_float(sheet.cell_value(rowx, 7))

    if not region_name:
        continue
    if not transformer_name:
        stats['trans_name_empty'] += 1
        continue

    norm_region = normalize_ar(region_name)
    norm_trans = normalize_ar(transformer_name)

    # 1. Find or create region
    region = region_norm_map.get(norm_region)
    if not region:
        try:
            region = env['utility.region'].create({
                'name': region_name,
                'type': 'region',
            })
            region_norm_map[norm_region] = region
            stats['region_created'] += 1
            log_lines.append(f"CREATED REGION: [{region_name}]")
        except Exception as e:
            stats['errors'] += 1
            log_lines.append(f"ERROR creating region [{region_name}]: {e}")
            continue

    # 2. Find or create transformer
    trans_key = (normalize_ar(region.name), norm_trans)
    transformer = trans_norm_map.get(trans_key)
    if not transformer:
        # Try to find in DB with ilike as fallback
        found = env['utility.transformer'].search([
            ('name', 'ilike', transformer_name[:20]),
            ('region_id', '=', region.id)
        ], limit=1)
        if found:
            transformer = found
            trans_norm_map[trans_key] = transformer
        else:
            try:
                # Detect if it's a cell (خلية)
                is_cell = 'خلية' in transformer_name or 'محطة تحويل' in transformer_name
                transformer = env['utility.transformer'].create({
                    'name': transformer_name,
                    'region_id': region.id,
                    'is_cell': is_cell,
                    'is_active': True,
                })
                trans_norm_map[trans_key] = transformer
                stats['trans_created'] += 1
            except Exception as e:
                stats['errors'] += 1
                log_lines.append(f"ERROR creating transformer [{transformer_name}]: {e}")
                continue

    # 3. Skip rows without meter number
    if not meter_number or meter_number in ('-', '0', '', 'None', '0.0'):
        stats['no_meter_num'] += 1
        continue

    # 4. Find or create meter
    meter = env['utility.meter'].search([('meter_number', '=', meter_number)], limit=1)
    if not meter:
        try:
            meter = env['utility.meter'].create({
                'meter_number': meter_number,
                'payment_type': 'postpaid',
                'connection_type': 'transformer',
                'linked_transformer_id': transformer.id,
                'multiplier': multiplier if multiplier > 0 else 1.0,
                'is_coupling_meter': True,
            })
            if not transformer.coupling_meter_id:
                transformer.coupling_meter_id = meter.id
            stats['meter_created'] += 1
        except Exception as e:
            stats['errors'] += 1
            log_lines.append(f"ERROR creating meter [{meter_number}]: {e}")
            continue
    else:
        # Link to transformer if not linked
        if not meter.linked_transformer_id:
            meter.write({
                'connection_type': 'transformer',
                'linked_transformer_id': transformer.id,
                'is_coupling_meter': True,
            })
            if not transformer.coupling_meter_id:
                transformer.coupling_meter_id = meter.id

    # 5. Create reading if not exists
    existing = env['utility.reading'].search([
        ('meter_id', '=', meter.id),
        ('date_range_id', '=', date_range.id if date_range else False),
        ('reading_purpose', '=', 'periodic'),
    ], limit=1)

    if existing:
        stats['reading_exists'] += 1
        continue

    try:
        env['utility.reading'].with_context(_bypass_reading_protection=True).create({
            'meter_id': meter.id,
            'reading_category': 'transformer',
            'reading_purpose': 'periodic',
            'date_range_id': date_range.id if date_range else False,
            'reading_date': '2026-07-31 12:00:00',
            'reading_value': curr_reading_val,
            'meter_multiplier': multiplier if multiplier > 0 else 1.0,
            'state': 'approved',
            'image_state': 'clear',
            'reading_source': 'import_july_2026',
        })
        stats['reading_created'] += 1
    except Exception as e:
        stats['errors'] += 1
        log_lines.append(f"ERROR creating reading for meter [{meter_number}]: {e}")

# Commit all changes
env.cr.commit()

# Write report
with open(output_file, 'w', encoding='utf-8') as f:
    f.write("=== FULL IMPORT RESULT ===\n")
    for k, v in stats.items():
        f.write(f"  {k}: {v}\n")
    f.write(f"\n  date_range used: {date_range.name if date_range else 'NONE'}\n")
    f.write("\n=== LOG (first 100 lines) ===\n")
    for line in log_lines[:100]:
        f.write(f"  {line}\n")

print("=== IMPORT COMPLETE ===")
for k, v in stats.items():
    print(f"  {k}: {v}")
print(f"  date_range: {date_range.name if date_range else 'NONE'}")
print(f"Full report: {output_file}")
