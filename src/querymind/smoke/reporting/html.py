"""Interactive HTML report generator for ApiSmokeTesting."""

# ruff: noqa: E501
from __future__ import annotations

import html
import json
import logging
from pathlib import Path

from querymind.smoke.masking import mask_headers, mask_request_preview, mask_text
from querymind.smoke.models import SmokeTestReport

logger = logging.getLogger(__name__)


def generate_html_report(report: SmokeTestReport) -> str:
    """Build a self-contained interactive HTML smoke report."""
    s = report.summary
    req_preview = mask_request_preview(report.request) if report.request else {}
    exch = report.exchange

    resp_headers = mask_headers(dict(exch.response_headers)) if exch else {}
    resp_body = mask_text(exch.response_body) if exch else ""
    status_code = exch.status_code if exch else None
    elapsed = exch.elapsed_ms if exch else 0

    rows_json = json.dumps(
        [
            {
                "id": r.test_id,
                "name": r.test_name,
                "status": r.status.value,
                "severity": r.severity.value,
                "duration": r.duration_ms,
                "expected": r.expected,
                "actual": mask_text(r.actual),
                "message": mask_text(r.message),
                "details": r.details,
            }
            for r in report.results
        ],
        default=str,
    )

    dist = {
        "PASS": s.passed,
        "FAIL": s.failed,
        "WARNING": s.warnings,
        "SKIPPED": s.skipped,
        "INFO": s.info,
    }
    max_bar = max(dist.values()) or 1

    def bar(n: int) -> str:
        width = int(40 * n / max_bar) if max_bar else 0
        return "█" * width + "░" * (40 - width)

    score = s.health_score
    score_blocks = int(score / 5)
    score_bar = "█" * score_blocks + "░" * (20 - score_blocks)

    generated = report.generated_at.strftime("%d %b %Y %I:%M %p")
    overall = html.escape(s.overall_status.value)
    endpoint = html.escape(report.endpoint)
    title = html.escape(report.title)

    req_method = html.escape(str(req_preview.get("method", "")))
    req_url = html.escape(str(req_preview.get("url", "")))
    req_headers_html = _kv_table(req_preview.get("headers") or {})
    req_body = html.escape(mask_text(str(req_preview.get("body") or "")) or "(none)")
    resp_headers_html = _kv_table(resp_headers)
    resp_body_esc = html.escape(resp_body[:8000] if resp_body else "(empty)")

    return _TEMPLATE.format(
        title=title,
        endpoint=endpoint,
        generated=generated,
        overall=overall,
        overall_class=_overall_class(s.overall_status.value),
        total=s.total,
        passed=s.passed,
        failed=s.failed,
        warnings=s.warnings,
        skipped=s.skipped,
        duration_ms=s.duration_ms,
        health_score=score,
        score_bar=score_bar,
        bar_pass=bar(dist["PASS"]),
        bar_warn=bar(dist["WARNING"]),
        bar_fail=bar(dist["FAIL"]),
        bar_skip=bar(dist["SKIPPED"]),
        n_pass=dist["PASS"],
        n_warn=dist["WARNING"],
        n_fail=dist["FAIL"],
        n_skip=dist["SKIPPED"],
        req_method=req_method,
        req_url=req_url,
        req_headers=req_headers_html,
        req_body=req_body,
        resp_status=html.escape(str(status_code) if status_code is not None else "N/A"),
        resp_time=elapsed,
        resp_headers=resp_headers_html,
        resp_body=resp_body_esc,
        rows_json=rows_json,
    )


def save_html_report(report: SmokeTestReport, directory: Path) -> Path:
    path = directory / "API-Smoke-Test-Report.html"
    path.write_text(generate_html_report(report), encoding="utf-8")
    logger.info("ReportGenerated type=html path=%s", path)
    return path


def _overall_class(status: str) -> str:
    if status == "FAIL":
        return "fail"
    if "WARN" in status:
        return "warn"
    return "pass"


def _kv_table(data: dict) -> str:
    if not data:
        return "<em>(none)</em>"
    rows = "".join(
        f"<tr><td>{html.escape(str(k))}</td><td><code>{html.escape(str(v))}</code></td></tr>"
        for k, v in data.items()
    )
    return f"<table class='kv'>{rows}</table>"


