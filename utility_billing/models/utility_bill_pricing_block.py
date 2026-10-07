from odoo import api, fields, models, _
from odoo.exceptions import UserError


class UtilityBillPricingBlock(models.Model):
    _name = 'utility.bill.pricing.block'
    _description = 'أثر الشريحة المطبقة في الفاتورة (Applied Pricing Block Snapshot Line)'
    _order = 'pricing_snapshot_id, sequence, id'

    pricing_snapshot_id = fields.Many2one(
        'utility.bill.pricing.snapshot',
        string='لقطة التسعير المرجعية',
        required=True,
        index=True,
        ondelete='cascade',
    )
    sale_order_id = fields.Many2one(
        'sale.order',
        related='pricing_snapshot_id.sale_order_id',
        string='الفاتورة',
        store=True,
        readonly=True,
    )
    sequence = fields.Integer(
        string='الترتيب',
        default=10,
    )
    source_block_id = fields.Many2one(
        'utility.contract.template.block',
        string='الشريحة المصدر (للتتبع فقط)',
        ondelete='set null',
    )
    customer_block_id = fields.Many2one(
        'utility.customer.block.line',
        string='الشريحة المحلية المصدر',
        ondelete='set null',
    )
    block_name = fields.Char(
        string='اسم الشريحة المطبقة',
        required=True,
    )
    from_kwh = fields.Float(
        string='من (kWh)',
        default=0.0,
    )
    to_kwh = fields.Float(
        string='إلى (kWh)',
        default=0.0,
    )
    quantity = fields.Float(
        string='الكمية الواقعة في الشريحة (kWh)',
        required=True,
        default=0.0,
    )
    price_per_kwh = fields.Monetary(
        string='السعر المطبق للوحدة',
        required=True,
        currency_field='currency_id',
    )
    amount = fields.Monetary(
        string='المبلغ المحتسب للشريحة',
        required=True,
        currency_field='currency_id',
    )
    is_discount = fields.Boolean(
        string='شريحة خصم مدعوم',
        default=False,
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='pricing_snapshot_id.currency_id',
        string='العملة',
        store=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        'res.company',
        related='pricing_snapshot_id.company_id',
        string='الشركة',
        store=True,
        readonly=True,
    )

    def write(self, vals):
        if not self.env.context.get('_allow_pricing_snapshot_modification'):
            for rec in self:
                if rec.sale_order_id and rec.sale_order_id.state in ('sale', 'done', 'cancel'):
                    raise UserError(_("لا يمكن تعديل بنود الشرائح المطبقة للفاتورة المؤكدة (%s).") % rec.sale_order_id.name)
        return super().write(vals)

    def unlink(self):
        if not self.env.context.get('_allow_pricing_snapshot_modification'):
            for rec in self:
                if rec.sale_order_id and rec.sale_order_id.state in ('sale', 'done'):
                    raise UserError(_("لا يمكن حذف بنود الشرائح المطبقة للفاتورة المؤكدة (%s).") % rec.sale_order_id.name)
        return super().unlink()
