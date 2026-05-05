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

SOURCES = ["arXiv", "OpenAlex", "Scopus", "Web of Science"]


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

    def cancelled():
        return job.get("status") == "cancelled"

    try:
        # 1. arXiv
        if cancelled():
            save_partial(job_id, all_results)
            return
        job["sources"]["arXiv"]["status"] = "running"
        try:
            results = search_arxiv(keywords=keywords, 
                                   time_lower_bound=date_from, 
                                   time_upper_bound=date_to)
            for r in results:
                r["source"] = "arXiv"
            all_results.extend(results)
            job["sources"]["arXiv"] = {"status": "done", "count": len(results)}
        except Exception as e:
            job["sources"]["arXiv"] = {"status": "error", "count": 0, "error": str(e)}
            print(f"arXiv error: {e}")

        # 2. OpenAlex
        if cancelled():
            save_partial(job_id, all_results)
            return
        job["sources"]["OpenAlex"]["status"] = "running"
        try:
            results = search_openalex(keywords=keywords, time_lower_bound=date_from, time_upper_bound=date_to)
            for r in results:
                r["source"] = "OpenAlex"
            all_results.extend(results)
            job["sources"]["OpenAlex"] = {"status": "done", "count": len(results)}
        except Exception as e:
            job["sources"]["OpenAlex"] = {"status": "error", "count": 0, "error": str(e)}
            print(f"OpenAlex error: {e}")

        # 3. Scopus
        if cancelled():
            save_partial(job_id, all_results)
            return
        job["sources"]["Scopus"]["status"] = "running"
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
            job["sources"]["Scopus"] = {"status": "done", "count": len(results)}
        except Exception as e:
            job["sources"]["Scopus"] = {"status": "error", "count": 0, "error": str(e)}
            print(f"Scopus error: {e}")

        # 4. Web of Science
        if cancelled():
            save_partial(job_id, all_results)
            return
        job["sources"]["Web of Science"]["status"] = "running"
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
            job["sources"]["Web of Science"] = {"status": "done", "count": len(results)}
        except Exception as e:
            job["sources"]["Web of Science"] = {"status": "error", "count": 0, "error": str(e)}
            print(f"WoS error: {e}")

        if cancelled():
            # Save partial results before returning
            save_partial(job_id, all_results)
            return

        # Deduplicate & save
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

        job["status"] = "done"
        job["csv_path"] = csv_path
        job["count"] = len(unique)
        job["raw_count"] = len(all_results)

    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)


def save_partial(job_id, all_results):
    """Save whatever results we have so far when cancelled."""
    job = jobs[job_id]
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

    job["csv_path"] = csv_path
    job["count"] = len(unique)
    job["raw_count"] = len(all_results)


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
  margin: 0;
  font-family: Inter, Arial, sans-serif;
  color: #1f1f1f;
  min-height: 100vh;
  background:
    radial-gradient(circle at 12% 18%, rgba(120, 119, 198, 0.22), transparent 30%),
    radial-gradient(circle at 88% 12%, rgba(255, 178, 107, 0.28), transparent 28%),
    radial-gradient(circle at 50% 95%, rgba(112, 201, 186, 0.18), transparent 36%),
    linear-gradient(135deg, #faf7f2 0%, #f6f1ea 45%, #eef3f6 100%);
}

.hero {
  text-align: center;
  padding: 86px 20px 46px;
}

.hero h1 {
  font-size: 56px;
  margin: 0;
  font-weight: 800;
  letter-spacing: -2px;
  color: #1c1917;
}
.hero p {
  margin-top: 14px;
  font-size: 21px;
  color: #756d66;
}
.description {
  max-width: 760px;
  margin: 0 auto 36px;
  padding: 24px 32px;
  text-align: left;
  background: rgba(255, 255, 255, 0.52);
  border: 1px solid rgba(255, 255, 255, 0.7);
  border-radius: 22px;
  backdrop-filter: blur(14px);
}

.description h2 {
  font-size: 18px;
  font-weight: 800;
  color: #1c1917;
  margin-bottom: 10px;
}

.description p {
  font-size: 16px;
  line-height: 1.7;
  color: #5f574f;
  margin: 0;
}

