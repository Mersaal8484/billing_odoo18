from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Restore Odoo's generated application permissions view after module upgrades."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['res.groups'].with_context(lang=None)._update_user_groups_view()
