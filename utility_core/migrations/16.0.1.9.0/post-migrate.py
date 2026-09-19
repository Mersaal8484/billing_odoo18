"""Apply the bounded cron-history cleanup policy to existing databases."""

import logging


_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    # The source record is noupdate=1, so update existing databases explicitly.
    cr.execute(
        """
        UPDATE ir_cron
           SET interval_number = 1,
               interval_type = 'days',
               batch_size = 5000
         WHERE utility_code = 'cron_execution_history_cleanup'
        """
    )
    cr.execute(
        """
        INSERT INTO ir_config_parameter (key, value, create_uid, create_date, write_uid, write_date)
        VALUES ('utility.cron_history_cleanup_batch_size', '5000', 1, NOW(), 1, NOW())
        ON CONFLICT (key) DO UPDATE
            SET value = EXCLUDED.value,
                write_uid = 1,
                write_date = NOW()
        WHERE ir_config_parameter.value IS NULL
           OR ir_config_parameter.value = ''
        """
    )
    _logger.info('utility_core 16.0.1.9.0: applied daily cron execution history cleanup policy')
