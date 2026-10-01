import logging

_logger = logging.getLogger(__name__)

# Composite indexes recommended by the performance gap analysis. They are
# created here (and not in utility_core) because the underlying tables and
# columns belong to utility_billing / its dependencies (sale.order inherits
# customer_id, bill_state from this module; utility.penalty is defined here).
_COMPOSITE_INDEXES = [
    # Sale order queries: filter by customer + bill_state + date for overdue detection
    (
        'sale_order_customer_billstate_date_idx',
        'sale_order',
        '(customer_id, bill_state, date_order)',
    ),
    # Penalty queries: lookup by sale_order_id for computed penalty amounts
    (
        'utility_penalty_sale_order_idx',
        'utility_penalty',
        '(sale_order_id)',
    ),
]


def _column_names(columns_expr):
    """Extract bare column names from an index column expression like '(a, b)'."""
    inner = columns_expr.strip().strip('()')
    return [part.strip().split()[0].strip('"') for part in inner.split(',')]


def _table_columns_exist(cr, table, columns):
    """Return True if the table and all requested columns currently exist."""
    cr.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = %s
        """,
        (table,),
    )
    existing = {row[0] for row in cr.fetchall()}
    return all(col in existing for col in _column_names(columns))


def post_init_hook(env):
    """Create composite database indexes after module installation.

    Each index is created inside a savepoint: a failure is logged and the
    transaction is rolled back to the savepoint so the module install can
    still commit successfully.
    """
    cr = env.cr
    for index_name, table, columns in _COMPOSITE_INDEXES:
        try:
            if not _table_columns_exist(cr, table, columns):
                _logger.info(
                    'utility_billing: skipping index %s on %s %s (columns not present)',
                    index_name, table, columns,
                )
                continue
            with cr.savepoint():
                cr.execute(
                    'CREATE INDEX IF NOT EXISTS %s ON %s %s'
                    % (index_name, table, columns)
                )
            _logger.info(
                'utility_billing: created composite index %s on %s %s',
                index_name, table, columns,
            )
        except Exception:
            _logger.warning(
                'utility_billing: could not create index %s on %s %s',
                index_name, table, columns,
                exc_info=True,
            )
