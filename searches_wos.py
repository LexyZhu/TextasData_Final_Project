import feedparser
from urllib.parse import quote
import json
import csv
import time
import pandas as pd
from springernature_api_client.openaccess import OpenAccessAPI


def search_arxiv():
    import feedparser
    from urllib.parse import quote
    import time

    base_url = "http://export.arxiv.org/api/query?"
    
    # 更新关键词查询逻辑
    query = 'all:((agent OR chatbot) AND (ai OR llm OR "large language model") AND ("mental health" OR psychiatry OR psychology))'
    query_encoded = quote(query)
    
    all_results = []
    start = 0
    max_per_request = 2000
    max_total = 10000  # arXiv 不建议超过此数量

    while start < max_total:
        url = (
            f"{base_url}search_query={query_encoded}"
            f"&start={start}&max_results={max_per_request}"
            f"&sortBy=submittedDate&sortOrder=descending"
        )
        print(f"🔍 Fetching arXiv records {start} to {start + max_per_request} ...")
        
        feed = feedparser.parse(url)
        entries = feed.entries
        print(f"Fetched {len(entries)} entries")

        if not entries:
            print("No more results.")
            break

        for entry in entries:
            try:
                published_year = int(entry.published[:4])
                published_date = entry.published[:10]
                if "2025-07-01" <= published_date <= "2025-12-18":
                    all_results.append({
                        "title": entry.title,
                        "authors": [author.name for author in entry.authors],
                        "published": entry.published,
                        "summary": entry.summary,
                        "link": entry.link
                    })
            except Exception as e:
                print(f"Error processing entry: {e}")
                continue

        start += max_per_request
        time.sleep(3)

    return all_results


import requests


import requests
import time

def search_medrxiv():
    # URL中已经包含了日期过滤，这是最高效的方式
    url = "https://api.biorxiv.org/details/medrxiv/2023-01-01/2025-07-01"
    
    results = []
    cursor = 0
    page_size = 100  # API每页返回的条目数

    # 使用无限循环，完全依赖API的返回结果来决定何时停止
    while True:
        paged_url = f"{url}/{cursor}"
        
        try:
            response = requests.get(paged_url, timeout=10) # 增加超时以防网络问题
            response.raise_for_status()  # 如果请求失败 (如 404, 500), 会抛出异常
            data = response.json()
        except requests.exceptions.RequestException as e:
            print(f"An error occurred during request: {e}")
            break
        except ValueError: # requests.exceptions.JSONDecodeError 继承自 ValueError
            print(f"Failed to decode JSON from response.")
            break

        entries = data.get("collection", [])
        print(f"Fetching medRxiv records from index {cursor}... Found {len(entries)} new entries.")

        # 如果API返回的集合是空的，说明没有更多数据了，这是正确的退出点
        if not entries:
            print("No more results from the API. Stopping.")
            break

        for item in entries:
            title = item.get("title", "").lower()
            abstract = item.get("abstract", "").lower()
            text_to_search = title + " " + abstract # 合并标题和摘要一次性搜索，更高效

            # 将所有条件用 'and' 合并到一个if语句中，更清晰
            # 这是客户端过滤，因为API不支持关键词搜索
            is_agent_related = ("agent" in text_to_search) or ("chatbot" in text_to_search)
            is_mh_related = any(kw in text_to_search for kw in ["mental health", "psychiatry", "psychology"])
            is_ai_related = any(kw in text_to_search for kw in ["ai", "llm", "large language model"])

            if is_agent_related and is_mh_related and is_ai_related:
                results.append({
                    "title": item.get("title"),
                    "authors": item.get("authors"),
                    "published": item.get("date", ""),
                    "summary": item.get("abstract"),
                    "link": f"https://doi.org/{item.get('doi')}" if item.get('doi') else ''
                })

        # 更新cursor以获取下一页
        cursor += len(entries) # 使用实际返回的数量来增加cursor，比固定的page_size更严谨

        # 友好的API使用习惯，在两次请求之间稍作等待
        time.sleep(0.2)

    print(f"\nSearch complete. Total filtered results found: {len(results)}")
    return results




