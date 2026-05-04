"""
app.py — Paper Sieve Web App

Clean web interface: users enter Topic/Domain and Methods/Tools keywords,
pick a time range, and download a combined deduplicated CSV of papers
from arXiv, OpenAlex, Scopus, and Web of Science.
"""

from flask import Flask, request, render_template_string, send_file, jsonify
import os
import re
import csv
import threading
import uuid

from search_arxiv import search_arxiv
from search_openalex import search_openalex
from search_scopus import search_scopus
from search_wos import search_wos

app = Flask(__name__)
jobs = {}

# need to delete after project marking
SCOPUS_API_KEY = "a6a4b4a8f0ff49676823b4b795cff8aa"
WOS_API_KEY = "296c7877068fd5bba5e70c4dd8540bfbbcf37346"


# ── Deduplication ──

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


# ── Search Worker ──

def run_search(job_id, keywords, date_from, date_to):
    job = jobs[job_id]
    all_results = []
    counts = {}

    try:
        # 1. arXiv
        job["progress"] = "Searching arXiv (1/4)..."
        try:
            results = search_arxiv(keywords=keywords, time_lower_bound=date_from, time_upper_bound=date_to)
            for r in results:
                r["source"] = "arXiv"
            all_results.extend(results)
            counts["arXiv"] = len(results)
        except Exception as e:
            counts["arXiv"] = 0
            print(f"arXiv error: {e}")

        job["progress"] = f"arXiv: {counts.get('arXiv', 0)} · Searching OpenAlex (2/4)..."

        # 2. OpenAlex
        try:
            results = search_openalex(keywords=keywords, time_lower_bound=date_from, time_upper_bound=date_to)
            for r in results:
                r["source"] = "OpenAlex"
            all_results.extend(results)
            counts["OpenAlex"] = len(results)
        except Exception as e:
            counts["OpenAlex"] = 0
            print(f"OpenAlex error: {e}")

        job["progress"] = f"arXiv: {counts.get('arXiv', 0)} · OpenAlex: {counts.get('OpenAlex', 0)} · Searching Scopus (3/4)..."

        # 3. Scopus
        try:
            results = search_scopus(
                keywords=keywords,
                api_key=SCOPUS_API_KEY,
                time_lower_bound=date_from,
                time_upper_bound=date_to,
            )
            for r in results:
                r["source"] = "Scopus"
            all_results.extend(results)
            counts["Scopus"] = len(results)
        except Exception as e:
            counts["Scopus"] = 0
            print(f"Scopus error: {e}")

        job["progress"] = f"arXiv: {counts.get('arXiv', 0)} · OpenAlex: {counts.get('OpenAlex', 0)} · Scopus: {counts.get('Scopus', 0)} · Searching WoS (4/4)..."

        # 4. Web of Science
        try:
            results = search_wos(
                keywords=keywords,
                api_key=WOS_API_KEY,
                time_lower_bound=date_from,
                time_upper_bound=date_to,
            )
            for r in results:
                r["source"] = "Web of Science"
            all_results.extend(results)
            counts["Web of Science"] = len(results)
        except Exception as e:
            counts["Web of Science"] = 0
            print(f"WoS error: {e}")

        # Deduplicate & save
        job["progress"] = "Deduplicating..."
        unique = deduplicate(all_results)

        output_dir = "output"
        os.makedirs(output_dir, exist_ok=True)
        csv_path = os.path.join(output_dir, f"{job_id}.csv")

        if unique:
            fieldnames = ["title", "authors", "summary", "published", "link", "source"]
            with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(unique)

        parts = [f"{src}: {cnt}" for src, cnt in counts.items() if cnt > 0]
        summary = " · ".join(parts)
        dupes = len(all_results) - len(unique)

        job["status"] = "done"
        job["progress"] = f"Done — {len(unique)} unique papers ({summary}, {dupes} duplicates removed)"
        job["csv_path"] = csv_path
        job["count"] = len(unique)
        job["raw_count"] = len(all_results)
        job["source_counts"] = counts

    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)
        job["progress"] = f"Error: {e}"


# ── HTML ──

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Paper Sieve</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: 'Inter', -apple-system, sans-serif;
  background: #FAFAF9;
  color: #1C1917;
  min-height: 100vh;
}

