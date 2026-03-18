import argparse
import csv
import random
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Set
from urllib.parse import urlparse

import requests


SEARCH_API_URL = "https://so.gitee.com/v1/search/widget/{widget_id}"
USER_AGENT_POOL = [
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) "
        "Gecko/20100101 Firefox/126.0"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6_6) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15"
    ),
]

BASE_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://gitee.com/",
    "Connection": "keep-alive",
}

CSV_COLUMNS = [
    "project_name",
    "author",
    "description",
    "star",
    "fork",
    "updated_at",
    "project_url",
    "language",
    "owner",
    "repo",
]


def random_sleep(delay_min: float, delay_max: float) -> None:
    if delay_max <= 0:
        return
    low = min(delay_min, delay_max)
    high = max(delay_min, delay_max)
    time.sleep(random.uniform(low, high))


def rotate_headers() -> Dict[str, str]:
    headers = dict(BASE_HEADERS)
    headers["User-Agent"] = random.choice(USER_AGENT_POOL)
    return headers


def setup_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(rotate_headers())
    return session


def request_with_backoff(
    session: requests.Session,
    url: str,
    params: Optional[Dict] = None,
    retries: int = 5,
    timeout: int = 20,
) -> Optional[requests.Response]:
    for attempt in range(1, retries + 1):
        try:
            session.headers.update(rotate_headers())
            response = session.get(url, params=params, timeout=timeout)

            if response.status_code == 200:
                return response

            if response.status_code in (403, 429, 500, 502, 503, 504):
                wait_sec = (2 ** attempt) + random.uniform(0.5, 1.8)
                print(f"[WARN] 接口受限/波动 status={response.status_code}，第{attempt}次退避 {wait_sec:.1f}s")
                time.sleep(wait_sec)
                continue

            print(f"[WARN] 请求异常 status={response.status_code} url={response.url}")
            return response
        except requests.RequestException as exc:
            wait_sec = (1.3 ** attempt) + random.uniform(0.3, 1.0)
            print(f"[WARN] 网络异常 第{attempt}次: {exc}，等待 {wait_sec:.1f}s")
            time.sleep(wait_sec)

    print(f"[ERROR] 请求失败 url={url}")
    return None


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def pick_first(fields: Dict, key: str, default: str = "") -> str:
    values = fields.get(key, [])
    if isinstance(values, list) and values:
        return clean_text(str(values[0]))
    return default


def parse_owner_repo_from_url(project_url: str) -> Dict[str, str]:
    path = urlparse(project_url).path.strip("/")
    parts = path.split("/")
    owner = parts[0] if len(parts) > 0 else ""
    repo = parts[1] if len(parts) > 1 else ""
    return {"owner": owner, "repo": repo}


def parse_projects_from_api(data: Dict) -> List[Dict[str, str]]:
    hits = data.get("hits", {}).get("hits", [])
    projects: List[Dict[str, str]] = []

    for hit in hits:
        fields = hit.get("fields", {})
        project_url = pick_first(fields, "url")
        if not project_url:
            continue

        title = pick_first(fields, "title")
        owner_repo = parse_owner_repo_from_url(project_url)
        owner = owner_repo["owner"]
        repo = owner_repo["repo"]

        author = owner
        project_name = repo
        if "/" in title:
            left, right = title.split("/", 1)
            author = clean_text(left) or author
            project_name = clean_text(right) or project_name
        elif title:
            project_name = title

        language = pick_first(fields, "langs")
        projects.append(
            {
                "project_name": project_name,
                "author": author,
                "description": pick_first(fields, "description"),
                "star": pick_first(fields, "count.star"),
                "fork": pick_first(fields, "count.fork"),
                "updated_at": pick_first(fields, "last_push_at"),
                "project_url": project_url,
                "language": language,
                "owner": owner,
                "repo": repo,
            }
        )

    return projects


def load_existing_urls(csv_path: Path) -> Set[str]:
    if not csv_path.exists():
        return set()
    existing: Set[str] = set()
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            project_url = (row.get("project_url") or "").strip()
            if project_url:
                existing.add(project_url)
    return existing


