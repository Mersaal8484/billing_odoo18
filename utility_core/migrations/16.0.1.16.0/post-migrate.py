"""Synchronize the seeded contract template with the current live setup."""

import logging


_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    cr.execute(
        """
        UPDATE utility_contract_template template
           SET pricing_mode = 'tier', service_charge = 500
          FROM ir_model_data data
         WHERE data.module = 'utility_core'
           AND data.name = 'utility_default_contract_template'
           AND data.model = 'utility.contract.template'
           AND data.res_id = template.id
        """
    )

    # The old live setup created these rows without external IDs. Remove only
    # those untracked rows after the data XML has created the canonical rows.
    cr.execute(
        """
        DELETE FROM utility_contract_template_line line
         WHERE line.template_id = (
                   SELECT data.res_id
                     FROM ir_model_data data
                    WHERE data.module = 'utility_core'
                      AND data.name = 'utility_default_contract_template'
                      AND data.model = 'utility.contract.template'
               )
           AND line.meter_line_type IN ('mu_allim', 'cleaning', 'municipality')
           AND NOT EXISTS (
                   SELECT 1
                     FROM ir_model_data data
                    WHERE data.model = 'utility.contract.template.line'
                      AND data.res_id = line.id
               )
        """
    )
    cr.execute(
        """
        DELETE FROM utility_contract_template_block block
         WHERE block.template_id = (
                   SELECT data.res_id
                     FROM ir_model_data data
                    WHERE data.module = 'utility_core'
                      AND data.name = 'utility_default_contract_template'
                      AND data.model = 'utility.contract.template'
               )
           AND NOT EXISTS (
                   SELECT 1
                     FROM ir_model_data data
                    WHERE data.model = 'utility.contract.template.block'
                      AND data.res_id = block.id
               )
        """
    )
    _logger.info('utility_core 16.0.1.16.0: synchronized default contract template data')
