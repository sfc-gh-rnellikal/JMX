# Snowflake Interactive Warehouse Performance POC

## Objective
Achieve **1,000+ QPS** throughput against a Snowflake **Interactive Warehouse** (NEW_INT_WH) using distributed JMeter load testing on AWS EKS.

## Results Summary

| Configuration | Clusters | Peak QPS | Avg QPS | Total Queries | P50 (ms) | P99 (ms) |
|--------------|----------|----------|---------|---------------|----------|----------|
| SMALL / 8 clusters | 8 | 897.7 | ~841 | - | ~218 | ~530 |
| XSMALL / 8 clusters | 8 | 969.5 | ~883 | - | ~220 | ~478 |
| **XSMALL / 10 clusters** | **10** | **1,040.2** | **1,000.9** | **701,639** | **152** | **425** |

**Winner: XSMALL / 10 clusters** - 1,000.9 avg QPS from ACCOUNT_USAGE, perfectly balanced across all 10 clusters (~10% each).

## Test Environment

### Snowflake
- **Account**: SFPSCOGS-KAPILARORA_AWS_POLARIS_UNISTORE
- **Warehouse**: NEW_INT_WH (Interactive type, XSMALL, 10 clusters)
- **Database/Schema**: DEMO.DEMO
- **Table**: ORDERS_INTERACTIVE (75.97 GB, 1.44 billion rows)
- **Query**: Aggregation with window function, scans ~14.73 MB/query, returns ~12,381 rows (~315 KB)
- **Interactive WH Constraint**: 5-second statement timeout (built-in, not configurable)

### AWS EKS
- **Cluster**: `interactive-poc` in `ap-northeast-3` (Osaka)
- **ECR**: `087354435437.dkr.ecr.ap-northeast-3.amazonaws.com/jmeter-snowflake:latest`
- **Pods**: 15 replicas
- **Pod Resources**: 2 CPU / 3Gi request, 4 CPU / 4Gi limit
- **JMeter**: 5.6.3 with Snowflake JDBC 3.20.0 (Arrow format)

### Load Profile
- **Threads per pod**: 80 (1,200 total)
- **Connection pool per pod**: 30 (450 total connections)
- **Pool/Thread ratio**: 30/80 (decoupled to reduce S3 throttling)
- **Think time**: 50ms
- **Result cache**: OFF (USE_CACHED_RESULT=false)

## Test Methodology

1. **Resize warehouse** to target configuration (size + cluster count)
2. **Deploy 15 JMeter pods** on EKS
3. **Whitelist EKS NAT gateway IPs** in Snowflake network policy (ACCOUNT_VPN_POLICY_SE)
4. **Warmup phase (10 min)**: Run continuous queries to warm SSD cache on all cluster nodes
5. **Measured test (10 min)**: Note start time, keep pods running (no restart), checkpoints at 2, 5, 8, 10 min
6. **Collect metrics** from INFORMATION_SCHEMA.QUERY_HISTORY_BY_WAREHOUSE (5-second windows) and ACCOUNT_USAGE.QUERY_HISTORY (full period)
7. **Do NOT suspend warehouse** between warmup and measured test

### Key Learnings
- **Do NOT restart pods** between warmup and measured test - pod cycling causes connection re-establishment overhead
- **SSD cache warmup is critical** - cold cache on Interactive WH causes queries to exceed 5s timeout
- **Pool/Thread decoupling** (30 pool / 80 threads) minimizes S3 SlowDown throttling vs 1:1 ratio
- **5-second samples** for QPS measurement to stay under QUERY_HISTORY 10K result limit
- **Use COMPUTE_WH** for analytics queries to avoid contention with test warehouse

## JDBC Connection Properties
```
USE_CACHED_RESULT=false
CLIENT_SESSION_KEEP_ALIVE=true
JDBC_QUERY_RESULT_FORMAT=ARROW
CLIENT_PREFETCH_THREADS=1
CLIENT_RESULT_CHUNK_SIZE=16
CLIENT_MEMORY_LIMIT=2048
CLIENT_OUT_OF_BAND_TELEMETRY_ENABLED=false
NET_TIMEOUT=300
CLIENT_METADATA_REQUEST_USE_CONNECTION_CTX=true
ENABLE_STAGE_S3_PRIVATELINK_FOR_US_EAST_1=false
```

