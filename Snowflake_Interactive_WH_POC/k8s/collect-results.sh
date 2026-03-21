#!/bin/bash

NAMESPACE="jmeter-test"
OUTPUT_DIR="./results"
DURATION=180

mkdir -p ${OUTPUT_DIR}

echo "============================================"
echo "Collecting Results from K8s Pods"
echo "============================================"

PODS=$(kubectl get pods -n ${NAMESPACE} -l app=jmeter-worker -o jsonpath='{.items[*].metadata.name}')

total_requests=0
for pod in ${PODS}; do
    echo "Collecting from ${pod}..."
    kubectl cp ${NAMESPACE}/${pod}:/results/ ${OUTPUT_DIR}/${pod}/ 2>/dev/null || true
    
    if [ -f "${OUTPUT_DIR}/${pod}/worker_${pod}.jtl" ]; then
        count=$(($(wc -l < "${OUTPUT_DIR}/${pod}/worker_${pod}.jtl") - 1))
        total_requests=$((total_requests + count))
        avg=$(awk -F',' 'NR>1 {sum+=$2; c++} END{printf "%.0f", sum/c}' "${OUTPUT_DIR}/${pod}/worker_${pod}.jtl")
        tp=$(echo "scale=1; $count / $DURATION" | bc)
        echo "  ${pod}: ${count} requests, ${avg}ms avg, ${tp} req/s"
    fi
done

echo ""
echo "============================================"
echo "AGGREGATE RESULTS"
echo "============================================"
throughput=$(echo "scale=1; $total_requests / $DURATION" | bc)
echo "Total Requests: ${total_requests}"
echo "Total Throughput: ${throughput} req/sec"
echo "============================================"
