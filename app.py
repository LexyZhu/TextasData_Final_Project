"""
app.py — Paper Sieve Web App

A Flask web app that lets users input keyword groups and a time range,
runs searches across arXiv, OpenAlex, Scopus, and WoS,
deduplicates results, and returns a combined CSV for download.

Usage:
    pip install flask feedparser requests
    python app.py

    Then open http://localhost:5000 in your browser.

Optional (for WoS/Scopus):
    pip install clarivate.wos_starter.client
"""

from flask import Flask, request, render_template_string, send_file, jsonify
import os
import re
import csv
import json
import threading
import uuid
from datetime import datetime

# Import your search modules
from search_arxiv import search_arxiv
from search_openalex import search_openalex

app = Flask(__name__)

# Store running jobs: job_id -> {status, progress, results, error}
jobs = {}

# ──────────────────────────────────────────────────────────────
# DEDUPLICATION
# ──────────────────────────────────────────────────────────────

def normalize_title(title):
    if not title:
        return ""
    t = title.lower().strip()
    t = re.sub(r"[^a-z0-9\s]", "", t)
    t = re.sub(r"\s+", " ", t)
    return t


def deduplicate(papers):
    seen = set()
    unique = []
    for paper in papers:
        key = normalize_title(paper.get("title", ""))
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(paper)
    return unique


# ──────────────────────────────────────────────────────────────
# SEARCH WORKER (runs in background thread)
# ──────────────────────────────────────────────────────────────

def run_search(job_id, keywords, date_from, date_to, sources, scopus_key, wos_key, oa_email):
    job = jobs[job_id]
    all_results = []

    try:
        # arXiv
        if "arxiv" in sources:
            job["progress"] = "Searching arXiv..."
            try:
                results = search_arxiv(
                    keywords=keywords,
                    time_lower_bound=date_from,
                    time_upper_bound=date_to,
                )
                for r in results:
                    r["source"] = "arXiv"
                all_results.extend(results)
                job["progress"] = f"arXiv: {len(results)} papers found"
            except Exception as e:
                job["progress"] = f"arXiv error: {e}"

        # OpenAlex
        if "openalex" in sources:
            job["progress"] = "Searching OpenAlex..."
            try:
                results = search_openalex(
                    keywords=keywords,
                    time_lower_bound=date_from,
                    time_upper_bound=date_to,
                    email=oa_email,
                )
                for r in results:
                    r["source"] = "OpenAlex"
                all_results.extend(results)
                job["progress"] = f"OpenAlex: {len(results)} papers found"
            except Exception as e:
                job["progress"] = f"OpenAlex error: {e}"

        # Scopus
        if "scopus" in sources and scopus_key:
            job["progress"] = "Searching Scopus..."
            try:
                from search_scopus import search_scopus
                results = search_scopus(
                    keywords=keywords,
                    api_key=scopus_key,
                    time_lower_bound=date_from,
                    time_upper_bound=date_to,
                    fetch_abstracts=False,  # faster
                )
                for r in results:
                    r["source"] = "Scopus"
                all_results.extend(results)
                job["progress"] = f"Scopus: {len(results)} papers found"
            except Exception as e:
                job["progress"] = f"Scopus error: {e}"

        # WoS
        if "wos" in sources and wos_key:
            job["progress"] = "Searching Web of Science..."
            try:
                from search_wos import search_wos
                results = search_wos(
                    keywords=keywords,
                    api_key=wos_key,
                    time_lower_bound=date_from,
                    time_upper_bound=date_to,
                )
                for r in results:
                    r["source"] = "WoS"
                all_results.extend(results)
                job["progress"] = f"WoS: {len(results)} papers found"
            except Exception as e:
                job["progress"] = f"WoS error: {e}"

        # Deduplicate
        job["progress"] = "Deduplicating..."
        unique = deduplicate(all_results)

        # Save CSV
        output_dir = "output"
        os.makedirs(output_dir, exist_ok=True)
        csv_path = os.path.join(output_dir, f"{job_id}.csv")

        if unique:
            fieldnames = ["title", "authors", "summary", "published", "link", "source"]
            with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(unique)

        job["status"] = "done"
        job["progress"] = f"Done. {len(all_results)} raw → {len(unique)} unique papers"
        job["csv_path"] = csv_path
        job["count"] = len(unique)
        job["raw_count"] = len(all_results)

        # Source breakdown
        src_counts = {}
        for p in unique:
            s = p.get("source", "unknown")
            src_counts[s] = src_counts.get(s, 0) + 1
        job["source_counts"] = src_counts

    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)
        job["progress"] = f"Error: {e}"


