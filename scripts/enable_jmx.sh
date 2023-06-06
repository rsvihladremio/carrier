#!/usr/bin/env bash
#
# Enables JMX on node

ENV_FILE="/opt/dremio/conf/dremio-env"
TELEMETRY_FILE="/opt/dremio/conf/dremio-telemetry.yaml"

function check_jmx {
    if [ $(grep -c "com.sun.management.jmxremote" $ENV_FILE) -gt 0 ]; then
        echo "Looks like jmx config might already be enabled. Please check $ENV_FILE manually"
    else
        echo "DREMIO_JAVA_SERVER_EXTRA_OPTS=\"\$DREMIO_JAVA_SERVER_EXTRA_OPTS -Dcom.sun.management.jmxremote.port=59001\"" >>  $ENV_FILE
        echo "DREMIO_JAVA_SERVER_EXTRA_OPTS=\"\$DREMIO_JAVA_SERVER_EXTRA_OPTS -Dcom.sun.management.jmxremote.authenticate=false\"" >> $ENV_FILE
        echo "DREMIO_JAVA_SERVER_EXTRA_OPTS=\"\$DREMIO_JAVA_SERVER_EXTRA_OPTS -Dcom.sun.management.jmxremote.ssl=false\"" >> $ENV_FILE
    fi
}

function make_telemetry_file {
    cat > $TELEMETRY_FILE << EOF
#
# Copyright (C) 2017-2019 Dremio Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#


auto-reload:
  enabled: True
  period: 100
  unit: MILLISECONDS

metrics:
  -
    name: kvstore
    reporter:

      type: jmx
  -
    name: jobs
    reporter:
      type: jmx
  -
    name: dremio
    reporter:
      type: jmx
  -
    name: fragments
    reporter:
      type: jmx
  -
    name: rpc
    reporter:
      type: jmx
  -
    name: reflections
    reporter:
      type: jmx
  -
    name: com.dremio
    reporter:
      type: jmx
  -
    name: gc
    reporter:
      type: jmx
  -
    name: buffer-pool
    reporter:
      type: jmx
  -
    name: memory
    reporter:
      type: jmx
  -
    name: threads
    reporter:
      type: jmx
  -
    name: rpcbit
    reporter:
      type: jmx
EOF
}

# Check for root / sudo
if [ "$(id -u)" -ne 0 ]; then
     echo "Please run as root / sudo" >&2
     exit 1
fi

check_jmx
make_telemetry_file
