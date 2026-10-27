import subprocess
import unittest
from unittest.mock import Mock,patch
from ai_vision.parking.parking_process_scope import terminate_worker_tree,isolate_worker


class ProcessScopeTests(unittest.TestCase):
    def worker(self, states):
        child=Mock(pid=12345)
        child.is_alive.side_effect=states
        return child

    def test_windows_only_targets_owned_pid_tree(self):
        child=self.worker([True,False])
        with patch("subprocess.run",return_value=Mock(returncode=0)) as run:
            self.assertTrue(terminate_worker_tree(child,platform="nt"))
        self.assertEqual(run.call_args.args[0],["taskkill","/PID","12345","/T","/F"])
        child.terminate.assert_not_called()

    def test_failed_tree_command_is_not_normal_success(self):
        child=self.worker([True,True,False])
        with patch("subprocess.run",return_value=Mock(returncode=1)):
            self.assertFalse(terminate_worker_tree(child,platform="nt"))
        child.terminate.assert_called_once()

    def test_tree_timeout_is_bounded_and_reviewed(self):
        child=self.worker([True,True,False])
        with patch("subprocess.run",side_effect=subprocess.TimeoutExpired("taskkill",5)):
            self.assertFalse(terminate_worker_tree(child,platform="nt"))
        child.terminate.assert_called_once()

    def test_already_exited_process_is_not_signalled(self):
        child=self.worker([False])
        with patch("subprocess.run") as run:
            self.assertTrue(terminate_worker_tree(child,platform="nt"))
        run.assert_not_called();child.terminate.assert_not_called()

    def test_invalid_pid_never_runs_command(self):
        child=self.worker([True]);child.pid=0
        with patch("subprocess.run") as run,self.assertRaises(ValueError):
            terminate_worker_tree(child,platform="nt")
        run.assert_not_called()

    def test_posix_only_signals_own_group(self):
        child=self.worker([True,False])
        with patch("os.getpgid",return_value=12345,create=True),patch("os.killpg",side_effect=[None,ProcessLookupError],create=True) as group:
            self.assertTrue(terminate_worker_tree(child,platform="posix"))
        self.assertEqual(group.call_args_list[0].args[0],12345)

    def test_posix_does_not_signal_server_group(self):
        child=self.worker([True,True,False])
        with patch("os.getpgid",return_value=999,create=True),patch("os.killpg",create=True) as group:
            self.assertFalse(terminate_worker_tree(child,platform="posix"))
        group.assert_not_called();child.terminate.assert_called_once()
