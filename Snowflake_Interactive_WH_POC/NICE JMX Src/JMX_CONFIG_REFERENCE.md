# JMeter JMX Configuration Reference

## JDBC Connection Configuration

| Property | Value | Description |
|----------|-------|-------------|
| `driver` | `net.snowflake.client.jdbc.SnowflakeDriver` | Snowflake JDBC driver class |
| `dbUrl` | `${__P(snowflake.url)}` | JDBC URL passed via `-J` or properties file |
| `username` | `${__P(snowflake.username)}` | Snowflake user |
| `password` | `${__P(snowflake.password)}` | Snowflake password/token |
| `dataSource` | `SnowflakePool` | Internal pool name referenced by samplers |
| `poolMax` | `${__P(snowflake.poolMax,700)}` | Max JDBC connections in pool (default 700 if not set) |
| `autocommit` | `true` | Auto-commit each statement |
| `keepAlive` | `true` | Keep connections alive in pool |
| `timeout` | `600000` | Connection timeout: 600 seconds (10 min) |
| `connectionAge` | `300000` | Max connection age: 300 seconds (5 min) before recycling |
| `trimInterval` | `60000` | Check for idle connections every 60 seconds |

## JDBC Connection Properties (Snowflake-Specific)

| Property | Value | Purpose |
|----------|-------|---------|
| `USE_CACHED_RESULT` | `false` | Disables result cache — forces query execution every time |
| `CLIENT_SESSION_KEEP_ALIVE` | `true` | Prevents session timeout during long tests |
| `JDBC_QUERY_RESULT_FORMAT` | `ARROW` | Uses Apache Arrow format for result transfer (faster than JSON) |
| `CLIENT_PREFETCH_THREADS` | `4` | Threads for prefetching result chunks from S3 |
| `CLIENT_RESULT_CHUNK_SIZE` | `48` | Result chunk size in MB for S3 downloads |
| `CLIENT_MEMORY_LIMIT` | `3072` | Max client memory for result processing (3 GB) |
| `CLIENT_OUT_OF_BAND_TELEMETRY_ENABLED` | `false` | Disables telemetry to reduce overhead |
| `NET_TIMEOUT` | `300` | Network timeout: 300 seconds |
| `CLIENT_METADATA_REQUEST_USE_CONNECTION_CTX` | `true` | Reuses connection context for metadata requests (avoids extra round-trips) |

> **Note**: The deployed K8s version uses more conservative values: `PREFETCH_THREADS=1`, `CHUNK_SIZE=16`, `MEMORY_LIMIT=2048` — to reduce S3 throttling at high concurrency.

## Thread Groups

### 1. Connection Pool Warmup (disabled in JMX)

| Property | Value |
|----------|-------|
| Threads | `${__P(snowflake.poolMax,500)}` |
| Ramp-up | 120 seconds |
| Loops | 1 |
| Query | `SELECT 1` |

### 2. Main Load Test (enabled)

| Property | Value |
|----------|-------|
| Threads | `${__P(snowflake.threads,500)}` |
| Ramp-up | 1 second (near-instant) |
| Loop count | -1 (infinite) |
| Duration | 600 seconds (10 min) |
| Scheduler | true |

## Result Collector

- Saves to `results/summary_results.jtl`
- Captures: timestamp, latency, success, label, response code, thread name, bytes, connect time

## How to Run Standalone

```bash
jmeter -n \
  -t "Snowflake_Performance_Test_V2 (1).jmx" \
  -q snowflake.properties \
  -l results.jtl
```

Override individual properties inline:

```bash
jmeter -n \
  -t "Snowflake_Performance_Test_V2 (1).jmx" \
  -q snowflake.properties \
  -Jsnowflake.threads=100 \
  -Jsnowflake.poolMax=50 \
  -Jtest.duration=300 \
  -l results.jtl
```
