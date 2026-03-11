# JMX Comparison: Kapil's V2 vs Our 8MB Test Plan

## Side-by-Side Configuration

| Aspect | **Kapil's V2** | **Ours (8MB)** | Impact |
|---|---|---|---|
| **Result Set Handler** | `Store as String` | `Count Records` | **CRITICAL** — see below |
| **Result Set Size** | Unknown (different table: `DEMO.DEMO.ORDERS_INTERACTIVE`, fixed date range `2452917-2452924`) | ~125K rows (~8MB per query, randomized date ranges) | **Not apples-to-apples** — his query may return far fewer rows |
| **USE_CACHED_RESULT** | `false` via `connectionProperties` | `false` via `initQuery` (ALTER SESSION) | Functionally same, but `connectionProperties` approach may not work — it's a session parameter, not a JDBC connection property |
| **Threads** | 500 (default) | 700 (4 nodes x 175) | We push more concurrent load |
| **Ramp-up** | **1 second** | 60 seconds | **CRITICAL** — he instant-starts all 500 threads. Unrealistic and can inflate QPS if queries are fast |
| **Throughput Timer** | **NONE** | ConstantThroughputTimer (700 QPS target) | He's running open-loop (blast as fast as possible). We're pacing to a realistic target |
| **Query Variety** | **1 single query** (same SQL every time) | 8 different queries (RandomController) | Single query benefits from Snowflake query plan reuse and micro-partition pruning cache |
| **Date Range** | **Fixed** (`2452917-2452924`) | Randomized (`__Random(100,110)` days) | Fixed range = identical query every time. Randomized = no cache benefit |
| **Table** | `DEMO.DEMO.ORDERS_INTERACTIVE` (unknown size) | `INTERACTIVE_DEMO.TPCH_INTERACTIVE.ORDERS` (15M rows TPC-H SF10) | **Different dataset entirely** |
| **Pool Size** | 500 | 700 (matches threads) | Both properly sized |
| **CLIENT_RESULT_CHUNK_SIZE** | `160` (explicitly set) | Not set (default) | Larger chunks = fewer round-trips for ARROW download |
| **JSR223 PostProcessor** | Yes (Groovy logging on every request) | No | Adds overhead per request (minor) |
| **JTL Logging** | Heavy (threadName, message, assertions, url, sentBytes, threadCounts, idleTime) | Lightweight | More JTL fields = more disk I/O per sample |
| **Deployment** | Single JMeter instance | 4 Docker containers (parallel) | Ours distributes client load |

---

## The 3 Biggest Issues Making This Comparison Unfair

### 1. `Store as String` vs `Count Records`

`Store as String` **accumulates all result data in JVM heap as String objects**. With 500 concurrent threads, if each query returns 8MB, that's 500 x 8MB = **4GB in heap simultaneously**. This either means:

- His query returns **very few rows** (not 125K), making it a fast query, OR
- He's running out of heap and the numbers aren't sustainable

`Count Records` (our approach) downloads all ARROW chunks via JDBC, counts rows, then discards from heap — this is a more realistic user pattern and is memory-sustainable.

### 2. Single Fixed Query vs 8 Randomized Queries

His test runs the **exact same SQL every single time** with a fixed date range. Snowflake can optimize this significantly:

- **Query plan reuse**: No recompilation needed after the first execution
- **Micro-partition metadata caching**: Subsequent runs skip partition pruning overhead
- **Potential result cache leakage**: Even with `USE_CACHED_RESULT=false` in `connectionProperties`, this may not actually disable caching if Snowflake treats it as an unsupported connection property rather than a session parameter

Our 8 queries with randomized date windows force Snowflake to do real compilation and execution work each time.

### 3. Different Table, Different Data

He's querying `DEMO.DEMO.ORDERS_INTERACTIVE` — **we don't know**:

- How many rows does his query return?
- How large is the table?
- What's the data distribution?
- What warehouse config is he using?

If his query returns 1,000 rows vs our 125,000 rows, the comparison is meaningless.

---

## What Would Be Needed for a Fair Comparison

1. **Run his exact SQL** and check the result set size (row count and bytes)
2. **Check `DEMO.DEMO.ORDERS_INTERACTIVE`** table size and structure
3. **Confirm his warehouse configuration** (size, cluster count, Interactive type?)
4. **Verify USE_CACHED_RESULT** — run `SHOW PARAMETERS LIKE 'USE_CACHED_RESULT' IN SESSION` during his test to confirm caching is actually disabled
5. **Match the result set handler** — both should use `Count Records` for 8MB tests
6. **Match the query variety** — both should use randomized queries to prevent plan reuse advantage

---

## Bottom Line

If his query returns small result sets, then he's essentially running a test closer to our **Test #11 (1-row baseline, 231 QPS)** rather than our **Test #12/13 (8MB results, 12.7-16.1 QPS)**. Higher QPS in that scenario would be expected and not a "better" result — just a **different test measuring something different**.

---

*Generated: March 10, 2026*