# def search_medrxiv():
#     import requests
#     import time

#     url = "https://api.biorxiv.org/details/medrxiv/2023-01-01/2025-07-01"
#     results = []
#     cursor = 0
#     page_size = 100
#     max_cursor = 5000

#     while cursor < max_cursor:
#         paged_url = f"{url}/{cursor}"
#         response = requests.get(paged_url)
#         data = response.json()

#         entries = data.get("collection", [])
#         print(f"Fetching medRxiv records {cursor} to {cursor + page_size} ... Got: {len(entries)}")
#         if not entries:
#             print("No more results.")
#             break

#         for item in entries:
#             title = item.get("title", "").lower()
#             abstract = item.get("abstract", "").lower()
#             date = item.get("date", "")
#             # 关键词过滤逻辑（严格匹配所有三类关键词）
#             if "agent" in title or "agent" in abstract:
#                 if any(kw in title or kw in abstract for kw in ["mental health", "psychiatry", "psychology"]):
#                     if any(kw in title or kw in abstract for kw in ["ai", "llm", "large language model"]):
#                         if "2023-01-01" <= date <= "2025-07-01":
#                             results.append({
#                                 "title": item.get("title"),
#                                 "authors": item.get("authors"),
#                                 "published": date,
#                                 "summary": item.get("abstract"),
#                                 "link": item.get("doi_url", '')
#                             })
#         print(f"100 filtered results: {len(results)}")
#         cursor += page_size
#         time.sleep(0.2)

#     print(f"Total filtered results: {len(results)}")
#     return results
import requests
import time
from itertools import product

# 你的关键词组
agent_group = ["agent"]
ai_group = ["ai", "llm", "large language model"]
mh_group = ["mental health", "psychiatry", "psychology"]

def search_osf_preprints_single_query(query, max_results=100):
    url = "https://api.osf.io/v2/preprints/"
    params = {
        "q": query,
        "size": min(max_results, 100)  # OSF每页最大100
    }
    response = requests.get(url, params=params, timeout=20)
    if response.status_code != 200:
        print(f"❌ Status code: {response.status_code}, message: {response.text[:200]}")
        return []
    try:
        data = response.json()
    except Exception as e:
        print(f"❌ JSON decode error: {e}")
        return []

    results = []
    for item in data.get("data", []):
        attributes = item.get("attributes", {})
        results.append({
            "title": attributes.get("title", ""),
            "description": attributes.get("description", ""),
            "date_created": attributes.get("date_created", "")[:10],
            "link": item["links"].get("html", ""),
            "id": item.get("id", ""),
        })
    return results

def deduplicate(results):
    seen = set()
    unique = []
    for item in results:
        key = (item["title"], item["link"])
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique

def search_osf():
    all_results = []
    for agent_kw, ai_kw, mh_kw in product(agent_group, ai_group, mh_group):
        query = f"{agent_kw} {ai_kw} {mh_kw}"
        print(f"🔍 Searching: {query}")
        results = search_osf_preprints_single_query(query)
        all_results.extend(results)
        time.sleep(1)  # 防止被限流
    unique_results = deduplicate(all_results)
    print(f"✅ Total unique OSF preprints: {len(unique_results)}")
    return unique_results


from Bio import Entrez

