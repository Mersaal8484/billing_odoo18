from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class UtilityMeterExt(models.Model):
    _inherit = 'utility.meter'

    # stock.lot.name is the sole physical serial source. This is a read-only
    # projection for integrations and legacy screens, not an independent value.
    serial_number = fields.Char(
        related='lot_id.name', string='الرقم التسلسلي', store=True,
        readonly=True, index=True,
    )

    product_id = fields.Many2one('product.product', 'المنتج', ondelete='restrict',
                                  help='منتج العداد المستخدم في المخزون لتتبع الرقم التسلسلي')
    lot_id = fields.Many2one('stock.lot', 'الرقم التسلسلي (Lot/Serial)', ondelete='restrict',
                             help='ربط العداد بالرقم التسلسلي في نظام المخزون')

    physical_state = fields.Selection([
        ('unresolved', 'غير محدد بالمخزون'),
        ('available', 'متاح بالمخزون'),
        ('installed', 'مركب لدى مشترك'),
        ('inspection', 'تحت الفحص'),
        ('repair', 'قيد الصيانة'),
        ('scrap', 'تالف / خردة'),
    ], string='الحالة الفيزيائية', compute='_compute_physical_state', store=False)
    last_integrity_check_at = fields.Datetime('تاريخ آخر فحص محاذاة', index=True)

    def _get_lot_current_location(self):
        self.ensure_one()
        if not self.lot_id:
            return False
        quants = self.env['stock.quant'].search([
            ('lot_id', '=', self.lot_id.id),
            ('quantity', '>', 0),
        ])
        if len(quants) > 1:
            raise ValidationError(_(
                'خلل في تكامل البيانات المخزنية: الرقم التسلسلي %s يتواجد بكمية موجبة في أكثر من موقع (%s).'
            ) % (self.lot_id.name, ', '.join(quants.mapped('location_id.display_name'))))
        return quants.location_id if quants else False

    @api.depends('lot_id', 'product_id')
    def _compute_physical_state(self):
        for meter in self:
            if not meter.lot_id or not meter.product_id:
                meter.physical_state = 'unresolved'
                continue
            loc = meter._get_lot_current_location()
            if not loc:
                meter.physical_state = 'available'
            elif loc.scrap_location:
                meter.physical_state = 'scrap'
            elif loc.usage == 'customer':
                meter.physical_state = 'installed'
            elif 'repair' in (loc.name or '').lower() or 'صيانة' in (loc.name or ''):
                meter.physical_state = 'repair'
            elif 'inspection' in (loc.name or '').lower() or 'فحص' in (loc.name or ''):
                meter.physical_state = 'inspection'
            else:
                meter.physical_state = 'available'

    def _get_physical_serial(self):
        self.ensure_one()
        return self.lot_id.name or ''

    @api.depends('lot_id.name')
    def _compute_qr_code(self):
        return super()._compute_qr_code()

    @api.model
    def _name_search_domain(self, name, operator='ilike'):
        domain = super()._name_search_domain(name, operator)
        if name:
            return ['|', ('lot_id.name', operator, name)] + domain
        return domain

    @api.model
    def _scan_domain(self, value):
        return ['|', ('meter_number', '=', value), ('lot_id.name', '=', value)]

    @api.model_create_multi
    def create(self, vals_list):
        """Convert legacy serial input into the canonical stock lot."""
        Lot = self.env['stock.lot']
        for vals in vals_list:
            legacy_serial = (vals.pop('serial_number', None) or '').strip() or False
            if not legacy_serial:
                continue
            lot = Lot.browse(vals.get('lot_id')).exists() if vals.get('lot_id') else Lot
            if lot and lot.name != legacy_serial:
                raise ValidationError(_(
                    'الرقم التسلسلي المدخل لا يطابق الرقم التسلسلي في المخزون.'
                ))
            if not lot:
                product = self.env['product.product'].browse(vals.get('product_id')).exists()
                if not product:
                    raise ValidationError(_(
                        'يجب تحديد منتج مهدأ بالتتبع التسلسلي قبل إنشاء رقم عداد مادي.'
                    ))
                lot = Lot.search([
                    ('name', '=', legacy_serial),
                    ('product_id', '=', product.id),
                ], limit=1)
                if not lot:
                    lot = Lot.create({
                        'name': legacy_serial,
                        'product_id': product.id,
                        'company_id': vals.get('company_id') or self.env.company.id,
                    })
                vals['lot_id'] = lot.id
        return super().create(vals_list)

    def write(self, vals):
        """Reject independent serial edits and route legacy input to stock."""
        vals = dict(vals)
        if 'serial_number' in vals:
            legacy_serial = (vals.pop('serial_number') or '').strip() or False
            for meter in self:
                if legacy_serial and meter.lot_id and meter.lot_id.name != legacy_serial:
                    raise ValidationError(_(
                        'لا يمكن تعديل الرقم التسلسلي من شاشة العداد؛ عدّل رقم Lot/Serial في المخزون.'
                    ))
                if legacy_serial and not meter.lot_id:
                    product = meter.product_id
                    if not product:
                        raise ValidationError(_(
                            'يجب تحديد منتج مهدأ بالتتبع التسلسلي قبل ربط الرقم المادي.'
                        ))
                    lot = self.env['stock.lot'].search([
                        ('name', '=', legacy_serial),
                        ('product_id', '=', product.id),
                    ], limit=1) or self.env['stock.lot'].create({
                        'name': legacy_serial,
                        'product_id': product.id,
                        'company_id': meter.company_id.id,
                    })
                    vals['lot_id'] = lot.id
        return super().write(vals)

    @api.onchange('model_id')
    def _onchange_model_id_product(self):
        if self.model_id and getattr(self.model_id, 'product_id', False) and not self.product_id:
            self.product_id = self.model_id.product_id

    @api.constrains('model_id', 'product_id')
    def _check_utility_inventory_model_product_consistency(self):
        for meter in self:
            if meter.model_id and getattr(meter.model_id, 'product_id', False) and meter.product_id:
                if meter.product_id != meter.model_id.product_id:
                    raise ValidationError(_(
                        'منتج العداد المختار بالمخزون (%s) لا يطابق منتج موديل العداد (%s).'
                    ) % (meter.product_id.display_name, meter.model_id.product_id.display_name))

    @api.constrains('product_id', 'lot_id', 'company_id')
    def _check_utility_inventory_serial_integrity(self):
        for meter in self:
            if meter.lot_id and meter.product_id:
                if meter.lot_id.product_id != meter.product_id:
                    raise ValidationError(_(
                        'الرقم التسلسلي (%s) غير مطابق لمنتج العداد (%s).'
                    ) % (meter.lot_id.name, meter.product_id.display_name))
            if meter.product_id and meter.product_id.tracking != 'serial':
                raise ValidationError(_(
                    'منتج العداد (%s) يجب أن يكون مهدأ بالتتبع التسلسلي (serial tracking).'
                ) % meter.product_id.display_name)
            if meter.lot_id:
                duplicate = self.search([
                    ('id', '!=', meter.id),
                    ('lot_id', '=', meter.lot_id.id),
                    ('active', '=', True),
                ], limit=1)
                if duplicate:
                    raise ValidationError(_(
                        'الرقم التسلسلي (%s) مستخدم مسبقًا لعداد آخر (%s).'
                    ) % (meter.lot_id.name, duplicate.meter_number or duplicate.display_name))
                if meter.lot_id.company_id and meter.company_id and meter.lot_id.company_id != meter.company_id:
                    raise ValidationError(_(
                        'شركة الرقم التسلسلي تسند إلى شركة مختلفة عن العداد.'
                    ))
                scrap_quant = self.env['stock.quant'].search([
                    ('lot_id', '=', meter.lot_id.id),
                    ('quantity', '>', 0),
                    ('location_id.scrap_location', '=', True),
                ], limit=1)
                if scrap_quant:
                    raise ValidationError(_(
                        'لا يمكن اختيار رقم تسلسلي مكهن أو تالف من مخزن الخردة (%s).'
                    ) % scrap_quant.location_id.display_name)

    # ── Canonical Multi-Warehouse Resolver ──────────────────────────────

    def _resolve_warehouse(self, warehouse=None, source_loc=None):
        """Strict deterministic multi-warehouse resolver.
        1. Explicit warehouse parameter
        2. Warehouse inferred from source_loc
        3. Warehouse inferred from the Lot's current internal location
        4. Safe fallback if company has EXACTLY ONE warehouse
        5. Raises ValidationError if multi-warehouse and unresolved
        """
        # 1. Explicit warehouse
        if warehouse:
            return warehouse

        company = (source_loc and source_loc.company_id) or (self and self.company_id) or self.env.company

        # 2. Inferred from source_loc
        if source_loc:
            wh = getattr(source_loc, 'warehouse_id', False)
            if not wh and hasattr(source_loc, 'get_warehouse'):
                wh = source_loc.get_warehouse()
            if wh and wh.company_id == company:
                return wh
            wh = self.env['stock.warehouse'].search([
                ('company_id', '=', company.id),
                '|', ('view_location_id', 'parent_of', source_loc.id),
                ('lot_stock_id', 'parent_of', source_loc.id),
            ], limit=1)
            if wh:
                return wh

        # 3. Inferred from current lot location
        if self and hasattr(self, '_get_lot_current_location'):
            cur_loc = self._get_lot_current_location()
            if cur_loc and (not cur_loc.company_id or cur_loc.company_id == company):
                wh = getattr(cur_loc, 'warehouse_id', False) or (
                    hasattr(cur_loc, 'get_warehouse') and cur_loc.get_warehouse()
                )
                if wh and wh.company_id == company:
                    return wh
                wh = self.env['stock.warehouse'].search([
                    ('company_id', '=', company.id),
                    '|', ('view_location_id', 'parent_of', cur_loc.id),
                    ('lot_stock_id', 'parent_of', cur_loc.id),
                ], limit=1)
                if wh:
                    return wh

        # 4. Safe single-warehouse company fallback
        warehouses = self.env['stock.warehouse'].search([('company_id', '=', company.id)])
        if len(warehouses) == 1:
            return warehouses[0]

        # 5. Deterministic failure
        if not warehouses:
            raise ValidationError(_('لم يتم العثور على أي مستودع مسجل للشركة %s.') % company.name)
        raise ValidationError(_(
            'لم يتم تحديد المستودع (Warehouse) المطلوب للعملية المخزنية، ويوجد أكثر من مستودع مسجل للشركة %s. '
            'يرجى اختيار المستودع صراحة في أمر الخدمة أو تفاصيل العملية.'
        ) % company.name)

    def _ensure_physical_identity(self, action_name='حركة مخزنية'):
        self.ensure_one()
        if not self.product_id or not self.lot_id:
            raise ValidationError(_(
                'العداد %s ليس له هوية مخزنية مادية مكتملة (يلزم تحديد المنتج والرقم التسلسلي بالمخزون) '
                'لتنفيذ إجراء "%s". لا يمكن تنفيذ عمليات مخزنية مادية لعدادات تراثية غير مهدأة بالمخزون.'
            ) % (self.meter_number or self.operational_number or self.display_name, action_name))

    def _resolve_meter_inspection_location(self, company=None, warehouse=None, source_loc=None):
        wh = self._resolve_warehouse(warehouse=warehouse, source_loc=source_loc)
        wh._ensure_utility_meter_locations()
        return wh.meter_inspection_location_id

    def _resolve_meter_repair_location(self, company=None, warehouse=None, source_loc=None):
        wh = self._resolve_warehouse(warehouse=warehouse, source_loc=source_loc)
        wh._ensure_utility_meter_locations()
        return wh.meter_repair_location_id

    def _resolve_meter_picking_type(self, source_loc, dest_loc, warehouse=None, company=None):
        wh = self._resolve_warehouse(warehouse=warehouse, source_loc=source_loc)
        
        if source_loc.usage == 'internal' and dest_loc.usage == 'customer':
            picking_type = wh.out_type_id
            label = 'إخراج / تسليم (Outgoing)'
        elif source_loc.usage == 'customer' and dest_loc.usage == 'internal':
            picking_type = wh.in_type_id
            label = 'إدخال / استلام (Incoming)'
        else:
            picking_type = wh.int_type_id
            label = 'نقل داخلي (Internal)'

        if not picking_type:
            # Fallback search within exact warehouse
            code = 'outgoing' if source_loc.usage == 'internal' and dest_loc.usage == 'customer' else (
                'incoming' if source_loc.usage == 'customer' and dest_loc.usage == 'internal' else 'internal'
            )
            picking_type = self.env['stock.picking.type'].search([
                ('code', '=', code),
                ('warehouse_id', '=', wh.id),
            ], limit=1)

        if not picking_type:
            raise ValidationError(_(
                'تعذر تحديد نوع الحركة المخزنية (%s) للمستودع "%s" بالشركة %s.'
            ) % (label, wh.name, wh.company_id.name))
        return picking_type

    def _validate_physical_meter_location(self, expected_usage=None):
        self.ensure_one()
        self._ensure_physical_identity(_('التحقق من موقع العداد'))
        loc = self._get_lot_current_location()

        if expected_usage and loc and loc.usage != expected_usage:
            raise ValidationError(_(
                'العداد %s موجود حاليًا في موقع "%s" وليس في الموقع المتوقع (%s).'
            ) % (self.meter_number, loc.display_name, expected_usage))

    def _validate_physical_meter_for_installation(self, source_loc=None):
        self.ensure_one()
        self._ensure_physical_identity(_('تركيب عداد'))

        if self.product_id.tracking != 'serial':
            raise ValidationError(_('منتج العداد (%s) لا يستخدم التتبع التسلسلي.') % self.product_id.display_name)

        if self.lot_id.product_id != self.product_id:
            raise ValidationError(_(
                'الرقم التسلسلي %s غير مطابق لمنتج العداد %s.'
            ) % (self.lot_id.name, self.product_id.display_name))

        if self.lot_id.company_id and self.company_id and self.lot_id.company_id != self.company_id:
            raise ValidationError(_('شركة الرقم التسلسلي تختلف عن شركة العداد.'))

        scrap_quant = self.env['stock.quant'].search([
            ('lot_id', '=', self.lot_id.id),
            ('quantity', '>', 0),
            ('location_id.scrap_location', '=', True),
        ], limit=1)
        if scrap_quant:
            raise ValidationError(_(
                'الرقم التسلسلي (%s) موجود في موقع التكهين/الخردة (%s) ولا يمكن تركيبه.'
            ) % (self.lot_id.name, scrap_quant.location_id.display_name))

        if source_loc and source_loc.usage == 'internal':
            quant = self.env['stock.quant'].search([
                ('lot_id', '=', self.lot_id.id),
                ('product_id', '=', self.product_id.id),
                ('location_id', 'child_of', source_loc.id),
                ('quantity', '>', 0),
            ], limit=1)
            if not quant:
                raise ValidationError(_(
                    'العداد المادي "%s" (رقم تسلسلي %s) غير متوفر مخزنيًا برصيد موجب (> 0) '
                    'في الموقع المخزني المحدد (%s).'
                ) % (self.display_name, self.lot_id.name, source_loc.complete_name))

        if source_loc and source_loc.usage == 'customer':
            current_loc = self._get_lot_current_location()
            if current_loc and current_loc.usage == 'customer':
                raise ValidationError(_('العداد %s مُركب بالفعل لدى مشترك آخر في المخزون.') % self.meter_number)

    def _get_existing_meter_picking(self, operation_type, operation_ref):
        if not operation_ref:
            return False
        return self.env['stock.picking'].search([
            ('utility_operation_ref', '=', operation_ref),
            ('utility_inventory_operation', '=', operation_type),
            ('state', '!=', 'cancel'),
        ], limit=1)

    def _create_single_stock_movement(self, source_loc, dest_loc, operation_type, warehouse=None, operation_ref=None, origin=None):
        self.ensure_one()
        existing = self._get_existing_meter_picking(operation_type, operation_ref)
        if existing:
            return existing

        wh = self._resolve_warehouse(warehouse=warehouse, source_loc=source_loc)
        company = wh.company_id
        picking_type = self._resolve_meter_picking_type(source_loc, dest_loc, warehouse=wh, company=company)

        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': source_loc.id,
            'location_dest_id': dest_loc.id,
            'origin': origin or operation_ref or self.meter_number,
            'utility_inventory_operation': operation_type,
            'utility_meter_id': self.id,
            'utility_operation_ref': operation_ref,
            'company_id': company.id,
        })

        move = self.env['stock.move'].create({
            'name': self.meter_number,
            'product_id': self.product_id.id,
            'product_uom_qty': 1,
            'product_uom': self.product_id.uom_id.id,
            'picking_id': picking.id,
            'location_id': source_loc.id,
            'location_dest_id': dest_loc.id,
            'company_id': company.id,
        })

        self.env['stock.move.line'].create({
            'move_id': move.id,
            'product_id': self.product_id.id,
            'product_uom_id': self.product_id.uom_id.id,
            'qty_done': 1,
            'lot_id': self.lot_id.id,
            'picking_id': picking.id,
            'location_id': source_loc.id,
            'location_dest_id': dest_loc.id,
            'company_id': company.id,
        })

        picking.action_confirm()
        picking.button_validate()
        return picking

    def inventory_install_meter(self, customer=None, warehouse=None, origin=None, operation_ref=None):
        """Execute physical meter installation (Warehouse Stock -> Customers)."""
        self.ensure_one()
        self._ensure_physical_identity(_('تركيب عداد'))

        # Idempotency check before resolving warehouse or movement validations
        existing = self._get_existing_meter_picking('install', operation_ref)
        if existing:
            return existing

        wh = self._resolve_warehouse(warehouse=warehouse)
        stock_loc = wh.lot_stock_id
        cust_loc = self.env.ref('stock.stock_location_customers', raise_if_not_found=False)
        if not stock_loc or not cust_loc:
            raise ValidationError(_('مواقع المخزون (Stock/Customers) غير معرفة في النظام.'))

        self._validate_physical_meter_for_installation(source_loc=stock_loc)

        op_ref = operation_ref or (f"{origin}:INSTALL:{self.id}" if origin else f"INSTALL:{self.id}")
        return self._create_single_stock_movement(
            source_loc=stock_loc,
            dest_loc=cust_loc,
            operation_type='install',
            warehouse=wh,
            operation_ref=op_ref,
            origin=origin,
        )

    def inventory_remove_meter(self, warehouse=None, destination='inspection', origin=None, operation_ref=None):
        """Execute physical meter removal (Customers -> Warehouse Inspection / Repair / Stock / Scrap)."""
        self.ensure_one()
        self._ensure_physical_identity(_('إزالة عداد'))

        cust_loc = self.env.ref('stock.stock_location_customers', raise_if_not_found=False)
        if not cust_loc:
            raise ValidationError(_('موقع العملاء (Customers Location) غير معرف.'))

        wh = self._resolve_warehouse(warehouse=warehouse)

        if destination == 'scrap':
            dest_loc = self.env.ref('stock.stock_location_scrapped', raise_if_not_found=False)
        elif destination == 'stock':
            dest_loc = wh.lot_stock_id
        elif destination == 'repair':
            dest_loc = self._resolve_meter_repair_location(warehouse=wh)
        else:
            dest_loc = self._resolve_meter_inspection_location(warehouse=wh, source_loc=cust_loc)

        if not dest_loc:
            raise ValidationError(_('موقع الوجهة المخزنية للإزالة غير معرف.'))

        op_ref = operation_ref or (f"{origin}:REMOVE:{self.id}" if origin else f"REMOVE:{self.id}")
        return self._create_single_stock_movement(
            source_loc=cust_loc,
            dest_loc=dest_loc,
            operation_type='remove',
            warehouse=wh,
            operation_ref=op_ref,
            origin=origin,
        )

    def inventory_replace_meter(self, new_meter, old_warehouse=None, new_warehouse=None, origin=None, operation_ref=None, old_destination='inspection'):
        """Atomic physical meter replacement:
        1. Resolve old_warehouse for old meter and new_warehouse for new meter
        2. Validate old & new physical meters completely upfront
        3. Remove old meter (Customers -> old_wh.meter_inspection_location_id)
        4. Install new meter (new_wh.lot_stock_id -> Customers)
        """
        self.ensure_one()
        old_meter = self

        # 1. Atomic Upfront Validation
        old_meter._ensure_physical_identity(_('إزالة عداد للاستبدال'))
        if not new_meter:
            raise ValidationError(_('يجب تحديد العداد الجديد المراد تركيبه.'))
        new_meter._ensure_physical_identity(_('تركيب عداد للاستبدال'))

        old_wh = old_meter._resolve_warehouse(warehouse=old_warehouse)
        new_wh = new_meter._resolve_warehouse(warehouse=new_warehouse)

        cust_loc = self.env.ref('stock.stock_location_customers', raise_if_not_found=False)
        if not cust_loc or not new_wh.lot_stock_id:
            raise ValidationError(_('مواقع المخزون (Stock/Customers) غير معرفة.'))

        new_meter._validate_physical_meter_for_installation(source_loc=new_wh.lot_stock_id)

        # 2. Execute Movements
        base_ref = operation_ref or origin or f"REPLACE:{old_meter.id}:{new_meter.id}"
        old_op_ref = f"{base_ref}:REPLACE_REMOVE:{old_meter.id}"
        new_op_ref = f"{base_ref}:REPLACE_INSTALL:{new_meter.id}"

        old_picking = old_meter.inventory_remove_meter(
            warehouse=old_wh,
            origin=origin,
            operation_ref=old_op_ref,
            destination=old_destination,
        )

        new_picking = new_meter.inventory_install_meter(
            warehouse=new_wh,
            origin=origin,
            operation_ref=new_op_ref,
        )

        return {
            'old_picking': old_picking,
            'new_picking': new_picking,
        }

    def inventory_return_to_stock(self, warehouse=None, origin=None, operation_ref=None):
        """Return meter from Warehouse Inspection -> Warehouse Stock."""
        self.ensure_one()
        self._ensure_physical_identity(_('إعادة العداد للمخزون'))

        wh = self._resolve_warehouse(warehouse=warehouse)
        inspection_loc = self._resolve_meter_inspection_location(warehouse=wh)
        stock_loc = wh.lot_stock_id
        if not inspection_loc or not stock_loc:
            raise ValidationError(_('مواقع المخزون (Inspection/Stock) غير معرفة للمستودع.'))

        op_ref = operation_ref or (f"{origin}:RETURN:{self.id}" if origin else f"RETURN:{self.id}")
        return self._create_single_stock_movement(
            source_loc=inspection_loc,
            dest_loc=stock_loc,
            operation_type='return',
            warehouse=wh,
            operation_ref=op_ref,
            origin=origin,
        )

    def inventory_repair_meter(self, action='to_repair', warehouse=None, origin=None, operation_ref=None):
        """Manage repair movements:
        - action='to_repair': Inspection -> Repair
        - action='from_repair': Repair -> Inspection (re-inspection before returning to stock)
        """
        self.ensure_one()
        self._ensure_physical_identity(_('صيانة العداد'))

        wh = self._resolve_warehouse(warehouse=warehouse)
        inspection_loc = self._resolve_meter_inspection_location(warehouse=wh)
        repair_loc = self._resolve_meter_repair_location(warehouse=wh)

        if action == 'from_repair':
            source_loc, dest_loc = repair_loc, inspection_loc
            op_code = 'from_repair'
        else:
            source_loc, dest_loc = inspection_loc, repair_loc
            op_code = 'to_repair'

        op_ref = operation_ref or (f"{origin}:REPAIR:{op_code}:{self.id}" if origin else f"REPAIR:{op_code}:{self.id}")
        return self._create_single_stock_movement(
            source_loc=source_loc,
            dest_loc=dest_loc,
            operation_type='repair',
            warehouse=wh,
            operation_ref=op_ref,
            origin=origin,
        )

    def inventory_scrap_meter(self, warehouse=None, origin=None, operation_ref=None):
        """Route meter from current location -> Scrap."""
        self.ensure_one()
        self._ensure_physical_identity(_('تكهين عداد'))

        current_loc = self._get_lot_current_location()
        wh = self._resolve_warehouse(warehouse=warehouse, source_loc=current_loc)
        source_loc = current_loc or wh.meter_inspection_location_id
        scrap_loc = self.env.ref('stock.stock_location_scrapped', raise_if_not_found=False) or self.env['stock.location'].search([
            ('scrap_location', '=', True),
            ('company_id', 'in', [self.company_id.id or self.env.company.id, False]),
        ], limit=1)
        if not source_loc or not scrap_loc:
            raise ValidationError(_('مواقع المخزون (Scrap Location) غير معرفة.'))

        op_ref = operation_ref or (f"{origin}:SCRAP:{self.id}" if origin else f"SCRAP:{self.id}")
        return self._create_single_stock_movement(
            source_loc=source_loc,
            dest_loc=scrap_loc,
            operation_type='scrap',
            warehouse=wh,
            operation_ref=op_ref,
            origin=origin,
        )

    @api.model
    def cron_check_meter_stock_alignment(self, batch_limit=500):
        """فحص وتدقيق التوافق بين الحالة المنطقية والموقع المخزني الفعلي.
        تستخدم الدالة Cursor مبنياً على تاريخ آخر فحص لتغطية جميع العدادات بالتتابع،
        وتكتشف وتسجل الفروقات في نموذج Exception Log (utility.meter.integrity.issue)
        دون أي تعديل آلي لحماية بيانات الأصول والمحاسبة، مع تطبيق منع التكرار (Deduplication)."""
        # Odoo 16 ORM لا يقبل 'NULLS FIRST' في order string.
        # نعوّض بدفعتين: أولاً العدادات التي لم تُفحص قط، ثم الأقدم فحصاً.
        never_checked = self.search(
            [('active', '=', True), ('last_integrity_check_at', '=', False)],
            order='id asc',
            limit=batch_limit,
        )
        remaining = batch_limit - len(never_checked)
        if remaining > 0:
            already_checked = self.search(
                [('active', '=', True), ('last_integrity_check_at', '!=', False)],
                order='last_integrity_check_at asc, id asc',
                limit=remaining,
            )
        else:
            already_checked = self.browse()
        meters = never_checked | already_checked
        Issue = self.env['utility.meter.integrity.issue']
        Quant = self.env['stock.quant']
        processed_issues = Issue.browse()
        now = fields.Datetime.now()

        def _log_or_update_issue(meter, issue_type, severity, message, lot=None, loc=None, cust=None, wh=None):
            existing = Issue.search([
                ('meter_id', '=', meter.id),
                ('issue_type', '=', issue_type),
                ('resolved', '=', False),
            ], limit=1)
            if existing:
                existing.write({
                    'detected_at': now,
                    'message': message,
                    'severity': severity,
                    'physical_location_id': loc.id if loc else existing.physical_location_id.id,
                    'logical_customer_id': cust.id if cust else existing.logical_customer_id.id,
                    'warehouse_id': wh.id if wh else existing.warehouse_id.id,
                })
                return existing
            else:
                return Issue.create({
                    'meter_id': meter.id,
                    'issue_type': issue_type,
                    'severity': severity,
                    'lot_id': lot.id if lot else meter.lot_id.id,
                    'physical_location_id': loc.id if loc else False,
                    'logical_customer_id': cust.id if cust else meter.customer_id.id,
                    'warehouse_id': wh.id if wh else False,
                    'message': message,
                })

        for meter in meters:
            # 1. lot_missing
            if not meter.lot_id:
                issue = _log_or_update_issue(
                    meter, 'lot_missing', 'critical',
                    _('العداد مفقود الهوية التسلسلية بالمخزون (لا يملك الرقم التسلسلي lot_id).')
                )
                processed_issues |= issue
                continue

            current_loc = meter._get_lot_current_location()

            # 2. logical_installed_but_stock_available
            if meter.customer_id and current_loc and current_loc.usage == 'internal':
                issue = _log_or_update_issue(
                    meter, 'logical_installed_but_stock_available', 'critical',
                    _('العداد معين منطقيًا للمشترك (%s) بينما موقعه المخزني الفعلي موقع داخلي (%s).') % (
                        meter.customer_id.display_name, current_loc.display_name),
                    lot=meter.lot_id, loc=current_loc, cust=meter.customer_id
                )
                processed_issues |= issue

            # 3. logical_unassigned_but_stock_customer
            elif not meter.customer_id and current_loc and current_loc.usage == 'customer':
                issue = _log_or_update_issue(
                    meter, 'logical_unassigned_but_stock_customer', 'warning',
                    _('العداد غير معين لأي مشترك منطقيًا ولكن موقعه المخزني الفعلي موقع عميل (%s).') % current_loc.display_name,
                    lot=meter.lot_id, loc=current_loc
                )
                processed_issues |= issue

            # 4. product_lot_mismatch
            if meter.product_id and meter.lot_id.product_id != meter.product_id:
                issue = _log_or_update_issue(
                    meter, 'product_lot_mismatch', 'critical',
                    _('منتج العداد (%s) لا يطابق منتج الرقم التسلسلي بالمخزون (%s).') % (
                        meter.product_id.display_name, meter.lot_id.product_id.display_name),
                    lot=meter.lot_id
                )
                processed_issues |= issue

            # 5. multiple_positive_quants
            positive_quants = Quant.search([
                ('lot_id', '=', meter.lot_id.id),
                ('quantity', '>', 0),
                ('location_id.usage', '=', 'internal'),
            ])
            if len(positive_quants) > 1:
                issue = _log_or_update_issue(
                    meter, 'multiple_positive_quants', 'critical',
                    _('الرقم التسلسلي للعداد (%s) لديه أرصدة موجبة مكررة في (%d) مواقع مخزنية داخلية.') % (
                        meter.lot_id.name, len(positive_quants)),
                    lot=meter.lot_id
                )
                processed_issues |= issue

            # 6. scrapped_but_active
            scrapped_quants = Quant.search([
                ('lot_id', '=', meter.lot_id.id),
                ('quantity', '>', 0),
                ('location_id.scrap_location', '=', True),
            ])
            if scrapped_quants and meter.active:
                issue = _log_or_update_issue(
                    meter, 'scrapped_but_active', 'critical',
                    _('العداد نشط في النظام بينما تم تكهين رقمه التسلسلي بالمخزون في موقع التكهين (%s).') % (
                        scrapped_quants[0].location_id.display_name),
                    lot=meter.lot_id, loc=scrapped_quants[0].location_id
                )
                processed_issues |= issue

            # 7. wrong_warehouse
            if current_loc and current_loc.warehouse_id and meter.company_id:
                wh = current_loc.warehouse_id
                if wh.company_id != meter.company_id:
                    issue = _log_or_update_issue(
                        meter, 'wrong_warehouse', 'critical',
                        _('المستودع الفعلي للعداد (%s) تابع لشركة (%s) بينما العداد تابع لشركة (%s).') % (
                            wh.name, wh.company_id.name, meter.company_id.name),
                        lot=meter.lot_id, loc=current_loc, wh=wh
                    )
                    processed_issues |= issue

        if meters:
            meters.write({'last_integrity_check_at': now})

        return len(processed_issues)


class UtilityMeterModelInventory(models.Model):
    _inherit = 'utility.meter.model'

    product_id = fields.Many2one(
        'product.product', 'المنتج بالمخزون', ondelete='restrict',
        domain="[('tracking', '=', 'serial')]",
        help='المنتج الذي يمثل هذا الموديل الفني في نظام المخزون',
    )

    def action_open_product(self):
        self.ensure_one()
        if self.product_id:
            return {
                'type': 'ir.actions.act_window',
                'name': 'المنتج في المخزون',
                'res_model': 'product.product',
                'res_id': self.product_id.id,
                'view_mode': 'form',
                'target': 'current',
            }
