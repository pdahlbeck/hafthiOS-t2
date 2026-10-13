import runpy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

diagnostics=runpy.run_path('scripts/t2-diagnostics.py')

class DiagnosticsTests(unittest.TestCase):
    def test_missing_hardware_is_unknown_not_success(self):
        with tempfile.TemporaryDirectory() as directory:
            result=diagnostics['hardware'](Path(directory))
        self.assertFalse(result['uefi'])
        self.assertEqual(result['model'],'unknown')
        self.assertEqual(result['displays'],[])
        self.assertIsNone(result['sleep_states'])

    def test_report_omits_power_serial_and_preserves_connector_status(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            battery=root/'class/power_supply/BAT0'
            battery.mkdir(parents=True)
            (battery/'capacity').write_text('75\n')
            (battery/'serial_number').write_text('PRIVATE')
            display=root/'class/drm/card2-eDP-1'
            display.mkdir(parents=True)
            (display/'status').write_text('connected\n')
            (root/'firmware/efi').mkdir(parents=True)
            result=diagnostics['hardware'](root)
        self.assertTrue(result['uefi'])
        self.assertEqual(result['displays'][0]['status'],'connected')
        self.assertEqual(result['power'][0]['capacity'],'75')
        self.assertNotIn('PRIVATE',str(result))

    def test_import_does_not_run_probes(self):
        with patch('subprocess.run') as probe:
            runpy.run_path('scripts/t2-diagnostics.py')
        probe.assert_not_called()
