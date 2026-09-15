import xlrd

file_path = r'C:\Users\TUF\Desktop\بيانات للرفع لنظام الاودو\الخلايا و المحولات يوليو 2026.xls'
output_file = r'F:\invo-system\diag_result.txt'

wb = xlrd.open_workbook(file_path)
sheet = wb.sheet_by_index(0)

header_row = -1
for rowx in range(min(10, sheet.nrows)):
    val = str(sheet.cell_value(rowx, 1)).strip()
    if 'المنطقة' in val or 'املنطقة' in val:
        header_row = rowx
        break

def clean_str(val):
    if val is None:
        return ''
    if isinstance(val, float):
        if val.is_integer():
            return str(int(val))
        return str(val)
    return str(val).strip()

excel_pairs = set()
excel_regions = set()

for rowx in range(header_row + 1, sheet.nrows):
    region_name = clean_str(sheet.cell_value(rowx, 1))
    transformer_name = clean_str(sheet.cell_value(rowx, 2))
    if region_name and transformer_name:
        excel_pairs.add((region_name, transformer_name))
        excel_regions.add(region_name)

db_regions = env['utility.region'].search([('type', '=', 'region')])
db_trans = env['utility.transformer'].search([])

not_found_pairs = []
found_count = 0
multi_count = 0

for region_name, trans_name in sorted(excel_pairs):
    regions = env['utility.region'].search([('name', 'ilike', region_name), ('type', '=', 'region')])
    trans_domain = [('name', 'ilike', trans_name)]
    if regions:
        trans_domain.append(('region_id', 'in', regions.ids))
    transformers = env['utility.transformer'].search(trans_domain)
    if len(transformers) == 0:
        not_found_pairs.append((region_name, trans_name))
    elif len(transformers) > 1:
        multi_count += 1
    else:
        found_count += 1

with open(output_file, 'w', encoding='utf-8') as f:
    f.write(f"=== DIAGNOSTIC REPORT ===\n")
    f.write(f"Excel unique pairs: {len(excel_pairs)}\n")
    f.write(f"Excel regions: {len(excel_regions)}\n")
    f.write(f"DB regions: {len(db_regions)}\n")
    f.write(f"DB transformers: {len(db_trans)}\n")
    f.write(f"Found: {found_count}, Not Found: {len(not_found_pairs)}, Multiple: {multi_count}\n\n")
    
    f.write("=== DB REGIONS ===\n")
    for r in db_regions:
        f.write(f"  [{r.name}]\n")
    
    f.write("\n=== EXCEL REGIONS ===\n")
    for r in sorted(excel_regions):
        f.write(f"  [{r}]\n")
    
    f.write("\n=== SAMPLE DB TRANSFORMERS (first 20) ===\n")
    for t in db_trans[:20]:
        f.write(f"  [{t.name}] region=[{t.region_id.name if t.region_id else 'NONE'}]\n")
    
    f.write("\n=== SAMPLE NOT FOUND (first 50) ===\n")
    for region_name, trans_name in not_found_pairs[:50]:
        f.write(f"  region=[{region_name}] trans=[{trans_name}]\n")

print(f"Done. Results written to: {output_file}")
print(f"DB regions: {len(db_regions)}, DB transformers: {len(db_trans)}")
print(f"Found: {found_count}, Not found: {len(not_found_pairs)}, Multiple: {multi_count}")
