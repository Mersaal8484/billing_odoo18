import xlrd
import logging

_logger = logging.getLogger(__name__)

file_path = r'C:\Users\TUF\Desktop\بيانات للرفع لنظام الاودو\الخلايا و المحولات يوليو 2026.xls'
wb = xlrd.open_workbook(file_path)
sheet = wb.sheet_by_index(0)

# Find header row
header_row = -1
for rowx in range(min(10, sheet.nrows)):
    val = str(sheet.cell_value(rowx, 1)).strip()
    if 'املنطقة' in val or 'المنطقة' in val:
        header_row = rowx
        break

if header_row == -1:
    raise ValueError("Could not find headers")

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

success_count = 0
not_found_count = 0
multiple_found_count = 0
no_meter_num_count = 0
reading_exists_count = 0

# Ensure date range exists
date_range = env['date.range'].search([('name', 'ilike', 'يوليو 2026')], limit=1)
if not date_range:
    date_range = env['date.range'].search([('name', 'ilike', 'يوليو')], limit=1)
if not date_range:
    date_range = env['date.range'].search([], limit=1)

for rowx in range(header_row + 1, sheet.nrows):
    region_name = clean_str(sheet.cell_value(rowx, 1))
    transformer_name = clean_str(sheet.cell_value(rowx, 2))
    meter_number = clean_str(sheet.cell_value(rowx, 3))
    prev_reading = clean_float(sheet.cell_value(rowx, 4))
    curr_reading = clean_float(sheet.cell_value(rowx, 5))
    multiplier = clean_float(sheet.cell_value(rowx, 7))
    
    if not region_name or not transformer_name:
        continue
        
    if not meter_number or meter_number in ('-', '0', '', 'None'):
        no_meter_num_count += 1
        continue
        
    # Find region
    region_domain = [('name', 'ilike', region_name), ('type', '=', 'region')]
    regions = env['utility.region'].search(region_domain)
    
    trans_domain = [('name', 'ilike', transformer_name)]
    if regions:
        trans_domain.append(('region_id', 'in', regions.ids))
        
    transformers = env['utility.transformer'].search(trans_domain)
    
    if len(transformers) == 0:
        not_found_count += 1
        continue
    elif len(transformers) > 1:
        multiple_found_count += 1
        continue
        
    transformer = transformers[0]
    
    # Create or find meter
    meter = env['utility.meter'].search([('meter_number', '=', meter_number)], limit=1)
    if not meter:
        meter = env['utility.meter'].create({
            'meter_number': meter_number,
            'payment_type': 'postpaid',
            'connection_type': 'transformer',
            'linked_transformer_id': transformer.id,
            'multiplier': multiplier if multiplier > 0 else 1.0,
            'is_coupling_meter': True,
        })
        transformer.coupling_meter_id = meter.id
    else:
        # Link it if not linked
        if meter.connection_type == 'not_connected' or not meter.linked_transformer_id:
            meter.write({
                'connection_type': 'transformer',
                'linked_transformer_id': transformer.id,
                'is_coupling_meter': True,
            })
            transformer.coupling_meter_id = meter.id
            
    # Create reading
    reading = env['utility.reading'].search([
        ('meter_id', '=', meter.id),
        ('date_range_id', '=', date_range.id if date_range else False)
    ], limit=1)
    
    if not reading:
        try:
            # We must use _bypass_reading_protection to allow setting state to approved directly
            env['utility.reading'].with_context(_bypass_reading_protection=True).create({
                'meter_id': meter.id,
                'reading_category': 'transformer',
                'reading_purpose': 'periodic',
                'date_range_id': date_range.id if date_range else False,
                'reading_date': '2026-07-31 12:00:00',
                'reading_value': curr_reading,
                'meter_multiplier': multiplier if multiplier > 0 else 1.0,
                'state': 'approved', 
                'image_state': 'clear',
            })
            success_count += 1
        except Exception as e:
            _logger.error(f"Failed to create reading for meter {meter_number}: {e}")
    else:
        reading_exists_count += 1

print(f"Success: {success_count}, Exists: {reading_exists_count}, Not Found: {not_found_count}, Multiple: {multiple_found_count}, No Meter Num: {no_meter_num_count}")
env.cr.commit()
