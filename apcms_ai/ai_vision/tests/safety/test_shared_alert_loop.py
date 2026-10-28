import unittest
from unittest.mock import Mock
from ai_vision.safety.shared_alert_loop import process_alerts


class SharedAlertLoopTests(unittest.TestCase):
    def test_dry_run_is_default(self):
        finished=Mock();finished.wait.side_effect=[False,True];cycle=Mock()
        process_alerts('out',finished,[],cycle=cycle)
        self.assertEqual(cycle.call_count,2)
        self.assertTrue(all('send' not in call.kwargs for call in cycle.call_args_list))

    def test_transient_error_keeps_detection_running_and_retries_on_close(self):
        finished=Mock();finished.wait.side_effect=[False,True];cycle=Mock(side_effect=[OSError(),None]);errors=[]
        process_alerts('out',finished,errors,dict(url='https://example.test/fire',token='secret'),cycle=cycle)
        self.assertEqual(errors,[]);self.assertEqual(cycle.call_count,2)
        self.assertTrue(cycle.call_args.kwargs['allow_test_records'])

    def test_final_failure_is_retained(self):
        finished=Mock();finished.wait.return_value=True;errors=[]
        process_alerts('out',finished,errors,cycle=Mock(side_effect=OSError()))
        self.assertEqual(errors,['OSError'])
