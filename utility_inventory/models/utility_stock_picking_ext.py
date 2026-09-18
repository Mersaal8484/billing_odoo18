from odoo import fields, models, _


class StockPickingUtility(models.Model):
    _inherit = 'stock.picking'

    utility_inventory_operation = fields.Selection([
        ('install', 'تركيب عداد'),
        ('remove', 'إزالة عداد'),
        ('return', 'إعادة للمخزون'),
        ('scrap', 'تكهين عداد'),
        ('repair', 'صيانة عداد'),
        ('replace_remove', 'إزالة عداد للاستبدال'),
        ('replace_install', 'تركيب عداد للاستبدال'),
    ], string='نوع عملية العداد المخزنية', index=True)

    utility_meter_id = fields.Many2one(
        'utility.meter', string='العداد المرتبط', index=True)

    utility_operation_ref = fields.Char(
        string='مرجع العملية المخزنية الصارم', index=True,
        help='مفتاح تتبع صارم لمنع تكرار الحركة المخزنية لنفس العملية التشغيلية (Idempotency Key).'
    )

    _sql_constraints = [
        ('unique_utility_operation_ref_company',
         'unique(utility_operation_ref, company_id)',
         'مرجع الحركة المخزنية للعداد مكرر لهذه الشركة! لا يمكن تنفيذ نفس العملية المخزنية مرتين.')
    ]