## Error Analysis (XSMALL/10 Clusters Test)

### Snowflake-Side
- **961 query timeouts** during warmup (Error 000630: 5-second Interactive WH timeout)
- Caused by cold SSD cache on newly provisioned cluster nodes fetching micro-partitions from S3
- **Zero failures during measured test** - warm cache kept all queries under 5s

### Client-Side
- **7,495 S3 SlowDown events** (HTTP 503) on result chunk downloads
- JDBC driver retries automatically - no query failures from this
- Causes QPS oscillation pattern in 5-second samples and adds E2E latency

## Credit Consumption (XSMALL/10 Clusters)
- **Compute**: 6.0 credits/hour
- **Cloud Services**: 10.5 credits/hour (high due to 1,000 QPS query coordination overhead)
- **Total**: ~16.5 credits/hour
- **Pro-rated for 10-min measured test**: ~3.3 credits

## Folder Structure
```
Snowflake_Interactive_WH_POC/
├── README.md                  <- This file
├── reports/
│   ├── eks_small_8clusters_30pool_80threads_report.html
│   ├── eks_xsmall_8clusters_30pool_80threads_report.html
│   └── eks_xsmall_10clusters_30pool_80threads_report.html
├── k8s/
│   ├── k8s-deployment.yaml    <- K8s manifests + inline JMX + credentials
│   ├── Dockerfile             <- JMeter container image
│   ├── entrypoint.sh          <- Continuous loop entrypoint
│   ├── deploy-to-eks.sh       <- EKS deployment script
│   └── collect-results.sh     <- Results collection script
└── jmx/
    ├── Snowflake_Performance_Test_V2.jmx
    └── Snowflake_Performance_Test_V2 (1).jmx
```

**Note**: The JMX actually used in testing is embedded inline in `k8s/k8s-deployment.yaml` as a ConfigMap. The standalone JMX files in `jmx/` have slightly different settings (PREFETCH_THREADS=4, CHUNK_SIZE=48, MEMORY_LIMIT=3072) vs the deployed version (PREFETCH_THREADS=1, CHUNK_SIZE=16, MEMORY_LIMIT=2048).

## Test Query
```sql
SELECT
    CR.CR_ORDER_NUMBER AS ORDER_KEY,
    CR.CR_REFUNDED_CUSTOMER_SK AS CUST_KEY,
    COUNT(DISTINCT CR.CR_REFUNDED_CUSTOMER_SK) OVER (PARTITION BY CR.CR_ORDER_NUMBER) AS ORDER_CUST_COUNT,
    SUM(COALESCE(CR.CR_RETURN_AMOUNT, 0)) AS TOTAL_RETURN_AMOUNT,
    MAX(CR.CR_REASON_SK) AS MAX_REASON,
    MAX(CR.CR_CALL_CENTER_SK) AS MAX_CALL_CENTER,
    MIN(CR.CR_RETURNED_DATE_SK) AS MIN_RETURN_DATE_SK,
    MAX(CR.CR_RETURNED_DATE_SK) AS MAX_RETURN_DATE_SK
FROM DEMO.DEMO.ORDERS_INTERACTIVE AS CR
WHERE CR.CR_RETURNED_DATE_SK BETWEEN 2452912 AND 2452924
  AND CR.CR_WAREHOUSE_SK IS NOT NULL
GROUP BY CR.CR_ORDER_NUMBER, CR.CR_REFUNDED_CUSTOMER_SK
```

## Test Dates
- **SMALL/8 clusters**: March 19, 2026 ~14:02-14:15 PDT
- **XSMALL/8 clusters**: March 19, 2026 ~14:35-14:52 PDT
- **XSMALL/10 clusters**: March 19, 2026 ~17:34-17:46 PDT (00:34-00:46 UTC March 20)
