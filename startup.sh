#!/bin/bash

# Create logs dir
mkdir -p $LOG_DIR

# Start redis server
redis-server > $LOG_DIR/redis.log &
touch $LOG_DIR/monitor_mic.log
# Start monitors running NuPIC
./start_metrics.py > $LOG_DIR/processes.log &

# Start Go server
cd server
if [ -z "$TAIL" ]; then
	exec ./server > $LOG_DIR/martini.log
else	
	./server > $LOG_DIR/martini.log &
	tail -F $LOG_DIR/*
fi