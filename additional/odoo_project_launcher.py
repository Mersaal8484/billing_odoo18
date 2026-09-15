"""Run Odoo with this project's addons taking precedence over legacy addons."""
import os
import sys


ODOO_ROOT = r'D:\odoo-16.0\odoo-16.0'
PROJECT_ADDONS = os.path.dirname(os.path.abspath(__file__))

if ODOO_ROOT not in sys.path:
    sys.path.insert(0, ODOO_ROOT)

import odoo  # noqa: E402


# Windows' default Odoo installation exposes custom_addons as a namespace path.
# Put this workspace first before Odoo imports any project module.
project_path = os.path.normcase(PROJECT_ADDONS)
odoo.addons.__path__[:] = [
    path for path in odoo.addons.__path__
    if os.path.normcase(os.path.abspath(path)) != project_path
]
odoo.addons.__path__.insert(0, PROJECT_ADDONS)


if __name__ == '__main__':
    odoo.cli.main()
