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
import subprocess
import tarfile
from getpass import getpass
from pathlib import Path
from threading import Thread, Lock


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Run a script on multiple hosts and collect output."
    )
    parser.add_argument(
        "script", help="Path to the script file to run on hosts.")
    parser.add_argument(
        "--hosts", help="Comma-separated list of hosts (e.g., 'host1,host2')."
    )
    parser.add_argument(
        "--hosts-file", help="File containing a list of hosts, one per line."
    )
    parser.add_argument("--username", help="Username for SSH authentication.")
    parser.add_argument(
        "--use-key",
        action="store_true",
        help="Use key-based authentication (default: False).",
    )
    parser.add_argument(
        "--shell",
        default="bash",
        choices=["bash", "zsh", "sh"],
        help="Shell to use for running the script (default: bash).",
    )
    parser.add_argument(
        "--script-args", nargs=argparse.REMAINDER, help="Arguments for the script"
    )

    args = parser.parse_args()
    args.password = None
    if not args.use_key:
        args.password = getpass.getpass("Enter password: ")
    return args


def load_hosts_from_file(hosts_file):
    with open(hosts_file, "r") as f:
        return [line.strip() for line in f.readlines()]


class Carrier:
    def __init__(
        self, script, hosts, username, password, use_key, shell, script_args=[]
    ):
        self.script = script
        self.hosts = hosts
        self.username = username
        self.password = password
        self.use_key = use_key
        self.shell = shell
        self.script_args = script_args
        self.output_archive = "output.tar.gz"
        self.log_file = "debug.log"
        self.log_lock = Lock()

    def run_cmd(self, cmd):
        with self.log_lock:
            with open(self.log_file, "a") as log:
                subprocess.run(
                    cmd, shell=True, check=True, stdout=log, stderr=subprocess.STDOUT
                )

    def ssh_cmd(self, host, cmd):
        base_cmd = f"ssh -o 'StrictHostKeyChecking no' -o 'UserKnownHostsFile /dev/null' -q {self.username}@{host}"
        if self.use_key:
            base_cmd += " "
        else:
            base_cmd += f' -t "echo {self.password} | sudo -S {cmd}"'
        return base_cmd

    def scp_cmd(self, src, dest):
        return f"scp -q -o 'StrictHostKeyChecking no' -o 'UserKnownHostsFile /dev/null' {src} {self.username}@{dest}"

    def run_script_on_host(self, host):
        host_tmp_dir = f"{host}_tmp"
        create_tmp_dir_cmd = self.ssh_cmd(host, f"mkdir -p {host_tmp_dir}")
        self.run_cmd(create_tmp_dir_cmd)

        copy_script_cmd = self.scp_cmd(
            self.script, f"{host}:{host_tmp_dir}/{Path(self.script).name}"
        )
        self.run_cmd(copy_script_cmd)

        script_args_str = " ".join(self.script_args)
        run_script_cmd = self.ssh_cmd(
            host,
            f"{self.shell} {host_tmp_dir}/{Path(self.script).name} {script_args_str}",
        )
        self.run_cmd(run_script_cmd)

        collect_files_cmd = self.ssh_cmd(
            host,
            f"tar -czf {host_tmp_dir}/{host}.tar.gz --exclude={host}.tar.gz --exclude={Path(self.script).name}-C {host_tmp_dir}/ .",
        )
        self.run_cmd(collect_files_cmd)

        copy_back_cmd = self.scp_cmd(
            f"{host}:{host_tmp_dir}/{host}.tar.gz", f"{host}.tar.gz"
        )
        self.run_cmd(copy_back_cmd)

    def run(self):
        threads = []
        for host in self.hosts:
            t = Thread(target=self.run_script_on_host, args=(host,))
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

        with tarfile.open(self.output_archive, "w:gz") as big_archive:
            for host in self.hosts:
                big_archive.add(f"{host}.tar.gz", arcname=f"{host}.tar.gz")
                os.remove(f"{host}.tar.gz")

        return f"All done! The final archive is {self.output_archive}"


def main():
    args = parse_arguments()

    if args.hosts:
        hosts = args.hosts.split(",")
    elif args.hosts_file:
        hosts = load_hosts_from_file(args.hosts_file)
    else:
        raise ValueError("Either --hosts or --hosts-file must be provided.")

    runner = Carrier(
        args.script,
        hosts,
        args.username,
        args.password,
        args.use_key,
        args.shell,
        args.script_args,
    )
    result = runner.run()
    print(result)


if __name__ == "__main__":
    main()
