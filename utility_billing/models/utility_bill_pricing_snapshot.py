import json
import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class UtilityBillPricingSnapshot(models.Model):
    _name = 'utility.bill.pricing.snapshot'
    _description = 'لقطة التسعير المطبقة في فاتورة الكهرباء (Immutable Billing Pricing Snapshot)'
    _order = 'created_at desc, id desc'
    _rec_name = 'display_name'

    sale_order_id = fields.Many2one(
        'sale.order',
        string='فاتورة الكهرباء (Sale Order)',
        required=True,
        index=True,
        ondelete='cascade',
        check_company=True,
    )
    reading_id = fields.Many2one(
        'utility.reading',
        string='قراءة العداد',
        index=True,
        ondelete='restrict',
        check_company=True,
    )
    customer_id = fields.Many2one(
        'utility.customer',
        string='حساب المشترك',
        required=True,
        index=True,
        ondelete='restrict',
        check_company=True,
    )
    meter_id = fields.Many2one(
        'utility.meter',
        string='العداد',
        index=True,
        ondelete='restrict',
        check_company=True,
    )
    date_range_id = fields.Many2one(
        'date.range',
        string='فترة الفوترة',
        index=True,
        ondelete='restrict',
    )
    company_id = fields.Many2one(
        'res.company',
        related='sale_order_id.company_id',
        string='الشركة',
        store=True,
        readonly=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='sale_order_id.currency_id',
        string='العملة',
        store=True,
        readonly=True,
    )

    # ── هوية العقد والإصدار المعتمد ─────────────────────────────────────────
    contract_template_id = fields.Many2one(
        'utility.contract.template',
        string='قالب العقد المعتمد',
        required=True,
        index=True,
        ondelete='restrict',
    )
    contract_template_version_id = fields.Many2one(
        'utility.contract.template.version',
        string='إصدار قالب العقد المطبق',
        required=True,
        index=True,
        ondelete='restrict',
    )
    version_code = fields.Char(
        string='رمز الإصدار',
        related='contract_template_version_id.version_code',
        store=True,
        readonly=True,
    )
    pricing_mode = fields.Selection([
        ('flat', 'سعر موحّد بدون شرائح'),
        ('tier', 'Flat Tier / سعر شريحة واحدة'),
        ('block', 'Progressive Tier / شرائح تصاعدية'),
        ('seasonal', 'موسمي'),
        ('tou', 'حسب وقت الاستخدام'),
    ], string='نمط التسعير المطبق', required=True, default='flat')

    # ── تفاصيل الاستهلاك والأسعار ──────────────────────────────────────────
    pricing_source = fields.Selection(
        [
            ('template', 'قالب العقد'),
            ('customer_local', 'تعرفة محلية للعميل'),
        ],
        string='مصدر شرائح التعرفة',
        required=True,
        default='template',
        readonly=True,
    )
    local_pricing_blocks_json = fields.Text(
        string='لقطة الشرائح المحلية',
        readonly=True,
        copy=False,
    )

    billing_consumption = fields.Float(
        string='إجمالي الاستهلاك المفوتر (kWh)',
        required=True,
        default=0.0,
    )
    price_per_kwh = fields.Monetary(
        string='سعر الوحدة الأساسي',
        currency_field='currency_id',
    )
    service_charge = fields.Monetary(
        string='رسم الخدمة الثابت',
        currency_field='currency_id',
    )
    min_charge = fields.Monetary(
        string='الحد الأدنى للفوترة',
        currency_field='currency_id',
    )
    max_charge = fields.Monetary(
        string='الحد الأقصى للفوترة',
        currency_field='currency_id',
    )

    # ── المبالغ المحسوبة والمطابقة ──────────────────────────────────────────
    amount_energy = fields.Monetary(
        string='مبلغ الطاقة (الاستهلاك)',
        default=0.0,
        currency_field='currency_id',
    )
    amount_service = fields.Monetary(
        string='مبلغ رسوم الخدمة',
        default=0.0,
        currency_field='currency_id',
    )
    amount_local_fee = fields.Monetary(
        string='مبلغ الرسوم المحلية',
        default=0.0,
        currency_field='currency_id',
    )
    amount_discount = fields.Monetary(
        string='مبلغ الخصم والدعم',
        default=0.0,
        currency_field='currency_id',
    )
    amount_private_transformer_fee = fields.Monetary(
        string='رسوم المحول الخاص',
        default=0.0,
        currency_field='currency_id',
    )
    pre_adjustment_total = fields.Monetary(
        string='المجموع قبل التسوية (Min/Max)',
        default=0.0,
        currency_field='currency_id',
    )
    min_max_adjustment_amount = fields.Monetary(
        string='مبلغ تسوية الحد الأدنى/الأقصى',
        default=0.0,
        currency_field='currency_id',
    )
    calculated_total = fields.Monetary(
        string='الإجمالي المحسوب للفاتورة',
        default=0.0,
        currency_field='currency_id',
    )

    # ── أدلة الخصم والمعادلات ──────────────────────────────────────────────
    discount_units = fields.Float(
        string='وحدات الاستهلاك المدعومة/المخصومة',
        default=0.0,
    )
    discount_formula_id = fields.Many2one(
        'utility.formula',
        string='معادلة الخصم المستخدمة',
        ondelete='set null',
    )
    discount_formula_code = fields.Char(
        string='رمز معادلة الخصم',
    )
    discount_formula_result = fields.Float(
        string='ناتج تنفيذ معادلة الخصم',
        default=0.0,
    )
    discount_sponsor_id = fields.Many2one(
        'res.partner',
        string='الجهة الداعمة المحملة بالخصم',
        ondelete='restrict',
    )

    # ── الشرائح المطبقة (Progressive / Single Tier) ─────────────────────────
    block_ids = fields.One2many(
        'utility.bill.pricing.block',
        'pricing_snapshot_id',
        string='أدلة الشرائح المطبقة',
        copy=True,
    )

    # ── التتبع والتدقيق ───────────────────────────────────────────────────
    snapshot_origin = fields.Selection([
        ('authoritative', 'أصيل وموثق أثناء الفوترة'),
        ('reconstructed', 'مُعاد بناؤه تاريخياً'),
    ], string='مصدر اللقطة', default='authoritative', required=True)

    created_at = fields.Datetime(
        string='وقت تسجيل اللقطة',
        default=fields.Datetime.now,
        required=True,
        readonly=True,
    )
    created_by = fields.Many2one(
        'res.users',
        string='المسجل',
        default=lambda self: self.env.user,
        readonly=True,
    )
    display_name = fields.Char(
        string='اسم العرض',
        compute='_compute_display_name',
        store=True,
    )

    _sql_constraints = [
        ('unique_sale_order_snapshot',
         'unique(sale_order_id)',
         'لكل فاتورة كهرباء لقطة تسعير واحدة فقط.'),
    ]

    def get_local_pricing_blocks(self):
        self.ensure_one()
        if self.pricing_source != 'customer_local':
            return []
        if not self.local_pricing_blocks_json:
            raise ValidationError(
                _('لقطة التعرفة المحلية لهذه الفاتورة غير مكتملة.')
            )
        try:
            blocks = json.loads(self.local_pricing_blocks_json)
        except (TypeError, ValueError) as error:
            raise ValidationError(
                _('تعذر قراءة لقطة التعرفة المحلية لهذه الفاتورة.')
            ) from error
        if not isinstance(blocks, list) or not all(
            isinstance(block, dict) for block in blocks
        ):
            raise ValidationError(
                _('تنسيق لقطة التعرفة المحلية لهذه الفاتورة غير صالح.')
            )
        return sorted(
            blocks,
            key=lambda block: (
                block.get('from_kwh', 0.0),
                block.get('sequence', 10),
                block.get('customer_block_id', 0),
            ),
        )

    @api.depends('sale_order_id.name', 'contract_template_version_id.version_code')
    def _compute_display_name(self):
        for rec in self:
            o_name = rec.sale_order_id.name or _('مسودة')
            v_code = rec.version_code or (rec.contract_template_version_id.version_code if rec.contract_template_version_id else '')
            rec.display_name = f"Pricing Snapshot: {o_name} ({v_code})"

    @api.constrains('contract_template_id', 'contract_template_version_id')
    def _check_template_version_consistency(self):
        """يُطبق القاعدة: إصدار القالب يجب أن ينتمي للقالب التجاري نفسه المُسجَّل على لقطة التسعير."""
        for rec in self:
            if (
                rec.contract_template_version_id
                and rec.contract_template_id
                and rec.contract_template_version_id.template_id.id != rec.contract_template_id.id
            ):
                raise ValidationError(_(
                    "تعارض في التدقيق المالي: إصدار قالب العقد المطبق '%s' ينتمي للقالب '%s'، "
                    "بينما لقطة التسعير مرتبطة بقالب مختلف '%s'. "
                    "يجب أن يكون إصدار القالب وقالب التسعير متطابقَين لضمان سلامة سجل التدقيق."
                ) % (
                    rec.contract_template_version_id.version_code,
                    rec.contract_template_version_id.template_id.name,
                    rec.contract_template_id.name,
                ))

    def write(self, vals):
        """حماية لقطة التسعير من التعديل بعد تأكيد الفاتورة أو ترحيلها."""
        if not self.env.context.get('_allow_pricing_snapshot_modification'):
            for rec in self:
                if rec.sale_order_id and rec.sale_order_id.state in ('sale', 'done', 'cancel'):
                    raise UserError(_(
                        "لا يمكن تعديل لقطة التسعير التاريخية للفاتورة (%s) لأن الفاتورة مؤكدة أو مرحلة. "
                        "أدلة التسعير تعتبر وثيقة تدقيق مالي ثابتة وغير قابلة للتعديل."
                    ) % rec.sale_order_id.name)
        return super().write(vals)

    def unlink(self):
        """حماية لقطة التسعير من الحذف إذا كانت الفاتورة مؤكدة."""
        if not self.env.context.get('_allow_pricing_snapshot_modification'):
            for rec in self:
                if rec.sale_order_id and rec.sale_order_id.state in ('sale', 'done'):
                    raise UserError(_(
                        "لا يمكن حذف لقطة التسعير للفاتورة المؤكدة (%s)."
                    ) % rec.sale_order_id.name)
        return super().unlink()
