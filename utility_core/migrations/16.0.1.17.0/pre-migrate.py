"""Map legacy default-template rows before the canonical data XML is loaded."""

import logging


_logger = logging.getLogger(__name__)


def _map_existing_row(cr, model, table, xml_name, where_sql, params):
    cr.execute(
        f"""
        INSERT INTO ir_model_data (module, name, model, res_id, noupdate)
        SELECT 'utility_core', %s, %s, row.id, TRUE
          FROM {table} row
         WHERE {where_sql}
           AND NOT EXISTS (
               SELECT 1
                 FROM ir_model_data data
                WHERE data.module = 'utility_core'
                  AND data.name = %s
           )
         LIMIT 1
        """,
        [xml_name, model, *params, xml_name],
    )


def migrate(cr, version):
    if not version:
        return

    template_where = """
        row.template_id = (
            SELECT data.res_id
              FROM ir_model_data data
             WHERE data.module = 'utility_core'
               AND data.name = 'utility_default_contract_template'
               AND data.model = 'utility.contract.template'
        )
    """
    line_ids = {
        'mu_allim': 'utility_default_contract_template_mu_allim_line',
        'cleaning': 'utility_default_contract_template_cleaning_line',
        'municipality': 'utility_default_contract_template_municipality_line',
    }
    for meter_line_type, xml_name in line_ids.items():
        _map_existing_row(
            cr,
            'utility.contract.template.line',
            'utility_contract_template_line',
            xml_name,
            f"{template_where} AND row.meter_line_type = %s",
            [meter_line_type],
        )

    for sequence in range(10, 90, 10):
        _map_existing_row(
            cr,
            'utility.contract.template.block',
            'utility_contract_template_block',
            f'utility_default_contract_template_block_{sequence // 10}',
            f"{template_where} AND row.sequence = %s AND row.is_discount = FALSE",
            [sequence],
        )

    _logger.info('utility_core 16.0.1.17.0: mapped legacy default template rows before data load')
