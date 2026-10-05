from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install', 'utility_mobile_roles')
class TestMobileRoleFlags(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.internal_group = cls.env.ref('base.group_user')
        cls.reader_role = cls.env.ref('utility_core.role_meter_reader')
        cls.collector_group = cls.env.ref('utility_core.group_utility_collector')

    def _create_user(self, suffix, **values):
        values.setdefault('name', 'Mobile Role %s' % suffix)
        values.setdefault('login', 'mobile_role_%s@example.test' % suffix)
        values.setdefault('groups_id', [(6, 0, [self.internal_group.id])])
        return self.env['res.users'].with_context(no_reset_password=True).create(values)

    def test_explicit_role_code_grants_reader_capability(self):
        user = self._create_user(
            'reader', utility_role_ids=[(6, 0, [self.reader_role.id])])

        self.assertTrue(user._get_mobile_role_flags()['is_meter_reader'])

    def test_explicit_group_grants_collector_capability(self):
        user = self._create_user(
            'collector',
            groups_id=[(6, 0, [self.internal_group.id, self.collector_group.id])],
        )

        self.assertTrue(user._get_mobile_role_flags()['is_collector'])

    def test_unassigned_user_receives_no_default_mobile_role(self):
        user = self._create_user('unassigned')

        self.assertFalse(any(user._get_mobile_role_flags().values()))
