# carrier

![Build Status](https://github.com/rsvihladremio/carrier/actions/workflows/python-unit-tests.yaml/badge.svg)

carrier script that runs a script on every node you want, be it on kubernetes or over ssh
`

## SSH based carrier usage

Just need to have ssh and scp installed. Can use key based auth or a username and password.

```bash

usage: carrier.py [-h] [--hosts HOSTS] [--hosts-file HOSTS_FILE] [--username USERNAME] [--use-key]
                  [--shell {bash,zsh,sh}] [--script-args ...]
                  script

Run a script on multiple hosts and collect output.

positional arguments:
  script                Path to the script file to run on hosts.

options:
  -h, --help            show this help message and exit
  --hosts HOSTS         Comma-separated list of hosts (e.g., 'host1,host2').
  --hosts-file HOSTS_FILE
                        File containing a list of hosts, one per line.
  --username USERNAME   Username for SSH authentication.
  --use-key             Use key-based authentication (default: False).
  --shell {bash,zsh,sh}
                        Shell to use for running the script (default: bash).
  --script-args ...     Arguments for the script
```

## Kubernetes based Carrier usage

Just need to have kubectl installed and the default context setup to be the cluster you want to collect against.

```
usage: carrier_k8s.py [-h] [--script-args ...] [--namespace NAMESPACE] [--labels LABELS]
                      [--shell {bash,zsh,sh}]
                      script

Run a script on multiple pods and collect output.

positional arguments:
  script                Path to the script file to run on pods.

options:
  -h, --help            show this help message and exit
  --script-args ...     Arguments for the script
  --namespace NAMESPACE
                        Kubernetes namespace to use.
  --labels LABELS       Comma-separated list of label selectors (e.g., 'app=myapp,env=prod').
  --shell {bash,zsh,sh}
                        Shell to use for running the script (default: bash).
```