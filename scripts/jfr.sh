#!/usr/bin/env bash
#
# Triggers a JFR on this node

function check_java {
    JVM=$(/usr/bin/java -version 2>&1 | grep -A 1 '[openjdk|java] version' | awk 'NR==2 {print $1}') 
    echo "JVM type: $JVM"
    if [ "$JVM" == 'Java(TM)' ]; then
        echo "Oracle Java found... proceeding"
    else
        echo "Oracle java is currently the only JDK that supports JFR"
        exit
    fi
}

function check_jfr {
    $JCMD $PROCPID JFR.check 
}

function start_jfr {
    $JCMD $PROCPID VM.unlock_commercial_features
    $JCMD $PROCPID JFR.start name=$JFRNAME settings=profile dumponexit=true duration="$DURATION"s
}

function stop_jfr {
    $JCMD $PROCPID JFR.stop name=$JFRNAME
}

function dump_jfr {
    $JCMD $PROCPID JFR.dump name=$JFRNAME filename=$JFRFILE 
}

TIMESTAMP=$(date '+%Y-%m-%d_%H-%M-%S')
DURATION=60
BASE_DIR=$(pwd)
NODE=$(hostname)
INTERVAL=10
JFRNAME="$NODE-DR_JFR"
PROCPID=$(ps -ef | grep -E "(dremio.*server|DremioDaemon)" | grep -vE "grep|preview" | awk '{print $2}')
PROCUSER="dremio"
JFRFILE="$BASE_DIR/$TIMESTAMP-$NODE-$PROCPID.jfr"
JCMD=$(which jcmd)

# Running - we dont need to check the java version
# since JFR should be supported i later versions of
# open JDK (so we dont use the check_java function)

# Start JFR
start_jfr
pwd

# Wait for duration then dump / stop
# We dont need to stop the JFR if we dump it
sleep $DURATION
dump_jfr
pwd
exit
