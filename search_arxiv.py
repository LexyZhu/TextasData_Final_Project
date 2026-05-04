import feedparser
from urllib.parse import quote
import time
import json
import csv


def build_query(keywords: list[list[str]]) -> str:
    """
    Build an arXiv API query string from keyword groups.

    Args:
        keywords: List of keyword groups. Each group is a list of terms
                  that are OR-joined. Groups are AND-joined together.
                  Example: [["agent", "chatbot"], ["ai", "llm"], ["mental health"]]
                  Result:  all:((agent OR chatbot) AND (ai OR llm) AND ("mental health"))

    Returns:
        Formatted arXiv query string.
    """
    parts = []
    for group in keywords:
        terms = []
        for term in group:
            term = term.strip()
            if " " in term:
                terms.append(f'"{term}"')
            else:
                terms.append(term)
        parts.append("(" + " OR ".join(terms) + ")")

    return "all:(" + " AND ".join(parts) + ")"


def search_arxiv(
    keywords: list[list[str]],
    time_lower_bound: str = "2025-07-01",
    time_upper_bound: str = "2025-12-18",
    max_total: int = 10000,
    max_per_request: int = 2000,
) -> list[dict]:
    """
    Search arXiv with user-defined keyword groups and time range.

    Args:
        keywords: List of keyword groups (list of lists).
                  Each inner list is OR-joined; groups are AND-joined.
        time_lower_bound: Start date inclusive (YYYY-MM-DD).
        time_upper_bound: End date inclusive (YYYY-MM-DD).
        max_total: Max total results to fetch.
        max_per_request: Results per API call (arXiv max is 2000).

    Returns:
        List of dicts with keys: title, authors, published, summary, link
    """
    base_url = "http://export.arxiv.org/api/query?"

    query = build_query(keywords)
    query_encoded = quote(query)

    print(f"Query: {query}")
    print(f"Time range: {time_lower_bound} to {time_upper_bound}\n")

    all_results = []
    start = 0

    while start < max_total:
        url = (
            f"{base_url}search_query={query_encoded}"
            f"&start={start}&max_results={max_per_request}"
            f"&sortBy=submittedDate&sortOrder=descending"
        )
        print(f"Fetching arXiv records {start} to {start + max_per_request} ...")

        feed = feedparser.parse(url)
        entries = feed.entries
        print(f"  Fetched {len(entries)} entries")

        if not entries:
            print("  No more results.")
            break

        for entry in entries:
            try:
                published_date = entry.published[:10]
                if time_lower_bound <= published_date <= time_upper_bound:
                    all_results.append({
                        "title": entry.title,
                        "authors": [author.name for author in entry.authors],
                        "published": entry.published,
                        "summary": entry.summary,
                        "link": entry.link,
                    })
            except Exception as e:
                print(f"  Error processing entry: {e}")
                continue

        start += max_per_request
        time.sleep(3)

    print(f"\nTotal results: {len(all_results)}")
    return all_results



# if __name__ == "__main__":

#     # --- Edit your keyword groups here ---
#     keywords = [
#         ["agent", "chatbot"],                           # Group 1 (OR-joined)
#         ["ai", "llm", "large language model"],          # Group 2 (OR-joined)
#         ["mental health", "psychiatry", "psychology"],   # Group 3 (OR-joined)
#     ]
#     # Groups are AND-joined:
#     # (agent OR chatbot) AND (ai OR llm OR "large language model") AND ("mental health" OR ...)

#     results = search_arxiv(
#         keywords=keywords,
#         time_lower_bound="2023-01-01",
#         time_upper_bound="2025-07-01",
#     )

#     # Save JSON
#     with open("result_arXiv.json", "w", encoding="utf-8") as f:
#         json.dump(results, f, ensure_ascii=False, indent=2)

#     # Save CSV
#     if results:
#         with open("result_arXiv.csv", "w", encoding="utf-8", newline="") as f:
#             writer = csv.DictWriter(f, fieldnames=results[0].keys())
#             writer.writeheader()
#             writer.writerows(results)

#     print(f"Saved {len(results)} papers to result_arXiv.json and result_arXiv.csv")