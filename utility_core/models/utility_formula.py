import logging
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)

# متغيرات آمنة مسموح بها داخل safe_eval للمعادلات
_FORMULA_SAFE_GLOBALS = {
    '__builtins__': {
        # دوال رياضية آمنة فقط
        'abs': abs, 'round': round, 'min': min, 'max': max,
        'int': int, 'float': float, 'bool': bool, 'str': str,
        'len': len, 'range': range, 'sum': sum,
        'True': True, 'False': False, 'None': None,
    },
}


class UtilityFormula(models.Model):
    _name = 'utility.formula'
    _description = 'صيغة حسابات بنود العقد'
    _rec_name = 'name'

    name = fields.Char('اسم المعادلة', required=True, translate=True)
    code = fields.Text('كود المعادلة', required=True,
        help='كود Python يتم تنفيذه لحساب الكمية.\n'
             'المتغيرات المتاحة:\n'
             '- consumption: float - الاستهلاك (kWh)\n'
             '- previous_reading: float - القراءة السابقة\n'
             '- current_reading: float - القراءة الحالية\n'
             '- template_id: int - معرف قالب العقد\n'
             '- template_name: str - اسم قالب العقد\n'
             '- account_id: int - معرف الحساب\n'
             '- account_name: str - اسم الحساب\n'
             '- category_id: int - معرف فئة المشترك\n'
             '- category_name: str - اسم فئة المشترك\n'
             '- line_id: int - معرف بند العقد\n'
             '- line_name: str - اسم بند العقد\n'
             '- discount_first_units: float - حد الوحدات المدعومة المشتق من شرائح الخصم\n'
             '- result: float - يجب تعيينها بقيمة الكمية المحسوبة\n'
             '- name: str - يمكن تغييرها لوصف مخصص')
    active = fields.Boolean('نشط', default=True)
    company_id = fields.Many2one('res.company', 'الشركة', default=lambda self: self.env.company)
    contract_line_count = fields.Integer(
        'عدد بنود العقود',
        compute='_compute_contract_line_count'
    )

    def _compute_contract_line_count(self):
        ContractLine = self.env['utility.contract.template.line']
        for record in self:
            record.contract_line_count = ContractLine.search_count(
                [('qty_formula_id', '=', record.id)]
            )

    # ── FIX: التحقق من صحة الكود عند الحفظ ──────────────────────────────────
    @api.constrains('code')
    def _validate_formula_syntax(self):
        """تحقق من صحة صياغة كود Python قبل الحفظ."""
        _DANGEROUS_PATTERNS = (
            'while True', 'while 1', 'for ever', '__import__', 'exec(', 'eval(',
            'compile(', 'globals()', 'locals()', 'getattr(', 'setattr(',
            'delattr(', 'os.', 'sys.', 'subprocess', 'open(', 'import ',
        )
        for record in self:
            if not record.code or not record.code.strip():
                raise ValidationError('كود المعادلة لا يمكن أن يكون فارغاً.')
            if len(record.code) > 5000:
                raise ValidationError(
                    'كود المعادلة "%s" يتجاوز الحد المسموح (5000 حرف).' % record.name
                )
            code_lower = record.code.lower()
            for pattern in _DANGEROUS_PATTERNS:
                if pattern.lower() in code_lower:
                    raise ValidationError(
                        'كود المعادلة "%s" يحتوي على نمط محظور: "%s"' % (record.name, pattern)
                    )
            try:
                compile(record.code, '<formula:%s>' % record.name, 'exec')
            except SyntaxError as e:
                raise ValidationError(
                    'خطأ في صياغة كود المعادلة "%s":\n%s\n'
                    'السطر: %s | العمود: %s'
                    % (record.name, e.msg, e.lineno, e.offset)
                ) from e

    def action_view_contract_lines(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('بنود نماذج العقود'),
            'res_model': 'utility.contract.template.line',
            'view_mode': 'list,form',
            'domain': [('qty_formula_id', '=', self.id)],
            'context': {'default_qty_formula_id': self.id},
        }

    def action_test_formula(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'تشغيل المعادلة',
            'res_model': 'utility.formula.test.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_formula_id': self.id},
        }

    def execute(self, consumption=0, previous_reading=0, current_reading=0,
                tariff=None, account=None, category=None, line=None,
                template=None, discount_first_units=None):
        """تنفيذ المعادلة مع المتغيرات الممررة.

        الأمان:
        - يُمرَّر _FORMULA_SAFE_GLOBALS لتقييد الـ builtins المتاحة.
        - لا يُمرَّر env أو أي كائن ORM لمنع الوصول غير المصرح به.
        - النتيجة يجب أن تكون رقمية (int أو float).
        """
        self.ensure_one()
        result = 0.0
        name = self.name

        if discount_first_units is None and template and hasattr(template, 'discount_block_ids'):
            finite_limits = template.discount_block_ids.filtered(lambda block: block.to_kwh and block.to_kwh > 0).mapped('to_kwh')
            discount_first_units = max(finite_limits) if finite_limits else 0.0

        locals_dict = {
            'consumption': float(consumption or 0.0),
            'previous_reading': float(previous_reading or 0.0),
            'current_reading': float(current_reading or 0.0),
            'template_id': template.id if template else 0,
            'template_name': template.name if template else '',
            'account_id': account.id if account else 0,
            'account_name': account.partner_id.name if account and account.partner_id else '',
            'category_id': category.id if category else 0,
            'category_name': category.name if category else '',
            'line_id': line.id if line else 0,
            'line_name': line.name if line else '',
            'discount_first_units': float(discount_first_units or 0.0),
            'result': result,
            'name': name,
        }

        try:
            # FIX: تمرير globals آمنة محدودة بدلاً من الـ builtins الكاملة
            safe_eval(
                self.code,
                globals_dict=dict(_FORMULA_SAFE_GLOBALS),
                locals_dict=locals_dict,
                mode='exec',
                nocopy=True,
            )
            result = locals_dict.get('result', 0.0)
            name = locals_dict.get('name', self.name)

            if not isinstance(result, (int, float)):
                raise ValueError(
                    'result يجب أن يكون رقماً. '
                    'القيمة المُعادة: %s (نوع: %s)' % (result, type(result).__name__)
                )
            result = float(result)

        except ValidationError:
            raise
        except Exception as e:
            msg = _(
                "خطأ في تنفيذ المعادلة '%s':\n"
                "الخطأ: %s\n"
                "السياق: استهلاك=%.2f، قراءة سابقة=%.2f، قراءة حالية=%.2f"
            ) % (
                self.name, e,
                float(consumption or 0),
                float(previous_reading or 0),
                float(current_reading or 0),
            )
            _logger.warning('Formula execution failed: formula_id=%d name=%s error=%s',
                            self.id, self.name, e)
            raise ValidationError(msg) from e

        return result, name
