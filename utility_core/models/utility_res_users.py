from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError


class ResUsers(models.Model):
    _inherit = 'res.users'

    utility_role_ids = fields.Many2many(
        'utility.user.role', 'res_users_utility_role_rel',
        'user_id', 'role_id',
        string='الأدوار الوظيفية',
        help='الأدوار الوظيفية التي تمنح المستخدم صلاحيات نظام إدارة الكهرباء. '
             'تُحوّل الأدوار تلقائياً إلى مجموعات Odoo الداخلية.')

    has_collection_role = fields.Boolean(
        string='لديه صلاحيات تحصيل',
        compute='_compute_has_collection_role',
        help='يظهر إعداد اليومية النقدية فقط للمستخدم ذي دور المتحصل أو أمين الصندوق.')

    # Kept as a compatibility field so databases upgrading from versions that
    # exposed it in res.users views can rebuild the generated groups view.
    # Installment-plan business logic has been removed from utility_billing.
    prevent_installment = fields.Boolean(
        string='منع إنشاء خطط التقسيط (حقل قديم)',
        default=False,
        help='حقل توافق قديم غير مستخدم في منطق النظام الحالي.',
    )
    collection_journal_id = fields.Many2one(
        'account.journal', string='اليومية النقدية للتحصيل',
        domain="[('type', '=', 'cash')]",
        help='اليومية الخاصة بالمحصل لتسجيل دفعات فواتير الكهرباء')

    collector_block_code = fields.Char(
        string="رمز دفتر التحصيل (Block Code)",
        help="الرمز أو الحرف المخصص لدفاتر تحصيل وقراءات هذا المستخدم"
    )
    legacy_user_code = fields.Char(
        string="كود المستخدم بالنظام القديم (Legacy User Code)",
        help="معرف المستخدم الخاص بالنظام المؤسسي السابق (PEC)"
    )
    assigned_region_ids = fields.Many2many(
        'utility.region', 'res_users_region_rel',
        'user_id', 'region_id',
        string="المناطق المخصصة (Assigned Regions)",
        domain="[('type', '=', 'region')]",
        help="المناطق الجغرافية والتشغيلية المصرح للمستخدم بإدارتها أو العمل فيها"
    )
    assigned_branch_ids = fields.Many2many(
        'utility.region', 'res_users_branch_rel',
        'user_id', 'branch_id',
        string="الفروع المخصصة صراحة (Explicit Branches)",
        domain="[('type', '=', 'area')]",
        help="الفروع المخصصة للمستخدم صراحة دون ترفيع كامل المنطقة الأم"
    )
    assigned_route_ids = fields.Many2many(
        'utility.route', 'res_users_route_rel',
        'user_id', 'route_id',
        string="خطوط السير المخصصة (Assigned Routes)",
        help="خطوط السير الجغرافية المصرح للمستخدم (متحصل أو قارئ) بالعمل فيها"
    )
    scope_mode = fields.Selection([
        ('restricted', 'تقييد بالنطاق التنظيمي'),
        ('global', 'وصول شامل على مستوى الشركة'),
    ], string='وضع النطاق التنظيمي', default='restricted', required=True,
       help='يحدد ما إذا كان المستخدم مقيداً بالتقسيمات الجغرافية المخصصة أو يملك وصولاً شاملاً.')

    @api.depends('utility_role_ids', 'utility_role_ids.code', 'groups_id')
    def _compute_has_collection_role(self):
        collector_group = self.env.ref(
            'utility_core.group_utility_collector', raise_if_not_found=False)
        cashier_group = self.env.ref(
            'utility_core.group_utility_cashier', raise_if_not_found=False)
        for user in self:
            role_codes = set(user.utility_role_ids.mapped('code'))
            has_role = bool({'collector', 'cashier'} & role_codes)
            if not has_role:
                has_role = bool(
                    (collector_group and collector_group in user.groups_id)
                    or (cashier_group and cashier_group in user.groups_id)
                )
            user.has_collection_role = has_role

    def action_create_collection_journal(self):
        """Create and assign a dedicated cash journal for the current user."""
        self.ensure_one()
        if not (self.env.user.has_group('utility_core.group_utility_admin')
                or self.env.user.has_group('base.group_account_manager')):
            raise AccessError(_(
                'إنشاء اليومية النقدية يستلزم صلاحية مدير النظام أو مدير المحاسبة.'
            ))
        if not self.has_collection_role:
            raise UserError(_(
                'لا يمكن إنشاء يومية نقدية إلا لمستخدم لديه دور متحصل ميداني أو أمين صندوق.'
            ))
        if self.collection_journal_id:
            return self._collection_journal_notification()

        company = self.company_id or self.env.company
        Journal = self.env['account.journal'].sudo()
        Account = self.env['account.account'].with_company(company).sudo()
        code_base = 'UC%03d' % self.id
        code = code_base[:5]
        suffix = 1
        while Journal.search([('company_id', '=', company.id), ('code', '=', code)], limit=1):
            code = ('UC%02d%d' % (self.id % 100, suffix))[:5]
            suffix += 1

        journal_name = _('يومية تحصيل - %s') % self.name
        cash_account = Account.search([
            ('company_ids', 'in', [company.id]),
            ('name', '=', _('حساب صندوق - %s') % self.name),
        ], limit=1)
        if not cash_account:
            account_code = '101%03d' % self.id
            account_code = account_code[-6:]
            account_suffix = 1
            while Account.search([
                ('company_ids', 'in', [company.id]),
                ('code', '=', account_code),
            ], limit=1):
                account_code = ('101%03d' % (self.id + account_suffix))[-6:]
                account_suffix += 1
            cash_account = Account.create({
                'name': _('حساب صندوق - %s') % self.name,
                'code': account_code,
                'account_type': 'asset_cash',
                'company_ids': [(6, 0, [company.id])],
            })

        journal = Journal.create({
            'name': journal_name,
            'code': code,
            'type': 'cash',
            'company_id': company.id,
            'default_account_id': cash_account.id,
        })
        self.sudo().collection_journal_id = journal.id
        return self._collection_journal_notification()

    def _collection_journal_notification(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('نجاح'),
                'message': _('تم ربط اليومية النقدية «%s» بالمستخدم.') % self.collection_journal_id.name,
                'type': 'success',
                'sticky': False,
            },
        }

    def _sync_utility_roles_to_groups(self):
        """Translate selected business roles to the underlying Odoo groups."""
        utility_category = self.env.ref(
            'utility_core.module_category_utility_erp', raise_if_not_found=False)
        admin_group = self.env.ref(
            'utility_core.group_utility_admin', raise_if_not_found=False)
        if not utility_category:
            return

        utility_groups = self.env['res.groups'].search([
            ('category_id', '=', utility_category.id),
        ])
        managed_groups = utility_groups - admin_group if admin_group else utility_groups
        for user in self:
            selected_groups = user.utility_role_ids.mapped('group_ids') & managed_groups
            preserved_admin = admin_group if admin_group and admin_group in user.groups_id else self.env['res.groups']
            desired_groups = (user.groups_id - managed_groups) | selected_groups | preserved_admin
            if desired_groups != user.groups_id:
                super(ResUsers, user.with_context(skip_utility_role_sync=True)).write({
                    'groups_id': [(6, 0, desired_groups.ids)],
                })

    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)
        if any(vals.get('utility_role_ids') for vals in vals_list):
            users._sync_utility_roles_to_groups()
        users._sync_utility_staff_links()
        return users

    def _sync_utility_staff_links(self):
        """Create or link a staff file for each new internal utility user.

        Existing unlinked staff records are reused only when the match is
        unambiguous: the partner is identical, or the name and at least one
        phone number match.  Otherwise a new staff file is created so a user
        is never attached to the wrong employee by an approximate name match.
        """
        Staff = self.env['utility.staff']
        for user in self.filtered(lambda record: record.active and not record.share):
            if Staff.search([('user_id', '=', user.id)], limit=1):
                continue

            partner = user.partner_id
            candidates = Staff.search([
                ('user_id', '=', False),
                ('company_id', '=', (user.company_id or self.env.company).id),
                ('name', '=', user.name),
            ])
            if partner:
                partner_matches = candidates.filtered(
                    lambda staff: staff.partner_id == partner
                )
                if len(partner_matches) == 1:
                    candidates = partner_matches

            user_phones = {
                value.strip()
                for value in (partner.phone, partner.mobile)
                if value and value.strip()
            }
            phone_matches = candidates.filtered(
                lambda staff: bool(user_phones.intersection({
                    value.strip()
                    for value in (staff.phone, staff.mobile)
                    if value and value.strip()
                }))
            )
            if len(phone_matches) == 1:
                candidates = phone_matches
            elif len(candidates) > 1 or (
                len(candidates) == 1 and not (
                    partner and candidates.partner_id == partner
                )
            ):
                candidates = Staff.browse()

            if len(candidates) == 1:
                candidates.write({'user_id': user.id})
                continue

            values = {
                'name': user.name,
                'user_id': user.id,
                'company_id': user.company_id.id or self.env.company.id,
                'phone': partner.phone or False,
                'mobile': partner.mobile or False,
                'region_id': user.assigned_region_ids[0].id if user.assigned_region_ids else False,
                'area_id': user.assigned_branch_ids[0].id if user.assigned_branch_ids else False,
            }
            if partner.utility_partner_type == 'employee':
                values['partner_id'] = partner.id
            Staff.create(values)

    def write(self, vals):
        scope_fields = {'scope_mode', 'assigned_region_ids', 'assigned_branch_ids'}
        if scope_fields.intersection(vals.keys()):
            if not (self.env.is_admin() or self.env.user.has_group('utility_core.group_utility_admin')):
                raise AccessError(_("فقط مدير النظام (Utility Admin) يحق له تعديل النطاق التنظيمي وصلاحيات الوصول الجغرافي للمستخدمين."))
        res = super().write(vals)
        if 'utility_role_ids' in vals and not self.env.context.get('skip_utility_role_sync'):
            self._sync_utility_roles_to_groups()
        return res

    def _is_global_utility_scope(self):
        """Returns True if the user has explicit GLOBAL scope or belongs to Utility Admin."""
        self.ensure_one()
        if self._is_admin() or self.has_group('utility_core.group_utility_admin'):
            return True
        return self.scope_mode == 'global'

    def _get_effective_region_ids(self):
        """Returns effective Region IDs (type='region'). Assigned Regions ONLY."""
        self.ensure_one()
        if self._is_global_utility_scope():
            return self.env['utility.region'].sudo().search([('type', '=', 'region')]).ids
        return self.assigned_region_ids.ids

    def _get_effective_branch_ids(self):
        """Returns effective Branch IDs (type='area').
        Effective Branches = Children of Assigned Regions + Explicit Branches.
        Explicit Branches do NOT escalate to add their parent Region to effective_regions.
        """
        self.ensure_one()
        if self._is_global_utility_scope():
            return self.env['utility.region'].sudo().search([('type', '=', 'area')]).ids

        region_ids = self.assigned_region_ids.ids
        child_branches = self.env['utility.region'].sudo().search([
            ('type', '=', 'area'),
            ('parent_id', 'in', region_ids)
        ]).ids if region_ids else []

        explicit_branches = self.assigned_branch_ids.ids
        return list(set(child_branches + explicit_branches))

    @api.model
    def check_pre_upgrade_scope_readiness(self):
        """Report restricted operational users who have no assigned regions or branches."""
        restricted_users = self.search([
            ('scope_mode', '=', 'restricted'),
            ('assigned_region_ids', '=', False),
            ('assigned_branch_ids', '=', False),
            ('share', '=', False)
        ])
        return {
            'unassigned_count': len(restricted_users),
            'unassigned_user_ids': restricted_users.ids,
            'unassigned_user_names': restricted_users.mapped('name'),
        }

    def check_record_scope(self, record):
        """Action-level authorization check validating whether a record falls inside the user's organizational scope."""
        self.ensure_one()
        if self._is_global_utility_scope():
            return True
        branch_ids = self._get_effective_branch_ids()
        region_ids = self._get_effective_region_ids()

        area = getattr(record, 'area_id', False) or getattr(getattr(record, 'customer_id', False), 'area_id', False) or getattr(getattr(record, 'account_id', False), 'area_id', False)
        region = getattr(record, 'region_id', False) or getattr(getattr(record, 'customer_id', False), 'region_id', False) or getattr(getattr(record, 'account_id', False), 'region_id', False)

        if area and area.id in branch_ids:
            return True
        if region and region.id in region_ids:
            return True
        raise AccessError(_("تعذر تحديد النطاق التنظيمي أو أن السجل يقع خارج نطاقك التنظيمي الجغرافي المخصص."))


class UtilityGroupsView(models.Model):
    """Keep electricity groups internal to the role selector."""

    _inherit = 'res.groups'

    @api.model
    def get_groups_by_application(self):
        groups_by_application = super().get_groups_by_application()
        utility_category = self.env.ref(
            'utility_core.module_category_utility_erp', raise_if_not_found=False)
        if not utility_category:
            return groups_by_application
        return [
            item for item in groups_by_application
            if item[0] != utility_category
        ]
