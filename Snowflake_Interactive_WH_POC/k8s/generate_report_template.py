import pandas as pd
import glob
import os
from datetime import datetime

RESULTS_DIR = "/Users/rnellikal/Documents/my_workspace/coco_ws/NiCE/05_interactive_poc/Snowflake_Interactive_WH_POC/k8s/results_6pod_10min"
TEMPLATE_DIR = "/Users/rnellikal/Documents/my_workspace/coco_ws/NiCE/05_interactive_poc/Snowflake_Interactive_WH_POC/reports"
OUTPUT_FILE = os.path.join(TEMPLATE_DIR, "eks_xsmall_6pods_30pool_80threads_10min_report.html")

files = sorted(glob.glob(os.path.join(RESULTS_DIR, "*.jtl")))
print(f"Found {len(files)} .jtl files")

dfs = []
for f in files:
    df = pd.read_csv(f)
    pod = os.path.basename(f).replace("_run1.jtl", "")
    df["pod"] = pod
    dfs.append(df)

data = pd.concat(dfs, ignore_index=True)
data["ts"] = pd.to_datetime(data["timeStamp"], unit="ms", utc=True)
data["elapsed_sec"] = data["elapsed"] / 1000.0
data["elapsed_ms"] = data["elapsed"]

total = len(data)
success = data["success"].sum()
errors = total - success
error_pct = (errors / total) * 100
start_time = data["ts"].min()
end_time = data["ts"].max()
duration_sec = (end_time - start_time).total_seconds()
avg_qps = total / duration_sec if duration_sec > 0 else 0

elapsed = data["elapsed_ms"]
avg_rt = elapsed.mean()
p50 = elapsed.median()
p90 = elapsed.quantile(0.90)
p95 = elapsed.quantile(0.95)
p99 = elapsed.quantile(0.99)
min_rt = elapsed.min()
max_rt = elapsed.max()

print(f"Duration: {duration_sec:.0f}s ({duration_sec/60:.1f} min)")
print(f"Total Requests: {total:,}")
print(f"Avg QPS: {avg_qps:.1f}")
print(f"Avg RT: {avg_rt:.0f}ms | P50: {p50:.0f}ms | P95: {p95:.0f}ms | P99: {p99:.0f}ms")
print(f"Errors: {errors:,} ({error_pct:.2f}%)")

