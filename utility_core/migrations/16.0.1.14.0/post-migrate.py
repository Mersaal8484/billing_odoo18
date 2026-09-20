"""Configure the global YER pricelist and preserve the company currency."""

import logging


_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    cr.execute(
        """
        UPDATE res_company company
           SET utility_default_pricelist_id = data.res_id
          FROM ir_model_data data
         WHERE data.module = 'utility_core'
           AND data.name = 'utility_default_pricelist_yer'
           AND data.model = 'product.pricelist'
           AND company.utility_default_pricelist_id IS NULL
        """
    )
    cr.execute(
        """
        UPDATE res_company company
           SET currency_id = currency.id
          FROM res_currency currency
         WHERE currency.name = 'YER'
           AND NOT EXISTS (
               SELECT 1 FROM account_move_line line
                WHERE line.company_id = company.id
           )
        """
    )
    _logger.info('utility_core 16.0.1.14.0: configured the global YER pricelist and company currency')