def search_pubmed(email="your_email@example.com"):
    from Bio import Entrez
    import time

    Entrez.email = email

    # ✅ 新的 PubMed 查询语法
    query = '((agent[All Fields] OR chatbot[All Fields]) AND (ai[All Fields] OR llm[All Fields] OR "large language model"[All Fields]) ' \
            'AND ("mental health"[All Fields] OR psychiatry[All Fields] OR psychology[All Fields])) ' \
            'AND ("2023/01/01"[Date - Publication] : "2025/07/01"[Date - Publication])'

    print("🔍 Searching PubMed...")

    # 检索匹配的 PubMed ID
    handle = Entrez.esearch(db="pubmed", term=query, retmax=1000, sort="pub+date")
    record = Entrez.read(handle)
    ids = record.get('IdList', [])

    if not ids:
        print("⛔ No results found.")
        return []

    print(f"✅ Retrieved {len(ids)} article IDs")

    # 获取具体文章信息
    time.sleep(1)  # 稍作延迟，防止被限
    handle = Entrez.efetch(db="pubmed", id=ids, rettype="medline", retmode="xml")
    records = Entrez.read(handle)

    results = []
    for article in records.get('PubmedArticle', []):
        try:
            title = article['MedlineCitation']['Article']['ArticleTitle']
            abstract = article['MedlineCitation']['Article']['Abstract']['AbstractText'][0]
            pub_date = article['MedlineCitation']['Article']['Journal']['JournalIssue']['PubDate']
            year = pub_date.get('Year', '')
            month = pub_date.get('Month', '01')
            day = pub_date.get('Day', '01')
            published = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            pmid = article['MedlineCitation']['PMID']

            if "2023-01-01" <= published <= "2025-07-01":
                results.append({
                    "title": title,
                    "summary": abstract,
                    "published": published,
                    "link": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}"
                })
        except Exception as e:
            print(f"⚠️ Skipped an entry due to error: {e}")
            continue

    print(f"✅ Total filtered PubMed results: {len(results)}")
    return results

def search_openalex():
    import requests
    import time

    base_url = "https://api.openalex.org/works"
    query = '(agent OR chatbot) AND (ai OR llm OR "large language model") AND ("mental health" OR psychiatry OR psychology)'
    
    per_page = 200  # 最大支持值
    page = 1
    headers = {
        "User-Agent": "YourAppName/0.1 (mailto:your@email.com)"
    }

    def decode_abstract(inv):
        if not inv:
            return ""
        buf = {}
        for w, pos in inv.items():
            for p in pos:
                buf[p] = w
        return " ".join(buf[i] for i in sorted(buf))
    
    results = []
    g1 = '(agent OR chatbot)'
    g2 = '(ai OR llm OR "large language model")'
    g3 = '("mental health" OR psychiatry OR psychology)'
    while True:
        params = {
            # "search": query,
            # "filter": "from_publication_date:2023-01-01,to_publication_date:2025-07-01",
            "filter": (
                f"title_and_abstract.search:{g1},"
                f"title_and_abstract.search:{g2},"
                f"title_and_abstract.search:{g3},"
                "from_publication_date:2023-01-01,"
                "to_publication_date:2025-07-01"
            ),
            "per_page": per_page,
            "page": page,
            "select": "id,display_name,abstract_inverted_index,publication_date",
            "sort": "relevance_score:desc"
        }
        print(f"🔍 Fetching OpenAlex records: page {page}")
        response = requests.get(base_url, params=params, headers=headers)
        if response.status_code != 200:
            print(f"❌ Request failed with status {response.status_code}")
            break
        try:
            data = response.json()
        except Exception as e:
            print(f"⚠️ Failed to parse JSON: {e}")
            break
        works = data.get("results", [])
        print(f"✅ Fetched {len(works)} items")
        for item in works:
            # title = item.get("title", "") or ""
            # abstract = item.get("abstract", "") or ""
            title = item.get("display_name", "")
            abstract_raw = item.get("abstract_inverted_index")
            abstract = decode_abstract(abstract_raw)
            results.append({
                "title": title,
                "summary": abstract,
                "published": item.get("publication_date", ""),
                "link": item.get("id", "")
            })
        if len(works) < per_page:
            print("🎯 Last page reached.")
            break
        page += 1
        time.sleep(1)  # 控制速率，防止封锁
    print(f"🎯 Total filtered OpenAlex results: {len(results)}")
    return results

from urllib.parse import quote
import requests
import time

