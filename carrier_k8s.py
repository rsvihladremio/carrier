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
import sys
import argparse
import os
import subprocess
import tarfile
import time
from pathlib import Path
import concurrent.futures


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Run a script on multiple pods and collect output."
    )
    parser.add_argument("script", help="Path to the script file to run on pods.")
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
        "--container", required=False, help="Kubernetes container to use."
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
    def __init__(
        self,
        script,
        namespace,
        labels,
        shell,
        script_args,
        output_archive="output.tar.gz",
        k8s_context=None,
        k8s_config=None,
    ):
        self.script = script
        self.namespace = namespace
        self.labels = labels
        self.shell = shell
        self.script_args = script_args
        if k8s_context is not None:
            self.k8s_context = "--context " + k8s_context
        else:
            self.k8s_context = ""
        if k8s_config is not None:
            self.k8s_config = "--kubeconfig " + k8s_config
        else:
            self.k8s_config = ""
        self.output_archive = output_archive

    def run_cmd(self, cmd, pod_log):
        pod_log.append(f"running command {cmd}\n")
        if sys.version_info[0] > 2 and sys.version_info[1] < 7:
            return subprocess.run(
                cmd,
                shell=True,
                check=True,
            )
        p = subprocess.run(cmd, shell=True, check=False, capture_output=True, text=True)
        pod_log.append("output:\t" + p.stdout + p.stderr + "\n\n")
        if p.returncode != 0:
            raise Exception("bad exit code " + str(p.returncode))

    def get_pods(self):
        cmd = f"kubectl get pods -n {self.namespace} -l {self.labels} -o jsonpath='{{.items[*].metadata.name}}' {self.k8s_context} {self.k8s_config}"
        output = subprocess.check_output(cmd, shell=True).decode("utf-8")
        return output.split()

    def run_script_on_pod(self, pod_name):
        exit_code = 0
        pod_log = [f"##\n## pod {pod_name} on namespace {self.namespace} log \n##\n"]
        try:
            # create a subdirectory under /tmp. We do this as /tmp is a well known location and we create a subdirectory to avoid collisions with other processes
            # this also makes cleanup easier later
            pod_tmp_dir = f"/tmp/{pod_name}_tmp"
            create_tmp_dir_cmd = f"kubectl exec  {self.k8s_context} {self.k8s_config} -n {self.namespace} {pod_name} -- mkdir -p {pod_tmp_dir}"
            self.run_cmd(create_tmp_dir_cmd, pod_log)

            # copy the script the subdirectory we created in /tmp
            copy_script_cmd = f"kubectl {self.k8s_context} {self.k8s_config} cp {self.script} {self.namespace}/{pod_name}:{pod_tmp_dir}/{Path(self.script).name}"
            self.run_cmd(copy_script_cmd, pod_log)

            # Check args has some content to avoid error
            # "TypeError: can only join an iterable"
            if self.script_args:
                script_args_str = " ".join(self.script_args)
            else:
                script_args_str = ""

            # Now cd to the sub directory and run our script using the k8s context, k8s config, k8s namespace and unix shell specified. Likewise pass any args that one needs to pass to the script
            run_script_cmd = f'kubectl exec {self.k8s_context} {self.k8s_config} -n {self.namespace} {pod_name} -- {self.shell} -c "cd {pod_tmp_dir} && {self.shell} {pod_tmp_dir}/{Path(self.script).name} {script_args_str}"'
            self.run_cmd(run_script_cmd, pod_log)

            # let collection rest so all files can be fully written to disk
            time.sleep(1)

            # Now use tar on the pod to archive all output in the subdirectory. We are excluding the script and the tar itself
            collect_files_cmd = f"kubectl exec {self.k8s_context} {self.k8s_config} -n {self.namespace} {pod_name} -- tar -czf {pod_tmp_dir}/{pod_name}.tar.gz --exclude={pod_name}.tar.gz --exclude={Path(self.script).name} -C {pod_tmp_dir}/ ."
            self.run_cmd(collect_files_cmd, pod_log)

            # copy the tar back to the local machine
            copy_back_cmd = f"kubectl cp {self.k8s_context} {self.k8s_config} {self.namespace}/{pod_name}:{pod_tmp_dir}/{pod_name}.tar.gz {pod_name}.tar.gz"
            self.run_cmd(copy_back_cmd, pod_log)
        except Exception as e:
            # since this failed we are returning the error here
            pod_log.append("result of last command was: ")
            pod_log.append(repr(e))
            pod_log.append("\n\n")
            exit_code = 1
        finally:
            # now we can to delete our subdirectory so we do not hog up all of the space on the system
            try:
                delete_subdir_cmd = f"kubectl exec {self.k8s_context} {self.k8s_config} -n {self.namespace} {pod_name} -- rm -fr {pod_tmp_dir}"
                self.run_cmd(delete_subdir_cmd, pod_log)
            except Exception as e:
                pod_log.append(
                    f"directory cleanup {pod_tmp_dir} failed due to error {e}\n"
                )
        pod_log.append(
            f"##\n## end log for pod {pod_name} of namespace {self.namespace} \n##\n"
        )
        return (exit_code, "".join(pod_log))

    def run(self):
        pods = self.get_pods()
        threads = []
        successful = 0
        failed = 0
        # setup a thread pool so the script can run on all the pods at once
        with concurrent.futures.ThreadPoolExecutor() as executor:
            for pod in pods:
                t = executor.submit(self.run_script_on_pod, pod)
                print(f"collection started on {pod} in namespace {self.namespace}")
                threads.append((pod, t))

            # this loops through all the threads in order and logs when they're done
            for t in threads:
                result = t[1].result()
                if result[0] != 0:
                    failed += 1
                    print(
                        f"pod {t[0]} in namespace {self.namespace} failed. Log is \n{result[1]}"
                    )
                else:
                    successful += 1
                    print(f"pod {t[0]} in namespace {self.namespace} is done")
        if successful > 0:
            print(
                f"archiving collected files into one archive named {self.output_archive}"
            )
            with tarfile.open(self.output_archive, "w:gz") as big_archive:
                for pod in pods:
                    big_archive.add(f"{pod}.tar.gz", arcname=f"{pod}.tar.gz")
                    os.remove(f"{pod}.tar.gz")
            return f"All done! The final archive is {self.output_archive}"
        else:
            return f"no successful collections out of {successful+ failed} pods"


def main():
    args = parse_arguments()
    runner = CarrierK8s(
        args.script, args.namespace, args.labels, args.shell, args.script_args
    )
    result = runner.run()
    print(result)


if __name__ == "__main__":
    if sys.version_info[0] < 3:
        raise Exception("Must be using Python 3")
    main()
