"""The uniqueness key must use a stored column on account_payment."""

import logging


_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    cr.execute(
        """
        DROP INDEX IF EXISTS account_payment_utility_collection_request_key_company_uniq
        """
    )
    _logger.info('utility_billing 16.0.2.8.0: prepared the collection idempotency constraint')