# ──────────────────────────────────────────────────────────────
# HTML TEMPLATE
# ──────────────────────────────────────────────────────────────

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Paper Sieve</title>
<link href="https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,400;8..60,600;8..60,700&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Source Serif 4', Georgia, serif; background: #F5F4F0; color: #1C1917; min-height: 100vh; }
.mono { font-family: 'IBM Plex Mono', monospace; }

.header { background: #1C1917; border-bottom: 3px solid #C084FC; padding: 18px 0; }
.header-inner { max-width: 720px; margin: 0 auto; padding: 0 24px; }
.header h1 { font-size: 22px; font-weight: 700; color: #FAFAF9; letter-spacing: -0.03em; }
.header .sub { font-size: 11px; color: #78716C; font-family: 'IBM Plex Mono', monospace; margin-top: 2px; }

.container { max-width: 720px; margin: 0 auto; padding: 28px 24px 60px; }

.card { background: #fff; border: 1px solid #E2E0DA; border-radius: 10px; padding: 20px 24px; margin-bottom: 14px; }
.card-title { font-size: 13px; font-weight: 600; color: #78716C; text-transform: uppercase; letter-spacing: 0.06em; font-family: 'IBM Plex Mono', monospace; margin-bottom: 14px; }

.group-row { display: flex; gap: 10px; align-items: center; margin-bottom: 10px; }
.group-label { font-size: 12px; font-weight: 600; color: #57534E; width: 90px; flex-shrink: 0; }
.group-input { flex: 1; height: 34px; padding: 0 10px; border-radius: 6px; font-size: 12px;
  border: 1px solid #E2E0DA; background: #FAFAF8; color: #1C1917;
  font-family: 'IBM Plex Mono', monospace; outline: none; }
.group-input:focus { border-color: #C084FC; }
.group-hint { font-size: 10px; color: #A8A29E; font-family: 'IBM Plex Mono', monospace; margin-top: -6px; margin-bottom: 10px; margin-left: 100px; }

.row { display: flex; gap: 10px; align-items: center; margin-bottom: 10px; }
.row label { font-size: 12px; font-weight: 600; color: #57534E; width: 90px; flex-shrink: 0; }
.row input { flex: 1; height: 34px; padding: 0 10px; border-radius: 6px; font-size: 12px;
  border: 1px solid #E2E0DA; background: #FAFAF8; color: #1C1917;
  font-family: 'IBM Plex Mono', monospace; outline: none; }

.check-row { display: flex; gap: 16px; align-items: center; margin-bottom: 6px; flex-wrap: wrap; }
.check-row label { font-size: 12px; color: #57534E; display: flex; align-items: center; gap: 5px; cursor: pointer; }
.check-row input[type="checkbox"] { accent-color: #C084FC; }

.btn { width: 100%; padding: 13px; border-radius: 8px; font-size: 14px; font-weight: 700;
  border: none; background: #1C1917; color: #fff; cursor: pointer;
  font-family: 'Source Serif 4', Georgia, serif; letter-spacing: -0.01em; transition: background 0.15s; }
.btn:hover { background: #292524; }
.btn:disabled { background: #78716C; cursor: not-allowed; }

.progress-box { margin-top: 14px; padding: 14px 18px; background: #1C1917; border-radius: 8px; display: none; }
.progress-text { font-size: 11px; color: #A8A29E; font-family: 'IBM Plex Mono', monospace; line-height: 1.8; }
.progress-text .done { color: #4ADE80; }
.progress-text .err { color: #FCA5A5; }

.result-box { margin-top: 14px; padding: 18px 24px; background: #fff; border: 1px solid #E2E0DA;
  border-radius: 10px; display: none; }
.result-box h3 { font-size: 16px; font-weight: 700; margin-bottom: 10px; }
.stat-row { display: flex; gap: 14px; margin-bottom: 14px; flex-wrap: wrap; }
.stat { background: #FAFAF8; border-radius: 6px; padding: 10px 14px; flex: 1; min-width: 100px; }
.stat .label { font-size: 9px; color: #A8A29E; font-family: 'IBM Plex Mono', monospace; text-transform: uppercase; letter-spacing: 0.06em; }
.stat .value { font-size: 20px; font-weight: 700; letter-spacing: -0.02em; margin-top: 2px; }

.dl-btn { display: inline-block; padding: 10px 24px; border-radius: 6px; font-size: 13px; font-weight: 600;
  border: 2px solid #C084FC; background: #F3E8FF; color: #6B21A8; cursor: pointer;
  font-family: 'Source Serif 4', Georgia, serif; text-decoration: none; transition: background 0.15s; }
.dl-btn:hover { background: #EDE9FE; }

.add-group-btn { padding: 6px 14px; border-radius: 5px; font-size: 11px;
  border: 1px dashed #D6D3D1; background: transparent; color: #78716C;
  cursor: pointer; font-family: 'IBM Plex Mono', monospace; margin-bottom: 10px; }
.remove-btn { width: 28px; height: 28px; border-radius: 4px; border: 1px solid #E2E0DA;
  background: #fff; color: #A8A29E; cursor: pointer; font-size: 14px; display: flex;
  align-items: center; justify-content: center; flex-shrink: 0; }
.remove-btn:hover { background: #FEF2F2; color: #991B1B; border-color: #FCA5A5; }
</style>
</head>
<body>

<div class="header">
  <div class="header-inner">
    <h1>Paper Sieve</h1>
    <div class="sub">type keywords → search arXiv · OpenAlex · Scopus · WoS → download CSV</div>
  </div>
</div>

<div class="container">

  <form id="searchForm" onsubmit="startSearch(event)">

    <!-- Keyword Groups -->
    <div class="card">
      <div class="card-title">Keyword Groups</div>
      <p style="font-size:12px; color:#78716C; margin-bottom:14px;">
        Each group is OR-joined internally. Groups are AND-joined together.<br>
        Separate keywords with commas.
      </p>
      <div id="groups-container">
        <div class="group-row">
          <span class="group-label">Group 1</span>
          <input class="group-input kw-group" placeholder="agent, chatbot" value="agent, chatbot">
          <button type="button" class="remove-btn" onclick="removeGroup(this)" title="Remove">×</button>
        </div>
        <div class="group-row">
          <span class="group-label">Group 2</span>
          <input class="group-input kw-group" placeholder="ai, llm, large language model" value="ai, llm, large language model">
          <button type="button" class="remove-btn" onclick="removeGroup(this)" title="Remove">×</button>
        </div>
        <div class="group-row">
          <span class="group-label">Group 3</span>
          <input class="group-input kw-group" placeholder="mental health, psychiatry, psychology" value="mental health, psychiatry, psychology">
          <button type="button" class="remove-btn" onclick="removeGroup(this)" title="Remove">×</button>
        </div>
      </div>
      <button type="button" class="add-group-btn" onclick="addGroup()">+ Add group</button>
    </div>

    <!-- Time Range -->
    <div class="card">
      <div class="card-title">Time Range</div>
      <div class="row">
        <label>From</label>
        <input type="date" id="dateFrom" value="2023-01-01">
      </div>
      <div class="row">
        <label>To</label>
        <input type="date" id="dateTo" value="2025-07-01">
      </div>
    </div>

    <!-- Sources -->
    <div class="card">
      <div class="card-title">Sources</div>
      <div class="check-row">
        <label><input type="checkbox" name="sources" value="arxiv" checked> arXiv</label>
        <label><input type="checkbox" name="sources" value="openalex" checked> OpenAlex</label>
        <label><input type="checkbox" name="sources" value="scopus"> Scopus</label>
        <label><input type="checkbox" name="sources" value="wos"> Web of Science</label>
      </div>
      <div id="api-keys" style="margin-top:12px;">
        <div class="row" id="scopus-key-row" style="display:none;">
          <label>Scopus key</label>
          <input type="password" id="scopusKey" placeholder="Elsevier API key">
        </div>
        <div class="row" id="wos-key-row" style="display:none;">
          <label>WoS key</label>
          <input type="password" id="wosKey" placeholder="Clarivate API key">
        </div>
      </div>
    </div>

    <!-- Email -->
    <div class="card">
      <div class="card-title">Contact Email</div>
      <p style="font-size:11px; color:#A8A29E; margin-bottom:8px; font-family:'IBM Plex Mono',monospace;">
        Used for OpenAlex rate limits (not stored)
      </p>
      <div class="row">
        <label>Email</label>
        <input type="email" id="oaEmail" value="your@email.com">
      </div>
    </div>

    <button type="submit" class="btn" id="searchBtn">Search & Download CSV</button>
  </form>

  <!-- Progress -->
  <div class="progress-box" id="progressBox">
    <div class="progress-text" id="progressText"></div>
  </div>

  <!-- Results -->
  <div class="result-box" id="resultBox">
    <h3>Search Complete</h3>
    <div class="stat-row" id="stats"></div>
    <div id="sourceBreakdown" style="margin-bottom:14px;"></div>
    <a class="dl-btn" id="downloadBtn" href="#">Download CSV</a>
  </div>

</div>

<script>
// Show/hide API key fields based on checkbox
document.querySelectorAll('input[name="sources"]').forEach(cb => {
  cb.addEventListener('change', () => {
    document.getElementById('scopus-key-row').style.display =
      document.querySelector('input[value="scopus"]').checked ? 'flex' : 'none';
    document.getElementById('wos-key-row').style.display =
      document.querySelector('input[value="wos"]').checked ? 'flex' : 'none';
  });
});

function addGroup() {
  const container = document.getElementById('groups-container');
  const count = container.children.length + 1;
  const row = document.createElement('div');
  row.className = 'group-row';
  row.innerHTML = `
    <span class="group-label">Group ${count}</span>
    <input class="group-input kw-group" placeholder="keyword1, keyword2, ...">
    <button type="button" class="remove-btn" onclick="removeGroup(this)" title="Remove">×</button>
  `;
  container.appendChild(row);
}

function removeGroup(btn) {
  const container = document.getElementById('groups-container');
  if (container.children.length > 1) {
    btn.parentElement.remove();
    // Re-number
    Array.from(container.children).forEach((row, i) => {
      row.querySelector('.group-label').textContent = `Group ${i + 1}`;
    });
  }
}

let pollInterval = null;

async function startSearch(e) {
  e.preventDefault();

  // Gather keyword groups
  const inputs = document.querySelectorAll('.kw-group');
  const keywords = [];
  inputs.forEach(inp => {
    const val = inp.value.trim();
    if (val) {
      keywords.push(val.split(',').map(k => k.trim()).filter(k => k));
    }
  });

  if (keywords.length === 0 || keywords.every(g => g.length === 0)) {
    alert('Enter at least one keyword group');
    return;
  }

  const sources = Array.from(document.querySelectorAll('input[name="sources"]:checked')).map(cb => cb.value);
  if (sources.length === 0) {
    alert('Select at least one source');
    return;
  }

  const body = {
    keywords,
    date_from: document.getElementById('dateFrom').value,
    date_to: document.getElementById('dateTo').value,
    sources,
    scopus_key: document.getElementById('scopusKey').value,
    wos_key: document.getElementById('wosKey').value,
    oa_email: document.getElementById('oaEmail').value,
  };

  // UI
  document.getElementById('searchBtn').disabled = true;
  document.getElementById('searchBtn').textContent = 'Searching...';
  document.getElementById('progressBox').style.display = 'block';
  document.getElementById('resultBox').style.display = 'none';
  document.getElementById('progressText').innerHTML = '<span>Starting search...</span>';

  // Start job
  const res = await fetch('/api/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const { job_id } = await res.json();

  // Poll for progress
  pollInterval = setInterval(async () => {
    const r = await fetch(`/api/status/${job_id}`);
    const data = await r.json();

    const el = document.getElementById('progressText');
    el.innerHTML += `<br><span>${data.progress}</span>`;
    el.parentElement.scrollTop = el.parentElement.scrollHeight;

    if (data.status === 'done') {
      clearInterval(pollInterval);
      document.getElementById('searchBtn').disabled = false;
      document.getElementById('searchBtn').textContent = 'Search & Download CSV';

      // Mark last line green
      el.innerHTML += `<br><span class="done">✓ ${data.progress}</span>`;

      // Show results
      document.getElementById('resultBox').style.display = 'block';
      document.getElementById('stats').innerHTML = `
        <div class="stat"><div class="label">Raw total</div><div class="value">${data.raw_count}</div></div>
        <div class="stat"><div class="label">Unique</div><div class="value" style="color:#059669">${data.count}</div></div>
        <div class="stat"><div class="label">Duplicates removed</div><div class="value" style="color:#78716C">${data.raw_count - data.count}</div></div>
      `;

      let breakdown = '<div style="font-size:11px; font-family:IBM Plex Mono,monospace; color:#57534E;">';
      for (const [src, cnt] of Object.entries(data.source_counts || {})) {
        breakdown += `<span style="margin-right:16px;">${src}: <strong>${cnt}</strong></span>`;
      }
      breakdown += '</div>';
      document.getElementById('sourceBreakdown').innerHTML = breakdown;

      document.getElementById('downloadBtn').href = `/api/download/${job_id}`;
    }

    if (data.status === 'error') {
      clearInterval(pollInterval);
      document.getElementById('searchBtn').disabled = false;
      document.getElementById('searchBtn').textContent = 'Search & Download CSV';
      el.innerHTML += `<br><span class="err">✗ Error: ${data.error}</span>`;
    }
  }, 2000);
}
</script>
</body>
</html>
"""

# ──────────────────────────────────────────────────────────────
# ROUTES
# ──────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/api/search", methods=["POST"])
def api_search():
    data = request.json
    keywords = data.get("keywords", [])
    date_from = data.get("date_from", "2023-01-01")
    date_to = data.get("date_to", "2025-07-01")
    sources = data.get("sources", ["arxiv", "openalex"])
    scopus_key = data.get("scopus_key", "")
    wos_key = data.get("wos_key", "")
    oa_email = data.get("oa_email", "your@email.com")

    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {
        "status": "running",
        "progress": "Starting...",
        "csv_path": None,
        "count": 0,
        "raw_count": 0,
        "source_counts": {},
        "error": None,
    }

    thread = threading.Thread(
        target=run_search,
        args=(job_id, keywords, date_from, date_to, sources, scopus_key, wos_key, oa_email),
        daemon=True,
    )
    thread.start()

    return jsonify({"job_id": job_id})


@app.route("/api/status/<job_id>")
def api_status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"status": "not_found"}), 404
    return jsonify(job)


@app.route("/api/download/<job_id>")
def api_download(job_id):
    job = jobs.get(job_id)
    if not job or not job.get("csv_path"):
        return "Not found", 404

    return send_file(
        job["csv_path"],
        as_attachment=True,
        download_name=f"papers_{job_id}.csv",
        mimetype="text/csv",
    )


if __name__ == "__main__":
    os.makedirs("output", exist_ok=True)
    print("\n" + "=" * 50)
    print("  Paper Sieve — http://localhost:5000")
    print("=" * 50 + "\n")
    app.run(debug=True, port=5000)
