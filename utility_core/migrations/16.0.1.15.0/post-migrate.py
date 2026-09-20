"""Apply the approved default service charge to the seeded contract template."""

import logging


_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    cr.execute(
        """
        UPDATE utility_contract_template template
           SET service_charge = 500
          FROM ir_model_data data
         WHERE data.module = 'utility_core'
           AND data.name = 'utility_default_contract_template'
           AND data.model = 'utility.contract.template'
           AND data.res_id = template.id
        """
    )
    cr.execute(
        """
        UPDATE utility_contract_template_line line
           SET specific_price = 500
          FROM ir_model_data data
         WHERE data.module = 'utility_core'
           AND data.name = 'utility_default_contract_template_service_line'
           AND data.model = 'utility.contract.template.line'
           AND data.res_id = line.id
        """
    )
    _logger.info('utility_core 16.0.1.15.0: default service charge set to 500')
