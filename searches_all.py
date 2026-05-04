
from search_arxiv import search_arxiv
from search_openalex import search_openalex
from search_scopus import search_scopus
from search_wos import search_wos

import json
import csv
import os
import re
import time
from datetime import datetime


# ──────────────────────────────────────────────────────────────
# CONFIGURATION
# ──────────────────────────────────────────────────────────────

KEYWORDS = [
    ["agent", "chatbot"],                           # Group 1 (OR-joined)
    ["ai", "llm", "large language model"],          # Group 2 (OR-joined)
]

TIME_LOWER_BOUND = "2026-01-01"
TIME_UPPER_BOUND = "2026-04-01"

# API keys — replace with your own
SCOPUS_API_KEY = "a6a4b4a8f0ff49676823b4b795cff8aa"
WOS_API_KEY = "296c7877068fd5bba5e70c4dd8540bfbbcf37346"
OPENALEX_EMAIL = "your@email.com"

# Toggle which sources to search
SOURCES_ENABLED = {
    "arxiv": True,
    "openalex": True,
    "scopus": True,
    "wos": True,
    "ssrn": True,  # via OpenAlex
}

OUTPUT_DIR = "./results/"


# ──────────────────────────────────────────────────────────────
# DEDUPLICATION
# ──────────────────────────────────────────────────────────────

def normalize_title(title: str) -> str:
    """Normalize a title for deduplication comparison."""
    if not title:
        return ""
    t = title.lower().strip()
    t = re.sub(r"[^a-z0-9\s]", "", t)   # remove punctuation
    t = re.sub(r"\s+", " ", t)           # collapse whitespace
    return t


def deduplicate(papers: list[dict]) -> list[dict]:
    """
    Remove duplicate papers based on normalized title.
    Keeps the first occurrence (which preserves source priority order).
    """
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
# SAVE HELPERS
# ──────────────────────────────────────────────────────────────

def save_json(filename: str, data):
    """Save results as JSON."""
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_csv(filename: str, data: list[dict]):
    """Save results as CSV."""
    if not data:
        return
    keys = data[0].keys()
    with open(filename, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(data)


# ──────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────

def run_all():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    all_results = []
    source_counts = {}

    print("=" * 60)
    print("PAPER SIEVE — UNIFIED SEARCH")
    print("=" * 60)
    print(f"Keywords: {KEYWORDS}")
    print(f"Time range: {TIME_LOWER_BOUND} to {TIME_UPPER_BOUND}")
    print(f"Sources: {[k for k, v in SOURCES_ENABLED.items() if v]}")
    print("=" * 60 + "\n")

    # ── arXiv ──
    if SOURCES_ENABLED.get("arxiv"):
        print("\n" + "─" * 40)
        print("SOURCE: arXiv")
        print("─" * 40)
        try:
            results = search_arxiv(
                keywords=KEYWORDS,
                time_lower_bound=TIME_LOWER_BOUND,
                time_upper_bound=TIME_UPPER_BOUND,
            )
            for r in results:
                r["source"] = "arXiv"
            all_results.extend(results)
            source_counts["arXiv"] = len(results)
            save_json(os.path.join(OUTPUT_DIR, "result_arXiv.json"), results)
            save_csv(os.path.join(OUTPUT_DIR, "result_arXiv.csv"), results)
        except Exception as e:
            print(f"arXiv search failed: {e}")
            source_counts["arXiv"] = 0

    # ── OpenAlex ──
    if SOURCES_ENABLED.get("openalex"):
        print("\n" + "─" * 40)
        print("SOURCE: OpenAlex")
        print("─" * 40)
        try:
            results = search_openalex(
                keywords=KEYWORDS,
                time_lower_bound=TIME_LOWER_BOUND,
                time_upper_bound=TIME_UPPER_BOUND,
                email=OPENALEX_EMAIL,
            )
            for r in results:
                r["source"] = "OpenAlex"
            all_results.extend(results)
            source_counts["OpenAlex"] = len(results)
            save_json(os.path.join(OUTPUT_DIR, "result_OpenAlex.json"), results)
            save_csv(os.path.join(OUTPUT_DIR, "result_OpenAlex.csv"), results)
        except Exception as e:
            print(f"OpenAlex search failed: {e}")
            source_counts["OpenAlex"] = 0

    # ── Scopus ──
    if SOURCES_ENABLED.get("scopus"):
        print("\n" + "─" * 40)
        print("SOURCE: Scopus")
        print("─" * 40)
        if SCOPUS_API_KEY == "YOUR_SCOPUS_API_KEY":
            print("  Skipped — no API key provided")
            source_counts["Scopus"] = 0
        else:
            try:
                results = search_scopus(
                    keywords=KEYWORDS,
                    api_key=SCOPUS_API_KEY,
                    time_lower_bound=TIME_LOWER_BOUND,
                    time_upper_bound=TIME_UPPER_BOUND,
                )
                for r in results:
                    r["source"] = "Scopus"
                all_results.extend(results)
                source_counts["Scopus"] = len(results)
                save_json(os.path.join(OUTPUT_DIR, "result_Scopus.json"), results)
                save_csv(os.path.join(OUTPUT_DIR, "result_Scopus.csv"), results)
            except Exception as e:
                print(f"Scopus search failed: {e}")
                source_counts["Scopus"] = 0

    # ── Web of Science ──
    if SOURCES_ENABLED.get("wos"):
        print("\n" + "─" * 40)
        print("SOURCE: Web of Science")
        print("─" * 40)
        if WOS_API_KEY == "YOUR_WOS_API_KEY":
            print("  Skipped — no API key provided")
            source_counts["WoS"] = 0
        else:
            try:
                results = search_wos(
                    keywords=KEYWORDS,
                    api_key=WOS_API_KEY,
                    time_lower_bound=TIME_LOWER_BOUND,
                    time_upper_bound=TIME_UPPER_BOUND,
                )
                for r in results:
                    r["source"] = "WoS"
                all_results.extend(results)
                source_counts["WoS"] = len(results)
                save_json(os.path.join(OUTPUT_DIR, "result_WoS.json"), results)
                save_csv(os.path.join(OUTPUT_DIR, "result_WoS.csv"), results)
            except Exception as e:
                print(f"WoS search failed: {e}")
                source_counts["WoS"] = 0

    # ── Deduplicate & save combined results ──
    print("\n" + "=" * 60)
    print("DEDUPLICATION")
    print("=" * 60)

    total_raw = len(all_results)
    unique_results = deduplicate(all_results)
    duplicates_removed = total_raw - len(unique_results)

    print(f"Total raw results: {total_raw}")
    print(f"Duplicates removed: {duplicates_removed}")
    print(f"Unique papers: {len(unique_results)}")

    save_json(os.path.join(OUTPUT_DIR, "combined_all.json"), unique_results)
    save_csv(os.path.join(OUTPUT_DIR, "combined_all.csv"), unique_results)

    # ── Summary ──
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for source, count in source_counts.items():
        print(f"  {source:>12}: {count:>5} papers")
    print(f"  {'─' * 20}")
    print(f"  {'Total raw':>12}: {total_raw:>5}")
    print(f"  {'Deduplicated':>12}: {len(unique_results):>5}")
    print(f"\nAll files saved to {OUTPUT_DIR}")
    print(f"  - Per-source: result_<source>.json / .csv")
    print(f"  - Combined:   combined_all.json / .csv")
    print("=" * 60)

    return unique_results


if __name__ == "__main__":
    results = run_all()