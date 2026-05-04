import requests
from urllib.parse import quote
import time
import json
import csv


def build_query(
    keywords: list[list[str]],
    time_lower_bound: str = "2023-01-01",
    time_upper_bound: str = "2025-12-31",
) -> str:
    """
    Build a Scopus query string from keyword groups.

    Args:
        keywords: List of keyword groups. Each group is a list of terms
                  that are OR-joined. Groups are AND-joined together.
                  Example: [["agent", "chatbot"], ["ai", "llm"], ["mental health"]]
                  Result:  TITLE-ABS-KEY((agent OR chatbot) AND ...) AND PUBYEAR > 2022 AND PUBYEAR < 2026
        time_lower_bound: Start date (YYYY-MM-DD), year part is used.
        time_upper_bound: End date (YYYY-MM-DD), year part is used.

    Returns:
        Formatted Scopus query string.
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

    topic_query = "TITLE-ABS-KEY(" + " AND ".join(parts) + ")"

    # PUBYEAR uses > and <, so offset by 1 to make bounds inclusive
    year_start = int(time_lower_bound[:4]) - 1
    year_end = int(time_upper_bound[:4]) + 1
    year_filter = f"PUBYEAR > {year_start} AND PUBYEAR < {year_end}"

    return f"{topic_query} AND {year_filter}"


def get_abstract_by_eid(eid: str, api_key: str) -> str:
    """Fetch abstract text for a single paper using its Scopus EID."""
    url = f"https://api.elsevier.com/content/abstract/eid/{eid}"
    headers = {
        "X-ELS-APIKey": api_key,
        "Accept": "application/json",
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            data = response.json()
            coredata = (
                data.get("abstracts-retrieval-response", {}).get("coredata", {})
            )
            return coredata.get("dc:description", "") or ""
        else:
            print(f"  Abstract fetch failed for {eid}: {response.status_code}")
            return ""
    except Exception as e:
        print(f"  Abstract fetch error for {eid}: {e}")
        return ""


def search_scopus(
    keywords: list[list[str]],
    api_key: str,
    time_lower_bound: str = "2023-01-01",
    time_upper_bound: str = "2025-07-01",
    fetch_abstracts: bool = True,
    count: int = 25,
    max_results: int = 5000,
) -> list[dict]:
    """
    Search Scopus with user-defined keyword groups and time range.

    Args:
        keywords: List of keyword groups (list of lists).
                  Each inner list is OR-joined; groups are AND-joined.
        api_key: Elsevier Scopus API key.
        time_lower_bound: Start date inclusive (YYYY-MM-DD).
        time_upper_bound: End date inclusive (YYYY-MM-DD).
        fetch_abstracts: If True, make a second API call per paper to get
                         the full abstract. Slower but more complete.
        count: Results per API page (Scopus max is 25).
        max_results: Safety cap on total results to fetch.

    Returns:
        List of dicts with keys: title, authors, summary, published, link
    """
    headers = {
        "X-ELS-APIKey": api_key,
        "Accept": "application/json",
    }

    query = build_query(keywords, time_lower_bound, time_upper_bound)

    print(f"Query: {query}")
    print(f"Time range: {time_lower_bound} to {time_upper_bound}")
    print(f"Fetch abstracts: {fetch_abstracts}\n")

    results = []
    start = 0

    while start < max_results:
        url = (
            f"https://api.elsevier.com/content/search/scopus"
            f"?query={quote(query)}&count={count}&start={start}"
        )

        print(f"Fetching Scopus records {start} to {start + count} ...")

        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            print(f"  API error: {e}")
            break

        entries = data.get("search-results", {}).get("entry", [])

        if not entries:
            print("  No more entries.")
            break

        # Check for error entries (Scopus returns error as an entry)
        if len(entries) == 1 and entries[0].get("error"):
            print(f"  Scopus error: {entries[0].get('error')}")
            break

        print(f"  Fetched {len(entries)} entries")

        for entry in entries:
            title = entry.get("dc:title", "")
            published = entry.get("prism:coverDate", "")
            doi = entry.get("prism:doi", "")
            link = f"https://doi.org/{doi}" if doi else entry.get("prism:url", "")

            # Authors
            authors = entry.get("dc:creator", "")

            # Abstract: fetch individually if requested
            summary = ""
            if fetch_abstracts:
                eid = entry.get("eid")
                if eid:
                    summary = get_abstract_by_eid(eid, api_key)
                    time.sleep(0.2)  # Rate limit for abstract endpoint

            results.append({
                "title": title,
                "authors": authors,
                "summary": summary,
                "published": published,
                "link": link,
            })

        if len(entries) < count:
            print("  Last page reached.")
            break

        start += count
        time.sleep(1)

    print(f"\nTotal Scopus results: {len(results)}")
    return results


# if __name__ == "__main__":

#     # --- Edit your keyword groups here ---
#     keywords = [
#         ["agent", "chatbot"],                           # Group 1 (OR-joined)
#         ["ai", "llm", "large language model"],          # Group 2 (OR-joined)
#         ["mental health", "psychiatry", "psychology"],   # Group 3 (OR-joined)
#     ]
#     # Groups are AND-joined:
#     # TITLE-ABS-KEY((agent OR chatbot) AND (...) AND (...)) AND PUBYEAR > 2022 AND PUBYEAR < 2026

#     SCOPUS_API_KEY = "a6a4b4a8f0ff49676823b4b795cff8aa"

#     results = search_scopus(
#         keywords=keywords,
#         api_key=SCOPUS_API_KEY,
#         time_lower_bound="2023-01-01",
#         time_upper_bound="2025-07-01",
#         fetch_abstracts=True,  # Set False for faster results without abstracts
#     )

#     # Save JSON
#     with open("result_Scopus.json", "w", encoding="utf-8") as f:
#         json.dump(results, f, ensure_ascii=False, indent=2)

#     # Save CSV
#     if results:
#         with open("result_Scopus.csv", "w", encoding="utf-8", newline="") as f:
#             writer = csv.DictWriter(f, fieldnames=results[0].keys())
#             writer.writeheader()
#             writer.writerows(results)

#     print(f"Saved {len(results)} papers to result_Scopus.json and result_Scopus.csv")