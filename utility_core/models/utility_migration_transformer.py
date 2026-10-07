from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class UtilityMigrationTransformer(models.Model):
    _name = 'utility.migration.transformer'
    _description = 'تهيئة بيانات المحولات (النظام القديم)'
    _order = 'id asc'

    company_id = fields.Many2one(
        'res.company', string='الشركة', required=True,
        default=lambda self: self.env.company, index=True)

    name = fields.Char('اسم العرض / المحول', required=True)
    legacy_region = fields.Char('رمز المنطقة')
    legacy_area = fields.Char('رمز الفرع')
    legacy_analytic_id = fields.Char('معرف الحساب التحليلي')
    is_active = fields.Boolean('هل فعال؟', default=True)

    transformer_code = fields.Char('رمز المحول / الحساب التحليلي')
    transformer_name = fields.Char('اسم المحول / الشريك')
    reference = fields.Char('المرجع / كود المحول الفيدر')
    description = fields.Text('الوصف')

    meter_number = fields.Char('رقم العداد (عداد رصد المحول)')
    meter_multiplier = fields.Float('معامل الضرب للعداد', default=1.0)
    current_reading = fields.Float('القراءة الحالية', digits=(12, 3))
    has_current_reading = fields.Boolean('تم إدخال قراءة حالية')
    total_consumption = fields.Float('إجمالي الاستهلاك', digits=(12, 3))
    image_status = fields.Char('حالة الصورة')
    opening_reading = fields.Float('قراءة بداية الاشتراك', digits=(12, 3))
    has_opening_reading = fields.Boolean('تم إدخال قراءة بداية الاشتراك')

    is_calculation_cell = fields.Boolean('خلية إحتساب', default=False)

    cell_meter_multiplier = fields.Float('الخلية / معامل الضرب للعداد', default=1.0)
    cell_meter_number = fields.Char('الخلية / رقم العداد')

    region_id = fields.Many2one('utility.region', string='المنطقة (Odoo)', domain="[('type', '=', 'region')]")
    area_id = fields.Many2one(
        'utility.region', string='الفرع (Odoo)',
        domain="[('type', '=', 'area'), ('parent_id', '=', region_id)]",
    )

    @api.constrains('region_id', 'area_id')
    def _check_region_area_consistency(self):
        for record in self:
            if record.region_id and record.area_id and record.area_id.parent_id != record.region_id:
                raise ValidationError(_(
                    'الفرع "%s" لا يتبع المنطقة "%s".'
                ) % (record.area_id.display_name, record.region_id.display_name))
    feeder_id = fields.Many2one('utility.feeder', string='الفيدر / الخلية (Odoo)')

    state = fields.Selection([
        ('draft', 'مسودة'),
        ('queued', 'في الانتظار'),
        ('processing', 'قيد المعالجة'),
        ('imported', 'تم الرفع'),
        ('error', 'خطأ')
    ], string='الحالة', default='draft', index=True)

    last_batch_id = fields.Many2one(
        'utility.migration.batch', string='دفعة التنفيذ الأخيرة',
        readonly=True, copy=False, index=True)

    error_message = fields.Text('رسالة الخطأ', readonly=True)
    source_row_number = fields.Integer('صف المصدر في Excel', readonly=True, index=True)

    created_transformer_id = fields.Many2one('utility.transformer', 'المحول المنشأ', readonly=True, copy=False)
    created_meter_id = fields.Many2one('utility.meter', 'العداد المنشأ', readonly=True, copy=False)
    created_reading_id = fields.Many2one('utility.reading', 'القراءة الافتتاحية المنشأة', readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'current_reading' in vals and vals['current_reading'] is not False and vals['current_reading'] is not None:
                vals['has_current_reading'] = True
            if 'opening_reading' in vals and vals['opening_reading'] is not False and vals['opening_reading'] is not None:
                vals['has_opening_reading'] = True
        return super().create(vals_list)

    def write(self, vals):
        if 'current_reading' in vals and vals['current_reading'] is not False and vals['current_reading'] is not None:
            vals['has_current_reading'] = True
        if 'opening_reading' in vals and vals['opening_reading'] is not False and vals['opening_reading'] is not None:
            vals['has_opening_reading'] = True
        return super().write(vals)

    def _get_staging_opening_reading_value(self):
        """إرجاع قيمة قراءة الافتتاح بدقة (تميز بين عدم الإدخال وقيمة الصفر)."""
        self.ensure_one()
        if self.has_current_reading:
            return float(self.current_reading)
        if self.has_opening_reading:
            return float(self.opening_reading)
        return None

    # -------------------------------------------------------------------------
    # Helper Actions (model-level)
    # -------------------------------------------------------------------------

    @api.model
    def action_download_template(self):
        return {
            'type': 'ir.actions.act_url',
            'url': '/utility_core/static/src/Transformer_Migration_Template.xlsx',
            'target': 'new',
        }

    def action_open_transformer(self):
        self.ensure_one()
        if not self.created_transformer_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'name': _('المحول'),
            'res_model': 'utility.transformer',
            'view_mode': 'form',
            'res_id': self.created_transformer_id.id,
            'target': 'current',
        }

    def action_open_meter(self):
        self.ensure_one()
        if not self.created_meter_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'name': _('العداد'),
            'res_model': 'utility.meter',
            'view_mode': 'form',
            'res_id': self.created_meter_id.id,
            'target': 'current',
        }

    # -------------------------------------------------------------------------
    # Code Mapping (Batch Cache & Flexible Strict/Non-Strict Mode)
    # -------------------------------------------------------------------------

    def action_map_codes(self, caches=None, strict=True):
        """مطابقة الرموز القديمة مع الدعم المرن للـ Upload والمنع الصارم عند الاعتماد (Business Import)."""
        if caches is None:
            caches = {}

        has_missing = False
        for rec in self:
            if rec.state == 'imported':
                continue
            company_id = rec.company_id.id or self.env.company.id
            if company_id not in caches:
                caches[company_id] = self.env['utility.migration.mapping'].get_mapping_cache(company_id)
            cache = caches[company_id]
            missing = []

            if rec.legacy_region:
                val = cache.get(('region', rec.legacy_region.strip()))
                if val:
                    rec.region_id = val.id
                else:
                    missing.append(f"MISSING_REGION_MAPPING: لم يتم العثور على ترميز المنطقة ({rec.legacy_region})")

            if rec.legacy_area:
                val = cache.get(('area', rec.legacy_area.strip()))
                if val:
                    rec.area_id = val.id
                else:
                    missing.append(f"MISSING_AREA_MAPPING: لم يتم العثور على ترميز الفرع ({rec.legacy_area})")

            if rec.cell_meter_number:
                cell_code = rec.cell_meter_number.strip()
                feeder = False
                m = self.env['utility.meter'].search([
                    ('company_id', '=', company_id),
                    ('meter_number', '=', cell_code),
                    ('connection_type', '=', 'feeder')
                ], limit=1)
                if m and m.linked_feeder_id:
                    feeder = m.linked_feeder_id

                if not feeder:
                    feeder = self.env['utility.feeder'].search([
                        ('company_id', '=', company_id),
                        ('code', '=', cell_code)
                    ], limit=1)

                if feeder:
                    rec.feeder_id = feeder.id

            if not rec.region_id:
                missing.append("MISSING_REGION_MAPPING: المحول العام يلزم ربطه بمنطقة (Region).")
            if not rec.area_id:
                missing.append("MISSING_AREA_MAPPING: المحول العام يلزم ربطه بفرع (Area).")
            elif rec.region_id and rec.area_id.parent_id != rec.region_id:
                missing.append(
                    f"AREA_NOT_IN_REGION: الفرع ({rec.area_id.display_name}) لا يتبع المنطقة ({rec.region_id.display_name})."
                )

            if missing:
                has_missing = True
                err = "\n".join(missing)
                rec.error_message = err
            else:
                rec.error_message = False

        if strict and has_missing:
            err_details = [rec.error_message for rec in self if rec.error_message]
            raise ValidationError("\n".join(err_details) if err_details else _('توجد سجلات تحتوي على رموز غير معرّفة في جدول الترميز.'))

    # -------------------------------------------------------------------------
    # Main Actions
    # -------------------------------------------------------------------------

    def action_import_data(self):
        caches = {}
        for rec in self:
            if rec.state == 'imported':
                continue
            try:
                with self.env.cr.savepoint():
                    rec.action_map_codes(caches=caches, strict=True)
                    company_id = rec.company_id.id or self.env.company.id

                    # 1. Preferred Identity Order: reference -> transformer_code -> legacy_analytic_id
                    code = (rec.reference or rec.transformer_code or rec.legacy_analytic_id or '').strip()
                    if not code:
                        raise ValidationError(_('MISSING_TRANSFORMER_IDENTITY: يلزم توفر مرجع (reference) أو رمز المحول لتحديد الهوية المرجعية.'))

                    trans_name = rec.transformer_name or rec.name or code

                    # Search or create utility.transformer (Company-Scoped & Identity-Checked)
                    transformer = rec.created_transformer_id
                    if not transformer:
                        transformers = self.env['utility.transformer'].search([
                            ('company_id', '=', company_id),
                            ('is_private', '=', False),
                            ('code', '=', code),
                        ])
                        if len(transformers) > 1:
                            raise ValidationError(_('AMBIGUOUS_TRANSFORMER_IDENTITY: تعددت المحولات بنفس الرمز (%s) لنفس الشركة.') % code)
                        transformer = transformers[:1]

                    trans_vals = {
                        'name': trans_name,
                        'code': code,
                        'notes': rec.description,
                        'company_id': company_id,
                        'active': rec.is_active,
                    }
                    if rec.feeder_id:
                        trans_vals['feeder_id'] = rec.feeder_id.id
                    if rec.area_id:
                        trans_vals['area_id'] = rec.area_id.id
                    if rec.region_id:
                        trans_vals['region_id'] = rec.region_id.id

                    if transformer:
                        transformer.write(trans_vals)
                    else:
                        transformer = self.env['utility.transformer'].create(trans_vals)

                    rec.created_transformer_id = transformer.id

                    # 1.5 Ensure a default route (مسار افتراضي) for every general transformer
                    if transformer and not transformer.is_private:
                        transformer._get_or_create_default_route()

                    # 2. Search or create meter as a Coupling Meter (Company-Scoped)
                    meter_num = (rec.meter_number or code).strip()
                    multiplier = rec.meter_multiplier or 1.0

                    meter = rec.created_meter_id
                    if not meter:
                        meters = self.env['utility.meter'].search([
                            ('company_id', '=', company_id),
                            ('meter_number', '=', meter_num),
                        ])
                        if len(meters) > 1:
                            raise ValidationError(_('AMBIGUOUS_METER_IDENTITY: تكرر رقم العداد (%s) داخل الشركة.') % meter_num)
                        meter = meters[:1]

                    status_active = self.env['utility.meter.status'].search([('code', '=', 'ACTIVE')], limit=1)

                    meter_vals = {
                        'meter_number': meter_num,
                        'operational_number': meter_num,
                        'multiplier': multiplier,
                        'connection_type': 'transformer',
                        'linked_transformer_id': transformer.id,
                        'company_id': company_id,
                        'payment_type': 'manual',
                        'is_coupling_meter': True,
                        'active': True,
                    }
                    if status_active:
                        meter_vals['status_id'] = status_active.id

                    if meter:
                        meter.write(meter_vals)
                    else:
                        meter = self.env['utility.meter'].create(meter_vals)

                    rec.created_meter_id = meter.id
                    transformer.write({'coupling_meter_id': meter.id})

                    # 3. Create initial/opening reading (Zero reading 0.0 is VALID!)
                    opening_val = rec._get_staging_opening_reading_value()
                    if opening_val is not None:
                        reading = rec.created_reading_id
                        if not reading:
                            reading = self.env['utility.reading'].search([
                                ('meter_id', '=', meter.id),
                                ('reading_purpose', '=', 'opening')
                            ], limit=1)

                        reading_vals = {
                            'meter_id': meter.id,
                            'reading_value': opening_val,
                            'reading_date': fields.Datetime.now(),
                            'reading_type': 'manual',
                            'reading_purpose': 'opening',
                            'reading_event': 'normal',
                            'is_initial_reading': True,
                            'reading_category': 'transformer',
                            'reading_source': 'legacy_migration',
                            'state': 'billed',
                        }

                        reading_ctx = {'_reading_state_transition': True, '_bypass_reading_protection': True}
                        if reading:
                            reading.with_context(**reading_ctx).write(reading_vals)
                        else:
                            reading = self.env['utility.reading'].with_context(**reading_ctx).create(reading_vals)

                        rec.created_reading_id = reading.id

                    rec.state = 'imported'
                    rec.error_message = False

            except Exception as e:
                rec.state = 'error'
                rec.error_message = str(e)

    def action_queue_migration(self):
        """إنشاء دفعة تنفيذ وإضافة المحولات المحددة إلى قائمة الانتظار للميجريشن (Pure Queueing)."""
        if not self:
            raise UserError(_('لم يتم تحديد أي سجلات للميجريشن.'))

        locked_records = self.search([('id', 'in', self.ids)], order='id asc')
        try:
            self.env.cr.execute(
                "SELECT id FROM utility_migration_transformer WHERE id IN %s FOR UPDATE NOWAIT",
                (tuple(self.ids),)
            )
        except Exception:
            raise UserError(_('السجلات المحددة قيد التعديل أو المعالجة بواسطة مستخدم آخر حالياً.'))

        companies = locked_records.mapped('company_id')
        if len(companies) > 1:
            raise UserError(_('يجب أن تنتمي جميع السجلات المحددة إلى شركة واحدة فقط.'))

        invalid_records = locked_records.filtered(lambda r: r.state in ('queued', 'processing'))
        if invalid_records:
            raise UserError(_('توجد سجلات قيد المعالجة أو في الانتظار بالفعل (مثل: %s).') % invalid_records[0].name)

        company_id = companies[0].id if companies else self.env.company.id

        batch = self.env['utility.migration.batch'].create({
            'migration_type': 'transformer',
            'company_id': company_id,
            'state': 'queued',
        })

        locked_records.write({
            'state': 'queued',
            'last_batch_id': batch.id,
            'error_message': False,
        })

        return {
            'type': 'ir.actions.act_window',
            'name': _('دفعة التنفيذ (%s)') % batch.name,
            'res_model': 'utility.migration.batch',
            'view_mode': 'form',
            'res_id': batch.id,
            'target': 'current',
        }
