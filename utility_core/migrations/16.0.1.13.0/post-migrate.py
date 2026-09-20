"""Apply the approved default contract-template workflow settings."""

import logging


_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    cr.execute(
        """
        UPDATE utility_contract_template template
           SET sale_autoconfirm = TRUE,
               create_invoice_automatically = TRUE,
               validate_invoice_automatically = FALSE,
               journal_id = COALESCE(template.journal_id, company.sales_journal_id)
          FROM res_company company
         WHERE template.company_id = company.id
        """
    )
    _logger.info('utility_core 16.0.1.13.0: applied default contract workflow settings')
