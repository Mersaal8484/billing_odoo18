import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)

# Sequences that must always use 9-digit numbers because they grow with the
# customer base (customers, meters, transformers, bills, readings, ...).
_SEQUENCE_PADDING = 9

# Standard Odoo sequences enlarged alongside the utility.* ones (utility bills
# are sale.orders, prepaid sales are pos.orders...).
_STANDARD_SEQUENCE_CODES = (
    'sale.order',
    'recurring.payment',
    'pos.order',
    'pos.order.line',
    'pos.session',
)

# Extra sequences created by code (kept out of the noupdate XML data on
# purpose so every database - old and new - gets them through one path).
_EXTRA_SEQUENCES = (
    ('utility.transformer', 'تسلسل أرقام المحولات', 'TRF/%(year)s/'),
    ('utility.transformer.private', 'تسلسل المحولات الخاصة', 'PRV/%(year)s/'),
)


def _column_names(columns_expr):
    """Extract bare column names from an index column expression like '(a, b)'.

    Note: expressions with parentheses, function calls or quoted identifiers
    are not supported; keep the index definitions simple.
    """
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


def _create_composite_indexes(cr, indexes, caller):
    """Create composite indexes safely.

    Each index creation runs inside a savepoint so a failure (e.g. a table or
    column that only appears in a later module of the install graph) never
    aborts the surrounding PostgreSQL transaction.
    """
    for index_name, table, columns in indexes:
        try:
            if not _table_columns_exist(cr, table, columns):
                _logger.info(
                    '%s: skipping index %s on %s %s (columns not present yet)',
                    caller, index_name, table, columns,
                )
                continue
            with cr.savepoint():
                cr.execute(
                    'CREATE INDEX IF NOT EXISTS %s ON %s %s'
                    % (index_name, table, columns)
                )
            _logger.info(
                '%s: created composite index %s on %s %s',
                caller, index_name, table, columns,
            )
        except Exception:
            _logger.warning(
                '%s: could not create index %s on %s %s',
                caller, index_name, table, columns,
                exc_info=True,
            )


def _enlarge_sequences(cr):
    """Enlarge every utility.* and standard document sequence to 9 digits."""
    cr.execute(
        """
        UPDATE ir_sequence
        SET padding = %s
        WHERE (
            code LIKE 'utility.%%'
            OR code IN (
                'sale.order',
                'recurring.payment',
                'pos.order',
                'pos.order.line',
                'pos.session'
            )
        )
          AND padding < %s
        """,
        (_SEQUENCE_PADDING, _SEQUENCE_PADDING),
    )


def _ensure_extra_sequences(cr):
    """Create the transformer sequences (regular + private) if missing."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    Sequence = env['ir.sequence']
    for code, name, prefix in _EXTRA_SEQUENCES:
        try:
            if Sequence.search([('code', '=', code)]):
                continue
            with cr.savepoint():
                Sequence.create({
                    'name': name,
                    'code': code,
                    'prefix': prefix,
                    'padding': _SEQUENCE_PADDING,
                    'company_id': False,
                })
            _logger.info('utility_core: created sequence %s (%s)', code, prefix)
        except Exception:
            _logger.warning(
                'utility_core: could not create sequence %s', code, exc_info=True,
            )


def post_init_hook(env):
    """Create composite database indexes and tune sequences after install."""
    cr = env.cr
    # utility_reading is defined in utility_core itself, so its columns are
    # guaranteed to exist at this point.
    _create_composite_indexes(cr, [
        (
            'utility_reading_meter_state_date_idx',
            'utility_reading',
            '(meter_id, state, reading_date)',
        ),
    ], 'utility_core')

    _enlarge_sequences(cr)
    _ensure_extra_sequences(cr)

    # Odoo temporarily stores a minimal placeholder for the generated user
    # permissions view while modules are being installed. Rebuild it after
    # utility_core is fully installed so the standard permissions return in
    # their normal application/category layout.
    env['res.groups'].with_context(lang=None)._update_user_groups_view()
