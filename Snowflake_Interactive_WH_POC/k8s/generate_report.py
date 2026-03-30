import pandas as pd
import glob
import os
from datetime import datetime, timezone

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results_run8")
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "jmeter_report_run8.html")

files = sorted(glob.glob(os.path.join(RESULTS_DIR, "*.jtl")))
print(f"Found {len(files)} .jtl files")

dfs = []
for f in files:
    df = pd.read_csv(f)
    pod = os.path.basename(f).replace("_run8.jtl", "")
    df["pod"] = pod
    dfs.append(df)

data = pd.concat(dfs, ignore_index=True)
data["timeStamp"] = pd.to_datetime(data["timeStamp"], unit="ms", utc=True)
data["elapsed_sec"] = data["elapsed"] / 1000.0

total = len(data)
success = data["success"].sum()
errors = total - success
error_pct = (errors / total) * 100 if total > 0 else 0
start_time = data["timeStamp"].min()
end_time = data["timeStamp"].max()
duration_sec = (end_time - start_time).total_seconds()
throughput = total / duration_sec if duration_sec > 0 else 0

elapsed = data["elapsed_sec"]
avg_rt = elapsed.mean()
median_rt = elapsed.median()
p90 = elapsed.quantile(0.90)
p95 = elapsed.quantile(0.95)
p99 = elapsed.quantile(0.99)
min_rt = elapsed.min()
max_rt = elapsed.max()
std_rt = elapsed.std()

data["time_bucket"] = data["timeStamp"].dt.floor("10s")
time_series = data.groupby("time_bucket").agg(
    count=("elapsed", "size"),
    avg_elapsed=("elapsed_sec", "mean"),
    p95_elapsed=("elapsed_sec", lambda x: x.quantile(0.95)),
    errors=("success", lambda x: (~x).sum())
).reset_index()
time_series["qps"] = time_series["count"] / 10.0

per_pod = data.groupby("pod").agg(
    count=("elapsed", "size"),
    avg_rt=("elapsed_sec", "mean"),
    p95_rt=("elapsed_sec", lambda x: x.quantile(0.95)),
    errors=("success", lambda x: (~x).sum()),
    min_rt=("elapsed_sec", "min"),
    max_rt=("elapsed_sec", "max")
).reset_index()
per_pod["error_pct"] = (per_pod["errors"] / per_pod["count"]) * 100
per_pod["qps"] = per_pod["count"] / duration_sec

rc_counts = data["responseCode"].value_counts().reset_index()
rc_counts.columns = ["Response Code", "Count"]

ts_labels = [t.strftime("%H:%M:%S") for t in time_series["time_bucket"]]
ts_qps = time_series["qps"].tolist()
ts_avg = time_series["avg_elapsed"].tolist()
ts_p95 = time_series["p95_elapsed"].tolist()
ts_errors = time_series["errors"].tolist()

hist_bins = [0, 0.5, 1, 2, 3, 5, 10, 15, 20, 30, 60, 120, 999]
hist_labels_list = ["<0.5s", "0.5-1s", "1-2s", "2-3s", "3-5s", "5-10s", "10-15s", "15-20s", "20-30s", "30-60s", "60-120s", ">120s"]
hist_counts = pd.cut(elapsed, bins=hist_bins, labels=hist_labels_list).value_counts().reindex(hist_labels_list).fillna(0).astype(int).tolist()

