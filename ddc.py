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
import tarfile
import subprocess
import uuid
import json

# Helper functions


def combine_tar_files(tar_files, output_tar_file):
    with tarfile.open(output_tar_file, "w") as final_tar:
        for tar_file in tar_files:
            tar_info = tarfile.TarInfo(name=os.path.basename(tar_file))
            tar_info.size = os.path.getsize(tar_file)
            with open(tar_file, "rb") as file:
                final_tar.addfile(tarinfo=tar_info, fileobj=file)


def compress_combined_file(file_path):
    gzip_available = (
        subprocess.run(
            ["command -v gzip"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=True,
        ).returncode
        == 0
    )
    if gzip_available:
        with tarfile.open(file_path, "r") as src_tar, tarfile.open(
            f"{file_path}.gz", "w:gz"
        ) as dest_tar:
            for member in src_tar.getmembers():
                dest_tar.addfile(member, src_tar.extractfile(member))
        os.remove(file_path)
        return f"{file_path}.gz"
    else:
        return file_path


def read_hosts_file(file_path):
    with open(file_path, "r") as file:
        hosts = [line.strip() for line in file.readlines()]
    return hosts


def parse_hosts_list(hosts_str):
    return [host.strip() for host in hosts_str.split(",")]


def get_pods_by_labels(labels, namespace):
    result = subprocess.run(
        ["kubectl", "get", "pods", "-n", namespace, "-l", labels, "-o", "json"],
        capture_output=True,
        text=True,
        check=True,
    )
    pod_list = json.loads(result.stdout)
    return [pod["metadata"]["name"] for pod in pod_list["items"]]


# SSH functions


def build_ssh_options(username=None, password=None, ignore_host_key=False):
    ssh_options = []
    if ignore_host_key:
        ssh_options.extend(
            ["-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null"]
        )
    if username:
        ssh_options.extend(["-l", username])
    if password:
        ssh_options.extend(
            [
                "-o",
                "PasswordAuthentication=yes",
                "-o",
                f'PasswordAuthentication="{password}"',
            ]
        )
    return ssh_options


def execute_script_on_host_ssh(
    host, script, username=None, password=None, ignore_host_key=False
):
    remote_dir = f"/tmp/{uuid.uuid4()}"
    remote_script = f"{remote_dir}/{os.path.basename(script)}"
    remote_output_tar = f"{remote_dir}/output.tar.gz"

    ssh_options = build_ssh_options(username, password, ignore_host_key)

    subprocess.run(["ssh"] + ssh_options + [host, "mkdir", remote_dir])
    subprocess.run(["scp"] + ssh_options + [script, f"{host}:{remote_script}"])
    subprocess.run(["ssh"] + ssh_options + [host, "chmod", "+x", remote_script])
    subprocess.run(
        ["ssh"] + ssh_options + [host, f"cd {remote_dir} && {remote_script}"]
    )
    subprocess.run(
        ["ssh"]
        + ssh_options
        + [host, f"cd {remote_dir} && tar czf {remote_output_tar} ."]
    )
    subprocess.run(
        ["scp"] + ssh_options + [f"{host}:{remote_output_tar}", f"{host}_output.tar.gz"]
    )
    subprocess.run(["ssh"] + ssh_options + [host, "rm", "-r", remote_dir])

    return f"{host}_output.tar.gz"


# kubectl functions


def execute_script_on_host_kubectl(host, script, namespace):
    remote_dir = f"/tmp/{uuid.uuid4()}"
    remote_script = f"{remote_dir}/{os.path.basename(script)}"
    remote_output_tar = f"{remote_dir}/output.tar.gz"

    subprocess.run(
        ["kubectl", "exec", host, "-n", namespace, "--", "mkdir", remote_dir]
    )
    subprocess.run(["kubectl", "cp", script, f"{namespace}/{host}:{remote_script}"])
    subprocess.run(
        ["kubectl", "exec", host, "-n", namespace, "--", "chmod", "+x", remote_script]
    )
    subprocess.run(
        [
            "kubectl",
            "exec",
            host,
            "-n",
            namespace,
            "--",
            "sh",
            "-c",
            f"cd {remote_dir} && {remote_script}",
        ]
    )
    subprocess.run(
        [
            "kubectl",
            "exec",
            host,
            "-n",
            namespace,
            "--",
            "sh",
            "-c",
            f"cd {remote_dir} && tar czf {remote_output_tar} .",
        ]
    )
    subprocess.run(
        [
            "kubectl",
            "cp",
            f"{namespace}/{host}:{remote_output_tar}",
            f"{host}_output.tar.gz",
        ]
    )
    subprocess.run(
        ["kubectl", "exec", host, "-n", namespace, "--", "rm", "-r", remote_dir]
    )

    return f"{host}_output.tar.gz"


# Main functions


def ssh(args):
    if args.hosts_file:
        hosts = read_hosts_file(args.hosts_file)
    elif args.hosts_list:
        hosts = parse_hosts_list(args.hosts_list)

    individual_tar_files = []
    for host in hosts:
        tar_file = execute_script_on_host_ssh(host, args.script)
        individual_tar_files.append(tar_file)

    combined_tar_file = "combined_results.tar"
    combine_tar_files(individual_tar_files, combined_tar_file)

    for tar_file in individual_tar_files:
        os.remove(tar_file)

    compressed_file = compress_combined_file(combined_tar_file)
    print(f"Combined results saved in {compressed_file}")


def kubectl(args):
    hosts = get_pods_by_labels(args.labels, args.namespace)

    individual_tar_files = []
    for host in hosts:
        tar_file = execute_script_on_host_kubectl(host, args.script, args.namespace)
        individual_tar_files.append(tar_file)

    combined_tar_file = "combined_results.tar"
    combine_tar_files(individual_tar_files, combined_tar_file)

    for tar_file in individual_tar_files:
        os.remove(tar_file)

    compressed_file = compress_combined_file(combined_tar_file)
    print(f"Combined results saved in {compressed_file}")


def configure_arg_parser(parser):
    subparsers = parser.add_subparsers()
    ssh_parser = subparsers.add_parser(
        "ssh", help="Use SSH to execute the script on remote hosts."
    )
    ssh_parser.add_argument(
        "--hosts-file",
        type=str,
        help="Path to the file containing a list of hosts (one per line)",
    )
    ssh_parser.add_argument(
        "--hosts-list", type=str, help="Comma-separated list of hosts"
    )
    ssh_parser.add_argument(
        "--script",
        type=str,
        required=True,
        help="Path to the script to run on each host",
    )
    ssh_parser.add_argument(
        "--username", type=str, help="Username for SSH authentication"
    )
    ssh_parser.add_argument(
        "--password", type=str, help="Password for SSH authentication"
    )
    ssh_parser.add_argument(
        "--ignore-host-key",
        action="store_true",
        help="Ignore SSH host key verification",
    )

    ssh_parser.set_defaults(func=ssh)

    kubectl_parser = subparsers.add_parser(
        "kubectl", help="Use kubectl to execute the script on Kubernetes Pods."
    )
    kubectl_parser.add_argument(
        "--labels",
        type=str,
        required=True,
        help='Comma-separated list of Kubernetes labels in the format "key=value"',
    )
    kubectl_parser.add_argument(
        "--namespace",
        type=str,
        required=True,
        help="Kubernetes namespace where the Pods are located",
    )
    kubectl_parser.add_argument(
        "--script",
        type=str,
        required=True,
        help="Path to the script to run on each Pod",
    )
    kubectl_parser.set_defaults(func=kubectl)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Execute a script on multiple remote hosts or Kubernetes Pods and collect the results."
    )
    configure_arg_parser(parser)

    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()
