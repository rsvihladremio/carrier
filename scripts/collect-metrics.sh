#!/usr/bin/env bash
#
# Script to pull OS and JVM info

function useage {
    echo
    echo "Usage: $0 <interval> <count>"
    echo
    echo "Example: $0 10 30 - (runs every 10 seconds until 30 runs have completed)"
    echo "Example: $0 10 -1 - (runs continuously, every 10 seconds)"
    echo "Example: $0 <no args> - (runs just once)"
    echo
    echo "Note: this script attempts to run as current user"
    echo "you can force this below by setting DR_USER if you wish"
    echo
    exit
}

# Find the SJK tool, if its not there, download the binary. For more info on the SJK see: https://github.com/aragozin/jvm-tools
function find_sjk {
    if [ ! -f $SJK ]; then
        echo "SJK not found, attempting to download ..."
        wget "https://repository.sonatype.org/service/local/artifact/maven/redirect?r=central-proxy&g=org.gridkit.jvmtool&a=sjk-plus&v=LATEST" -O $SJK
    fi
}

function run_threaddump {
    echo ">>> $(date '+%Y-%m-%d_%H:%M:%S') ... running thread dump"
    echo ">>> $(date '+%Y-%m-%d_%H:%M:%S') ... running thread dump" >> $TD_LOG
    sudo -u $DR_USER $JSTACK -l $DR_PID >> $TD_LOG
}

# Run the SJK ttop output sorted by thread CPU usage
function run_cpu_ttop {
   echo ">>> $(date '+%Y-%m-%d_%H:%M:%S') ... running ttop (CPU)"
   sudo -u $DR_USER $JAVA $SJK ttop -o CPU -n 50 -p $DR_PID >> $TTOP_CPU_LOG &
}

# Run the SJK ttop output sorted by thread ALLOC (iheap memory allocation) usage
function run_alloc_ttop {
   echo ">>> $(date '+%Y-%m-%d_%H:%M:%S') ... running ttop (ALLOC)"
   sudo -u $DR_USER $JAVA $SJK ttop -o ALLOC -n 50 -p $DR_PID >> $TTOP_ALLOC_LOG &
}

function kill_ttop {
    for PID in $(ps -ef | grep ttop | grep -v grep | awk '{print $2}')
    do
        echo ">>> $(date '+%Y-%m-%d_%H:%M:%S') ... Killing ttop process $PID"
        sudo -u $DR_USER kill $PID
    done
}

function run_top_once {
    echo ">>> $(date '+%Y-%m-%d_%H:%M:%S') ... running top for pid $DR_PID"
    echo ">>> $(date '+%Y-%m-%d_%H:%M:%S') ... running top for pid $DR_PID"  >> $LOG
    top -b -n 1 -p $DR_PID >> $LOG
}

function run_iostat_once {
   echo ">>> $(date '+%Y-%m-%d_%H:%M:%S') ... running iostat"
   echo ">>> $(date '+%Y-%m-%d_%H:%M:%S') ... running iostat" >> $LOG
   iostat -c -d -t -x 1 1 >> $LOG
}

function run_vmstat_once {
   echo ">>> $(date '+%Y-%m-%d_%H:%M:%S') ... running vmstat"
   echo ">>> $(date '+%Y-%m-%d_%H:%M:%S') ... running VMstat" >> $LOG
   vmstat -w >> $LOG
}

function run_netstat {
   echo ">>> $(date '+%Y-%m-%d_%H:%M:%S') ... running netstat"
   echo ">>> $(date '+%Y-%m-%d_%H:%M:%S') ... running netstat" >> $LOG
   netstat -s >> $LOG
}

function run_lsof {
   echo ">>> $(date '+%Y-%m-%d_%H:%M:%S') ... running lsof"
   echo ">>> $(date '+%Y-%m-%d_%H:%M:%S') ... running lsof" >> $LOG
   lsof -p $DR_PID >> $LOG
}

function run_proc {
   echo ">>> $(date '+%Y-%m-%d_%H:%M:%S') ... running cat proc"
   echo ">>> $(date '+%Y-%m-%d_%H:%M:%S') ... running cat proc" >> $LOG
   sudo cat /proc/$DR_PID/net/sockstat >> $LOG
   echo " " >> $LOG
   sudo cat /proc/$DR_PID/status >> $LOG
}


if [ $# -ne 0 ] && [ $# -ne 2 ]; then
    useage
    exit
fi

# Configuration
#
# Set things like Dremio PID here
# for example you might use:
#
# $(cat /var/run/dremio.pid)
#
# Also other things like file location,
# date format, file names and such
#
# Also remember to set DR_USER to the user
# that runs the dremio process (not always the login user)

NODE=$(hostname)
DATE=$(date '+%Y-%m-%d_%H-%M-%S')
MONDIR="/tmp"
if [ $# -ne 0 ]; then
    DELAY=$1
    COUNT=$2
else
    DELAY=1
    COUNT=1
fi
DR_PID=$(ps -ef | grep -E "dremio.*server" | grep -vE "grep|preview" | awk '{print $2}')
DR_USER=dremio
LOG="$MONDIR/$NODE-$DATE-monitor-$DR_PID.out"
TD_LOG="$MONDIR/$NODE-$DATE-monitor-thread-dump-$DR_PID.out"
TTOP_CPU_LOG="$MONDIR/$NODE-$DATE-monitor-ttop-cpu-$DR_PID.out"
TTOP_ALLOC_LOG="$MONDIR/$NODE-$DATE-monitor-ttop-alloc-$DR_PID.out"
export PATH=$PATH:$JAVA_HOME/bin
JSTACK=$(which jstack)
JAVA=$(which java)" -jar "
SJK="/tmp/sjk-plus-0.19.jar"

# Main control
#
# This is where we call functions
# to run commands to get diagnostics

# Run the ttop commands first in the background
# these will continue running until they are killed
# if you CTRL+C this script you will have to kill
# ttop manually

echo "Checking presence of SJK"
find_sjk
echo "Running monitor script... please check sjk is not still running after with \"ps -ef | grep ttop\""
run_cpu_ttop
run_alloc_ttop

# Execute loop to run regular commands
# typically sjk and thread dumps
# in addition to some OS level commands
#
# Note using a negative value for the count
# means the script will run indefinitely

if [ $COUNT -lt 0 ]; then
    while true
    do
        echo "Running continuously"
        run_proc
        run_top_once
        run_iostat_once
        run_vmstat_once
        run_threaddump
        run_netstat
        run_lsof
        sleep $DELAY
    done
else

    for loop in $(seq $COUNT)
    do
        echo "Running iteration $loop of $COUNT"
        run_proc
        run_top_once
        run_iostat_once
        run_vmstat_once
        run_threaddump
        run_netstat
        run_lsof
        sleep $DELAY
    done
fi

# Clean up ttop processes and exit
kill_ttop
echo "Exiting monitor script ... please find outputs in $MONDIR"
exit
