#    Copyright 2023 Dremio
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#       http://www.apache.org/licenses/LICENSE-2.0
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

import unittest
from unittest.mock import MagicMock, patch
from carrier_k8s import CarrierK8s


class TestCarrierK8s(unittest.TestCase):
    def setUp(self):
        self.runner = CarrierK8s("test_script.sh", "default", "app=myapp", "bash", [])

    def test_init(self):
        self.assertEqual(self.runner.script, "test_script.sh")
        self.assertEqual(self.runner.namespace, "default")
        self.assertEqual(self.runner.labels, "app=myapp")
        self.assertEqual(self.runner.shell, "bash")

    @patch("subprocess.check_output")
    def test_get_pods(self, mock_check_output):
        mock_check_output.return_value = b"pod1\npod2\n"
        pods = self.runner.get_pods()
        self.assertEqual(pods, ["pod1", "pod2"])

    @patch("carrier_k8s.CarrierK8s.run_cmd")
    def test_run_script_on_pod(self, mock_run_cmd):
        self.runner.run_script_on_pod("pod1")
        self.assertEqual(mock_run_cmd.call_count, 5)

    @patch("carrier_k8s.CarrierK8s.get_pods")
    @patch("carrier_k8s.CarrierK8s.run_script_on_pod")
    @patch("tarfile.open")
    @patch("os.remove")
    def test_run(self, mock_remove, mock_open, mock_run_script_on_pod, mock_get_pods):
        mock_get_pods.return_value = ["pod1", "pod2"]
        self.runner.run()
        mock_run_script_on_pod.assert_called()
        mock_open.assert_called_once_with("output.tar.gz", "w:gz")
        mock_remove.assert_called()


if __name__ == "__main__":
    unittest.main()
