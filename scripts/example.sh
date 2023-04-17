echo $(host -a) > host.log
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
cp /var/log/dpkg.log $SCRIPT_DIR
