import unittest
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
from display import manager

class GpuDetectionTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.temp_dir)
        
    def _create_mock_gpu(self, card_name, pci_id, slot_name):
        card_dir = Path(self.temp_dir) / card_name
        card_dir.mkdir(parents=True)
        device_dir = card_dir / "device"
        device_dir.mkdir()
        uevent_path = device_dir / "uevent"
        uevent_path.write_text(f"PCI_ID={pci_id}\nPCI_SLOT_NAME={slot_name}\n", encoding="utf-8")
        return str(card_dir)

    @patch("glob.glob")
    def test_detect_gpus_integrated_and_discrete(self, mock_glob):
        igpu_path = self._create_mock_gpu("card0", "8086:7D45", "0000:00:02.0")
        dgpu_path = self._create_mock_gpu("card1", "10de:2204", "0000:01:00.0")
        mock_glob.return_value = [igpu_path, dgpu_path]
        
        gpus = manager._detect_gpus()
        self.assertIsNotNone(gpus["igpu"])
        self.assertIsNotNone(gpus["dgpu"])
        self.assertEqual(gpus["igpu"]["vendor"], "0x8086")
        self.assertEqual(gpus["igpu"]["device"], "0x7d45")
        self.assertEqual(gpus["dgpu"]["vendor"], "0x10de")
        self.assertEqual(gpus["dgpu"]["device"], "0x2204")

    @patch("display.manager._detect_gpus")
    def test_udev_rule_includes_gpu_symlinks(self, mock_detect):
        mock_detect.return_value = {
            "igpu": {"vendor": "0x8086", "device": "0x7d45", "card": "card0"},
            "dgpu": {"vendor": "0x10de", "device": "0x2204", "card": "card1"}
        }
        
        rule = manager._udev_rule()
        self.assertIn('ATTRS{vendor}=="0x8086", ATTRS{device}=="0x7d45", SYMLINK+="dri/by-name/igpu"', rule)
        self.assertIn('ATTRS{vendor}=="0x10de", ATTRS{device}=="0x2204", SYMLINK+="dri/by-name/dgpu"', rule)

    @patch("display.manager._detect_gpus")
    @patch("display.manager.get_user_input")
    @patch("display.manager.load_state")
    @patch("display.manager.save_state")
    @patch("display.manager.refresh_managed_files")
    @patch("display.manager._remember_sunshine_execstart")
    @patch("display.manager._remember_sunshine_audio_sink")
    @patch("display.manager._ensure_dependencies")
    @patch("display.manager._install_udev_rule")
    @patch("display.manager._daemon_reload")
    @patch("display.manager._sunshine_service_active")
    def test_setup_display_asks_for_gpu_preference(self, mock_active, mock_reload, mock_install, mock_deps, mock_audio, mock_exec, mock_refresh, mock_save, mock_load, mock_input, mock_detect):
        state = manager._default_state()
        mock_load.return_value = state
        mock_detect.return_value = {
            "igpu": {"vendor": "0x8086", "device": "0x7d45", "card": "card0"},
            "dgpu": {"vendor": "0x10de", "device": "0x2204", "card": "card1"}
        }
        mock_input.return_value = "1" # dGPU
        mock_deps.return_value = []
        mock_install.return_value = True
        mock_active.return_value = False
        mock_refresh.return_value = state
        mock_exec.return_value = state
        
        manager.setup_display()
        
        self.assertEqual(state["wlr_drm_devices"], "/dev/dri/by-name/dgpu")
        mock_input.assert_called()

    @patch("display.manager._detect_gpus")
    @patch("display.manager.load_state")
    @patch("display.manager.save_state")
    @patch("display.manager.refresh_managed_files")
    @patch("display.manager._remember_sunshine_execstart")
    @patch("display.manager._remember_sunshine_audio_sink")
    @patch("display.manager._ensure_dependencies")
    @patch("display.manager._install_udev_rule")
    @patch("display.manager._daemon_reload")
    @patch("display.manager._sunshine_service_active")
    def test_setup_display_defaults_when_one_gpu(self, mock_active, mock_reload, mock_install, mock_deps, mock_audio, mock_exec, mock_refresh, mock_save, mock_load, mock_detect):
        state = manager._default_state()
        mock_load.return_value = state
        mock_detect.return_value = {
            "igpu": {"vendor": "0x8086", "device": "0x7d45", "card": "card0"},
            "dgpu": None
        }
        mock_deps.return_value = []
        mock_install.return_value = True
        mock_active.return_value = False
        mock_refresh.return_value = state
        mock_exec.return_value = state
        
        manager.setup_display()
        
        self.assertEqual(state["wlr_drm_devices"], "/dev/dri/by-name/igpu")

if __name__ == "__main__":
    unittest.main()
