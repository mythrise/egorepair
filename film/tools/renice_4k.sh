#!/bin/bash
# lower the priority of the 4K pipeline (and every descendant) so a fast render can take the CPU
roots=$(ps -eo pid,args | grep -E "render_all.sh 3840|queue_b.sh|finish.sh" | grep -v grep | awk '{print $1}')
all="$roots"; frontier="$roots"
while [ -n "$frontier" ]; do next=""; for p in $frontier; do c=$(ps -o pid= --ppid $p); next="$next $c"; done; all="$all $next"; frontier=$(echo $next); done
renice -n 19 -p $all > /dev/null 2>&1
echo "reniced $(echo $all | wc -w) processes"
