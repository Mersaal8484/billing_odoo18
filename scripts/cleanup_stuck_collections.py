"""Safely inspect or remove abandoned draft field-collection payments.

Run with the Odoo virtual environment.  The default is dry-run; ``--apply``
requires an explicit backup acknowledgement and never touches posted payments.
"""

import argparse
import configparser
import sys
from pathlib import Path

def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, help='Path to odoo.conf')
    parser.add_argument('--database', required=True, help='Target database name')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--dry-run', action='store_true', help='List candidates (default)')
    mode.add_argument('--apply', action='store_true', help='Delete only proven-safe drafts')
    parser.add_argument(
        '--backup-confirmed', action='store_true',
        help='Required with --apply after taking a verified database backup.',
    )
    return parser


def _load_odoo(config_path):
    """Load the Odoo source tree declared by this deployment's configuration."""
    raw_config = configparser.ConfigParser()
    if not raw_config.read(config_path, encoding='utf-8'):
        raise SystemExit('Unable to read Odoo configuration: %s' % config_path)
    addons_path = raw_config.get('options', 'addons_path', fallback='').split(',')
    if not addons_path or not addons_path[0].strip():
        raise SystemExit('addons_path is required in the Odoo configuration.')
    odoo_root = str(Path(addons_path[0].strip()).parent)
    if odoo_root not in sys.path:
        sys.path.insert(0, odoo_root)

    import odoo
    from odoo import api, SUPERUSER_ID
    from odoo.tools import config
    return odoo, api, SUPERUSER_ID, config


def _safe_to_remove(payment, collection_model, allocation_model):
    collection = collection_model.search([('payment_id', '=', payment.id)], limit=1)
    allocation = allocation_model.search([('payment_id', '=', payment.id)], limit=1)
    return (
        payment.state == 'draft'
        and not payment.move_id
        and not collection
        and not allocation
    ), collection, allocation


def main(argv=None):
    args = _parser().parse_args(argv)
    if args.apply and not args.backup_confirmed:
        raise SystemExit('--apply requires --backup-confirmed after a verified backup.')

    odoo, api, superuser_id, odoo_config = _load_odoo(args.config)
    odoo_config.parse_config(['-c', args.config, '-d', args.database])
    registry = odoo.registry(args.database)
    with registry.cursor() as cr:
        env = api.Environment(cr, superuser_id, {})
        payments = env['account.payment'].search([
            ('collection_request_key', '!=', False),
            ('state', '=', 'draft'),
        ], order='create_date, id')
        collection_model = env['utility.collection']
        allocation_model = env['utility.payment.allocation']

        removed = 0
        for payment in payments:
            safe, collection, allocation = _safe_to_remove(
                payment, collection_model, allocation_model)
            print(
                'payment=%s name=%s key=%s amount=%s invoice=%s collector=%s '
                'created=%s collection=%s allocation=%s safe=%s' % (
                    payment.id, payment.name, payment.collection_request_key,
                    payment.amount, payment.utility_invoice_id.display_name,
                    payment.collector_id.display_name, payment.create_date,
                    collection.display_name or '-', allocation.display_name or '-', safe,
                )
            )
            if args.apply and safe:
                payment.unlink()
                removed += 1

        if args.apply:
            cr.commit()
            print('Removed %s proven-safe draft payment(s).' % removed)
        else:
            cr.rollback()
            print('Dry run complete: no data was changed.')


if __name__ == '__main__':
    main(sys.argv[1:])
