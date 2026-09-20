"""Set the global donor partner for existing companies."""

import logging


_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    cr.execute(
        """
        UPDATE res_company company
           SET utility_default_sponsor_id = partner.id
          FROM ir_model_data data
          JOIN res_partner partner ON partner.id = data.res_id
         WHERE data.module = 'utility_core'
           AND data.name = 'partner_sponsor_fund'
           AND data.model = 'res.partner'
           AND partner.utility_partner_type = 'donor'
           AND company.utility_default_sponsor_id IS NULL
        """
    )
    _logger.info('utility_core 16.0.1.11.0: configured the global default donor partner')