data["time_bucket_2min"] = ((data["ts"] - start_time).dt.total_seconds() // 120).astype(int)
checkpoints = []
for bucket in sorted(data["time_bucket_2min"].unique()):
    chunk = data[data["time_bucket_2min"] == bucket]
    bucket_duration = (chunk["ts"].max() - chunk["ts"].min()).total_seconds()
    if bucket_duration < 1:
        bucket_duration = 1
    qps = len(chunk) / bucket_duration
    checkpoints.append({
        "label": f"{(bucket+1)*2} min",
        "qps": round(qps, 1),
        "avg": round(chunk["elapsed_ms"].mean(), 1),
        "p50": round(chunk["elapsed_ms"].median(), 0),
        "p95": round(chunk["elapsed_ms"].quantile(0.95), 0),
        "p99": round(chunk["elapsed_ms"].quantile(0.99), 0),
    })

per_pod = data.groupby("pod").agg(
    count=("elapsed", "size"),
    avg_rt=("elapsed_ms", "mean"),
    p50_rt=("elapsed_ms", "median"),
    p99_rt=("elapsed_ms", lambda x: x.quantile(0.99)),
    errors=("success", lambda x: (~x).sum())
).reset_index()
per_pod["share"] = (per_pod["count"] / total * 100).round(1)

error_df = data[~data["success"]]
error_codes = error_df["responseCode"].value_counts()

max_qps = max(c["qps"] for c in checkpoints)
max_p99 = max(c["p99"] for c in checkpoints)
lat_scale = max_p99 * 1.1

# --- Build HTML using template structure ---
def qps_class(qps):
    return "qps-high" if qps >= avg_qps * 0.95 else "qps-mid"

def bar_height(qps):
    return int(qps / max_qps * 200)

def bar_color(qps):
    if qps >= avg_qps * 0.95:
        return "linear-gradient(180deg, #66bb6a, #388e3c)"
    return "linear-gradient(180deg, #fdd835, #f9a825)"

def bar_value_color(qps):
    return "#66bb6a" if qps >= avg_qps * 0.95 else "#fdd835"

checkpoint_rows = ""
for c in checkpoints:
    checkpoint_rows += f"""                <tr>
                    <td>{c['label']}</td>
                    <td><span class="qps-value {qps_class(c['qps'])}">{c['qps']}</span></td>
                    <td class="latency">{c['avg']}</td>
                    <td class="latency">{int(c['p50'])}</td>
                    <td class="latency">{int(c['p95'])}</td>
                    <td class="latency">{int(c['p99'])}</td>
                </tr>
"""

e2e_rows = ""
for c in checkpoints:
    overhead = round(c["avg"] - c["avg"] * 0.3, 0)
    e2e_rows += f"""                <tr>
                    <td>{c['label']}</td>
                    <td class="e2e">{int(c['avg'])}</td>
                    <td class="e2e">{int(c['p50'])}</td>
                    <td class="e2e">{int(c['p95'])}</td>
                    <td class="e2e">{int(c['p99'])}</td>
                    <td class="latency">~{int(overhead)}</td>
                </tr>
"""

qps_bars = ""
for c in checkpoints:
    h = bar_height(c["qps"])
    color = bar_color(c["qps"])
    vcolor = bar_value_color(c["qps"])
    qps_bars += f"""                <div class="bar-group">
                    <div class="bar-value" style="color:{vcolor};">{c['qps']}</div>
                    <div class="bar" style="height:{h}px; background: {color};"></div>
                    <div class="bar-label">{c['label']}</div>
                </div>
"""

lat_groups = ""
for c in checkpoints:
    p50_h = int(c["p50"] / lat_scale * 130)
    p95_h = int(c["p95"] / lat_scale * 130)
    p99_h = int(c["p99"] / lat_scale * 130)
    lat_groups += f"""                <div class="latency-group">
                    <div class="latency-bars">
                        <div class="lat-bar p50" style="height: {p50_h}px;" title="P50: {int(c['p50'])}ms"></div>
                        <div class="lat-bar p95" style="height: {p95_h}px;" title="P95: {int(c['p95'])}ms"></div>
                        <div class="lat-bar p99" style="height: {p99_h}px;" title="P99: {int(c['p99'])}ms"></div>
                    </div>
                    <div style="font-size:11px; color:#6b8dad;">{c['label']}</div>
                    <div style="font-size:10px; color:#4fc3f7; margin-top:2px;">{int(c['p50'])} / {int(c['p95'])} / {int(c['p99'])}</div>
                </div>
"""

pod_rows = ""
for _, row in per_pod.sort_values("pod").iterrows():
    short = row["pod"].replace("jmeter-workers-f9489dd89-", "")
    pod_rows += f"""                <tr>
                    <td>{short}</td>
                    <td>{int(row['count']):,}</td>
                    <td>{row['share']}%</td>
                    <td class="latency">{row['avg_rt']:.1f}</td>
                    <td class="latency">{int(row['p50_rt'])}</td>
                    <td class="latency">{int(row['p99_rt'])}</td>
                </tr>
"""

error_section = ""
if errors > 0:
    error_detail = ""
    for code, cnt in error_codes.items():
        error_detail += f"Error code {code}: {cnt:,} occurrences<br>\n"
    error_section = f"""            <div style="background: #162230; border-radius: 10px; padding: 20px; border: 1px solid #1e3a52;">
                <div style="font-size: 13px; font-weight: 600; color: #7eb8f7; margin-bottom: 14px; text-transform: uppercase; letter-spacing: 1px;">Client-Side Errors</div>
                <div style="display: flex; align-items: baseline; gap: 8px; margin-bottom: 10px;">
                    <span style="font-size: 36px; font-weight: 800; color: #ff9800;">{errors:,}</span>
                    <span style="font-size: 13px; color: #90a4ae;">total errors ({error_pct:.2f}%)</span>
                </div>
                <div style="font-size: 12px; color: #546e7a; line-height: 1.8;">
                    {error_detail}
                </div>
            </div>"""
else:
    error_section = """            <div style="background: #162230; border-radius: 10px; padding: 20px; border: 1px solid #1e3a52;">
                <div style="font-size: 13px; font-weight: 600; color: #7eb8f7; margin-bottom: 14px; text-transform: uppercase; letter-spacing: 1px;">Error Summary</div>
                <div style="display: flex; align-items: baseline; gap: 8px; margin-bottom: 10px;">
                    <span style="font-size: 36px; font-weight: 800; color: #66bb6a;">0</span>
                    <span style="font-size: 13px; color: #90a4ae;">errors</span>
                </div>
                <div style="font-size: 12px; color: #546e7a; line-height: 1.8;">
                    <span style="color: #66bb6a; font-weight: 600;">Zero failures during test</span>
                </div>
            </div>"""

total_threads = 6 * 80
total_pool = 6 * 30

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Snowflake Performance Test Report - XSMALL/10 Clusters/6 Pods</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #0f1923; color: #e0e6ed; }}
        .header {{ background: linear-gradient(135deg, #1a73e8, #0d47a1); padding: 40px; text-align: center; }}
        .header h1 {{ font-size: 28px; font-weight: 700; color: #fff; margin-bottom: 8px; }}
        .header p {{ font-size: 14px; color: #b3d4fc; }}
        .container {{ max-width: 1200px; margin: 0 auto; padding: 30px 20px; }}
        .time-banner {{ display: flex; justify-content: center; gap: 60px; background: #162230; border: 1px solid #1a73e8; border-radius: 10px; padding: 20px 40px; margin-bottom: 30px; flex-wrap: wrap; }}
        .time-item {{ text-align: center; }}
        .time-item .label {{ font-size: 11px; text-transform: uppercase; letter-spacing: 1.5px; color: #7eb8f7; margin-bottom: 6px; }}
        .time-item .value {{ font-size: 18px; font-weight: 600; color: #fff; font-family: 'Courier New', monospace; }}
        .config-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 14px; margin-bottom: 30px; }}
        .config-card {{ background: #162230; border-radius: 10px; padding: 16px; text-align: center; border: 1px solid #1e3a52; }}
        .config-card .label {{ font-size: 10px; text-transform: uppercase; letter-spacing: 1.2px; color: #6b8dad; margin-bottom: 6px; }}
        .config-card .value {{ font-size: 20px; font-weight: 700; color: #4fc3f7; }}
        .config-card .value.highlight {{ color: #66bb6a; }}
        .config-card .sub {{ font-size: 10px; color: #546e7a; margin-top: 4px; }}
        .section-title {{ font-size: 20px; font-weight: 600; color: #fff; margin: 30px 0 16px 0; padding-bottom: 8px; border-bottom: 2px solid #1a73e8; }}
        .results-table {{ width: 100%; border-collapse: separate; border-spacing: 0; background: #162230; border-radius: 10px; overflow: hidden; margin-bottom: 30px; }}
        .results-table thead th {{ background: #1a3a5c; padding: 12px 10px; text-align: center; font-size: 11px; text-transform: uppercase; letter-spacing: 0.8px; color: #7eb8f7; font-weight: 600; }}
        .results-table tbody td {{ padding: 12px 10px; text-align: center; border-top: 1px solid #1e3a52; font-size: 14px; }}
        .results-table tbody tr:hover {{ background: #1a3050; }}
        .qps-value {{ font-weight: 700; font-size: 17px; }}
        .qps-high {{ color: #66bb6a; }}
        .qps-mid {{ color: #fdd835; }}
        .latency {{ color: #b0bec5; font-family: 'Courier New', monospace; }}
        .e2e {{ color: #ce93d8; font-family: 'Courier New', monospace; }}
        .peak-banner {{ background: linear-gradient(135deg, #1b5e20, #2e7d32); border-radius: 10px; padding: 30px; text-align: center; margin-bottom: 30px; }}
        .peak-banner .peak-label {{ font-size: 13px; text-transform: uppercase; letter-spacing: 2px; color: #a5d6a7; margin-bottom: 8px; }}
        .peak-banner .peak-value {{ font-size: 52px; font-weight: 800; color: #fff; }}
        .peak-banner .peak-unit {{ font-size: 18px; color: #a5d6a7; margin-left: 4px; }}
        .peak-banner .peak-detail {{ font-size: 13px; color: #c8e6c9; margin-top: 8px; }}
        .chart-container {{ background: #162230; border-radius: 10px; padding: 30px; margin-bottom: 30px; border: 1px solid #1e3a52; }}
        .chart-title {{ font-size: 14px; font-weight: 600; color: #7eb8f7; margin-bottom: 20px; text-transform: uppercase; letter-spacing: 1px; }}
        .bar-chart {{ display: flex; align-items: flex-end; justify-content: space-around; height: 220px; padding: 0 10px; }}
        .bar-group {{ display: flex; flex-direction: column; align-items: center; flex: 1; }}
        .bar {{ width: 50px; border-radius: 6px 6px 0 0; transition: all 0.3s; min-height: 4px; }}
        .bar:hover {{ opacity: 0.85; }}
        .bar-label {{ margin-top: 10px; font-size: 11px; color: #6b8dad; }}
        .bar-value {{ font-size: 12px; font-weight: 700; }}
        .latency-chart {{ display: flex; justify-content: space-around; margin-top: 20px; }}
        .latency-group {{ text-align: center; flex: 1; }}
        .latency-bars {{ display: flex; align-items: flex-end; justify-content: center; gap: 4px; height: 140px; margin-bottom: 8px; }}
        .lat-bar {{ width: 18px; border-radius: 3px 3px 0 0; }}
        .lat-bar.p50 {{ background: #4fc3f7; }}
        .lat-bar.p95 {{ background: #ff9800; }}
        .lat-bar.p99 {{ background: #ef5350; }}
        .legend {{ display: flex; justify-content: center; gap: 30px; margin-top: 16px; }}
        .legend-item {{ display: flex; align-items: center; gap: 6px; font-size: 12px; color: #6b8dad; }}
        .legend-dot {{ width: 12px; height: 12px; border-radius: 3px; }}
        .query-box {{ background: #0d1820; border: 1px solid #1e3a52; border-radius: 10px; padding: 20px; margin-bottom: 30px; overflow-x: auto; }}
        .query-box pre {{ font-family: 'Courier New', monospace; font-size: 12px; color: #81d4fa; line-height: 1.6; white-space: pre-wrap; }}
        .query-box .keyword {{ color: #ff9800; font-weight: 600; }}
        .query-box .table-name {{ color: #66bb6a; }}
        .query-box .func {{ color: #ce93d8; }}
        .notes {{ background: #162230; border-radius: 10px; padding: 24px; border-left: 4px solid #1a73e8; }}
        .notes h3 {{ font-size: 14px; color: #7eb8f7; margin-bottom: 12px; text-transform: uppercase; letter-spacing: 1px; }}
        .notes ul {{ list-style: none; }}
        .notes li {{ padding: 5px 0; font-size: 13px; color: #90a4ae; }}
        .notes li::before {{ content: "\\2192 "; color: #1a73e8; font-weight: bold; }}
        .footer {{ text-align: center; padding: 20px; font-size: 11px; color: #455a64; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Snowflake Interactive Warehouse Performance Test</h1>
        <p>TPCH_INTERACTIVE_WH &middot; SMALL &middot; 10 Clusters &middot; 6 Pods &middot; 30 Pool / 80 Threads</p>
    </div>

    <div class="container">
        <div class="time-banner">
            <div class="time-item">
                <div class="label">Test Start (UTC)</div>
                <div class="value">{start_time.strftime('%Y-%m-%d %H:%M:%S')}</div>
            </div>
            <div class="time-item">
                <div class="label">Test End (UTC)</div>
                <div class="value">{end_time.strftime('%Y-%m-%d %H:%M:%S')}</div>
            </div>
            <div class="time-item">
                <div class="label">Duration</div>
                <div class="value">~{int(duration_sec/60)} min</div>
            </div>
        </div>

        <div class="section-title">Test Configuration</div>
        <div class="config-grid">
            <div class="config-card">
                <div class="label">Warehouse</div>
                <div class="value" style="font-size:14px;">TPCH_INTERACTIVE_WH</div>
            </div>
            <div class="config-card">
                <div class="label">WH Size</div>
                <div class="value">SMALL</div>
            </div>
            <div class="config-card">
                <div class="label">Clusters</div>
                <div class="value highlight">10</div>
            </div>
            <div class="config-card">
                <div class="label">Pods</div>
                <div class="value highlight">6</div>
            </div>
            <div class="config-card">
                <div class="label">Threads/Pod</div>
                <div class="value">80</div>
                <div class="sub">{total_threads} total threads</div>
            </div>
            <div class="config-card">
                <div class="label">Pool/Pod</div>
                <div class="value">30</div>
                <div class="sub">{total_pool} total connections</div>
            </div>
            <div class="config-card">
                <div class="label">Pod CPU</div>
                <div class="value" style="font-size:16px;">2 / 4</div>
                <div class="sub">request / limit</div>
            </div>
            <div class="config-card">
                <div class="label">Pod Memory</div>
                <div class="value" style="font-size:16px;">3Gi / 4Gi</div>
                <div class="sub">request / limit</div>
            </div>
            <div class="config-card">
                <div class="label">Table</div>
                <div class="value" style="font-size:14px;">ORDERS_INTERACTIVE</div>
                <div class="sub">INTERACTIVE_DEMO.TPCH_INTERACTIVE</div>
            </div>
            <div class="config-card">
                <div class="label">Table Size</div>
                <div class="value" style="font-size:18px;">75.97 GB</div>
                <div class="sub">1.44 billion rows</div>
            </div>
            <div class="config-card">
                <div class="label">Result Size</div>
                <div class="value" style="font-size:18px;">~315 KB</div>
                <div class="sub">~12,383 rows</div>
            </div>
            <div class="config-card">
                <div class="label">Region</div>
                <div class="value" style="font-size:16px;">us-west-2</div>
                <div class="sub">Oregon</div>
            </div>
        </div>

        <div class="peak-banner">
            <div class="peak-label">Average QPS (JMeter Client-Side &middot; {total:,} queries in {int(duration_sec)} seconds)</div>
            <div class="peak-value">{avg_qps:.1f}<span class="peak-unit">QPS</span></div>
            <div class="peak-detail">Peak 2-min sample: {max_qps:.1f} QPS &middot; {success:,} success / {errors:,} failure &middot; {error_pct:.2f}% error rate</div>
        </div>

        <div class="section-title">Client-Side Latency (JMeter E2E)</div>
        <table class="results-table">
            <thead>
                <tr>
                    <th>Checkpoint</th>
                    <th>QPS</th>
                    <th>Avg (ms)</th>
                    <th>P50 (ms)</th>
                    <th>P95 (ms)</th>
                    <th>P99 (ms)</th>
                </tr>
            </thead>
            <tbody>
{checkpoint_rows}            </tbody>
        </table>

        <div class="section-title">QPS Over Time</div>
        <div class="chart-container">
            <div class="chart-title">Queries Per Second at Each 2-Minute Checkpoint</div>
            <div class="bar-chart">
{qps_bars}            </div>
        </div>

        <div class="section-title">Latency Distribution (Client-Side E2E)</div>
        <div class="chart-container">
            <div class="chart-title">P50 / P95 / P99 Latency (ms) at 2-Minute Checkpoints</div>
            <div class="latency-chart">
{lat_groups}            </div>
            <div class="legend">
                <div class="legend-item"><div class="legend-dot" style="background:#4fc3f7;"></div> P50</div>
                <div class="legend-item"><div class="legend-dot" style="background:#ff9800;"></div> P95</div>
                <div class="legend-item"><div class="legend-dot" style="background:#ef5350;"></div> P99</div>
            </div>
        </div>

        <div class="section-title">Pod Distribution</div>
        <p style="font-size:12px; color:#546e7a; margin-bottom:14px;">{total:,} total queries distributed across {len(per_pod)} pods.</p>
        <table class="results-table">
            <thead>
                <tr>
                    <th>Pod</th>
                    <th>Queries</th>
                    <th>Share %</th>
                    <th>Avg (ms)</th>
                    <th>P50 (ms)</th>
                    <th>P99 (ms)</th>
                </tr>
            </thead>
            <tbody>
{pod_rows}            </tbody>
        </table>

        <div class="section-title">Error Analysis</div>
        <div style="margin-bottom: 30px;">
{error_section}
        </div>

        <div class="section-title">Test Query</div>
        <div class="query-box">
            <pre><span class="keyword">SELECT</span>
    CR.CR_ORDER_NUMBER <span class="keyword">AS</span> ORDER_KEY,
    CR.CR_REFUNDED_CUSTOMER_SK <span class="keyword">AS</span> CUST_KEY,
    <span class="func">COUNT</span>(<span class="keyword">DISTINCT</span> CR.CR_REFUNDED_CUSTOMER_SK) <span class="func">OVER</span> (<span class="keyword">PARTITION BY</span> CR.CR_ORDER_NUMBER) <span class="keyword">AS</span> ORDER_CUST_COUNT,
    <span class="func">SUM</span>(<span class="func">COALESCE</span>(CR.CR_RETURN_AMOUNT, 0)) <span class="keyword">AS</span> TOTAL_RETURN_AMOUNT,
    <span class="func">MAX</span>(CR.CR_REASON_SK) <span class="keyword">AS</span> MAX_REASON,
    <span class="func">MAX</span>(CR.CR_CALL_CENTER_SK) <span class="keyword">AS</span> MAX_CALL_CENTER,
    <span class="func">MIN</span>(CR.CR_RETURNED_DATE_SK) <span class="keyword">AS</span> MIN_RETURN_DATE_SK,
    <span class="func">MAX</span>(CR.CR_RETURNED_DATE_SK) <span class="keyword">AS</span> MAX_RETURN_DATE_SK
<span class="keyword">FROM</span> <span class="table-name">INTERACTIVE_DEMO.TPCH_INTERACTIVE.ORDERS_INTERACTIVE</span> <span class="keyword">AS</span> CR
<span class="keyword">WHERE</span> CR.CR_RETURNED_DATE_SK <span class="keyword">BETWEEN</span> 2452912 <span class="keyword">AND</span> 2452924
  <span class="keyword">AND</span> CR.CR_WAREHOUSE_SK <span class="keyword">IS NOT NULL</span>
<span class="keyword">GROUP BY</span> CR.CR_ORDER_NUMBER, CR.CR_REFUNDED_CUSTOMER_SK</pre>
            <div style="margin-top:12px; font-size:11px; color:#546e7a;">
                Table: ORDERS_INTERACTIVE (75.97 GB, 1.44B rows) &middot; Result: ~12,383 rows, ~315 KB
            </div>
        </div>

        <div class="notes">
            <h3>Observations</h3>
            <ul>
                <li><strong>{avg_qps:.1f} avg QPS</strong> from JMeter client-side ({total:,} queries / {int(duration_sec)} seconds)</li>
                <li>Peak 2-min sample of {max_qps:.1f} QPS</li>
                <li>6 pods with 80 threads each = {total_threads} total concurrent threads</li>
                <li>P50 latency: {p50:.0f}ms | P95: {p95:.0f}ms | P99: {p99:.0f}ms</li>
                <li>Error rate: {error_pct:.2f}% ({errors:,} out of {total:,} requests)</li>
                <li>EKS cluster: rnellikal-jmeter-interactive-poc (us-west-2, subnet 2a only)</li>
                <li>Node type: m5.xlarge (4 vCPU, 16GB) &mdash; 1 pod per node</li>
                <li>Snowflake account: SFPSCOGS-RNELLIKAL &middot; Warehouse: TPCH_INTERACTIVE_WH (SMALL, 10 clusters)</li>
            </ul>
        </div>

        <div class="footer">
            Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} &middot; Snowflake Account: SFPSCOGS-RNELLIKAL &middot; EKS Cluster: rnellikal-jmeter-interactive-poc (us-west-2)
        </div>
    </div>
</body>
</html>"""

with open(OUTPUT_FILE, "w") as f:
    f.write(html)
print(f"\nReport saved: {OUTPUT_FILE}")
