# Implementation Plan: Kafka Streaming (Snowpipe Streaming V2) into Interactive Tables

## Overview

This plan introduces **write ingestion** via Kafka + Snowpipe Streaming V2 into the existing Interactive Table POC.
The existing POC performs high-concurrency **reads** from an interactive table using JMeter on Kubernetes.
This extension adds a Kafka-based streaming pipeline that **writes** ~25MB of data at 6-7K events/second
into the same interactive table, enabling a concurrent read+write demo.

**Reference**: [Snowflake Quickstart - Kafka Interactive Tables Streaming](https://www.snowflake.com/en/developers/guides/kafka-interactive-tables-streaming/)

---

## Architecture

```
┌─────────────────────┐     ┌──────────────────┐     ┌──────────────────────────────────┐
│  Python Data        │────▶│  Apache Kafka     │────▶│  Snowflake Kafka Connector       │
│  Generator          │     │  (KRaft Mode)     │     │  (Snowpipe Streaming v2)         │
│  (6-7K events/sec)  │     │  Topic:orders_data│     │  tasks.max=3                     │
└─────────────────────┘     └──────────────────┘     └───────────────┬──────────────────┘
                                                                     │
                                                                     ▼
┌─────────────────────┐     ┌──────────────────────────────────────────────────────────┐
│  JMeter Read Test   │────▶│  INTERACTIVE_DEMO.TPCH_INTERACTIVE.ORDERS_INTERACTIVE    │
│  (EKS / Local)      │     │  Interactive Table | 1.44B rows | 76GB | 27 NUMBER cols  │
│  TPCH_INTERACTIVE_WH│     │  Clustered on (CR_RETURNED_DATE_SK, cr_item_sk)          │
└─────────────────────┘     └──────────────────────────────────────────────────────────┘
```

---

## Target Snowflake Objects

| Object | Value |
|--------|-------|
| Database | `INTERACTIVE_DEMO` |
| Schema | `TPCH_INTERACTIVE` |
| Table | `ORDERS_INTERACTIVE` (Interactive, 27 NUMBER columns) |
| Warehouse | `TPCH_INTERACTIVE_WH` (Interactive, Small, 10 clusters) |
| Kafka User | `KAFKA_USER` (RSA key pair auth) |
| Kafka Role | `KAFKA_CONNECTOR_ROLE` |

## Table Schema (27 columns, all NUMBER)

| Column | Type |
|--------|------|
| CR_RETURNED_DATE_SK | NUMBER(38,0) |
| CR_RETURNED_TIME_SK | NUMBER(38,0) |
| CR_ITEM_SK | NUMBER(38,0) |
| CR_REFUNDED_CUSTOMER_SK | NUMBER(38,0) |
| CR_REFUNDED_CDEMO_SK | NUMBER(38,0) |
| CR_REFUNDED_HDEMO_SK | NUMBER(38,0) |
| CR_REFUNDED_ADDR_SK | NUMBER(38,0) |
| CR_RETURNING_CUSTOMER_SK | NUMBER(38,0) |
| CR_RETURNING_CDEMO_SK | NUMBER(38,0) |
| CR_RETURNING_HDEMO_SK | NUMBER(38,0) |
| CR_RETURNING_ADDR_SK | NUMBER(38,0) |
| CR_CALL_CENTER_SK | NUMBER(38,0) |
| CR_CATALOG_PAGE_SK | NUMBER(38,0) |
| CR_SHIP_MODE_SK | NUMBER(38,0) |
| CR_WAREHOUSE_SK | NUMBER(38,0) |
| CR_REASON_SK | NUMBER(38,0) |
| CR_ORDER_NUMBER | NUMBER(38,0) |
| CR_RETURN_QUANTITY | NUMBER(38,0) |
| CR_RETURN_AMOUNT | NUMBER(7,2) |
| CR_RETURN_TAX | NUMBER(7,2) |
| CR_RETURN_AMT_INC_TAX | NUMBER(7,2) |
| CR_FEE | NUMBER(7,2) |
| CR_RETURN_SHIP_COST | NUMBER(7,2) |
| CR_REFUNDED_CASH | NUMBER(7,2) |
| CR_REVERSED_CHARGE | NUMBER(7,2) |
| CR_STORE_CREDIT | NUMBER(7,2) |
| CR_NET_LOSS | NUMBER(7,2) |

## Data Size Math

- ~550-600 bytes per JSON record (27 numeric fields)
- 25MB ≈ ~45,000-50,000 records
- At 6,500 events/sec → ~7-8 seconds of generation

---

## New Directory Structure

```
Snowflake_Interactive_WH_POC/
├── implementation_plan.md      ← THIS FILE
├── jmx/                        (existing - modified)
│   ├── Snowflake_Performance_Test_V2.jmx
│   ├── snowflake.properties
│   └── ...
├── k8s/                        (existing - modified)
│   ├── k8s-deployment.yaml
│   └── ...
├── reports/                    (existing)
└── kafka_streaming/            ← NEW
    ├── docker-compose.yml
    ├── Dockerfile.connect
    ├── requirements.txt
    ├── snowflake_setup.sql
    ├── generate_orders_data.py
    ├── send_message.py
    └── deploy_connector.sh
```

---

## Step-by-Step Implementation

### Step 1: Snowflake Setup (`kafka_streaming/snowflake_setup.sql`)

Run in Snowsight as ACCOUNTADMIN:

1. Create `KAFKA_CONNECTOR_ROLE` with INSERT privileges on the existing table
2. Create `KAFKA_USER` with RSA key pair authentication
3. Grant USAGE on database/schema, INSERT on table
4. Generate RSA key pair locally:
   ```bash
   openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out rsa_key.p8 -nocrypt
   openssl rsa -in rsa_key.p8 -pubout -out rsa_key.pub
   ```
5. Assign public key to user via `ALTER USER KAFKA_USER SET RSA_PUBLIC_KEY='...'`

### Step 2: Start Local Kafka (`kafka_streaming/docker-compose.yml`)

```bash
cd kafka_streaming
mkdir -p keys connect-config
cp /path/to/rsa_key.p8 keys/
docker compose up -d
docker compose ps  # verify both services healthy
```

### Step 3: Create Kafka Topic

```bash
docker exec -it kafka kafka-topics --create \
  --topic orders_data \
  --bootstrap-server localhost:9092 \
  --partitions 3 \
  --replication-factor 1
```

### Step 4: Deploy Kafka Connector (`kafka_streaming/deploy_connector.sh`)

```bash
export SNOWFLAKE_ACCOUNT="your-account-identifier"
bash deploy_connector.sh
# Verify: curl -s http://localhost:8083/connectors/snowflake-orders/status | python3 -m json.tool
```

Key connector config:
- `snowflake.ingestion.method`: `SNOWPIPE_STREAMING`
- `snowflake.streaming.v2.enabled`: `true`
- `snowflake.enable.schematization`: `TRUE`
- `snowflake.topic2table.map`: `orders_data:ORDERS_INTERACTIVE`
- `buffer.flush.time`: `1` (1 sec flush for near-real-time)
- `buffer.count.records`: `10000`

### Step 5: Test with Single Message

```bash
pip install kafka-python confluent-kafka
python send_message.py
# Then verify in Snowflake: SELECT COUNT(*) FROM INTERACTIVE_DEMO.TPCH_INTERACTIVE.ORDERS_INTERACTIVE
```

### Step 6: Run Full Data Generation

```bash
python generate_orders_data.py --rate 6500 --target-mb 25
```

### Step 7: Run Concurrent Read+Write Test

Terminal 1 - Start Kafka streaming:
```bash
python generate_orders_data.py --rate 6500 --duration 5
```

Terminal 2 - Start JMeter read test:
```bash
jmeter -n -t ../jmx/Snowflake_Performance_Test_V2.jmx -q ../jmx/snowflake.properties -l results.jtl
```

---

## JMeter Modifications

### `jmx/Snowflake_Performance_Test_V2.jmx`
- Line 110: `FROM DEMO.DEMO.ORDERS_INTERACTIVE` → `FROM INTERACTIVE_DEMO.TPCH_INTERACTIVE.ORDERS_INTERACTIVE`

### `jmx/snowflake.properties`
- Line 5: Update JDBC URL to `warehouse=TPCH_INTERACTIVE_WH&db=INTERACTIVE_DEMO&schema=TPCH_INTERACTIVE`

### `k8s/k8s-deployment.yaml`
- Line 13 (Secret): Update JDBC URL to new warehouse/db/schema
- Line 81 (ConfigMap inline JMX): Update table reference in query

---

## Verification Checklist

- [ ] `snowflake_setup.sql` executed successfully
- [ ] `DESC USER KAFKA_USER` shows RSA_PUBLIC_KEY fingerprint
- [ ] `docker compose ps` shows both kafka and kafka-connect healthy
- [ ] `kafka-topics --describe --topic orders_data` shows 3 partitions
- [ ] Connector status shows all 3 tasks RUNNING
- [ ] `send_message.py` successfully sends a test record
- [ ] Test record appears in `ORDERS_INTERACTIVE` within ~10 seconds
- [ ] `generate_orders_data.py` achieves target rate of 6-7K events/sec
- [ ] ~25MB of data ingested successfully
- [ ] JMeter queries work with updated table/warehouse references
- [ ] Concurrent read+write test runs without errors
