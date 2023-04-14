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

import argparse
import unittest
import subprocess
from unittest.mock import patch, call
import carrier


class TestDDC(unittest.TestCase):
    def test_read_hosts_file(self):
        with open("test_hosts_file.txt", "w") as file:
            file.write("host1\nhost2\nhost3\n")

        expected_hosts = ["host1", "host2", "host3"]
        actual_hosts = carrier.read_hosts_file("test_hosts_file.txt")

        self.assertEqual(expected_hosts, actual_hosts)

    def test_parse_hosts_list(self):
        hosts_str = "host1,host2,host3"
        expected_hosts = ["host1", "host2", "host3"]
        actual_hosts = carrier.parse_hosts_list(hosts_str)

        self.assertEqual(expected_hosts, actual_hosts)

    @patch("ddc.subprocess.run")
    @patch("ddc.uuid.uuid4", return_value="12345678-1234-1234-1234-123456789abc")
    def test_execute_script_on_host_ssh(self, mock_uuid4, mock_run):
        carrier.execute_script_on_host_ssh(
            "host1",
            "collect.sh",
            username="myuser",
            password="mypass",
            ignore_host_key=True,
        )

        expected_calls = [
            call(
                [
                    "ssh",
                    "-o",
                    "StrictHostKeyChecking=no",
                    "-o",
                    "UserKnownHostsFile=/dev/null",
                    "-l",
                    "myuser",
                    "-o",
                    "PasswordAuthentication=yes",
                    "-o",
                    'PasswordAuthentication="mypass"',
                    "host1",
                    "mkdir",
                    "/tmp/12345678-1234-1234-1234-123456789abc",
                ]
            ),
            call(
                [
                    "scp",
                    "-o",
                    "StrictHostKeyChecking=no",
                    "-o",
                    "UserKnownHostsFile=/dev/null",
                    "-l",
                    "myuser",
                    "-o",
                    "PasswordAuthentication=yes",
                    "-o",
                    'PasswordAuthentication="mypass"',
                    "collect.sh",
                    "host1:/tmp/12345678-1234-1234-1234-123456789abc/collect.sh",
                ]
            ),
            call(
                [
                    "ssh",
                    "-o",
                    "StrictHostKeyChecking=no",
                    "-o",
                    "UserKnownHostsFile=/dev/null",
                    "-l",
                    "myuser",
                    "-o",
                    "PasswordAuthentication=yes",
                    "-o",
                    'PasswordAuthentication="mypass"',
                    "host1",
                    "chmod",
                    "+x",
                    "/tmp/12345678-1234-1234-1234-123456789abc/collect.sh",
                ]
            ),
            call(
                [
                    "ssh",
                    "-o",
                    "StrictHostKeyChecking=no",
                    "-o",
                    "UserKnownHostsFile=/dev/null",
                    "-l",
                    "myuser",
                    "-o",
                    "PasswordAuthentication=yes",
                    "-o",
                    'PasswordAuthentication="mypass"',
                    "host1",
                    "cd /tmp/12345678-1234-1234-1234-123456789abc && /tmp/12345678-1234-1234-1234-123456789abc/collect.sh",
                ]
            ),
            call(
                [
                    "ssh",
                    "-o",
                    "StrictHostKeyChecking=no",
                    "-o",
                    "UserKnownHostsFile=/dev/null",
                    "-l",
                    "myuser",
                    "-o",
                    "PasswordAuthentication=yes",
                    "-o",
                    'PasswordAuthentication="mypass"',
                    "host1",
                    "cd /tmp/12345678-1234-1234-1234-123456789abc && tar czf /tmp/12345678-1234-1234-1234-123456789abc/output.tar.gz .",
                ]
            ),
            call(
                [
                    "scp",
                    "-o",
                    "StrictHostKeyChecking=no",
                    "-o",
                    "UserKnownHostsFile=/dev/null",
                    "-l",
                    "myuser",
                    "-o",
                    "PasswordAuthentication=yes",
                    "-o",
                    'PasswordAuthentication="mypass"',
                    "host1:/tmp/12345678-1234-1234-1234-123456789abc/output.tar.gz",
                    "host1_output.tar.gz",
                ]
            ),
            call(
                [
                    "ssh",
                    "-o",
                    "StrictHostKeyChecking=no",
                    "-o",
                    "UserKnownHostsFile=/dev/null",
                    "-l",
                    "myuser",
                    "-o",
                    "PasswordAuthentication=yes",
                    "-o",
                    'PasswordAuthentication="mypass"',
                    "host1",
                    "rm",
                    "-r",
                    "/tmp/12345678-1234-1234-1234-123456789abc",
                ]
            ),
        ]
        mock_run.assert_has_calls(expected_calls)

    @patch("ddc.subprocess.run")
    @patch("ddc.uuid.uuid4", return_value="12345678-1234-1234-1234-123456789abc")
    def test_execute_script_on_host_kubectl(self, mock_uuid4, mock_run):
        carrier.execute_script_on_host_kubectl(
            "pod1", "collect.sh", namespace="my-namespace"
        )

        expected_calls = [
            call(
                [
                    "kubectl",
                    "exec",
                    "pod1",
                    "-n",
                    "my-namespace",
                    "--",
                    "mkdir",
                    "/tmp/12345678-1234-1234-1234-123456789abc",
                ]
            ),
            call(
                [
                    "kubectl",
                    "cp",
                    "collect.sh",
                    "my-namespace/pod1:/tmp/12345678-1234-1234-1234-123456789abc/collect.sh",
                ]
            ),
            call(
                [
                    "kubectl",
                    "exec",
                    "pod1",
                    "-n",
                    "my-namespace",
                    "--",
                    "chmod",
                    "+x",
                    "/tmp/12345678-1234-1234-1234-123456789abc/collect.sh",
                ]
            ),
            call(
                [
                    "kubectl",
                    "exec",
                    "pod1",
                    "-n",
                    "my-namespace",
                    "--",
                    "sh",
                    "-c",
                    "cd /tmp/12345678-1234-1234-1234-123456789abc && /tmp/12345678-1234-1234-1234-123456789abc/collect.sh",
                ]
            ),
            call(
                [
                    "kubectl",
                    "exec",
                    "pod1",
                    "-n",
                    "my-namespace",
                    "--",
                    "sh",
                    "-c",
                    "cd /tmp/12345678-1234-1234-1234-123456789abc && tar czf /tmp/12345678-1234-1234-1234-123456789abc/output.tar.gz .",
                ]
            ),
            call(
                [
                    "kubectl",
                    "cp",
                    "my-namespace/pod1:/tmp/12345678-1234-1234-1234-123456789abc/output.tar.gz",
                    "pod1_output.tar.gz",
                ]
            ),
            call(
                [
                    "kubectl",
                    "exec",
                    "pod1",
                    "-n",
                    "my-namespace",
                    "--",
                    "rm",
                    "-r",
                    "/tmp/12345678-1234-1234-1234-123456789abc",
                ]
            ),
        ]
        mock_run.assert_has_calls(expected_calls)

    @patch(
        "ddc.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout='{"items": [{"metadata": {"name": "pod1"}}, {"metadata": {"name": "pod2"}}]}',
        ),
    )
    def test_get_pods_by_labels(self, mock_run):
        pods = carrier.get_pods_by_labels(
            "app=myapp,env=production", namespace="my-namespace"
        )
        self.assertEqual(pods, ["pod1", "pod2"])
        mock_run.assert_called_once_with(
            [
                "kubectl",
                "get",
                "pods",
                "-n",
                "my-namespace",
                "-l",
                "app=myapp,env=production",
                "-o",
                "json",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

    def test_build_ssh_options(self):
        ssh_options = carrier.build_ssh_options(
            username="myuser", password="mypass", ignore_host_key=True
        )
        self.assertEqual(
            ssh_options,
            [
                "-o",
                "StrictHostKeyChecking=no",
                "-o",
                "UserKnownHostsFile=/dev/null",
                "-l",
                "myuser",
                "-o",
                "PasswordAuthentication=yes",
                "-o",
                'PasswordAuthentication="mypass"',
            ],
        )


if __name__ == "__main__":
    unittest.main()
