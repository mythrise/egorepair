#!/bin/bash
# usage: pause_4k.sh STOP|CONT  — suspend/resume the whole 4K pipeline tree
roots=$(ps -eo pid,args | grep -E "render_all.sh 3840|queue_b.sh|finish.sh" | grep -v grep | awk '{print $1}')
all="$roots"; frontier="$roots"
while [ -n "$frontier" ]; do next=""; for p in $frontier; do c=$(ps -o pid= --ppid $p); next="$next $c"; done; all="$all $next"; frontier=$(echo $next); done
kill -$1 $all 2>/dev/null
echo "$1 sent to $(echo $all | wc -w) processes"
