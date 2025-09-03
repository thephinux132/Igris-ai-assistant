import unittest
from unittest.mock import patch, MagicMock, mock_open
import json
import sys
import os
import tkinter as tk
from pathlib import Path

# Add the project root to the path to allow importing the script
script_path = Path(__file__).parent
project_root = script_path.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'core'))
sys.path.insert(0, str(script_path))

# Mock modules that might not be installed or are problematic in a test environment
# before importing the main script.
MOCK_MODULES = {
    'psutil': MagicMock(),
    'speech_recognition': MagicMock(),
    'pyttsx3': MagicMock(),
    'igris_core': MagicMock(__file__='mocked_igris_core'),
    'core.igris_core': MagicMock(__file__='mocked_core_igris_core'),
    'memory_manager': MagicMock(),
    'core.memory_manager': MagicMock(),
    'memory_manager_gui': MagicMock(),
    'core.memory_manager_gui': MagicMock(),
    'igris_phase2_5_patch_integrated': MagicMock(),
    'suggestion_engine': MagicMock(),
    'plugin_execution_logger': MagicMock(),
}
for mod_name, mock_obj in MOCK_MODULES.items():
    sys.modules[mod_name] = mock_obj

# Now import the script to be tested
import igris_control_gui_main_final_fixed_importlib_patch_patched as igris_gui

