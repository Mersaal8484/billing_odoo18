"""Backfill the role selector from existing utility group memberships."""

import logging

from odoo import SUPERUSER_ID, api


_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    env = api.Environment(cr, SUPERUSER_ID, {})
    users = env['res.users'].search([])
    roles = env['utility.user.role'].search([])
    rows = []
    for user in users:
        for role in roles:
            if role.group_ids & user.groups_id:
                rows.append((user.id, role.id))

    if rows:
        cr.executemany(
            """
            INSERT INTO res_users_utility_role_rel (user_id, role_id)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
            """,
            rows,
        )

    # Recreate Odoo's categorized permissions view after the module upgrade.
    # During loading Odoo may leave base.user_groups_view as a placeholder.
    env['res.groups'].with_context(lang=None)._update_user_groups_view()
    _logger.info('utility_core 16.0.1.19.0: backfilled %s user-role links', len(rows))