def get_abstract_by_eid(eid, api_key):
    url = f"https://api.elsevier.com/content/abstract/eid/{eid}"
    headers = {
        "X-ELS-APIKey": api_key,
        "Accept": "application/json"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        coredata = data.get('abstracts-retrieval-response', {}).get('coredata', {})
        abstract = coredata.get('dc:description', '')
        return abstract
    else:
        print(f"⚠️ Failed to fetch abstract for EID {eid}: status {response.status_code}")
        return ""

def search_scopus(api_key):
    headers = {
        'X-ELS-APIKey': api_key,
        'Accept': 'application/json'
    }

    # 正确拆分条件 —— TITLE-ABS-KEY 中不包含 PUBYEAR
    title_query = 'TITLE-ABS-KEY((agent OR chatbot) AND (ai OR llm OR "large language model") AND ("mental health" OR psychiatry OR psychology))'
    year_filter = 'PUBYEAR > 2023 AND PUBYEAR < 2026'
    full_query = f"{title_query} AND {year_filter}"

    count = 25
    start = 0
    results = []
    max_requests = 5000
    request_count = 0

    while request_count < max_requests:
        url = f"https://api.elsevier.com/content/search/scopus?query={quote(full_query)}&count={count}&start={start}"
        try:
            print(f"🔍 Fetching Scopus records {start} to {start + count} ...")
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            print("❌ API Request Error:", e)
            break

        entries = data.get("search-results", {}).get("entry", [])
        if not entries:
            print("⚠️ No more entries found.")
            break

        for entry in entries:
            eid = entry.get("eid")
            summary = get_abstract_by_eid(eid, api_key) if eid else ""
            results.append({
                "title": entry.get("dc:title"),
                "published": entry.get("prism:coverDate", ""),
                "summary": summary,
                "link": entry.get("prism:url")
            })

        if len(entries) < count:
            break
        start += count
        request_count += 1
        time.sleep(1)  # Respectful pause for rate limits

    print(f"✅ Total filtered Scopus results: {len(results)}")
    return results

import clarivate.wos_starter.client
from clarivate.wos_starter.client.rest import ApiException

def search_wos(api_key, max_pages=100):
    all_results = []
    db = 'WOS'
    limit = 50  # WOS API 限制最大为 50
    page = 1
    sort_field = 'LD+D'  # 发表日期降序排列

    # ✅ 更新后的查询语法（Topic + 关键词 + 年份范围）
    # q = 'TS=(agent AND (ai OR llm OR "large language model") AND (mental health OR psychiatry OR psychology)) AND PY=(2023-2025)'
    q = 'TS=((agent OR chatbot) AND (ai OR llm OR "large language model") AND ("mental health" OR psychiatry OR psychology)) AND PY=(2023-2025)'
    configuration = clarivate.wos_starter.client.Configuration(
        host="https://api.clarivate.com/apis/wos-starter/v1"
    )
    configuration.api_key['ClarivateApiKeyAuth'] = api_key

    while page <= max_pages:
        with clarivate.wos_starter.client.ApiClient(configuration) as api_client:
            api_instance = clarivate.wos_starter.client.DocumentsApi(api_client)
            try:
                print(f"🔍 Fetching WOS page {page} ...")
                api_response = api_instance.documents_get(q, db=db, limit=limit, page=page, sort_field=sort_field)
                data = api_response.model_dump()  # 推荐用model_dump
                docs = data.get('hits', [])
                print(f"文献数量: {len(docs)}")
                # for doc in docs:
                #     print(doc)  # 这里的doc是dict，可以直接访问字段

                if not docs:
                    print("⛔ No more results.")
                    break

                for doc in docs:
                    title = doc.get('title', '') or ''
                    abstract = doc.get('abstract', '') or ''
                    publication_year = doc.get('source', {}).get('publish_year', '')
                    # combined_text = (title + abstract).lower()

                    # if not publication_year or not publication_year.isdigit():
                    #     continue
                    # if not (2023 <= int(publication_year) <= 2025):
                    #     continue

                    # if "agent" in combined_text and \
                    #    any(kw in combined_text for kw in ["mental health", "psychiatry", "psychology"]) and \
                    #    any(kw in combined_text for kw in ["ai", "llm", "large language model"]):

                    all_results.append({
                        "title": title,
                        "summary": abstract,
                        "published": publication_year,
                        "link": doc.get('doi', '')
                    })

                if len(docs) < limit:
                    break
                page += 1

            except ApiException as e:
                print(f"❌ WOS API Error: {e}")
                break

    print(f"✅ Total filtered WOS results: {len(all_results)}")
    return all_results

def search_springer(api_key):
    """
    Springer Open Access API 查询，参考官方文档：
    https://dev.springernature.com/docs/api-endpoints/open-access/
    """
    query = '((agent OR chatbot) AND (ai OR llm OR "large language model") AND ("mental health" OR psychiatry OR psychology))'
    oa_client = OpenAccessAPI(api_key=api_key)
    all_records = []
    s = 1
    p = 10
    page_count = 0
    try:
        while True:
            response = oa_client.search(
                q=query,
                p=p,
                s=s,
                fetch_all=False,
                is_premium=False
            )
            # 官方返回结构应有'records'字段
            records = response.get('records') if isinstance(response, dict) else None
            print(f"[DEBUG] type(records): {type(records)}")
            if records:
                print(f"[DEBUG] records sample: {json.dumps(records[:1], ensure_ascii=False, indent=2)}")
            if not records:
                break
            all_records.extend(records)
            page_count += 1
            if len(records) < p or page_count >= 100:
                break
            s += p
            time.sleep(1)  # 每次请求间隔1秒，防止被封禁
    except Exception as e:
        print(f"Springer API 请求失败: {e}")
        return None

    if not all_records:
        print("Springer API 请求无结果")
        return None

    results = []
    for item in all_records:
        year = item.get("publicationDate", "")[:4]
        if year and 2023 <= int(year) <= 2025:
            # 修正摘要提取逻辑
            abstract = item.get("abstract", "")
            if isinstance(abstract, dict):
                summary = abstract.get("p", "")
            elif isinstance(abstract, str):
                summary = abstract
            else:
                summary = ""
            results.append({
                "title": item.get("title"),
                "summary": summary,
                "published": item.get("publicationDate"),
                "link": item.get("url", [{}])[0].get("value", "") if item.get("url") else ""
            })
    if results:
        return pd.DataFrame(results)
    else:
        print("Springer API 请求无结果，返回内容：", all_records)
        return None

def save_results(filename, results):
    # 如果是DataFrame，先转为dict
    if hasattr(results, 'to_dict'):
        results = results.to_dict(orient='records')
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
        

def save_results_csv(filename, results):
    # 支持DataFrame类型
    if hasattr(results, 'empty'):
        if results.empty:
            return
        results = results.to_dict(orient='records')
    if not results:
        return
    keys = results[0].keys()
    with open(filename, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(results)

if __name__ == "__main__":
    # arxiv_results = search_arxiv()
    # save_results("result_arXiv.json", arxiv_results)
    # save_results_csv("result_arXiv.csv", arxiv_results)

    # medrxiv_results = search_medrxiv()
    # save_results("result_medRxiv.json", medrxiv_results)
    # save_results_csv("result_medRxiv.csv", medrxiv_results)

    # osf_results = search_osf()
    # save_results("result_OSF.json", osf_results)
    # save_results_csv("result_OSF.csv", osf_results)

    # PubMed
    # pubmed_results = search_pubmed(email="your_email@example.com")
    # save_results("result_PubMed.json", pubmed_results)
    # save_results_csv("result_PubMed.csv", pubmed_results)

    # # # OpenAlex
    # openalex_results = search_openalex()
    # save_results("result_OpenAlex.json", openalex_results)
    # save_results_csv("result_OpenAlex.csv", openalex_results)

    # Scopus 
    # scopus_api_key = "a6a4b4a8f0ff49676823b4b795cff8aa"
    # scopus_results = search_scopus(scopus_api_key)
    # save_results("result_Scopus.json", scopus_results)
    # save_results_csv("result_Scopus.csv", scopus_results)

    # WoS (等两天)
    # wos_api_key = "296c7877068fd5bba5e70c4dd8540bfbbcf37346"
    # wos_results = search_wos(wos_api_key)
    # save_results("result_WoS.json", wos_results)
    # save_results_csv("result_WoS.csv", wos_results)

    # # Springer Nature 
    springer_api_key = "9d77ee8d226739c0a15b871ef9333d7d"
    springer_results = search_springer(springer_api_key)
    save_results("result_Springer.json", springer_results)
    save_results_csv("result_Springer.csv", springer_results)