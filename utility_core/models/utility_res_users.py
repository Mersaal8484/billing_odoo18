from odoo import api, fields, models, _
from odoo.exceptions import AccessError


class ResUsers(models.Model):
    _inherit = 'res.users'

    utility_role_ids = fields.Many2many(
        'utility.user.role', 'res_users_utility_role_rel',
        'user_id', 'role_id',
        string='الأدوار الوظيفية',
        help='الأدوار الوظيفية التي تمنح المستخدم صلاحيات نظام إدارة الكهرباء. '
             'تُحوّل الأدوار تلقائياً إلى مجموعات Odoo الداخلية.')

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
        return users

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