class TestIgrisGui(unittest.TestCase):

    def setUp(self):
        """Set up for each test."""
        # Reset any global state if necessary
        igris_gui.policy = {}
        igris_gui.identity = {}
        # We need to mock tkinter as we are not running a GUI
        self.mock_tk = patch('tkinter.Tk').start()
        self.addCleanup(patch.stopall)

    def test_clean_ai_response(self):
        self.assertEqual(igris_gui.clean_ai_response("  \n  Block 1\n\nBlock 2  \n  "), "Block 2")
        self.assertEqual(igris_gui.clean_ai_response("Single block"), "Single block")
        self.assertEqual(igris_gui.clean_ai_response("\n\n"), "")
        self.assertEqual(igris_gui.clean_ai_response(""), "")
        self.assertEqual(igris_gui.clean_ai_response("Block 1\n\n\nBlock 2\n\nBlock 3"), "Block 3")

    @patch('igris_control_gui_main_final_fixed_importlib_patch_patched.ALIASES_FILE')
    def test_load_aliases(self, mock_aliases_file):
        # Test loading valid aliases
        mock_aliases_file.read_text.return_value = '{"ls": "list files", "g": "git"}'
        self.assertEqual(igris_gui.load_aliases(), {"ls": "list files", "g": "git"})

        # Test file not found
        mock_aliases_file.read_text.side_effect = FileNotFoundError
        self.assertEqual(igris_gui.load_aliases(), {})

        # Test invalid JSON
        mock_aliases_file.read_text.side_effect = None
        mock_aliases_file.read_text.return_value = '{"ls": "list files"'
        self.assertEqual(igris_gui.load_aliases(), {})

    @patch('igris_control_gui_main_final_fixed_importlib_patch_patched.ALIASES_FILE')
    def test_save_aliases(self, mock_aliases_file):
        aliases = {"c": "clear"}
        mock_write = mock_open()
        mock_aliases_file.write_text = mock_write
        mock_aliases_file.parent.mkdir = MagicMock()

        igris_gui.save_aliases(aliases)

        mock_aliases_file.parent.mkdir.assert_called_once_with(parents=True, exist_ok=True)
        mock_write.assert_called_once_with(json.dumps(aliases, indent=2), encoding='utf-8')

    @patch('subprocess.run')
    def test_run_cmd(self, mock_subprocess_run):
        # Test successful command
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "Success output"
        mock_proc.stderr = ""
        mock_subprocess_run.return_value = mock_proc
        result = igris_gui.run_cmd(["echo", "hello"])
        self.assertEqual(result, "Success output")
        mock_subprocess_run.assert_called_with(
            "echo hello", capture_output=True, shell=True, check=False,
            encoding='utf-8', errors='replace'
        )

        # Test command with no output
        mock_proc.stdout = ""
        result = igris_gui.run_cmd(["touch", "file"])
        self.assertEqual(result, "Command executed.")

        # Test command failure
        mock_proc.returncode = 1
        mock_proc.stdout = ""
        mock_proc.stderr = "Error output"
        result = igris_gui.run_cmd(["bad_command"])
        self.assertIn("[ERROR]", result)
        self.assertIn("returned 1", result)
        self.assertIn("Error output", result)

        # Test FileNotFoundError
        mock_subprocess_run.side_effect = FileNotFoundError
        result = igris_gui.run_cmd(["nonexistent_command"])
        self.assertIn("[ERROR] Command not found", result)

    @patch('igris_control_gui_main_final_fixed_importlib_patch_patched.psutil', create=True)
    @patch('time.time')
    def test_get_system_uptime(self, mock_time, mock_psutil):
        mock_time.return_value = 1000000
        mock_psutil.boot_time.return_value = mock_time.return_value - (2 * 86400 + 3 * 3600 + 4 * 60 + 5)
        uptime_str = igris_gui.get_system_uptime()
        self.assertEqual(uptime_str, "2 day(s), 3 hour(s), 4 minute(s), 5 second(s)")

        # Test with psutil not available
        igris_gui.psutil = None
        self.assertEqual(igris_gui.get_system_uptime(), "Uptime unavailable (psutil not installed).")
        igris_gui.psutil = mock_psutil # restore

    @patch('igris_control_gui_main_final_fixed_importlib_patch_patched.get_system_uptime')
    @patch('igris_control_gui_main_final_fixed_importlib_patch_patched.psutil', create=True)
    def test_get_system_status_report(self, mock_psutil, mock_get_uptime):
        mock_psutil.cpu_percent.return_value = 15.5
        mock_psutil.virtual_memory.return_value = MagicMock(percent=50.0, used=8 * 1024**3, total=16 * 1024**3)
        mock_psutil.disk_usage.return_value = MagicMock(percent=75.0, free=250 * 1024**3, total=1000 * 1024**3)
        mock_get_uptime.return_value = "1 day(s)"

        report = igris_gui.get_system_status_report()
        self.assertIn("CPU Load: 15.5%", report)
        self.assertIn("Memory Usage: 50.0% (8192 MB / 16384 MB)", report)
        self.assertIn("Disk Usage (C:\\): 75.0% (250 GB free / 1000 GB total)", report)
        self.assertIn("Uptime: 1 day(s)", report)

        # Test with psutil not available
        original_psutil = igris_gui.psutil
        igris_gui.psutil = None
        self.assertEqual(igris_gui.get_system_status_report(), "psutil not available: system metrics unavailable.")
        igris_gui.psutil = original_psutil

    @patch('igris_control_gui_main_final_fixed_importlib_patch_patched.load_config')
    def test_local_match_action(self, mock_load_config):
        mock_load_config.return_value = {
            "tasks": [
                {"task": "reboot", "action": "shutdown /r", "phrases": ["reboot", "restart computer"]},
                {"task": "check disk", "action": "chkdsk", "requires_admin": True, "phrases": ["check disk"]},
            ]
        }

        # Exact match
        result = igris_gui.local_match_action("reboot")
        self.assertIsNotNone(result)
        self.assertEqual(result['task_name'], "reboot")
        self.assertEqual(result['action'], "shutdown /r")
        self.assertEqual(result['reasoning'], "Exact local match")

        # Partial match
        result = igris_gui.local_match_action("please restart computer now")
        self.assertIsNotNone(result)
        self.assertEqual(result['task_name'], "reboot")
        self.assertEqual(result['reasoning'], "Partial local match")

        # No match
        result = igris_gui.local_match_action("do something else")
        self.assertIsNone(result)

        # Admin required match
        result = igris_gui.local_match_action("check disk")
        self.assertTrue(result['requires_admin'])

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)