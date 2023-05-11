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
import os
from carrier_k8s import CarrierK8s
from pytest_kind import KindCluster
from pathlib import Path
from pykube import Pod
import operator
import time
import tarfile
import tempfile


TEST_DATA_DIR = Path(__file__).resolve().parent / "data"


def search_file_in_nested_tar_gz(archive_path, file_name):
    with tarfile.open(archive_path, "r:gz") as tar:
        for member in tar.getmembers():
            if member.isfile() and member.name == file_name:
                # Found the desired file in the current nested tar.gz
                with tempfile.TemporaryDirectory() as temp_dir:
                    tar.extract(member, path=temp_dir)
                    extracted_file_path = os.path.join(temp_dir, member.name)
                    with open(extracted_file_path, "r") as extracted_file:
                        file_content = extracted_file.read()
                return file_content

            if member.isfile() and member.name.endswith(".tar.gz"):
                # Extract the nested tar.gz to a temporary directory
                with tempfile.TemporaryDirectory() as temp_dir:
                    tar.extract(member, path=temp_dir)
                    nested_archive_path = os.path.join(temp_dir, member.name)

                    # Recursively search within the nested tar.gz
                    result = search_file_in_nested_tar_gz(
                        nested_archive_path, file_name
                    )

                return result

    # File not found
    return None


def check_file_in_tar_gz(archive_path, file_name):
    # Open the tar.gz archive
    with tarfile.open(archive_path, "r:gz") as tar:
        # Check if the file exists in the archive
        return file_name in tar.getnames()


class TestCarrierK8s(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cluster = KindCluster("dremio-testing")
        cls.cluster.create()
        cls.cluster.kubectl("apply", "-f", TEST_DATA_DIR / "statefulset.yaml")
        count = 0
        max_tries = 30
        while True:
            count += 1
            total = len(
                list(
                    filter(
                        operator.attrgetter("ready"),
                        Pod.objects(cls.cluster.api).filter(
                            selector="app.kubernetes.io/name=dremio-easy-chart"
                        ),
                    )
                )
            )
            if count > max_tries:
                raise Exception("too many tries to see if the new pod was deployed")
            if total > 0:
                break
            else:
                time.sleep(5)

    @classmethod
    def tearDownClass(cls):
        cls.cluster.delete()

    def setUp(self):
        self.runner = CarrierK8s(
            TEST_DATA_DIR / "test_script.sh",
            "default",
            "app.kubernetes.io/name=dremio-easy-chart",
            "bash",
            [],
            TEST_DATA_DIR / "output" / "output.tar.gz",
            "kind-dremio-testing",
            ".pytest-kind/dremio-testing/kubeconfig",
        )

    def tearDown(self):
        try:
            os.remove(TEST_DATA_DIR / "output" / "output.tar.gz")
        except:
            pass

    def test_get_pods(self):
        pods = self.runner.get_pods()
        self.assertEqual(pods, ["demo-dremio-easy-chart-0"])

    def test_run_carrier(self):
        archive_path = TEST_DATA_DIR / "output" / "output.tar.gz"
        nested_archive = "demo-dremio-easy-chart-0.tar.gz"
        self.runner.run()
        check_file_in_tar_gz(archive_path, nested_archive)
        f = search_file_in_nested_tar_gz(archive_path, "./carrier.log")
        self.assertEqual("this is my test log\n", f)
        server_out = search_file_in_nested_tar_gz(archive_path, "./server.out")
        self.assertNotEqual(None, server_out)


if __name__ == "__main__":
    unittest.main()
