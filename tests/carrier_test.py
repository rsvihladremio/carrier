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
from carrier import Carrier


class TestCarrier(unittest.TestCase):
    def setUp(self):
        self.runner = Carrier(
            "test_script.sh", ["host1", "host2"], "user", "password", False, "bash"
        )

    def test_init(self):
        self.assertEqual(self.runner.script, "test_script.sh")
        self.assertEqual(self.runner.hosts, ["host1", "host2"])
        self.assertEqual(self.runner.username, "user")
        self.assertEqual(self.runner.use_key, False)
        self.assertEqual(self.runner.shell, "bash")

    @patch("subprocess.check_output")
    def test_ssh_cmd(self, mock_check_output):
        cmd = self.runner.ssh_cmd("host1", "ls")
        self.assertIn("ssh", cmd)

    @patch("subprocess.check_output")
    def test_scp_cmd(self, mock_check_output):
        cmd = self.runner.scp_write_cmd("test.txt", "host1:/tmp/test.txt")
        self.assertIn("scp", cmd)

    @patch("carrier.Carrier.run_cmd")
    def test_run_script_on_host(self, mock_run_cmd):
        self.runner.run_script_on_host("host1")
        self.assertEqual(mock_run_cmd.call_count, 5)

    @patch("carrier.Carrier.run_script_on_host")
    @patch("tarfile.open")
    @patch("os.remove")
    def test_run(self, mock_remove, mock_open, mock_run_script_on_host):
        self.runner.hosts = ["host1", "host2"]
        self.runner.run()
        mock_run_script_on_host.assert_called()
        mock_open.assert_called_once_with("output.tar.gz", "w:gz")
        mock_remove.assert_called()


if __name__ == "__main__":
    unittest.main()
