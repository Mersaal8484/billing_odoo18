from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class UtilityMigrationCustomer(models.Model):
    _name = 'utility.migration.customer'
    _description = 'تهيئة بيانات العملاء (النظام القديم)'
    _order = 'id asc'

    company_id = fields.Many2one(
        'res.company', string='الشركة', required=True,
        default=lambda self: self.env.company, index=True)

    name = fields.Char('الاسم', required=True)
    owner_reference = fields.Char(
        'مرجع المالك القديم', index=True,
        help='بيانات تاريخية للاستيراد فقط؛ لا تستخدم لمطابقة أو دمج حسابات.')
    mobile = fields.Char('الموبايل')
    customer_number = fields.Char('رقم المشترك', required=True)
    national_id = fields.Char('الرقم الوطني')
    current_balance = fields.Float('الرصيد الحالي (الافتتاحي)')
    previous_balance = fields.Char('الرصيد السابق (الخط الساخن)')

    meter_number = fields.Char('رقم العداد')
    last_reading = fields.Float('اخر قراءة مسجلة', digits=(12, 3))
    has_last_reading = fields.Boolean('تم إدخال آخر قراءة مسجلة')

    char_code = fields.Char('رقم الحرف')
    subscriber_no = fields.Char('الرقم الجديد')
    meter_reading = fields.Integer('قراءة العداد في النظام')
    opening_reading = fields.Float('قراءة الافتتاح', digits=(12, 3))
    has_opening_reading = fields.Boolean('تم إدخال قراءة افتتاح')

    legacy_region = fields.Char('رمز المنطقة')
    legacy_area = fields.Char('رمز الفرع')
    legacy_category = fields.Char('رمز الفئة')
    legacy_subscriber_type = fields.Char('رمز نوع المشترك')
    legacy_contract = fields.Char('رمز قالب العقد')

    region_id = fields.Many2one('utility.region', string='المنطقة (Odoo)', domain="[('type', '=', 'region')]")
    area_id = fields.Many2one('utility.region', string='الفرع (Odoo)', domain="[('type', '=', 'area')]")
    category_id = fields.Many2one('utility.subscriber.category', string='الفئة (Odoo)')
    subscriber_type_id = fields.Many2one('utility.subscriber', string='نوع المشترك (Odoo)')
    contract_template_id = fields.Many2one('utility.contract.template', string="قالب العقد (النظام)")

    phase = fields.Selection([
        ('single', '1 Phase'),
        ('three', '3 Phase')
    ], string='الطور')
    is_private_transformer = fields.Boolean(string='هل المحول خاص؟')

    is_active = fields.Boolean('هل فعال؟', default=True)

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

    created_partner_id = fields.Many2one('res.partner', 'جهة الاتصال المنشأة', readonly=True, copy=False)
    created_customer_id = fields.Many2one('utility.customer', 'حساب العميل المنشأ', readonly=True, copy=False)
    created_meter_id = fields.Many2one('utility.meter', 'العداد المنشأ', readonly=True, copy=False)
    created_reading_id = fields.Many2one('utility.reading', 'القراءة الافتتاحية المنشأة', readonly=True, copy=False)
    opening_move_id = fields.Many2one('account.move', 'قيد الرصيد الافتتاحي', readonly=True, copy=False)
    balance_repair_move_id = fields.Many2one(
        'account.move', 'قيد تصحيح توزيع الأرصدة', readonly=True, copy=False)
    balance_allocation_repaired = fields.Boolean(
        'تم تصحيح توزيع الأرصدة', readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'last_reading' in vals and vals['last_reading'] is not False and vals['last_reading'] is not None:
                vals['has_last_reading'] = True
            if 'opening_reading' in vals and vals['opening_reading'] is not False and vals['opening_reading'] is not None:
                vals['has_opening_reading'] = True
        return super().create(vals_list)

    def write(self, vals):
        if 'last_reading' in vals and vals['last_reading'] is not False and vals['last_reading'] is not None:
            vals['has_last_reading'] = True
        if 'opening_reading' in vals and vals['opening_reading'] is not False and vals['opening_reading'] is not None:
            vals['has_opening_reading'] = True
        return super().write(vals)

    def _get_staging_opening_reading_value(self):
        """إرجاع قيمة قراءة الافتتاح بدقة (تميز بين عدم الإدخال وقيمة الصفر)."""
        self.ensure_one()
        if self.has_last_reading:
            return float(self.last_reading)
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
            'url': '/utility_core/static/src/Migration_Template.xlsx',
            'target': 'new',
        }

    @api.model
    def action_open_import_wizard(self):
        return self.env.ref('utility_core.action_utility_migration_import_wizard').read()[0]

    @api.model
    def action_open_mapping(self):
        return self.env.ref('utility_core.action_utility_migration_mapping').read()[0]

    def action_open_customer(self):
        self.ensure_one()
        if not self.created_customer_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'name': _('حساب المشترك'),
            'res_model': 'utility.customer',
            'view_mode': 'form',
            'res_id': self.created_customer_id.id,
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

            if rec.legacy_category:
                val = cache.get(('category', rec.legacy_category.strip()))
                if val:
                    rec.category_id = val.id
                else:
                    missing.append(f"MISSING_CATEGORY_MAPPING: لم يتم العثور على ترميز الفئة ({rec.legacy_category})")

            if rec.legacy_subscriber_type:
                val = cache.get(('subscriber', rec.legacy_subscriber_type.strip()))
                if val:
                    rec.subscriber_type_id = val.id
                else:
                    missing.append(f"MISSING_SUBSCRIBER_MAPPING: لم يتم العثور على ترميز نوع المشترك ({rec.legacy_subscriber_type})")

            if rec.legacy_contract:
                val = cache.get(('contract', rec.legacy_contract.strip()))
                if val:
                    rec.contract_template_id = val.id
                else:
                    missing.append(f"MISSING_CONTRACT_MAPPING: لم يتم العثور على ترميز قالب العقد ({rec.legacy_contract})")

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
    # Private helpers
    # -------------------------------------------------------------------------

    def _resolve_meter_model(self):
        """تحديد موديل العداد بأمان وفقًا للمعمارية الحالية (الطور readonly projection من الموديل)."""
        self.ensure_one()
        if not self.phase:
            raise ValidationError(_('MISSING_METER_PHASE: يجب تحديد طور العداد للعميل %s.') % self.customer_number)

        company = self.company_id or self.env.company
        model = (
            company.legacy_single_phase_meter_model_id
            if self.phase == 'single'
            else company.legacy_three_phase_meter_model_id
        )
        if not model:
            code = (
                'LEGACY_SINGLE_PHASE_METER_MODEL_NOT_CONFIGURED'
                if self.phase == 'single'
                else 'LEGACY_THREE_PHASE_METER_MODEL_NOT_CONFIGURED'
            )
            raise ValidationError(_('%s: لم يتم إعداد موديل العداد الافتراضي للعميل %s والعداد %s (الطور: %s، صف Excel: %s).') % (
                code, self.customer_number, self.meter_number,
                self.phase, self.source_row_number or '?'))
        if model.phase != self.phase:
            raise ValidationError(_('LEGACY_DEFAULT_METER_MODEL_PHASE_MISMATCH: موديل العداد الافتراضي لا يطابق الطور %s.') % self.phase)
        return model

    def _get_previous_balance(self):
        """Return the legacy previous balance as the postpaid receivable amount."""
        self.ensure_one()
        try:
            value = str(self.previous_balance or '').strip()
            return float(value.replace('٬', '').replace(',', '').replace('٫', '.')) if value else 0.0
        except (ValueError, TypeError):
            return 0.0

    def _get_pec_credit(self):
        """Compatibility alias retained for integrations using the former helper name."""
        return self._get_previous_balance()

    def _build_customer_partner_vals(self):
        """Build the single dedicated partner for this electricity account."""
        self.ensure_one()
        vals = {
            'name': self.name,
            'mobile': self.mobile,
            'national_id': self.national_id,
            'region_id': self.region_id.id if self.region_id else False,
            'area_id': self.area_id.id if self.area_id else False,
            'subscriber_status': 'old',
            'is_subscriber': True,
            'subscriber_active_status': 'active' if self.is_active else 'inactive',
            'char_code': self.char_code,
            'subscriber_no': self.subscriber_no or self.customer_number,
            'meter_reading': self.meter_reading if self.meter_reading is not False else (self.last_reading or 0),
            'opening_reading': self.opening_reading if self.has_opening_reading else (self.last_reading or 0),
            'meter_number': self.meter_number,
            # This is an informational opening balance, not an accounts receivable entry.
            'open_balance': self.current_balance,
        }
        if self.subscriber_type_id:
            vals['subscriber_id'] = self.subscriber_type_id.id
        return vals

    def _build_partner_vals(self):
        """Backward-compatible name for the canonical account-partner builder."""
        return self._build_customer_partner_vals()

    def _get_or_create_private_transformer(self, partner):
        """إنشاء أو ربط محول خاص للمشترك محصور بالشركة."""
        self.ensure_one()
        if not self.is_private_transformer:
            return False

        company_id = self.company_id.id or self.env.company.id
        code = f"PRV-{self.customer_number or self.national_id or partner.id}"
        name = f"محول خاص - {partner.name}"

        transformer = self.env['utility.transformer'].search([
            ('company_id', '=', company_id),
            ('is_private', '=', True),
            ('code', '=', code),
        ], limit=1)

        area_or_region = self.area_id or self.region_id

        if not transformer:
            transformer_vals = {
                'name': name,
                'code': code,
                'company_id': company_id,
                'area_id': area_or_region.id if area_or_region and area_or_region.type == 'area' else False,
                'zone_region_id': area_or_region.id if area_or_region and area_or_region.type == 'zone' else False,
                'is_private': True,
            }
            if hasattr(self.env['utility.transformer'], 'phase'):
                transformer_vals['phase'] = self.phase or 'single'
            transformer = self.env['utility.transformer'].create(transformer_vals)
        return transformer

    def _upsert_partner(self):
        """Create or update dedicated partner idempotently using created_partner_id."""
        self.ensure_one()
        vals = self._build_partner_vals()
        partner = self.created_partner_id
        if partner:
            partner.write(vals)
        else:
            partner = self.env['res.partner'].create(vals)
        return partner

    def _get_balance_accounting_setup(self, partner):
        """Resolve the journal and accounts used for migrated postpaid debt."""
        self.ensure_one()
        company_id = self.company_id.id or self.env.company.id
        company = self.env['res.company'].browse(company_id)
        journal = (
            company.opening_journal_id
            or self.env['account.journal'].search([('code', '=', 'OPEN'), ('company_id', '=', company_id)], limit=1)
            or self.env['account.journal'].search([('type', '=', 'general'), ('company_id', '=', company_id)], limit=1)
        )
        account_receivable = partner.with_company(company_id).property_account_receivable_id
        if not account_receivable or account_receivable.company_id.id not in (company_id, False):
            account_receivable = (
                self.env['account.account'].search([
                    ('account_type', '=', 'asset_receivable'),
                    ('company_id', '=', company_id)
                ], limit=1)
                or self.env['account.account'].search([
                    ('code', '=like', '12%'),
                    ('company_id', '=', company_id)
                ], limit=1)
            )
            if not account_receivable:
                account_receivable = self.env['account.account'].create({
                    'name': 'حساب العملاء والذمم المدينة',
                    'code': '120000',
                    'account_type': 'asset_receivable',
                    'company_id': company_id,
                    'reconcile': True,
                })
            partner.sudo().with_company(company_id).write({'property_account_receivable_id': account_receivable.id})

        account_suspense = (
            company.opening_clearing_account_id
            or company.account_journal_suspense_account_id
            or self.env['account.account'].search([
                ('account_type', 'in', ('equity', 'equity_unaffected')),
                ('company_id', '=', company_id)
            ], limit=1)
            or self.env['account.account'].search([
                ('code', '=like', '3%'),
                ('company_id', '=', company_id)
            ], limit=1)
        )
        if not account_suspense:
            account_suspense = self.env['account.account'].create({
                'name': 'حساب الأرصدة الافتتاحية (حقوق ملكية)',
                'code': '300000',
                'account_type': 'equity',
                'company_id': company_id,
            })
        if not journal:
            raise UserError(_('لا توجد يومية عمليات (General Journal) معرّفة في النظام للشركة المحددة.'))

        return company, journal, account_receivable, account_suspense

    def _create_opening_balance_entry(self, partner, customer=None):
        """Create a receivable entry only for the legacy previous/postpaid balance."""
        self.ensure_one()
        deferred_balance = self._get_previous_balance()
        if self.opening_move_id or not deferred_balance:
            return

        company, journal, account_receivable, account_suspense = self._get_balance_accounting_setup(partner)
        company_id = company.id

        line_ids = []
        if deferred_balance > 0:
            line_ids.append((0, 0, {
                'name': 'مديونية آجل مرحّلة - %s' % self.name,
                'partner_id': partner.id,
                'account_id': account_receivable.id,
                'debit': deferred_balance,
                'credit': 0.0,
            }))
            line_ids.append((0, 0, {
                'name': 'مديونية آجل مرحّلة - %s' % self.name,
                'account_id': account_suspense.id,
                'debit': 0.0,
                'credit': deferred_balance,
            }))
        elif deferred_balance < 0:
            credit_amount = abs(deferred_balance)
            line_ids.append((0, 0, {
                'name': 'مديونية آجل دائنة مرحّلة - %s' % self.name,
                'account_id': account_suspense.id,
                'debit': credit_amount,
                'credit': 0.0,
            }))
            line_ids.append((0, 0, {
                'name': 'مديونية آجل دائنة مرحّلة - %s' % self.name,
                'partner_id': partner.id,
                'account_id': account_receivable.id,
                'debit': 0.0,
                'credit': credit_amount,
            }))

        if line_ids:
            move_vals = {
                'move_type': 'entry',
                'journal_id': journal.id,
                'company_id': company_id,
                'partner_id': partner.id if customer else False,
                'date': fields.Date.today(),
                'ref': 'مديونية آجل مرحّلة - %s' % self.customer_number,
                'line_ids': line_ids,
            }
            if customer and 'utility_customer_id' in self.env['account.move']._fields:
                move_vals['utility_customer_id'] = customer.id
            move = self.env['account.move'].create(move_vals)
            move.action_post()
            self.opening_move_id = move.id
            if customer:
                customer.opening_move_id = move.id
            partner.write({
                'is_credit_raised': True,
                'credit_raise_date': fields.Date.today(),
            })

    def _get_opening_receivable_balance(self):
        """Return the receivable balance actually posted by the original migration entry."""
        self.ensure_one()
        if not self.opening_move_id:
            return 0.0
        receivable_lines = self.opening_move_id.line_ids.filtered(
            lambda line: line.account_id.account_type == 'asset_receivable'
        )
        return sum(receivable_lines.mapped('balance'))

    def _create_balance_repair_entry(self, partner, customer, difference):
        """Post one auditable adjustment from the old migration allocation to the correct debt."""
        self.ensure_one()
        company, journal, account_receivable, account_suspense = self._get_balance_accounting_setup(partner)
        if company.currency_id.is_zero(difference):
            return False

        label = 'تصحيح توزيع أرصدة الميجريشن - %s' % self.customer_number
        if difference > 0:
            receivable_vals = {'debit': difference, 'credit': 0.0}
            suspense_vals = {'debit': 0.0, 'credit': difference}
        else:
            amount = abs(difference)
            receivable_vals = {'debit': 0.0, 'credit': amount}
            suspense_vals = {'debit': amount, 'credit': 0.0}

        move_vals = {
            'move_type': 'entry',
            'journal_id': journal.id,
            'company_id': company.id,
            'partner_id': partner.id,
            'date': fields.Date.today(),
            'ref': label,
            'line_ids': [
                (0, 0, dict({
                    'name': label,
                    'partner_id': partner.id,
                    'account_id': account_receivable.id,
                }, **receivable_vals)),
                (0, 0, dict({
                    'name': label,
                    'account_id': account_suspense.id,
                }, **suspense_vals)),
            ],
        }
        if 'utility_customer_id' in self.env['account.move']._fields:
            move_vals['utility_customer_id'] = customer.id
        move = self.env['account.move'].create(move_vals)
        move.action_post()
        return move

    def action_repair_balance_allocation(self):
        """Correct imported records without deleting their posted migration journal entries."""
        invalid_records = self.filtered(
            lambda rec: rec.state != 'imported' or not rec.created_partner_id or not rec.created_customer_id
        )
        if invalid_records:
            raise UserError(_(
                'يمكن تصحيح السجلات التي تم رفعها فقط ولها حساب مشترك مرتبط. مثال: %s'
            ) % invalid_records[0].name)

        for rec in self:
            if rec.balance_allocation_repaired:
                continue

            partner = rec.created_partner_id
            customer = rec.created_customer_id
            # The workbook's current/opening balance belongs in the dedicated opening field.
            partner.write({'open_balance': rec.current_balance})

            if rec.opening_move_id:
                actual_deferred_balance = rec._get_opening_receivable_balance()
                difference = rec._get_previous_balance() - actual_deferred_balance
                repair_move = rec._create_balance_repair_entry(partner, customer, difference)
                if repair_move:
                    rec.balance_repair_move_id = repair_move.id
            else:
                rec._create_opening_balance_entry(partner, customer)

            rec.balance_allocation_repaired = True
        return True

    def _create_customer_account(self, partner):
        """إنشاء حساب المشترك والعداد والقراءة الافتتاحية بإلزامية حصر الشركة والتحقق من الموديل."""
        self.ensure_one()

        if not self.contract_template_id:
            raise UserError(_('يجب تحديد قالب العقد قبل تفعيل العميل "%s".') % self.name)
        if not self.meter_number:
            raise UserError(_('يجب إدخال رقم العداد قبل تفعيل العميل "%s".') % self.name)
        if not self.category_id:
            raise UserError(_('يجب تحديد فئة المشترك للعميل "%s".') % self.name)
        if not self.subscriber_type_id:
            raise UserError(_('يجب تحديد نوع المشترك للعميل "%s".') % self.name)

        company_id = self.company_id.id or self.env.company.id

        # 0. Private Transformer
        transformer = self._get_or_create_private_transformer(partner)

        # 1. Create or update utility.customer (Check created_customer_id first)
        customer = self.created_customer_id
        if not customer:
            customers = self.env['utility.customer'].search([
                ('customer_number', '=', self.customer_number),
                ('company_id', '=', company_id)
            ])
            if len(customers) > 1:
                raise ValidationError(_('AMBIGUOUS_CUSTOMER_IDENTITY: تكرر رقم المشترك (%s) داخل الشركة.') % self.customer_number)
            customer = customers[:1]

        customer_vals = {
            'customer_number': self.customer_number,
            'partner_id': partner.id,
            'category_id': self.category_id.id,
            'subscriber_id': self.subscriber_type_id.id,
            'state': 'draft',
            'contract_template_id': self.contract_template_id.id,
            'company_id': company_id,
        }
        if transformer:
            customer_vals['transformer_id'] = transformer.id
            if transformer.feeder_id:
                customer_vals['cell_id'] = transformer.feeder_id.id

        if customer:
            if customer.partner_id != partner:
                raise UserError(_('الحساب %s مرتبط بشريك مخصص مختلف؛ لم يتم تغيير تاريخه المحاسبي.') % customer.customer_number)
            customer_vals.pop('partner_id', None)
            customer.with_context(
                skip_opening_entry=True,
                allow_utility_account_partner_change=True,
            ).write(customer_vals)
        else:
            customer = self.env['utility.customer'].with_context(skip_opening_entry=True).create(customer_vals)

        self.created_customer_id = customer.id
        account_partner = customer.partner_id
        account_partner.write(self._build_customer_partner_vals())

        # 2. Create / link meter (NO direct write to readonly meter.phase or related transformer_id/feeder_id)
        model = self._resolve_meter_model()
        status_active = self.env['utility.meter.status'].search([('code', '=', 'ACTIVE')], limit=1)

        meter_vals = {
            'meter_number': self.meter_number,
            'operational_number': self.meter_number,
            'connection_type': 'subscriber',
            'customer_id': customer.id,
            'company_id': company_id,
            'active': True,
        }
        if model:
            meter_vals['model_id'] = model.id
        if status_active:
            meter_vals['status_id'] = status_active.id

        meter = self.created_meter_id
        if not meter:
            meters = self.env['utility.meter'].search([
                ('company_id', '=', company_id),
                ('meter_number', '=', self.meter_number)
            ])
            if len(meters) > 1:
                raise ValidationError(_('AMBIGUOUS_METER_IDENTITY: تكرر رقم العداد (%s) داخل الشركة.') % self.meter_number)
            meter = meters[:1]

        if not meter:
            meter = self.env['utility.meter'].create(meter_vals)
        else:
            meter.write(meter_vals)

        self.created_meter_id = meter.id
        customer.with_context(lifecycle_operation=True).write({'meter_id': meter.id})

        if transformer and meter:
            transformer.write({'coupling_meter_id': meter.id})

        # 3. Create opening reading (Zero reading is VALID!)
        opening_val = self._get_staging_opening_reading_value()
        if opening_val is not None:
            existing_reading = self.created_reading_id
            if not existing_reading:
                existing_reading = self.env['utility.reading'].search([
                    ('meter_id', '=', meter.id),
                    ('reading_purpose', '=', 'opening')
                ], limit=1)

            reading_vals = {
                'meter_id': meter.id,
                'reading_value': opening_val,
                'reading_date': fields.Datetime.now(),
                'reading_type': 'manual',
                'reading_purpose': 'opening',
                'is_initial_reading': True,
                'reading_category': 'customer',
                'reading_source': 'legacy_migration',
                'state': 'billed',
            }

            if not existing_reading:
                existing_reading = self.env['utility.reading'].create(reading_vals)
            else:
                existing_reading.write(reading_vals)

            self.created_reading_id = existing_reading.id

        # 4. Create opening balance journal entry
        customer.action_activate()
        self._create_opening_balance_entry(account_partner, customer)

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
                    partner = rec._upsert_partner()
                    rec.created_partner_id = partner.id

                    if rec.is_active:
                        rec.with_context(skip_service_activation_charge=True)._create_customer_account(partner)

                    rec.state = 'imported'
                    rec.error_message = False

            except Exception as e:
                rec.state = 'error'
                rec.error_message = str(e)

    def action_activate_inactive(self):
        """تفعيل عميل غير فعال (Server Action / Button)."""
        for rec in self:
            if rec.state != 'imported':
                raise UserError(_(
                    'يجب أن يكون السجل في حالة "تم الرفع" قبل التفعيل.\nالعميل: %s'
                ) % rec.name)
            if rec.created_customer_id:
                raise UserError(_(
                    'العميل "%s" لديه حساب مشترك بالفعل (رقم: %s).\nلا يمكن إنشاء حساب مكرر.'
                ) % (rec.name, rec.created_customer_id.customer_number))
            if not rec.created_partner_id:
                raise UserError(_(
                    'لا توجد جهة اتصال مرتبطة بالعميل "%s".\nيرجى إعادة رفع البيانات أولاً.'
                ) % rec.name)

            partner = rec.created_partner_id
            partner.write(rec._build_customer_partner_vals())
            rec._create_customer_account(partner)
            rec.is_active = True
            partner.subscriber_active_status = 'active'

    def action_queue_migration(self):
        """إنشاء دفعة تنفيذ وإضافة السجلات المحددة إلى قائمة الانتظار للميجريشن (Pure Queueing)."""
        if not self:
            raise UserError(_('لم يتم تحديد أي سجلات للميجريشن.'))

        locked_records = self.search([('id', 'in', self.ids)], order='id asc')
        try:
            self.env.cr.execute(
                "SELECT id FROM utility_migration_customer WHERE id IN %s FOR UPDATE NOWAIT",
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
            'migration_type': 'customer',
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
