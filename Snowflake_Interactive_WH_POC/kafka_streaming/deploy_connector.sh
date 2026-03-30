#!/usr/bin/env bash
# Deploy the Snowflake Kafka Connector for Snowpipe Streaming v2
# into INTERACTIVE_DEMO.TPCH_INTERACTIVE.ORDERS_INTERACTIVE
#
# Prerequisites:
#   1. Kafka and Kafka Connect are running (docker compose up -d)
#   2. RSA private key is at keys/rsa_key.p8
#   3. SNOWFLAKE_ACCOUNT env var is set
#
# Usage:
#   export SNOWFLAKE_ACCOUNT="your-account-identifier"
#   bash deploy_connector.sh

set -euo pipefail

if [ -z "${SNOWFLAKE_ACCOUNT:-}" ]; then
    echo "ERROR: SNOWFLAKE_ACCOUNT environment variable is not set."
    echo "Set it to your Snowflake account identifier (e.g., orgname-acctname)"
    exit 1
fi

if [ ! -f keys/rsa_key.p8 ]; then
    echo "ERROR: RSA private key not found at keys/rsa_key.p8"
    echo "Generate one with:"
    echo "  openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out keys/rsa_key.p8 -nocrypt"
    exit 1
fi

PRIVATE_KEY=$(grep -v "BEGIN\|END" keys/rsa_key.p8 | tr -d '\n')

echo "Creating Kafka topic 'orders_data'..."
docker exec kafka kafka-topics --create \
    --topic orders_data \
    --bootstrap-server localhost:9092 \
    --partitions 3 \
    --replication-factor 1 \
    --if-not-exists

echo "Deploying Snowflake connector..."
curl -s -X POST http://localhost:8083/connectors \
    -H "Content-Type: application/json" \
    -d '{
    "name": "snowflake-orders",
    "config": {
        "connector.class": "com.snowflake.kafka.connector.SnowflakeStreamingSinkConnector",
        "tasks.max": "3",
        "topics": "orders_data",
        "snowflake.url.name": "'"${SNOWFLAKE_ACCOUNT}"'.snowflakecomputing.com",
        "snowflake.user.name": "KAFKA_USER",
        "snowflake.private.key": "'"${PRIVATE_KEY}"'",
        "snowflake.database.name": "INTERACTIVE_DEMO",
        "snowflake.schema.name": "TPCH_INTERACTIVE",
        "snowflake.role.name": "KAFKA_CONNECTOR_ROLE",
        "snowflake.ingestion.method": "SNOWPIPE_STREAMING",
        "snowflake.enable.schematization": "TRUE",
        "snowflake.topic2table.map": "orders_data:ORDERS_INTERACTIVE",
        "key.converter": "org.apache.kafka.connect.storage.StringConverter",
        "value.converter": "org.apache.kafka.connect.json.JsonConverter",
        "value.converter.schemas.enable": "false",
        "buffer.flush.time": "1",
        "buffer.count.records": "10000",
        "buffer.size.bytes": "20000000",
        "errors.tolerance": "all",
        "errors.log.enable": "true",
        "snowflake.streaming.enable.altering.target.pipes.tables": "false",
        "snowflake.streaming.v2.enabled": "true"
    }
}' | python3 -m json.tool

echo ""
echo "Waiting 10 seconds for connector to initialize..."
sleep 10

echo "Checking connector status..."
curl -s http://localhost:8083/connectors/snowflake-orders/status | python3 -m json.tool
