#!/bin/bash

export JVM_ARGS="--add-opens=java.base/java.nio=ALL-UNNAMED \
                 --add-opens=java.base/sun.nio.ch=ALL-UNNAMED \
                 -Xmx2g -Xms1g"

echo "Starting JMeter worker: ${HOSTNAME}"
echo "Threads: ${THREADS_PER_WORKER:-50}"
echo "Pool Size: ${POOL_SIZE:-50}"
echo "Duration: ${DURATION:-600} seconds"
echo "Mode: CONTINUOUS LOOP"

SF_HOST=$(echo "${SNOWFLAKE_JDBC_URL}" | sed 's|jdbc:snowflake://||' | sed 's|/.*||')
echo "Checking connectivity to ${SF_HOST}..."

while true; do
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "https://${SF_HOST}/session/v1/login-request" 2>/dev/null || echo "000")
    if [ "${HTTP_CODE}" != "000" ]; then
        echo "Connectivity OK (HTTP ${HTTP_CODE}) at $(date)"
        break
    fi
    echo "Connectivity check failed. Retrying in 10 seconds..."
    sleep 10
done

RUN_COUNT=0

while true; do
    RUN_COUNT=$((RUN_COUNT + 1))
    RESULTS_FILE="/results/worker_${HOSTNAME}_run${RUN_COUNT}.jtl"
    
    echo ""
    echo "========== Starting Run #${RUN_COUNT} =========="
    echo "Time: $(date)"
    
    jmeter -n \
        -t /jmeter/test.jmx \
        -Jsnowflake.url="${SNOWFLAKE_JDBC_URL}" \
        -Jsnowflake.username="${SNOWFLAKE_USER}" \
        -Jsnowflake.password="${SNOWFLAKE_PASSWORD}" \
        -Jsnowflake.poolMax=${POOL_SIZE:-50} \
        -Jsnowflake.threads=${THREADS_PER_WORKER:-50} \
        -Jtest.duration=${DURATION:-600} \
        -l ${RESULTS_FILE} || true
    
    echo "Run #${RUN_COUNT} completed at $(date)"
    
    if [ -f "${RESULTS_FILE}" ]; then
        REQUESTS=$(($(wc -l < "${RESULTS_FILE}") - 1))
        echo "Requests in this run: ${REQUESTS}"
    fi
    
    echo "Restarting test in 5 seconds..."
    sleep 5
done
