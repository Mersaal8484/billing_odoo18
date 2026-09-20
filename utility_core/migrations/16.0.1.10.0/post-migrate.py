"""Classify existing partners for the utility partner-role domains."""

import logging


_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    # Preserve subscribers first; a subscriber contact may also be an internal
    # user's partner, but it must remain selectable for billing.
    cr.execute(
        """
        UPDATE res_partner
           SET utility_partner_type = 'subscriber',
               is_subscriber = TRUE
         WHERE is_subscriber = TRUE
            OR id IN (SELECT partner_id FROM utility_customer WHERE partner_id IS NOT NULL)
        """
    )
    cr.execute(
        """
        UPDATE res_partner
           SET utility_partner_type = 'donor',
               is_subscriber = FALSE
         WHERE utility_partner_type = 'other'
           AND id IN (
               SELECT sponsor_id
                 FROM utility_subscriber
                WHERE sponsor_id IS NOT NULL
           )
        """
    )
    cr.execute(
        """
        UPDATE res_partner
           SET utility_partner_type = 'employee',
               is_subscriber = FALSE
         WHERE utility_partner_type = 'other'
           AND id IN (
               SELECT partner_id FROM res_users
                WHERE partner_id IS NOT NULL AND active = TRUE AND share = FALSE
               UNION
               SELECT partner_id FROM utility_staff
                WHERE partner_id IS NOT NULL
           )
        """
    )
    _logger.info('utility_core 16.0.1.10.0: classified existing utility partners')
