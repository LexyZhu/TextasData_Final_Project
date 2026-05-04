import requests
import time
import json
import csv


def build_query_openalex(keywords: list[list[str]]) -> list[str]:
    """
    Build OpenAlex filter groups from keyword groups.

    Args:
        keywords: List of keyword groups. Each group is a list of terms
                  that are OR-joined. Groups become separate
                  title_and_abstract.search filters (AND-joined by OpenAlex).
                  Example: [["agent", "chatbot"], ["ai", "llm"]]
                  Result:  ["(agent OR chatbot)", "(ai OR llm)"]

    Returns:
        List of query strings, one per group.
    """
    groups = []
    for group in keywords:
        terms = []
        for term in group:
            term = term.strip()
            if " " in term:
                terms.append(f'"{term}"')
            else:
                terms.append(term)
        groups.append("(" + " OR ".join(terms) + ")")
    return groups


def decode_abstract(inverted_index: dict) -> str:
    """Reconstruct abstract text from OpenAlex inverted index format."""
    if not inverted_index:
        return ""
    buf = {}
    for word, positions in inverted_index.items():
        for pos in positions:
            buf[pos] = word
    return " ".join(buf[i] for i in sorted(buf))


def search_openalex(
    keywords: list[list[str]],
    time_lower_bound: str = "2023-01-01",
    time_upper_bound: str = "2025-07-01",
    email: str = "your@email.com",
    per_page: int = 200,
    max_pages: int = 100,
) -> list[dict]:
    """
    Search OpenAlex with user-defined keyword groups and time range.

    Args:
        keywords: List of keyword groups (list of lists).
                  Each inner list is OR-joined; groups are AND-joined.
        time_lower_bound: Start date inclusive (YYYY-MM-DD).
        time_upper_bound: End date inclusive (YYYY-MM-DD).
        email: Contact email for polite API usage (higher rate limits).
        per_page: Results per page (OpenAlex max is 200).
        max_pages: Safety limit on number of pages to fetch.

    Returns:
        List of dicts with keys: title, summary, published, link
    """
    base_url = "https://api.openalex.org/works"
    headers = {
        "User-Agent": f"PaperSieve/1.0 (mailto:{email})"
    }

    query_groups = build_query_openalex(keywords)

    # Build the filter string:
    # Each keyword group becomes a title_and_abstract.search filter,
    # combined with date range filters. OpenAlex AND-joins comma-separated filters.
    filter_parts = [f"title_and_abstract.search:{g}" for g in query_groups]
    filter_parts.append(f"from_publication_date:{time_lower_bound}")
    filter_parts.append(f"to_publication_date:{time_upper_bound}")
    filter_string = ",".join(filter_parts)

    print(f"Query groups: {query_groups}")
    print(f"Time range: {time_lower_bound} to {time_upper_bound}")
    print(f"Filter: {filter_string}\n")

    results = []
    page = 1

    while page <= max_pages:
        params = {
            "filter": filter_string,
            "per_page": per_page,
            "page": page,
            "select": "id,display_name,abstract_inverted_index,publication_date,authorships",
            "sort": "relevance_score:desc",
        }

        print(f"Fetching OpenAlex page {page} ...")
        response = requests.get(base_url, params=params, headers=headers)

        if response.status_code != 200:
            print(f"  Request failed: {response.status_code}")
            break

        try:
            data = response.json()
        except Exception as e:
            print(f"  Failed to parse JSON: {e}")
            break

        works = data.get("results", [])
        print(f"  Fetched {len(works)} items")

        for item in works:
            title = item.get("display_name", "")
            abstract = decode_abstract(item.get("abstract_inverted_index"))
            published = item.get("publication_date", "")

            # Extract author names
            authorships = item.get("authorships", [])
            authors = [
                a.get("author", {}).get("display_name", "")
                for a in authorships
                if a.get("author", {}).get("display_name")
            ]

            results.append({
                "title": title,
                "authors": ", ".join(authors),
                "summary": abstract,
                "published": published,
                "link": item.get("id", ""),
            })

        if len(works) < per_page:
            print("  Last page reached.")
            break

        page += 1
        time.sleep(1)

    print(f"\nTotal OpenAlex results: {len(results)}")
    return results


# if __name__ == "__main__":

#     # --- Edit your keyword groups here ---
#     keywords = [
#         ["agent", "chatbot"],                           # Group 1 (OR-joined)
#         ["ai", "llm", "large language model"],          # Group 2 (OR-joined)
#         ["mental health", "psychiatry", "psychology"],   # Group 3 (OR-joined)
#     ]
#     # Groups are AND-joined via OpenAlex's comma-separated filter syntax

#     results = search_openalex(
#         keywords=keywords,
#         time_lower_bound="2023-01-01",
#         time_upper_bound="2025-07-01",
#         email="your@email.com",
#     )

#     # Save JSON
#     with open("result_OpenAlex.json", "w", encoding="utf-8") as f:
#         json.dump(results, f, ensure_ascii=False, indent=2)

#     # Save CSV
#     if results:
#         with open("result_OpenAlex.csv", "w", encoding="utf-8", newline="") as f:
#             writer = csv.DictWriter(f, fieldnames=results[0].keys())
#             writer.writeheader()
#             writer.writerows(results)

#     print(f"Saved {len(results)} papers to result_OpenAlex.json and result_OpenAlex.csv")