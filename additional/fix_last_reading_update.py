file = r'F:\invo-system\utility_core\models\utility_reading.py'

with open(file, 'r', encoding='utf-8') as f:
    content = f.read()

# أضف create override بعد تعريف الـ class مباشرة
# نبحث عن نهاية الـ imports وبداية الـ class

new_methods = '''
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        # تحديث آخر قراءة في العداد تلقائياً
        meters = records.mapped('meter_id')
        if meters:
            meters._update_last_reading()
        return records

    def write(self, vals):
        result = super().write(vals)
        if 'reading_value' in vals or 'reading_date' in vals:
            meters = self.mapped('meter_id')
            if meters:
                meters._update_last_reading()
        return result

'''

# أضف بعد السطر الأخير من تعريف الحقول وقبل أول method
# نبحث عن أول @api.depends أو def
import re

# إيجاد موضع الإدراج — بعد آخر حقل وقبل أول دالة
pattern = r'(    _order = [^\n]+\n)'
match = re.search(pattern, content)

if match:
    insert_pos = match.end()
    content = content[:insert_pos] + new_methods + content[insert_pos:]
    with open(file, 'w', encoding='utf-8') as f:
        f.write(content)
    print('SUCCESS - create/write override added')
else:
    # محاولة ثانية - البحث عن active field
    pattern2 = r'(    active = fields\.Boolean[^\n]+\n)'
    match2 = re.search(pattern2, content)
    if match2:
        insert_pos = match2.start()
        content = content[:insert_pos] + new_methods + content[insert_pos:]
        with open(file, 'w', encoding='utf-8') as f:
            f.write(content)
        print('SUCCESS - added before active field')
    else:
        print('NOT FOUND - trying class definition')
        # أضف بعد class definition
        class_match = re.search(r'(class UtilityReading\(models\.Model\):\n)', content)
        if class_match:
            insert_pos = class_match.end()
            content = content[:insert_pos] + new_methods + content[insert_pos:]
            with open(file, 'w', encoding='utf-8') as f:
                f.write(content)
            print('SUCCESS - added after class definition')
        else:
            print('FAILED - could not find insertion point')
