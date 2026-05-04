import clarivate.wos_starter.client
from clarivate.wos_starter.client.rest import ApiException
import json
import csv


def build_query(
    keywords: list[list[str]],
    time_lower_bound: str = "2023-01-01",
    time_upper_bound: str = "2025-12-31",
) -> str:
    """
    Build a Web of Science query string from keyword groups.

    Args:
        keywords: List of keyword groups. Each group is a list of terms
                  that are OR-joined. Groups are AND-joined together.
                  Example: [["agent", "chatbot"], ["ai", "llm"], ["mental health"]]
                  Result:  TS=((agent OR chatbot) AND (ai OR llm) AND ("mental health")) AND PY=(2023-2025)
        time_lower_bound: Start date (YYYY-MM-DD), year part is used.
        time_upper_bound: End date (YYYY-MM-DD), year part is used.

    Returns:
        Formatted WoS query string.
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

    topic_query = "TS=(" + " AND ".join(parts) + ")"

    year_start = time_lower_bound[:4]
    year_end = time_upper_bound[:4]
    year_filter = f"PY=({year_start}-{year_end})"

    return f"{topic_query} AND {year_filter}"


def search_wos(
    keywords: list[list[str]],
    api_key: str,
    time_lower_bound: str = "2023-01-01",
    time_upper_bound: str = "2025-07-01",
    max_pages: int = 100,
    limit: int = 50,
) -> list[dict]:
    """
    Search Web of Science with user-defined keyword groups and time range.

    Args:
        keywords: List of keyword groups (list of lists).
                  Each inner list is OR-joined; groups are AND-joined.
        api_key: Clarivate WoS Starter API key.
        time_lower_bound: Start date inclusive (YYYY-MM-DD).
        time_upper_bound: End date inclusive (YYYY-MM-DD).
        max_pages: Max number of result pages to fetch.
        limit: Results per page (WoS max is 50).

    Returns:
        List of dicts with keys: title, authors, summary, published, link
    """
    query = build_query(keywords, time_lower_bound, time_upper_bound)

    print(f"Query: {query}")
    print(f"Time range: {time_lower_bound} to {time_upper_bound}\n")

    configuration = clarivate.wos_starter.client.Configuration(
        host="https://api.clarivate.com/apis/wos-starter/v1"
    )
    configuration.api_key["ClarivateApiKeyAuth"] = api_key

    all_results = []
    page = 1

    while page <= max_pages:
        with clarivate.wos_starter.client.ApiClient(configuration) as api_client:
            api_instance = clarivate.wos_starter.client.DocumentsApi(api_client)
            try:
                print(f"Fetching WoS page {page} ...")
                api_response = api_instance.documents_get(
                    query,
                    db="WOS",
                    limit=limit,
                    page=page,
                    sort_field="LD+D",
                )
                data = api_response.model_dump()
                docs = data.get("hits", [])
                print(f"  Fetched {len(docs)} documents")

                if not docs:
                    print("  No more results.")
                    break

                for doc in docs:
                    title = doc.get("title", "") or ""
                    abstract = doc.get("abstract", "") or ""
                    source = doc.get("source", {}) or {}
                    publish_year = source.get("publish_year", "")
                    publish_month = source.get("publish_month", "")

                    # Build a date string from available fields
                    if publish_year and publish_month:
                        published = f"{publish_year}-{str(publish_month).zfill(2)}"
                    elif publish_year:
                        published = str(publish_year)
                    else:
                        published = ""

                    # Extract authors
                    names = doc.get("names", {}) or {}
                    author_list = names.get("authors", []) or []
                    if isinstance(author_list, list):
                        authors = ", ".join(
                            a.get("display_name", "") or a.get("wos_standard", "")
                            for a in author_list
                            if isinstance(a, dict)
                        )
                    else:
                        authors = ""

                    # DOI link
                    doi = doc.get("doi", "") or ""
                    uid = doc.get("uid", "") or ""
                    if doi:
                        link = f"https://doi.org/{doi}"
                    elif uid:
                        link = f"https://www.webofscience.com/wos/woscc/full-record/{uid}"
                    else:
                        link = ""

                    all_results.append({
                        "title": title,
                        "authors": authors,
                        "summary": abstract,
                        "published": published,
                        "link": link,
                    })

                if len(docs) < limit:
                    print("  Last page reached.")
                    break

                page += 1

            except ApiException as e:
                print(f" WoS API error: {e}")
                break

    print(f"\nTotal WoS results: {len(all_results)}")
    return all_results


# if __name__ == "__main__":

#     # --- Edit your keyword groups here ---
#     keywords = [
#         ["agent", "chatbot"],                           # Group 1 (OR-joined)
#         ["ai", "llm", "large language model"],          # Group 2 (OR-joined)
#         ["mental health", "psychiatry", "psychology"],   # Group 3 (OR-joined)
#     ]
#     # Groups are AND-joined:
#     # TS=((agent OR chatbot) AND (ai OR llm OR "large language model") AND (...)) AND PY=(2023-2025)

#     WOS_API_KEY = "296c7877068fd5bba5e70c4dd8540bfbbcf37346"

#     results = search_wos(
#         keywords=keywords,
#         api_key=WOS_API_KEY,
#         time_lower_bound="2023-01-01",
#         time_upper_bound="2025-07-01",
#     )

#     # Save JSON
#     with open("result_WoS.json", "w", encoding="utf-8") as f:
#         json.dump(results, f, ensure_ascii=False, indent=2)

#     # Save CSV
#     if results:
#         with open("result_WoS.csv", "w", encoding="utf-8", newline="") as f:
#             writer = csv.DictWriter(f, fieldnames=results[0].keys())
#             writer.writeheader()
#             writer.writerows(results)

#     print(f"Saved {len(results)} papers to result_WoS.json and result_WoS.csv")