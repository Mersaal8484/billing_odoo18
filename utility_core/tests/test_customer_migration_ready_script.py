import importlib.util
import sys
from datetime import date
from pathlib import Path
from unittest import TestCase


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / 'scripts'
    / 'import_customer_migration_ready.py'
)
SPEC = importlib.util.spec_from_file_location(
    'import_customer_migration_ready', SCRIPT_PATH
)
SCRIPT = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = SCRIPT
SPEC.loader.exec_module(SCRIPT)


class TestCustomerMigrationReadyScript(TestCase):

    def test_meter_match_key_preserves_structured_identifiers(self):
        self.assertEqual(SCRIPT.meter_match_key('00302914'), '302914')
        self.assertEqual(SCRIPT.meter_match_key('07/09340'), '07/09340')
        self.assertEqual(SCRIPT.meter_match_key('0000'), '0')

    def test_numeric_accepts_legacy_export_formats(self):
        self.assertEqual(SCRIPT.numeric("'1,250.50"), 1250.50)
        self.assertEqual(SCRIPT.numeric('1٬250٫50'), 1250.50)
        self.assertEqual(SCRIPT.numeric(None), 0.0)

    def test_mapping_registry_resolves_code_bracket_and_target_name(self):
        registry = SCRIPT.MappingRegistry()
        registry.add('category', 'c1', '[CAT_PUB] أهالي')
        self.assertEqual(registry.resolve('category', 'c1', None), 'c1')
        self.assertEqual(registry.resolve('category', 'CAT_PUB', None), 'c1')
        self.assertEqual(registry.resolve('category', '[CAT_PUB] أهالي', None), 'c1')
        self.assertEqual(registry.resolve('category', '', 'c1'), 'c1')

    def test_choose_source_requires_unambiguous_match(self):
        first = [''] * 55
        second = [''] * 55
        first[SCRIPT.SOURCE_METER_NUMBER] = '00123'
        second[SCRIPT.SOURCE_METER_NUMBER] = '123'
        candidates = [(10, first), (11, second)]
        self.assertEqual(SCRIPT.choose_source(candidates, '00123')[0], 10)
        self.assertEqual(SCRIPT.choose_source(candidates, '123')[0], 11)
        self.assertEqual(SCRIPT.choose_source(candidates, '000123'), (None, None))

    def test_phase_boolean_and_date_parsers_are_strict(self):
        self.assertEqual(SCRIPT.parse_phase('single'), 'single')
        self.assertEqual(SCRIPT.parse_phase('محول تيار'), 'three')
        self.assertTrue(SCRIPT.parse_bool('نعم', False))
        self.assertFalse(SCRIPT.parse_bool('لا', True))
        self.assertEqual(SCRIPT.parse_date('2026-09-01', None), date(2026, 9, 1))
        with self.assertRaises(ValueError):
            SCRIPT.parse_phase('غير معروف')
        with self.assertRaises(ValueError):
            SCRIPT.parse_bool('ربما', True)
