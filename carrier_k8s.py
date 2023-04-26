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
import os
import sys
import subprocess
import tarfile
from pathlib import Path
from threading import Thread, Lock


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Run a script on multiple pods and collect output."
    )
    parser.add_argument(
        "script", help="Path to the script file to run on pods.")
    parser.add_argument(
        "--script-args",
        nargs=argparse.REMAINDER,
        default=[],
        help="Arguments for the script",
    )
    parser.add_argument(
        "--namespace", default="default", help="Kubernetes namespace to use."
    )
    parser.add_argument(
        "--container",
        required=False,
        help="Kubernetes container to use."
    )
    parser.add_argument(
        "--labels",
        help="Comma-separated list of label selectors (e.g., 'app=myapp,env=prod').",
    )
    parser.add_argument(
        "--shell",
        default="bash",
        choices=["bash", "zsh", "sh"],
        help="Shell to use for running the script (default: bash).",
    )
    return parser.parse_args()


class CarrierK8s:
    def __init__(self, script, namespace, labels, shell, script_args):
        self.script = script
        self.namespace = namespace
        self.labels = labels
        self.shell = shell
        self.script_args = script_args
        self.output_archive = "output.tar.gz"
        self.log_file = "debug.log"
        self.log_lock = Lock()

    def run_cmd(self, cmd):
        with self.log_lock:
            with open(self.log_file, "a") as log:
                return subprocess.run(
                    cmd, shell=True, check=False, stdout=log, stderr=subprocess.STDOUT
                )

    def get_pods(self):
        cmd = f"kubectl get pods -n {self.namespace} -l {self.labels} -o jsonpath='{{.items[*].metadata.name}}'"
        output = subprocess.check_output(cmd, shell=True).decode("utf-8")
        return output.split()

    def run_script_on_pod(self, pod_name):
        pod_dir = f"{pod_name}_tmp"
        pod_tmp_base_dir = "/tmp"
        pod_tmp_dir = f"{pod_tmp_base_dir}/{pod_name}_tmp"

        # Check write access to /tmp dir
        rights_check = (
            f"kubectl exec -n {self.namespace} {pod_name} -- test -w {pod_tmp_base_dir}"
        )
        exit_code = self.run_cmd(rights_check)
        # If /tmp path  has no write access raise exception
        if exit_code.returncode != 0:
            raise ValueError(
                f"do not have the rights to write to either {pod_tmp_dir}")

        create_tmp_dir_cmd = (
            f"kubectl exec -n {self.namespace} {pod_name} -- mkdir -p {pod_tmp_dir}"
        )
        print("creating tmp dir")
        self.feedback(f"creating tmp dir {pod_tmp_dir}")
        self.run_cmd(create_tmp_dir_cmd)

        copy_script_cmd = f"kubectl cp {self.script} {self.namespace}/{pod_name}:{pod_tmp_dir}/{Path(self.script).name}"
        self.feedback(f"copying script {self.script}")
        self.run_cmd(copy_script_cmd)

        script_args_str = " ".join(self.script_args)
        run_script_cmd = f"kubectl exec -n {self.namespace} {pod_name} -- {self.shell} -c \"cd {pod_tmp_dir} && {pod_tmp_dir}/{Path(self.script).name} {script_args_str}\""
        self.feedback(f"running script")
        self.run_cmd(run_script_cmd)

        collect_files_cmd = f"kubectl exec -n {self.namespace} {pod_name} -- tar -czf {pod_tmp_dir}/{pod_name}.tar.gz --exclude={pod_name}.tar.gz --exclude={Path(self.script).name} -C {pod_tmp_dir}/ ."
        self.feedback(f"archiving files")
        self.run_cmd(collect_files_cmd)

        copy_back_cmd = f"kubectl cp {self.namespace}/{pod_name}:{pod_tmp_dir}/{pod_name}.tar.gz {pod_name}.tar.gz"
        self.feedback(f"copying back files")
        self.run_cmd(copy_back_cmd)

    def run(self):
        pods = self.get_pods()

        threads = []
        for pod in pods:
            t = Thread(target=self.run_script_on_pod, args=(pod,))
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

        with tarfile.open(self.output_archive, "w:gz") as big_archive:
            for pod in pods:
                big_archive.add(f"{pod}.tar.gz", arcname=f"{pod}.tar.gz")
                os.remove(f"{pod}.tar.gz")

        return f"All done! The final archive is {self.output_archive}"

    def feedback(self, fb_string):
        fb_output = f"progress: {fb_string}"
        print(fb_output)


def main():
    args = parse_arguments()
    runner = CarrierK8s(
        args.script, args.namespace, args.labels, args.shell, args.script_args
    )
    result = runner.run()
    print(result)


if __name__ == "__main__":
    main()