.hero {
  padding: 80px 24px 60px;
  text-align: center;
  background: linear-gradient(180deg, #F5F5F0 0%, #FAFAF9 100%);
}
.hero h1 {
  font-size: 40px;
  font-weight: 700;
  letter-spacing: -0.03em;
  color: #1C1917;
  margin-bottom: 8px;
}
.hero p {
  font-size: 16px;
  color: #78716C;
  font-weight: 400;
}

.search-wrap {
  max-width: 620px;
  margin: -20px auto 0;
  padding: 0 24px 80px;
  position: relative;
}
.search-box {
  background: #fff;
  border: 1px solid #E7E5E4;
  border-radius: 12px;
  padding: 28px 32px 24px;
  box-shadow: 0 1px 3px rgba(0,0,0,.04), 0 6px 24px rgba(0,0,0,.03);
}

.field-group { margin-bottom: 20px; }
.field-label {
  font-size: 13px;
  font-weight: 600;
  color: #44403C;
  margin-bottom: 6px;
  display: block;
}
.field-hint {
  font-size: 11px;
  color: #A8A29E;
  margin-bottom: 8px;
  display: block;
}
.field-input {
  width: 100%;
  height: 44px;
  padding: 0 14px;
  border-radius: 8px;
  font-size: 14px;
  border: 1px solid #E7E5E4;
  background: #FAFAF9;
  color: #1C1917;
  font-family: 'Inter', sans-serif;
  outline: none;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.field-input:focus {
  border-color: #1C1917;
  box-shadow: 0 0 0 3px rgba(28,25,23,.06);
}
.field-input::placeholder { color: #D6D3D1; }

.date-row { display: flex; gap: 12px; }
.date-row .date-field { flex: 1; }
.date-row .date-field label {
  font-size: 11px;
  font-weight: 500;
  color: #78716C;
  margin-bottom: 4px;
  display: block;
}
.date-input {
  width: 100%;
  height: 40px;
  padding: 0 10px;
  border-radius: 8px;
  font-size: 13px;
  border: 1px solid #E7E5E4;
  background: #FAFAF9;
  color: #1C1917;
  font-family: 'Inter', sans-serif;
  outline: none;
}
.date-input:focus { border-color: #1C1917; }

.divider {
  border: none;
  border-top: 1px solid #F5F5F4;
  margin: 20px 0;
}

.submit-btn {
  width: 100%;
  height: 48px;
  border-radius: 8px;
  font-size: 15px;
  font-weight: 600;
  border: none;
  background: #1C1917;
  color: #fff;
  cursor: pointer;
  font-family: 'Inter', sans-serif;
  transition: background 0.15s;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}
.submit-btn:hover { background: #292524; }
.submit-btn:disabled { background: #A8A29E; cursor: not-allowed; }
.submit-btn .arrow { font-size: 18px; opacity: 0.7; }

.progress-area {
  margin-top: 16px;
  display: none;
}
.progress-bar-track {
  height: 3px;
  background: #F5F5F4;
  border-radius: 2px;
  overflow: hidden;
  margin-bottom: 10px;
}
.progress-bar-fill {
  height: 100%;
  background: #1C1917;
  width: 0%;
  border-radius: 2px;
  transition: width 0.5s;
}
.progress-status {
  font-size: 12px;
  color: #78716C;
  text-align: center;
}

.result-area {
  margin-top: 20px;
  display: none;
}
.result-card {
  background: #fff;
  border: 1px solid #E7E5E4;
  border-radius: 12px;
  padding: 24px 28px;
  text-align: center;
}
.result-count {
  font-size: 48px;
  font-weight: 700;
  color: #1C1917;
  letter-spacing: -0.03em;
}
.result-label {
  font-size: 14px;
  color: #78716C;
  margin-top: 2px;
  margin-bottom: 4px;
}
.result-breakdown {
  font-size: 12px;
  color: #A8A29E;
  margin-bottom: 20px;
}
.dl-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 12px 32px;
  border-radius: 8px;
  font-size: 15px;
  font-weight: 600;
  border: none;
  background: #1C1917;
  color: #fff;
  cursor: pointer;
  font-family: 'Inter', sans-serif;
  text-decoration: none;
  transition: background 0.15s;
}
.dl-btn:hover { background: #292524; }
.dl-btn svg { width: 18px; height: 18px; }

.footer {
  text-align: center;
  padding: 40px 24px;
  font-size: 11px;
  color: #D6D3D1;
}
</style>
</head>
<body>

<div class="hero">
  <h1>Paper Sieve - 1:30 version</h1>
  <p>Search academic papers across databases and download results as CSV</p>
</div>

<div class="search-wrap">
  <form id="searchForm" onsubmit="startSearch(event)" class="search-box">

    <div class="field-group">
      <label class="field-label">Topic / Domain</label>
      <span class="field-hint">Separate keywords with commas — these are OR-joined</span>
      <input class="field-input" id="topicInput" placeholder="e.g. social science, economics" value="social science, economics">
    </div>

    <div class="field-group">
      <label class="field-label">Methods / Tools</label>
      <span class="field-hint">Separate keywords with commas — these are OR-joined</span>
      <input class="field-input" id="methodInput" placeholder="e.g. AI, large language model" value="AI, large language model">
    </div>

    <hr class="divider">

    <div class="field-group">
      <label class="field-label">Time Range</label>
      <div class="date-row">
        <div class="date-field">
          <label>From</label>
          <input type="date" class="date-input" id="dateFrom" value="2026-01-01">
        </div>
        <div class="date-field">
          <label>To</label>
          <input type="date" class="date-input" id="dateTo" value="2026-05-01">
        </div>
      </div>
    </div>

    <button type="submit" class="submit-btn" id="searchBtn">
      Search papers <span class="arrow">↗</span>
    </button>

    <div class="progress-area" id="progressArea">
      <div class="progress-bar-track">
        <div class="progress-bar-fill" id="progressFill"></div>
      </div>
      <div class="progress-status" id="progressStatus">Starting...</div>
    </div>

    <div class="result-area" id="resultArea">
      <div class="result-card">
        <div class="result-count" id="resultCount">0</div>
        <div class="result-label">unique papers found</div>
        <div class="result-breakdown" id="resultBreakdown"></div>
        <a class="dl-btn" id="downloadBtn" href="#">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
          Download CSV
        </a>
      </div>
    </div>

  </form>
</div>

<div class="footer">Paper Sieve — arXiv · OpenAlex · Scopus · Web of Science</div>

<script>
let pollInterval = null;

async function startSearch(e) {
  e.preventDefault();

  const topic = document.getElementById('topicInput').value.trim();
  const method = document.getElementById('methodInput').value.trim();

  if (!topic && !method) { alert('Enter at least one keyword'); return; }

  const keywords = [];
  if (topic) keywords.push(topic.split(',').map(k => k.trim()).filter(k => k));
  if (method) keywords.push(method.split(',').map(k => k.trim()).filter(k => k));

  const body = {
    keywords,
    date_from: document.getElementById('dateFrom').value,
    date_to: document.getElementById('dateTo').value,
  };

  const btn = document.getElementById('searchBtn');
  btn.disabled = true;
  btn.innerHTML = 'Searching... <span class="arrow">↗</span>';
  document.getElementById('progressArea').style.display = 'block';
  document.getElementById('resultArea').style.display = 'none';
  document.getElementById('progressFill').style.width = '0%';
  document.getElementById('progressFill').style.background = '#1C1917';
  document.getElementById('progressStatus').textContent = 'Starting search...';

  const res = await fetch('/api/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const { job_id } = await res.json();

  let step = 0;
  pollInterval = setInterval(async () => {
    const r = await fetch('/api/status/' + job_id);
    const data = await r.json();

    step++;
    const pct = Math.min(step * 8, 90);
    document.getElementById('progressFill').style.width = pct + '%';
    document.getElementById('progressStatus').textContent = data.progress;

    if (data.status === 'done') {
      clearInterval(pollInterval);
      document.getElementById('progressFill').style.width = '100%';
      document.getElementById('progressStatus').textContent = data.progress;

      btn.disabled = false;
      btn.innerHTML = 'Search papers <span class="arrow">↗</span>';

      document.getElementById('resultArea').style.display = 'block';
      document.getElementById('resultCount').textContent = data.count;

      let breakdown = '';
      for (const [src, cnt] of Object.entries(data.source_counts || {})) {
        if (cnt > 0) breakdown += src + ': ' + cnt + '   ';
      }
      if (data.raw_count > data.count) {
        breakdown += '(' + (data.raw_count - data.count) + ' duplicates removed)';
      }
      document.getElementById('resultBreakdown').textContent = breakdown;
      document.getElementById('downloadBtn').href = '/api/download/' + job_id;
    }

    if (data.status === 'error') {
      clearInterval(pollInterval);
      document.getElementById('progressFill').style.width = '100%';
      document.getElementById('progressFill').style.background = '#EF4444';
      document.getElementById('progressStatus').textContent = 'Error: ' + data.error;
      btn.disabled = false;
      btn.innerHTML = 'Search papers <span class="arrow">↗</span>';
    }
  }, 2000);
}
</script>
</body>
</html>
"""


# ── Routes ──

@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/api/search", methods=["POST"])
def api_search():
    data = request.json
    keywords = data.get("keywords", [])
    date_from = data.get("date_from", "2023-01-01")
    date_to = data.get("date_to", "2025-07-01")

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
        args=(job_id, keywords, date_from, date_to),
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
    print("\n  Paper Sieve — http://localhost:5000\n")
    app.run(debug=True, port=5000)