_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{title}</title>
<style>
:root {{
  --bg:#0f1419; --panel:#1a2332; --border:#2d3a4d; --text:#e7ecf3; --muted:#8b9bb4;
  --pass:#3dd68c; --fail:#f07178; --warn:#ffcc66; --info:#82aaff; --skip:#7a8699;
  --accent:#5b9fd4;
}}
* {{ box-sizing:border-box; }}
body {{
  margin:0; font-family: "Segoe UI", system-ui, -apple-system, sans-serif;
  background:var(--bg); color:var(--text); line-height:1.5;
}}
.wrap {{ max-width:1100px; margin:0 auto; padding:32px 20px 64px; }}
h1 {{ font-size:1.75rem; margin:0 0 4px; font-weight:650; letter-spacing:-0.02em; }}
.sub {{ color:var(--muted); margin-bottom:24px; }}
.badge {{
  display:inline-block; padding:4px 12px; border-radius:4px; font-weight:600; font-size:0.85rem;
}}
.badge.pass {{ background:#1b3d2f; color:var(--pass); }}
.badge.warn {{ background:#3d3420; color:var(--warn); }}
.badge.fail {{ background:#3d1f24; color:var(--fail); }}
.cards {{ display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin:20px 0; }}
.card {{
  background:var(--panel); border:1px solid var(--border); border-radius:8px; padding:16px;
}}
.card .label {{ color:var(--muted); font-size:0.75rem; text-transform:uppercase; letter-spacing:0.06em; }}
.card .value {{ font-size:1.75rem; font-weight:700; margin-top:4px; }}
.card.pass .value {{ color:var(--pass); }}
.card.fail .value {{ color:var(--fail); }}
.card.warn .value {{ color:var(--warn); }}
.health {{
  background:var(--panel); border:1px solid var(--border); border-radius:8px;
  padding:20px; margin:16px 0 24px;
}}
.health .score {{ font-size:2.5rem; font-weight:700; color:var(--accent); }}
.bar {{ font-family:ui-monospace,monospace; color:var(--accent); letter-spacing:1px; }}
.dist {{ font-family:ui-monospace,monospace; font-size:0.85rem; color:var(--muted); white-space:pre; }}
.toolbar {{
  display:flex; flex-wrap:wrap; gap:8px; align-items:center; margin:16px 0 8px;
}}
.toolbar input, .toolbar select {{
  background:var(--panel); border:1px solid var(--border); color:var(--text);
  padding:8px 10px; border-radius:6px; font-size:0.9rem;
}}
table.results {{
  width:100%; border-collapse:collapse; background:var(--panel);
  border:1px solid var(--border); border-radius:8px; overflow:hidden;
}}
table.results th, table.results td {{
  text-align:left; padding:10px 12px; border-bottom:1px solid var(--border); font-size:0.9rem;
}}
table.results th {{ color:var(--muted); font-weight:600; cursor:pointer; user-select:none; }}
table.results tr:hover td {{ background:#222c3c; }}
table.results tr.expanded td {{ background:#222c3c; }}
.status {{ font-weight:600; font-size:0.8rem; }}
.status.PASS {{ color:var(--pass); }}
.status.FAIL {{ color:var(--fail); }}
.status.WARNING {{ color:var(--warn); }}
.status.SKIPPED {{ color:var(--skip); }}
.status.INFO {{ color:var(--info); }}
.detail {{
  display:none; padding:12px 16px 16px; background:#151c27; border-bottom:1px solid var(--border);
  font-size:0.85rem; color:var(--muted);
}}
.detail.open {{ display:block; }}
.detail strong {{ color:var(--text); }}
pre {{
  background:#0d1117; border:1px solid var(--border); border-radius:6px;
  padding:12px; overflow:auto; color:#c9d1d9; font-size:0.8rem;
}}
details.section {{
  background:var(--panel); border:1px solid var(--border); border-radius:8px;
  margin:12px 0; padding:12px 16px;
}}
details.section summary {{ cursor:pointer; font-weight:600; }}
table.kv td {{ padding:4px 12px 4px 0; vertical-align:top; }}
table.kv td:first-child {{ color:var(--muted); white-space:nowrap; }}
@media (max-width:720px) {{ .cards {{ grid-template-columns:1fr 1fr; }} }}
</style>
</head>
<body>
<div class="wrap">
  <h1>{title}</h1>
  <div class="sub">
    Endpoint: <strong>{endpoint}</strong><br/>
    Generated: {generated}<br/>
    Overall: <span class="badge {overall_class}">{overall}</span>
    &nbsp;·&nbsp; Duration: {duration_ms} ms
  </div>

  <div class="cards">
    <div class="card"><div class="label">Total</div><div class="value">{total}</div></div>
    <div class="card pass"><div class="label">Passed</div><div class="value">{passed}</div></div>
    <div class="card fail"><div class="label">Failed</div><div class="value">{failed}</div></div>
    <div class="card warn"><div class="label">Warning</div><div class="value">{warnings}</div></div>
  </div>

  <div class="health">
    <div class="label" style="color:var(--muted);font-size:0.75rem;text-transform:uppercase;letter-spacing:0.06em;">
      API Health Score
    </div>
    <div class="score">{health_score}%</div>
    <div class="bar">{score_bar}</div>
    <p style="color:var(--muted);font-size:0.8rem;margin:8px 0 0;">
      Score = average of per-test weights (PASS=100, WARNING=70, FAIL=0, SKIPPED=50, INFO=100). Configurable via settings.
    </p>
    <div class="dist" style="margin-top:12px;">
PASS       {bar_pass} {n_pass}
WARNING    {bar_warn} {n_warn}
FAIL       {bar_fail} {n_fail}
SKIPPED    {bar_skip} {n_skip}
    </div>
  </div>

  <div class="toolbar">
    <input id="search" type="search" placeholder="Search tests…" style="min-width:200px;"/>
    <select id="statusFilter">
      <option value="">All statuses</option>
      <option>PASS</option><option>FAIL</option><option>WARNING</option>
      <option>SKIPPED</option><option>INFO</option>
    </select>
    <select id="severityFilter">
      <option value="">All severities</option>
      <option>CRITICAL</option><option>HIGH</option><option>MEDIUM</option>
      <option>LOW</option><option>INFO</option>
    </select>
  </div>

  <table class="results" id="resultsTable">
    <thead>
      <tr>
        <th data-sort="name">Test</th>
        <th data-sort="status">Status</th>
        <th data-sort="duration">Duration</th>
        <th data-sort="severity">Severity</th>
      </tr>
    </thead>
    <tbody id="resultsBody"></tbody>
  </table>

  <details class="section" open>
    <summary>REQUEST</summary>
    <p><strong>{req_method}</strong> {req_url}</p>
    <p><strong>Headers</strong></p>
    {req_headers}
    <p><strong>Body</strong></p>
    <pre>{req_body}</pre>
  </details>

  <details class="section" open>
    <summary>RESPONSE</summary>
    <p>Status: <strong>{resp_status}</strong> · Response Time: <strong>{resp_time} ms</strong></p>
    <p><strong>Headers</strong></p>
    {resp_headers}
    <p><strong>Body</strong></p>
    <pre>{resp_body}</pre>
  </details>
</div>
<script>
const ROWS = {rows_json};
let sortKey = "name";
let sortAsc = true;

function render() {{
  const q = document.getElementById("search").value.toLowerCase();
  const sf = document.getElementById("statusFilter").value;
  const vf = document.getElementById("severityFilter").value;
  let rows = ROWS.filter(r => {{
    if (sf && r.status !== sf) return false;
    if (vf && r.severity !== vf) return false;
    if (q && !(r.name.toLowerCase().includes(q) || r.id.toLowerCase().includes(q)
        || (r.message||"").toLowerCase().includes(q))) return false;
    return true;
  }});
  rows.sort((a,b) => {{
    let av = a[sortKey], bv = b[sortKey];
    if (typeof av === "string") av = av.toLowerCase();
    if (typeof bv === "string") bv = bv.toLowerCase();
    if (av < bv) return sortAsc ? -1 : 1;
    if (av > bv) return sortAsc ? 1 : -1;
    return 0;
  }});
  const tb = document.getElementById("resultsBody");
  tb.innerHTML = "";
  rows.forEach((r, i) => {{
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${{esc(r.name)}} <span style="color:var(--muted);font-size:0.75rem">${{esc(r.id)}}</span></td>
      <td><span class="status ${{r.status}}">${{r.status}}</span></td>
      <td>${{r.duration}} ms</td>
      <td>${{esc(r.severity)}}</td>`;
    const detail = document.createElement("tr");
    detail.innerHTML = `<td colspan="4"><div class="detail" id="d${{i}}">
      <div><strong>Expected:</strong> ${{esc(r.expected)}}</div>
      <div><strong>Actual:</strong> ${{esc(r.actual)}}</div>
      <div><strong>Message:</strong> ${{esc(r.message)}}</div>
      <pre>${{esc(JSON.stringify(r.details || {{}}, null, 2))}}</pre>
    </div></td>`;
    tr.addEventListener("click", () => {{
      tr.classList.toggle("expanded");
      document.getElementById("d"+i).classList.toggle("open");
    }});
    tb.appendChild(tr);
    tb.appendChild(detail);
  }});
}}
function esc(s) {{
  return String(s ?? "").replace(/[&<>"']/g, c => ({{
    "&":"&amp;","<":"&lt;",">":"&gt;","\\"":"&quot;","'":"&#39;"
  }})[c]);
}}
document.getElementById("search").addEventListener("input", render);
document.getElementById("statusFilter").addEventListener("change", render);
document.getElementById("severityFilter").addEventListener("change", render);
document.querySelectorAll("th[data-sort]").forEach(th => {{
  th.addEventListener("click", () => {{
    const k = th.getAttribute("data-sort");
    if (sortKey === k) sortAsc = !sortAsc; else {{ sortKey = k; sortAsc = true; }}
    render();
  }});
}});
render();
</script>
</body>
</html>
"""
