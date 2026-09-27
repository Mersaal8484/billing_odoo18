"""
اختبارات الارتداد الأمني — مزامنة النطاق الجغرافي بين utility.staff وres.users

تُغطي المتطلبات في §4 من مواصفة الإصلاح:
1. موظف بمنطقته الصحيحة يرى سجلات منطقته فقط (لا رؤية شاملة بالخطأ).
2. موظف بمنطقة مختلفة لا يرى سجلات منطقة زميله إطلاقاً.
3. موظف global-scope يرى كل شيء.
4. موظف جديد يُنشأ من utility.staff يحصل على نطاقه تلقائياً بلا تدخل يدوي.
5. مستخدم restricted بلا موظف مرتبط يرى صفر سجلات (fail-closed).
"""
from odoo.tests.common import TransactionCase


class TestStaffScopeSync(TransactionCase):
    """اختبارات تزامن النطاق الجغرافي: utility.staff → res.users."""

    def _staff_for_user(self, user, values):
        """Use the auto-created staff file when the user already has one."""
        staff = self.env['utility.staff'].search([
            ('user_id', '=', user.id),
        ], limit=1)
        if staff:
            staff.write(values)
            return staff
        return self.env['utility.staff'].create(dict(values, user_id=user.id))

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = cls.env.company

        # ── المناطق الجغرافية ──────────────────────────────────────────────
        cls.region_a = cls.env['utility.region'].create({
            'name': 'منطقة صنعاء (اختبار تزامن)',
            'code': 'SYNC_REG_A',
            'type': 'region',
            'company_id': company.id,
        })
        cls.area_a1 = cls.env['utility.region'].create({
            'name': 'فرع التحرير (اختبار تزامن)',
            'code': 'SYNC_AREA_A1',
            'type': 'area',
            'parent_id': cls.region_a.id,
            'company_id': company.id,
        })
        cls.region_b = cls.env['utility.region'].create({
            'name': 'منطقة عدن (اختبار تزامن)',
            'code': 'SYNC_REG_B',
            'type': 'region',
            'company_id': company.id,
        })
        cls.area_b1 = cls.env['utility.region'].create({
            'name': 'فرع كريتر (اختبار تزامن)',
            'code': 'SYNC_AREA_B1',
            'type': 'area',
            'parent_id': cls.region_b.id,
            'company_id': company.id,
        })

        # ── مستخدمون تشغيليون (بلا نطاق مبدئياً) ─────────────────────────
        base_groups = [
            cls.env.ref('base.group_user').id,
            cls.env.ref('utility_core.group_utility_supervisor').id,
        ]
        cls.user_a = cls.env['res.users'].create({
            'name': 'مستخدم صنعاء — اختبار تزامن',
            'login': 'sync_test_user_a',
            'email': 'sync_a@utility.local',
            'scope_mode': 'restricted',
            'groups_id': [(6, 0, base_groups)],
        })
        cls.user_b = cls.env['res.users'].create({
            'name': 'مستخدم عدن — اختبار تزامن',
            'login': 'sync_test_user_b',
            'email': 'sync_b@utility.local',
            'scope_mode': 'restricted',
            'groups_id': [(6, 0, base_groups)],
        })
        cls.user_global = cls.env['res.users'].create({
            'name': 'مستخدم شامل — اختبار تزامن',
            'login': 'sync_test_user_global',
            'email': 'sync_global@utility.local',
            'scope_mode': 'global',
            'groups_id': [(6, 0, base_groups)],
        })

        # ── شركاء + عملاء ─────────────────────────────────────────────────
        partner_a = cls.env['res.partner'].create({
            'name': 'شريك صنعاء (تزامن)',
            'region_id': cls.region_a.id,
            'area_id': cls.area_a1.id,
            'company_id': company.id,
        })
        partner_b = cls.env['res.partner'].create({
            'name': 'شريك عدن (تزامن)',
            'region_id': cls.region_b.id,
            'area_id': cls.area_b1.id,
            'company_id': company.id,
        })
        cls.customer_a = cls.env['utility.customer'].create({
            'name': 'حساب صنعاء (تزامن)',
            'partner_id': partner_a.id,
            'customer_number': 'SYNC_CUST_A',
            'company_id': company.id,
        })
        cls.customer_b = cls.env['utility.customer'].create({
            'name': 'حساب عدن (تزامن)',
            'partner_id': partner_b.id,
            'customer_number': 'SYNC_CUST_B',
            'company_id': company.id,
        })

    # ── §4-1: إنشاء موظف يُزامن النطاق تلقائياً ──────────────────────────
    def test_01_staff_create_syncs_region_to_user(self):
        """موظف جديد بـ region_id + user_id يُملأ assigned_region_ids تلقائياً دون تدخل يدوي."""
        auto_staff = self.env['utility.staff'].search([
            ('user_id', '=', self.user_a.id),
        ], limit=1)
        self.assertTrue(auto_staff, "إنشاء المستخدم الداخلي يجب أن ينشئ ملف موظف مرتبطاً به")
        self.assertEqual(auto_staff.name, self.user_a.name)
        self.assertFalse(
            self.user_a.assigned_region_ids,
            "المستخدم يجب أن يبدأ بلا نطاق قبل إنشاء سجل الموظف",
        )

        self._staff_for_user(self.user_a, {
            'name': 'موظف صنعاء (اختبار إنشاء)',
            'region_id': self.region_a.id,
            'area_id': self.area_a1.id,
        })

        self.assertIn(
            self.region_a,
            self.user_a.assigned_region_ids,
            "بعد إنشاء utility.staff، يجب أن يُضاف region_a تلقائياً إلى assigned_region_ids للمستخدم",
        )
        self.assertIn(
            self.area_a1,
            self.user_a.assigned_branch_ids,
            "بعد إنشاء utility.staff، يجب أن يُضاف area_a1 تلقائياً إلى assigned_branch_ids للمستخدم",
        )

    # ── §4-2: تعديل region_id على الموظف يُحدِّث المستخدم ────────────────
    def test_02_staff_write_region_syncs_to_user(self):
        """تغيير region_id على موظف قائم يُحدِّث assigned_region_ids للمستخدم المرتبط فوراً."""
        staff = self._staff_for_user(self.user_b, {
            'name': 'موظف عدن (اختبار تعديل)',
            'region_id': self.region_b.id,
        })
        self.assertIn(self.region_b, self.user_b.assigned_region_ids)

        # نُغيّر المنطقة إلى A
        staff.write({'region_id': self.region_a.id})

        self.assertIn(
            self.region_a,
            self.user_b.assigned_region_ids,
            "بعد write(region_id=A) على الموظف، يجب أن يُحدَّث assigned_region_ids للمستخدم إلى A",
        )
        self.assertNotIn(
            self.region_b,
            self.user_b.assigned_region_ids,
            "المنطقة القديمة B يجب أن تُزال من assigned_region_ids عند الاستبدال",
        )

    # ── §4-3: عزل بين المناطق — موظف A لا يرى سجلات B ───────────────────
    def test_03_staff_scope_cross_region_isolation(self):
        """موظف منطقة A يرى عملاء A فقط، ولا يرى عملاء منطقة B إطلاقاً.
        يُغطي الاتجاهين: صحة الرؤية الإيجابية وصحة الحجب السلبية."""
        clean_user_a = self.env['res.users'].create({
            'name': 'مستخدم صنعاء 2 — عزل',
            'login': 'isolation_test_user_a',
            'email': 'isolation_a@utility.local',
            'scope_mode': 'restricted',
            'groups_id': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('utility_core.group_utility_supervisor').id,
            ])],
        })
        self._staff_for_user(clean_user_a, {
            'name': 'موظف صنعاء — عزل',
            'region_id': self.region_a.id,
        })

        customers_seen = self.env['utility.customer'].with_user(clean_user_a).search([])

        self.assertIn(
            self.customer_a,
            customers_seen,
            "موظف منطقة A يجب أن يرى عميل A",
        )
        self.assertNotIn(
            self.customer_b,
            customers_seen,
            "موظف منطقة A يجب ألا يرى عميل B — خرق عزل جغرافي خطير",
        )

    # ── §4-4: مستخدم global يرى كل شيء كما هو مُصمَّم ───────────────────
    def test_04_global_scope_user_sees_all(self):
        """مستخدم بـ scope_mode='global' يرى جميع العملاء بغض النظر عن المناطق."""
        customers_seen = self.env['utility.customer'].with_user(self.user_global).search([])

        self.assertIn(
            self.customer_a,
            customers_seen,
            "مستخدم global يجب أن يرى عميل A",
        )
        self.assertIn(
            self.customer_b,
            customers_seen,
            "مستخدم global يجب أن يرى عميل B",
        )

    # ── §4-5: ضمان عدم تخفيف أمني — مستخدم بلا موظف يرى صفر ────────────
    def test_05_restricted_user_without_staff_sees_nothing(self):
        """مستخدم restricted بلا موظف مرتبط (= بلا assigned_region_ids) يرى صفر عملاء.
        يضمن أن المزامنة لا تمنح وصولاً غير مستحق (fail-closed)."""
        orphan_user = self.env['res.users'].create({
            'name': 'مستخدم بلا موظف — اختبار حجب',
            'login': 'orphan_test_user',
            'email': 'orphan@utility.local',
            'scope_mode': 'restricted',
            'groups_id': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('utility_core.group_utility_supervisor').id,
            ])],
        })

        customers_seen = self.env['utility.customer'].with_user(orphan_user).search([])

        self.assertEqual(
            len(customers_seen),
            0,
            "مستخدم restricted بلا نطاق يجب أن يرى صفر سجلات (fail-closed)",
        )