pod_labels = per_pod["pod"].str.replace("jmeter-workers-7fb7df4676-", "").tolist()
pod_qps = per_pod["qps"].round(1).tolist()
pod_avg = per_pod["avg_rt"].round(3).tolist()

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>JMeter Load Test Report - Run 8</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #e2e8f0; padding: 20px; }}
  .header {{ background: linear-gradient(135deg, #1e40af, #7c3aed); padding: 30px; border-radius: 12px; margin-bottom: 24px; }}
  .header h1 {{ font-size: 28px; color: #fff; }}
  .header .subtitle {{ color: #c7d2fe; margin-top: 8px; font-size: 14px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px; }}
  .card {{ background: #1e293b; border-radius: 10px; padding: 20px; border: 1px solid #334155; }}
  .card .label {{ font-size: 12px; color: #94a3b8; text-transform: uppercase; letter-spacing: 1px; }}
  .card .value {{ font-size: 28px; font-weight: 700; margin-top: 4px; }}
  .card .value.green {{ color: #4ade80; }}
  .card .value.blue {{ color: #60a5fa; }}
  .card .value.yellow {{ color: #fbbf24; }}
  .card .value.red {{ color: #f87171; }}
  .card .value.purple {{ color: #c084fc; }}
  .chart-container {{ background: #1e293b; border-radius: 10px; padding: 20px; border: 1px solid #334155; margin-bottom: 24px; }}
  .chart-container h2 {{ font-size: 16px; color: #94a3b8; margin-bottom: 16px; }}
  .two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 24px; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th {{ text-align: left; padding: 10px 12px; background: #334155; color: #94a3b8; font-size: 12px; text-transform: uppercase; }}
  td {{ padding: 10px 12px; border-bottom: 1px solid #334155; font-size: 13px; }}
  tr:hover {{ background: #334155; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }}
  .badge-green {{ background: #065f46; color: #6ee7b7; }}
  .badge-red {{ background: #7f1d1d; color: #fca5a5; }}
  @media (max-width: 768px) {{ .two-col {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>
<div class="header">
  <h1>Snowflake Interactive WH - JMeter Load Test Report</h1>
  <div class="subtitle">Run 8 | {start_time.strftime('%Y-%m-%d %H:%M:%S UTC')} → {end_time.strftime('%H:%M:%S UTC')} | 10 Pods × 80 Threads | Cluster: rnellikal-jmeter-interactive-poc (us-west-2)</div>
</div>

<div class="grid">
  <div class="card"><div class="label">Total Requests</div><div class="value blue">{total:,}</div></div>
  <div class="card"><div class="label">Throughput (QPS)</div><div class="value green">{throughput:.1f}</div></div>
  <div class="card"><div class="label">Avg Response Time</div><div class="value yellow">{avg_rt:.3f}s</div></div>
  <div class="card"><div class="label">P95 Response Time</div><div class="value yellow">{p95:.3f}s</div></div>
  <div class="card"><div class="label">P99 Response Time</div><div class="value purple">{p99:.3f}s</div></div>
  <div class="card"><div class="label">Error Rate</div><div class="value {'red' if error_pct > 1 else 'green'}">{error_pct:.2f}%</div></div>
  <div class="card"><div class="label">Duration</div><div class="value blue">{duration_sec:.0f}s ({duration_sec/60:.1f}m)</div></div>
  <div class="card"><div class="label">Success / Errors</div><div class="value green">{success:,} <span style="color:#f87171">/ {errors:,}</span></div></div>
</div>

<div class="chart-container">
  <h2>Throughput Over Time (QPS per 10s bucket)</h2>
  <canvas id="qpsChart" height="80"></canvas>
</div>

<div class="two-col">
  <div class="chart-container">
    <h2>Response Time Over Time</h2>
    <canvas id="rtChart" height="120"></canvas>
  </div>
  <div class="chart-container">
    <h2>Response Time Distribution</h2>
    <canvas id="histChart" height="120"></canvas>
  </div>
</div>

<div class="two-col">
  <div class="chart-container">
    <h2>QPS by Pod</h2>
    <canvas id="podQpsChart" height="120"></canvas>
  </div>
  <div class="chart-container">
    <h2>Avg Response Time by Pod</h2>
    <canvas id="podRtChart" height="120"></canvas>
  </div>
</div>

<div class="chart-container">
  <h2>Response Time Summary</h2>
  <table>
    <tr><th>Metric</th><th>Value</th></tr>
    <tr><td>Min</td><td>{min_rt:.3f}s</td></tr>
    <tr><td>Average</td><td>{avg_rt:.3f}s</td></tr>
    <tr><td>Median (P50)</td><td>{median_rt:.3f}s</td></tr>
    <tr><td>P90</td><td>{p90:.3f}s</td></tr>
    <tr><td>P95</td><td>{p95:.3f}s</td></tr>
    <tr><td>P99</td><td>{p99:.3f}s</td></tr>
    <tr><td>Max</td><td>{max_rt:.3f}s</td></tr>
    <tr><td>Std Dev</td><td>{std_rt:.3f}s</td></tr>
  </table>
</div>

<div class="chart-container">
  <h2>Per-Pod Breakdown</h2>
  <table>
    <tr><th>Pod</th><th>Requests</th><th>QPS</th><th>Avg RT</th><th>P95 RT</th><th>Min</th><th>Max</th><th>Errors</th><th>Error %</th></tr>
"""

for _, row in per_pod.sort_values("pod").iterrows():
    badge = "badge-green" if row["error_pct"] < 1 else "badge-red"
    short_pod = row["pod"].replace("jmeter-workers-7fb7df4676-", "")
    html += f"""    <tr>
      <td>{short_pod}</td><td>{int(row['count']):,}</td><td>{row['qps']:.1f}</td>
      <td>{row['avg_rt']:.3f}s</td><td>{row['p95_rt']:.3f}s</td>
      <td>{row['min_rt']:.3f}s</td><td>{row['max_rt']:.3f}s</td>
      <td>{int(row['errors']):,}</td><td><span class="badge {badge}">{row['error_pct']:.1f}%</span></td>
    </tr>\n"""

html += f"""  </table>
</div>

<div class="chart-container">
  <h2>Response Codes</h2>
  <table>
    <tr><th>Code</th><th>Count</th><th>Percentage</th></tr>
"""
for _, row in rc_counts.iterrows():
    pct = row["Count"] / total * 100
    html += f'    <tr><td>{row["Response Code"]}</td><td>{row["Count"]:,}</td><td>{pct:.1f}%</td></tr>\n'

html += f"""  </table>
</div>

<script>
const chartDefaults = {{ responsive: true, maintainAspectRatio: true }};
Chart.defaults.color = '#94a3b8';
Chart.defaults.borderColor = '#334155';

new Chart(document.getElementById('qpsChart'), {{
  type: 'line',
  data: {{
    labels: {ts_labels},
    datasets: [{{
      label: 'QPS',
      data: {ts_qps},
      borderColor: '#4ade80',
      backgroundColor: 'rgba(74,222,128,0.1)',
      fill: true,
      tension: 0.3,
      pointRadius: 0
    }}]
  }},
  options: {{ ...chartDefaults, scales: {{ y: {{ beginAtZero: true, title: {{ display: true, text: 'Queries/sec' }} }} }} }}
}});

new Chart(document.getElementById('rtChart'), {{
  type: 'line',
  data: {{
    labels: {ts_labels},
    datasets: [
      {{ label: 'Avg RT', data: {ts_avg}, borderColor: '#fbbf24', tension: 0.3, pointRadius: 0 }},
      {{ label: 'P95 RT', data: {ts_p95}, borderColor: '#f87171', tension: 0.3, pointRadius: 0 }}
    ]
  }},
  options: {{ ...chartDefaults, scales: {{ y: {{ beginAtZero: true, title: {{ display: true, text: 'Seconds' }} }} }} }}
}});

new Chart(document.getElementById('histChart'), {{
  type: 'bar',
  data: {{
    labels: {hist_labels_list},
    datasets: [{{ label: 'Count', data: {hist_counts}, backgroundColor: '#60a5fa' }}]
  }},
  options: {{ ...chartDefaults, scales: {{ y: {{ beginAtZero: true }} }} }}
}});

new Chart(document.getElementById('podQpsChart'), {{
  type: 'bar',
  data: {{
    labels: {pod_labels},
    datasets: [{{ label: 'QPS', data: {pod_qps}, backgroundColor: '#4ade80' }}]
  }},
  options: {{ ...chartDefaults, scales: {{ y: {{ beginAtZero: true }} }} }}
}});

new Chart(document.getElementById('podRtChart'), {{
  type: 'bar',
  data: {{
    labels: {pod_labels},
    datasets: [{{ label: 'Avg RT (s)', data: {pod_avg}, backgroundColor: '#fbbf24' }}]
  }},
  options: {{ ...chartDefaults, scales: {{ y: {{ beginAtZero: true }} }} }}
}});
</script>
</body>
</html>"""

with open(OUTPUT_FILE, "w") as f:
    f.write(html)

print(f"\nReport generated: {OUTPUT_FILE}")
print(f"\n=== Quick Summary ===")
print(f"Duration: {duration_sec:.0f}s ({duration_sec/60:.1f} min)")
print(f"Total Requests: {total:,}")
print(f"Throughput: {throughput:.1f} QPS")
print(f"Avg RT: {avg_rt:.3f}s | P95: {p95:.3f}s | P99: {p99:.3f}s")
print(f"Errors: {errors:,} ({error_pct:.2f}%)")