def append_rows_to_csv(csv_path: Path, rows: List[Dict[str, str]]) -> None:
    if not rows:
        return
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not csv_path.exists()
    with csv_path.open("a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        if write_header:
            writer.writeheader()
        writer.writerows(rows)


def spider_forum(
    keyword: str,
    start_page: int,
    end_page: int,
    output_dir: Path,
    widget_id: str,
    query_id: str,
    page_size: int,
    delay_min: float,
    delay_max: float,
) -> None:
    if start_page < 1 or end_page < start_page:
        raise ValueError("页码范围不合法，请确保 start_page >= 1 且 end_page >= start_page")

    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / f"gitee_so_{keyword}_projects.csv"
    seen_urls = load_existing_urls(csv_path)

    total_count = len(seen_urls)
    previous_signature: Optional[tuple] = None
    api_url = SEARCH_API_URL.format(widget_id=widget_id)

    with setup_session() as session:
        for page in range(start_page, end_page + 1):
            offset = (page - 1) * page_size
            print(f"\n[INFO] 正在抓取第{page}页 (from={offset})")

            params = {
                "query": query_id,
                "q": keyword,
                "from": offset,
                "size": page_size,
                "sort_by_f": "",
            }
            response = request_with_backoff(session, api_url, params=params, retries=5, timeout=20)
            if response is None:
                continue
            if response.status_code == 400:
                print("[INFO] 分页偏移超出接口可返回范围，停止翻页")
                break
            if response.status_code != 200:
                continue

            try:
                data = response.json()
            except ValueError:
                print("[WARN] JSON解析失败，跳过本页")
                continue

            projects = parse_projects_from_api(data)
            print(f"[INFO] 第{page}页解析到 {len(projects)} 条项目")

            current_signature = tuple(item.get("project_url", "") for item in projects)
            if previous_signature is not None and current_signature == previous_signature:
                print("[WARN] 当前页与上一页结果完全一致，可能触发同页回退，提前停止。")
                break
            previous_signature = current_signature

            if not projects:
                print("[INFO] 当前页无数据，停止翻页")
                break

            new_rows: List[Dict[str, str]] = []
            for item in projects:
                if item["project_url"] in seen_urls:
                    continue
                seen_urls.add(item["project_url"])
                new_rows.append(item)

            append_rows_to_csv(csv_path, new_rows)
            total_count += len(new_rows)
            print(f"[OK] 第{page}页新增 {len(new_rows)} 条，累计 {total_count} 条")

            random_sleep(delay_min, delay_max)

    print("\n[INFO] 抓取结束")
    print(f"[INFO] 汇总表: {csv_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="抓取 so.gitee.com 搜索结果并导出单一汇总CSV")
    parser.add_argument("--keyword", default="爬虫", help="搜索关键词，默认 爬虫")
    parser.add_argument("--start", type=int, default=1, help="起始页码，默认 1")
    parser.add_argument("--end", type=int, default=20, help="结束页码，默认 20")
    parser.add_argument("--size", type=int, default=20, help="每页大小，默认 20")
    parser.add_argument("--query-id", default="1048", help="query 参数，默认 1048")
    parser.add_argument("--widget-id", default="wong1slagnlmzwvsu5ya", help="widget id")
    parser.add_argument("--delay-min", type=float, default=0.8, help="随机延时最小秒数")
    parser.add_argument("--delay-max", type=float, default=2.0, help="随机延时最大秒数")
    parser.add_argument("--force", action="store_true", help="强制重抓时清空旧汇总表")
    parser.add_argument(
        "--output",
        default=r"D:\file\python网络爬虫\实验二\爬取内容",
        help="输出目录",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    csv_output = Path(args.output) / f"gitee_so_{args.keyword}_projects.csv"
    if args.force and csv_output.exists():
        csv_output.unlink(missing_ok=True)

    spider_forum(
        keyword=args.keyword,
        start_page=args.start,
        end_page=args.end,
        output_dir=Path(args.output),
        widget_id=args.widget_id,
        query_id=args.query_id,
        page_size=args.size,
        delay_min=args.delay_min,
        delay_max=args.delay_max,
    )