.process {
  max-width: 760px;
  margin: 8px auto 46px;
  padding: 0 24px;
  text-align: center;
}

.process-kicker {
  font-size: 13px;
  font-weight: 800;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: #7c6f64;
  margin-bottom: 14px;
}

.process h2 {
  font-size: 42px;
  line-height: 1.1;
  font-weight: 850;
  letter-spacing: -1.4px;
  color: #1c2541;
  margin-bottom: 46px;
}

.process-steps {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 26px;
  position: relative;
}

.process-step {
  position: relative;
  padding: 0 16px;
}

.process-icon {
  font-size: 30px;
  color: #756d66;
  height: 42px;
  margin-bottom: 18px;
}

.process-number {
  width: 72px;
  height: 72px;
  margin: 0 auto 24px;
  border-radius: 50%;
  background: #17213d;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 26px;
  font-weight: 800;
  position: relative;
  z-index: 2;
}

.process-step:not(:last-child)::after {
  content: "";
  position: absolute;
  top: 96px;
  left: calc(50% + 54px);
  width: calc(100% - 56px);
  border-top: 3px dashed rgba(124, 111, 100, 0.32);
}

.process-step h3 {
  font-size: 22px;
  color: #1c1917;
  margin-bottom: 14px;
}

.process-step p {
  max-width: 240px;
  margin: 0 auto;
  font-size: 16px;
  line-height: 1.55;
  color: #6f6862;
}

@media (max-width: 900px) {
  .process-steps {
    grid-template-columns: 1fr 1fr;
    row-gap: 36px;
  }

  .process-step::after {
    display: none;
  }
}

@media (max-width: 560px) {
  .process h2 {
    font-size: 32px;
  }

  .process-steps {
    grid-template-columns: 1fr;
  }
}

.search-wrap {
  max-width: 680px;
  margin: 0 auto;
  padding: 0 24px 90px;
}

.search-box {
  background: rgba(255, 255, 255, 0.78);
  backdrop-filter: blur(18px);
  border: 1px solid rgba(255, 255, 255, 0.75);
  border-radius: 28px;
  padding: 42px 46px 36px;
  box-shadow:
    0 24px 70px rgba(28, 25, 23, 0.10),
    inset 0 1px 0 rgba(255, 255, 255, 0.9);
}

.field-group {
  margin-bottom: 28px;
}

.field-label {
  font-size: 16px;
  font-weight: 700;
  color: #3d3833;
  margin-bottom: 7px;
  display: block;
}

.field-hint {
  font-size: 13px;
  color: #9c948d;
  margin-bottom: 10px;
  display: block;
}

.field-input {
  width: 100%;
  height: 58px;
  padding: 0 20px;
  border-radius: 14px;
  font-size: 18px;
  border: 1px solid #e1ddd7;
  background: rgba(255, 255, 255, 0.82);
  color: #1c1917;
  font-family: Inter, sans-serif;
  outline: none;
  transition: all 0.18s ease;
}

.field-input:focus {
  border-color: #8b7cf6;
  box-shadow: 0 0 0 4px rgba(139, 124, 246, 0.15);
  background: #fff;
}

