from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class UtilityMeterReplacement(models.Model):
    _inherit = 'utility.meter.replacement'
    _description = 'سجل استبدال العداد'
    _order = 'replacement_date desc'

    order_number = fields.Char('رقم العملية', default=lambda self: _('New'), readonly=True)
    replacement_date = fields.Date('تاريخ التنفيذ الفعلي للاستبدال', default=fields.Date.today)
    old_meter_final_reading = fields.Float('القراءة النهائية للقديم', related='old_closing_reading', readonly=False, store=True)
    new_meter_initial_reading = fields.Float('القراءة الابتدائية للجديد', related='new_opening_reading', readonly=False, store=True)
    unbilled_consumption = fields.Float('الاستهلاك غير المفوتر للقديم', related='old_uninvoiced_consumption', store=True)
    replacement_notes = fields.Text('ملاحظات الاستبدال')
    picking_ids = fields.One2many('stock.picking', compute='_compute_picking_ids', string='حركات المخزون')
    picking_count = fields.Integer(compute='_compute_picking_ids', string='عدد حركات المخزون')

    def _compute_picking_ids(self):
        for rec in self:
            ref = rec.order_number or rec.name
            pickings = self.env['stock.picking'].search([
                '|',
                ('origin', '=', ref),
                ('utility_operation_ref', 'ilike', f"REPLACEMENT:{ref}"),
            ])
            rec.picking_ids = pickings
            rec.picking_count = len(pickings)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('order_number', _('New')) == _('New'):
                while True:
                    seq = self.env['ir.sequence'].next_by_code('utility.meter.replacement') or _('New')
                    if seq == _('New') or not self.sudo().search_count([('order_number', '=', seq)]):
                        vals['order_number'] = seq
                        break
        return super().create(vals_list)

    def action_complete_replacement(self):
        """Complete logistics around the unified core replacement flow."""
        self.ensure_one()
        if self.state == 'done':
            raise ValidationError(_('هذه العملية مكتملة بالفعل!'))
        self.write({
            'old_closing_reading': self.old_meter_final_reading or self.old_closing_reading,
            'new_opening_reading': self.new_meter_initial_reading or self.new_opening_reading,
            'replace_date': fields.Datetime.to_datetime(self.replacement_date) if self.replacement_date else self.replace_date,
        })
        old_meter = self.old_meter_id
        new_meter = self.new_meter_id
        ref = self.order_number or self.name

        # 1. Delegate physical stock execution to canonical inventory layer if physical identity is present
        if (
            old_meter and hasattr(old_meter, 'inventory_replace_meter')
            and old_meter.product_id and old_meter.lot_id
            and new_meter and new_meter.product_id and new_meter.lot_id
        ):
            old_meter.inventory_replace_meter(
                new_meter=new_meter,
                origin=ref,
                operation_ref=f"REPLACEMENT:{ref}",
                old_destination='inspection',
            )
        elif (
            new_meter and hasattr(new_meter, 'inventory_install_meter')
            and new_meter.product_id and new_meter.lot_id
        ):
            new_meter.inventory_install_meter(
                origin=ref,
                operation_ref=f"REPLACEMENT:{ref}:INSTALL",
            )

        # 2. Confirm logical customer & meter state update
        result = self._action_confirm_replacement_unified()
        return result
