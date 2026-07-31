"""KPIダッシュボード用に投稿データをJSONへ書き出す（docs/kpi_data.json）。
GitHub Pagesはリポジトリの docs/ を公開するため、書き出すだけでよい。
commit & push はワークフロー（.github/workflows/export-kpi.yml 等）側で行う。
"""
import os
import re
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

import json

import requests
from dotenv import load_dotenv

load_dotenv()

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_PATH = os.path.join(REPO_ROOT, "docs", "kpi_data.json")

NOTION_TOKEN = os.getenv("NOTION_API_KEY")
THREADS_TOKEN = os.getenv("THREADS_ACCESS_TOKEN")
THREADS_API = "https://graph.threads.net/v1.0"


def _extract_id(val):
    m = re.search(r"([a-f0-9]{32})", (val or "").replace("-", ""))
    return m.group(1) if m else val


DB_ID = _extract_id(os.getenv("NOTION_DATABASE_ID", ""))

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}


def fetch_follower_count():
    # 新規アカや権限未成熟だと400を返すことがある。失敗しても全体を止めずNoneを返す。
    try:
        r = requests.get(
            f"{THREADS_API}/me/threads_insights",
            params={"metric": "followers_count", "access_token": THREADS_TOKEN},
        )
        if r.status_code != 200:
            return None
        for item in r.json().get("data", []):
            if item.get("name") == "followers_count":
                return item.get("total_value", {}).get("value")
    except Exception:
        return None
    return None


def export_kpi():
    all_results = []
    payload = {
        "filter": {"property": "投稿済み", "checkbox": {"equals": True}},
        "sorts": [{"property": "投稿日", "direction": "ascending"}],
        "page_size": 100,
    }
    has_more = True
    cursor = None
    while has_more:
        if cursor:
            payload["start_cursor"] = cursor
        r = requests.post(f"https://api.notion.com/v1/databases/{DB_ID}/query", headers=HEADERS, json=payload)
        r.raise_for_status()
        data = r.json()
        all_results.extend(data.get("results", []))
        has_more = data.get("has_more", False)
        cursor = data.get("next_cursor")

    posts = []
    for page in all_results:
        props = page["properties"]
        date_val = props.get("投稿日", {}).get("date", {}) or {}
        start = date_val.get("start", "")
        date_key = start[:10] if start else "unknown"
        hour = int(start[11:13]) if "T" in start and len(start) >= 13 else None
        imp = props.get("インプレッション", {}).get("number")
        likes = props.get("いいね数", {}).get("number")
        comments = props.get("コメント数", {}).get("number")
        content_prop = props.get("投稿文", {}).get("rich_text", [])
        full = "".join(rt.get("text", {}).get("content", "") for rt in content_prop)
        content = full.replace("\n", " ")[:60]

        memo_prop = props.get("メモ", {}).get("rich_text", [])
        memo = memo_prop[0]["text"]["content"] if memo_prop else ""
        reposts_match = re.search(r"リポスト:(\d+)", memo)
        shares_match = re.search(r"シェア:(\d+)", memo)
        reposts = int(reposts_match.group(1)) if reposts_match else None
        shares = int(shares_match.group(1)) if shares_match else None

        posts.append(
            {
                "date": date_key,
                "hour": hour,
                "imp": imp,
                "content": content,
                "text": full[:1500],
                "likes": likes,
                "comments": comments,
                "reposts": reposts,
                "shares": shares,
            }
        )

    followers = []
    if os.path.exists(OUTPUT_PATH):
        try:
            with open(OUTPUT_PATH, encoding="utf-8") as f:
                prev = json.load(f)
            followers = prev.get("followers", [])
        except Exception:
            followers = []

    today_key = datetime.now().strftime("%Y-%m-%d")
    follower_count = fetch_follower_count()
    if follower_count is not None:
        followers = [f for f in followers if f["date"] != today_key]
        followers.append({"date": today_key, "count": follower_count})
        followers.sort(key=lambda f: f["date"])

    output = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "posts": posts,
        "followers": followers,
    }
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"{len(posts)}件のデータを書き出しました（フォロワー{follower_count}人） -> {OUTPUT_PATH}")
    return output


if __name__ == "__main__":
    export_kpi()