.divider {
  border: none;
  height: 1px;
  background: linear-gradient(to right, transparent, #ddd7cf, transparent);
  margin: 30px 0;
}

.date-row {
  display: flex;
  gap: 18px;
}

.date-row .date-field {
  flex: 1;
}

.date-row .date-field label {
  font-size: 13px;
  font-weight: 600;
  color: #756d66;
  margin-bottom: 7px;
  display: block;
}

.date-input {
  width: 100%;
  height: 54px;
  padding: 0 16px;
  border-radius: 14px;
  font-size: 16px;
  border: 1px solid #e1ddd7;
  background: rgba(255, 255, 255, 0.82);
  color: #1c1917;
  font-family: Inter, sans-serif;
  outline: none;
}

.btn-row {
  display: flex;
  gap: 12px;
  margin-top: 28px;
}

.submit-btn {
  flex: 1;
  height: 64px;
  border-radius: 16px;
  font-size: 20px;
  font-weight: 800;
  border: none;
  background: linear-gradient(135deg, #1f1c1a, #3b332d);
  color: #fff;
  cursor: pointer;
  font-family: Inter, sans-serif;
  transition: transform 0.18s ease, box-shadow 0.18s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
}

.submit-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 14px 28px rgba(28, 25, 23, 0.18);
}

.submit-btn:disabled { background: #A8A29E; cursor: not-allowed; }
.cancel-btn {
  width: 120px; height: 48px; border-radius: 8px; font-size: 14px; font-weight: 600;
  border: 1px solid #FCA5A5; background: #FEF2F2; color: #991B1B; cursor: pointer;
  font-family: 'Inter', sans-serif; transition: background 0.15s; display: none;
}
.cancel-btn:hover { background: #FEE2E2; }

/* ── Per-source progress ── */
.progress-area { margin-top: 20px; display: none; }

.source-row {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 0;
  border-bottom: 1px solid #F5F5F4;
}
.source-row:last-child { border-bottom: none; }

.source-icon {
  width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0;
  background: #E7E5E4;
  transition: background 0.3s;
}
.source-icon.waiting { background: #E7E5E4; }
.source-icon.running { background: #FBBF24; animation: pulse 1s ease-in-out infinite; }
.source-icon.done { background: #22C55E; }
.source-icon.error { background: #EF4444; }
.source-icon.cancelled { background: #A8A29E; }

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.source-name {
  font-size: 13px; font-weight: 500; color: #1C1917; width: 120px; flex-shrink: 0;
}
.source-bar-track {
  flex: 1; height: 4px; background: #F5F5F4; border-radius: 2px; overflow: hidden;
}
.source-bar-fill {
  height: 100%; border-radius: 2px; width: 0%;
  transition: width 0.5s, background 0.3s;
  background: #E7E5E4;
}
.source-bar-fill.running { background: #FBBF24; width: 60%; }
.source-bar-fill.done { background: #22C55E; width: 100%; }
.source-bar-fill.error { background: #EF4444; width: 100%; }
.source-bar-fill.cancelled { background: #A8A29E; width: 30%; }

.source-count {
  font-size: 12px; font-weight: 600; color: #A8A29E; width: 60px; text-align: right;
  font-variant-numeric: tabular-nums;
}
.source-count.done { color: #22C55E; }
.source-count.error { color: #EF4444; }

/* ── Result ── */
.result-area { margin-top: 20px; display: none; }
.result-card {
  background: #fff; border: 1px solid #E7E5E4; border-radius: 12px;
  padding: 24px 28px; text-align: center;
}
.result-count { font-size: 48px; font-weight: 700; color: #1C1917; letter-spacing: -0.03em; }
.result-label { font-size: 14px; color: #78716C; margin-top: 2px; margin-bottom: 4px; }
.result-breakdown { font-size: 12px; color: #A8A29E; margin-bottom: 20px; }
.dl-btn {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 12px 32px; border-radius: 8px; font-size: 15px; font-weight: 600;
  border: none; background: #1C1917; color: #fff; cursor: pointer;
  font-family: 'Inter', sans-serif; text-decoration: none; transition: background 0.15s;
}
.dl-btn:hover { background: #292524; }
.dl-btn svg { width: 18px; height: 18px; }

.footer { text-align: center; padding: 40px 24px; font-size: 11px; color: #D6D3D1; }
</style>
</head>
<body>

<div class="hero">
  <h1>Paper Sieve</h1>
  <p><strong>Author:</strong> Lexy Zhu</p>
</div>

<section class="description">
  <h2>Description</h2>
  <p>
     Paper Sieve is a literature search tool designed to help users efficiently collect and deduplicate papers from arXiv, OpenAlex, Scopus, and Web of Science based on two sets of user-defined keywords and a specified publication time range.

  </p>
</section>

<section class="process">
  <div class="process-kicker">The Process</div>
  <h2>Search papers in minutes, not hours</h2>

  <div class="process-steps">
    <div class="process-step">
      <div class="process-icon">⌕</div>
      <div class="process-number">1</div>
      <h3>Enter Keywords</h3>
      <p>Provide two keyword groups. Terms within each group are OR-joined to broaden the search.</p>
    </div>

    <div class="process-step">
      <div class="process-icon">↻</div>
      <div class="process-number">2</div>
      <h3>Search Databases</h3>
      <p>Paper Sieve searches arXiv, OpenAlex, Scopus, and Web of Science within your selected time range.</p>
    </div>

    <div class="process-step">
      <div class="process-icon">◇</div>
      <div class="process-number">3</div>
      <h3>Deduplicate</h3>
      <p>Collected records are merged and duplicate papers are removed for a cleaner literature list.</p>
    </div>

    <div class="process-step">
      <div class="process-icon">⇩</div>
      <div class="process-number">4</div>
      <h3>Export CSV</h3>
      <p>Download the final results as a CSV file for screening, review, or further analysis.</p>
    </div>
  </div>
</section>

<div class="search-wrap">
  <div class="search-box">

    <div class="field-group">
      <label class="field-label">Keywords Group 1</label>
      <span class="field-hint">Separate keywords with commas (these are OR-joined)</span>
      <input class="field-input" id="topicInput" placeholder="e.g. wage inequality, economics" value="wage inequality, economics">
    </div>

    <div class="field-group">
      <label class="field-label">Keywords Group 2</label>
      <span class="field-hint">Separate keywords with commas (these are OR-joined)</span>
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

    <div class="btn-row">
      <button type="button" class="submit-btn" id="searchBtn" onclick="startSearch()">
        Search papers <span class="arrow" style="font-size:18px;opacity:.7">↗</span>
      </button>
      <button type="button" class="cancel-btn" id="cancelBtn" onclick="cancelSearch()">
        Cancel
      </button>
    </div>

    <!-- Per-source progress -->
    <div class="progress-area" id="progressArea">
      <div class="source-row" id="row-arXiv">
        <div class="source-icon waiting" id="icon-arXiv"></div>
        <div class="source-name">arXiv</div>
        <div class="source-bar-track"><div class="source-bar-fill" id="bar-arXiv"></div></div>
        <div class="source-count" id="count-arXiv">—</div>
      </div>
      <div class="source-row" id="row-OpenAlex">
        <div class="source-icon waiting" id="icon-OpenAlex"></div>
        <div class="source-name">OpenAlex</div>
        <div class="source-bar-track"><div class="source-bar-fill" id="bar-OpenAlex"></div></div>
        <div class="source-count" id="count-OpenAlex">—</div>
      </div>
      <div class="source-row" id="row-Scopus">
        <div class="source-icon waiting" id="icon-Scopus"></div>
        <div class="source-name">Scopus</div>
        <div class="source-bar-track"><div class="source-bar-fill" id="bar-Scopus"></div></div>
        <div class="source-count" id="count-Scopus">—</div>
      </div>
      <div class="source-row" id="row-WoS">
        <div class="source-icon waiting" id="icon-WoS"></div>
        <div class="source-name">Web of Science</div>
        <div class="source-bar-track"><div class="source-bar-fill" id="bar-WoS"></div></div>
        <div class="source-count" id="count-WoS">—</div>
      </div>
    </div>

    <!-- Results -->
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

  </div>
</div>

<div class="footer">Paper Sieve — arXiv · OpenAlex · Scopus · Web of Science</div>

<script>
let pollInterval = null;
let currentJobId = null;

const SOURCE_MAP = {
  'arXiv': 'arXiv',
  'OpenAlex': 'OpenAlex',
  'Scopus': 'Scopus',
  'Web of Science': 'WoS'
};

function resetSourceRows() {
  for (const [src, id] of Object.entries(SOURCE_MAP)) {
    document.getElementById('icon-' + id).className = 'source-icon waiting';
    document.getElementById('bar-' + id).className = 'source-bar-fill';
    document.getElementById('bar-' + id).style.width = '0%';
    document.getElementById('count-' + id).textContent = '—';
    document.getElementById('count-' + id).className = 'source-count';
  }
}

function updateSourceRow(src, status, count) {
  const id = SOURCE_MAP[src];
  if (!id) return;

  const icon = document.getElementById('icon-' + id);
  const bar = document.getElementById('bar-' + id);
  const cnt = document.getElementById('count-' + id);

  icon.className = 'source-icon ' + status;
  bar.className = 'source-bar-fill ' + status;

  if (status === 'done') {
    cnt.textContent = count + ' papers';
    cnt.className = 'source-count done';
  } else if (status === 'error') {
    cnt.textContent = 'error';
    cnt.className = 'source-count error';
  } else if (status === 'running') {
    cnt.textContent = 'searching...';
    cnt.className = 'source-count';
  } else if (status === 'cancelled') {
    cnt.textContent = 'cancelled';
    cnt.className = 'source-count';
  }
}

async function startSearch() {
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

  // UI setup
  const btn = document.getElementById('searchBtn');
  const cancelBtn = document.getElementById('cancelBtn');
  btn.disabled = true;
  btn.innerHTML = 'Searching...';
  cancelBtn.style.display = 'block';
  document.getElementById('progressArea').style.display = 'block';
  document.getElementById('resultArea').style.display = 'none';
  resetSourceRows();

  const res = await fetch('/api/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const { job_id } = await res.json();
  currentJobId = job_id;

  pollInterval = setInterval(async () => {
    const r = await fetch('/api/status/' + job_id);
    const data = await r.json();

    // Update each source row
    if (data.sources) {
      for (const [src, info] of Object.entries(data.sources)) {
        updateSourceRow(src, info.status, info.count || 0);
      }
    }

    if (data.status === 'done') {
      clearInterval(pollInterval);
      btn.disabled = false;
      btn.innerHTML = 'Search papers <span style="font-size:18px;opacity:.7">↗</span>';
      cancelBtn.style.display = 'none';

      document.getElementById('resultArea').style.display = 'block';
      document.getElementById('resultCount').textContent = data.count;

      let breakdown = '';
      if (data.sources) {
        for (const [src, info] of Object.entries(data.sources)) {
          if (info.count > 0) breakdown += src + ': ' + info.count + '   ';
        }
      }
      if (data.raw_count > data.count) {
        breakdown += '(' + (data.raw_count - data.count) + ' duplicates removed)';
      }
      document.getElementById('resultBreakdown').textContent = breakdown;
      document.getElementById('downloadBtn').href = '/api/download/' + job_id;
    }

    if (data.status === 'cancelled') {
      clearInterval(pollInterval);
      btn.disabled = false;
      btn.innerHTML = 'Search papers <span style="font-size:18px;opacity:.7">↗</span>';
      cancelBtn.style.display = 'none';

      // Mark remaining sources as cancelled
      if (data.sources) {
        for (const [src, info] of Object.entries(data.sources)) {
          if (info.status === 'waiting' || info.status === 'running') {
            updateSourceRow(src, 'cancelled', 0);
          }
        }
      }

      // Still show results if any were collected
      if (data.count > 0) {
        document.getElementById('resultArea').style.display = 'block';
        document.getElementById('resultCount').textContent = data.count;
        document.getElementById('resultBreakdown').textContent = 'Search was cancelled — partial results';
        document.getElementById('downloadBtn').href = '/api/download/' + job_id;
      }
    }

    if (data.status === 'error') {
      clearInterval(pollInterval);
      btn.disabled = false;
      btn.innerHTML = 'Search papers <span style="font-size:18px;opacity:.7">↗</span>';
      cancelBtn.style.display = 'none';
    }
  }, 1500);
}

async function cancelSearch() {
  if (!currentJobId) return;
  await fetch('/api/cancel/' + currentJobId, { method: 'POST' });
  document.getElementById('cancelBtn').disabled = true;
  document.getElementById('cancelBtn').textContent = 'Cancelling...';
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
        "csv_path": None,
        "count": 0,
        "raw_count": 0,
        "error": None,
        "sources": {
            "arXiv": {"status": "waiting", "count": 0},
            "OpenAlex": {"status": "waiting", "count": 0},
            "Scopus": {"status": "waiting", "count": 0},
            "Web of Science": {"status": "waiting", "count": 0},
        },
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


@app.route("/api/cancel/<job_id>", methods=["POST"])
def api_cancel(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"status": "not_found"}), 404

    # Mark as cancelled — the worker thread checks this between sources
    job["status"] = "cancelled"
    return jsonify({"status": "cancelled"})


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