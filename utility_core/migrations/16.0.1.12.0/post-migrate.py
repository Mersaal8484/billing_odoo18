"""Preserve support discounts already configured on existing templates."""

import logging


_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    cr.execute(
        """
        UPDATE utility_contract_template template
           SET subsidy_enabled = TRUE
         WHERE template.discount_formula_id IS NOT NULL
            OR EXISTS (
                SELECT 1
                  FROM utility_contract_template_line line
                 WHERE line.template_id = template.id
                   AND line.meter_line_type = 'discount'
            )
        """
    )
    _logger.info('utility_core 16.0.1.12.0: preserved existing support-discount templates')
