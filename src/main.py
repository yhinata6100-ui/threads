"""Notion連携 + Threads自動投稿のコア関数。
post_scheduled.py / sync_metrics.py / export_kpi.py から import して使う。
"""
import os
import re
import time as _time
from datetime import datetime

import requests
from dotenv import load_dotenv

load_dotenv()

NOTION_TOKEN = os.getenv("NOTION_API_KEY")


def _extract_id(val: str) -> str:
    m = re.search(r"([a-f0-9]{32})", (val or "").replace("-", ""))
    return m.group(1) if m else val


DB_ID = _extract_id(os.getenv("NOTION_DATABASE_ID", ""))
RESEARCH_DB_ID = _extract_id(os.getenv("NOTION_RESEARCH_DB_ID", ""))
THREADS_TOKEN = os.getenv("THREADS_ACCESS_TOKEN")
THREADS_API = "https://graph.threads.net/v1.0"

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}


# ──────────────────────────────────────────────
# 投稿管理（Notion）
# ──────────────────────────────────────────────

def save_posts(posts: list):
    """posts: [{"content": str, "scheduled_at": "2026-07-31T21:14:00+09:00"(必須推奨), "time_slot": str(任意)}]
    content内で単独行の "---" を挟むと、post_scheduled.pyがスレッド返信チェーンとして連結投稿する。
    投稿日は必ず時刻付きdatetimeにすること。日付だけだとpost_scheduled.pyは投稿しない。
    """
    today = datetime.now().strftime("%Y-%m-%d")
    saved = []
    for post in posts:
        scheduled_at = post.get("scheduled_at")
        date_start = scheduled_at if scheduled_at else today
        props = {
            "リンク 1": {"title": [{"text": {"content": ""}}]},
            "投稿文": {"rich_text": [{"text": {"content": post["content"][:2000]}}]},
            "投稿日": {"date": {"start": date_start}},
            "投稿済み": {"checkbox": False},
        }
        if post.get("time_slot"):
            props["時間帯"] = {"select": {"name": post["time_slot"]}}
        r = requests.post(
            "https://api.notion.com/v1/pages",
            headers=HEADERS,
            json={"parent": {"database_id": DB_ID}, "properties": props},
        )
        r.raise_for_status()
        page_id = r.json()["id"]
        saved.append(page_id)
        print(f"保存完了 -> {post.get('time_slot', '')} {date_start} ID:{page_id}")
    return saved


def list_recent_posts():
    r = requests.post(
        f"https://api.notion.com/v1/databases/{DB_ID}/query",
        headers=HEADERS,
        json={"sorts": [{"property": "投稿日", "direction": "descending"}], "page_size": 10},
    )
    r.raise_for_status()
    posts = []
    for page in r.json()["results"]:
        props = page["properties"]
        title_prop = props.get("リンク 1", {}).get("title", [])
        content_prop = props.get("投稿文", {}).get("rich_text", [])
        content = (
            content_prop[0]["text"]["content"]
            if content_prop
            else (title_prop[0]["text"]["content"] if title_prop else "(内容なし)")
        )
        date_val = props.get("投稿日", {}).get("date")
        post_date = date_val["start"] if date_val else "不明"
        imp = props.get("インプレッション", {}).get("number")
        posts.append(
            {
                "id": page["id"],
                "content": content[:40] + ("..." if len(content) > 40 else ""),
                "date": post_date,
                "impressions": imp,
            }
        )
    return posts


def update_metrics(page_id: str, metrics: dict):
    properties = {}
    if metrics.get("url"):
        properties["リンク 1"] = {"title": [{"text": {"content": metrics["url"]}}]}
    if metrics.get("impressions") is not None:
        properties["インプレッション"] = {"number": metrics["impressions"]}
    if metrics.get("likes") is not None:
        properties["いいね数"] = {"number": metrics["likes"]}
    if metrics.get("comments") is not None:
        properties["コメント数"] = {"number": metrics["comments"]}
    if metrics.get("memo"):
        properties["メモ"] = {"rich_text": [{"text": {"content": metrics["memo"]}}]}
    r = requests.patch(
        f"https://api.notion.com/v1/pages/{page_id}", headers=HEADERS, json={"properties": properties}
    )
    r.raise_for_status()
    print("数値を更新しました")


# ──────────────────────────────────────────────
# Threads API — メトリクス取得
# ──────────────────────────────────────────────

def _find_notion_page_by_url(url: str):
    r = requests.post(
        f"https://api.notion.com/v1/databases/{DB_ID}/query",
        headers=HEADERS,
        json={"filter": {"property": "リンク 1", "title": {"equals": url}}},
    )
    r.raise_for_status()
    results = r.json().get("results", [])
    return results[0]["id"] if results else None


def fetch_threads_metrics(limit: int = 10):
    r = requests.get(
        f"{THREADS_API}/me/threads",
        params={"fields": "id,text,timestamp,permalink", "limit": limit, "access_token": THREADS_TOKEN},
    )
    r.raise_for_status()
    results = []
    for post in r.json().get("data", []):
        post_id = post["id"]
        ir = requests.get(
            f"{THREADS_API}/{post_id}/insights",
            params={"metric": "views,likes,replies,reposts,shares", "access_token": THREADS_TOKEN},
        )
        metrics = {"views": None, "likes": None, "replies": None, "reposts": None, "shares": None}
        if ir.status_code == 200:
            for item in ir.json().get("data", []):
                values = item.get("values", [])
                metrics[item["name"]] = values[0]["value"] if values else None
        timestamp = post.get("timestamp", "")
        results.append(
            {
                "id": post_id,
                "content": post.get("text", ""),
                "date": timestamp[:10] if timestamp else "不明",
                "permalink": post.get("permalink", ""),
                "impressions": metrics["views"],
                "likes": metrics["likes"],
                "comments": metrics["replies"],
                "reposts": metrics["reposts"],
                "shares": metrics["shares"],
            }
        )
    return results


def sync_threads_to_notion(limit: int = 20):
    posts = fetch_threads_metrics(limit)
    created, updated = 0, 0
    for post in posts:
        url = post["permalink"] or f"https://www.threads.net/post/{post['id']}"
        memo = f"リポスト:{post['reposts']} / シェア:{post['shares']}"
        props = {
            "リンク 1": {"title": [{"text": {"content": url}}]},
            "投稿文": {"rich_text": [{"text": {"content": post["content"][:2000]}}]},
            "投稿日": {"date": {"start": post["date"]}},
            "メモ": {"rich_text": [{"text": {"content": memo}}]},
            "投稿URL": {"url": url},
        }
        if post["impressions"] is not None:
            props["インプレッション"] = {"number": post["impressions"]}
        if post["likes"] is not None:
            props["いいね数"] = {"number": post["likes"]}
        if post["comments"] is not None:
            props["コメント数"] = {"number": post["comments"]}
        existing_id = _find_notion_page_by_url(url)
        if existing_id:
            requests.patch(
                f"https://api.notion.com/v1/pages/{existing_id}", headers=HEADERS, json={"properties": props}
            ).raise_for_status()
            updated += 1
        else:
            requests.post(
                "https://api.notion.com/v1/pages",
                headers=HEADERS,
                json={"parent": {"database_id": DB_ID}, "properties": props},
            ).raise_for_status()
            created += 1
    print(f"同期完了 — 新規:{created}件 / 更新:{updated}件")
    return {"created": created, "updated": updated}


# ──────────────────────────────────────────────
# Threads API — 自動投稿
# ──────────────────────────────────────────────

def publish_to_threads(text: str, reply_to_id: str = None) -> str:
    params = {"media_type": "TEXT", "text": text, "access_token": THREADS_TOKEN}
    if reply_to_id:
        params["reply_to_id"] = reply_to_id
    r = requests.post(f"{THREADS_API}/me/threads", params=params)
    r.raise_for_status()
    container_id = r.json()["id"]
    _time.sleep(3)
    r = requests.post(
        f"{THREADS_API}/me/threads_publish",
        params={"creation_id": container_id, "access_token": THREADS_TOKEN},
    )
    r.raise_for_status()
    return r.json()["id"]


def get_permalink(thread_id: str) -> str:
    """公開済み投稿の実URL（permalink）を取得する。取れない場合は空文字。"""
    try:
        r = requests.get(
            f"{THREADS_API}/{thread_id}", params={"fields": "permalink", "access_token": THREADS_TOKEN}
        )
        r.raise_for_status()
        return r.json().get("permalink", "") or ""
    except Exception:
        return ""


def publish_thread_series(posts: list) -> str:
    """複数の投稿をスレッド（返信チェーン）として連結投稿する。最初の投稿のURL（permalink）を返す。"""
    reply_to_id = None
    first_url = None
    for i, text in enumerate(posts):
        thread_id = publish_to_threads(text, reply_to_id=reply_to_id)
        if i == 0:
            first_url = get_permalink(thread_id) or f"https://www.threads.net/post/{thread_id}"
        reply_to_id = thread_id
        if i < len(posts) - 1:
            _time.sleep(3)
    return first_url


def get_todays_scheduled_post(time_slot: str):
    today = datetime.now().strftime("%Y-%m-%d")
    r = requests.post(
        f"https://api.notion.com/v1/databases/{DB_ID}/query",
        headers=HEADERS,
        json={
            "filter": {
                "and": [
                    {"property": "投稿日", "date": {"equals": today}},
                    {"property": "時間帯", "select": {"equals": time_slot}},
                    {"property": "投稿済み", "checkbox": {"equals": False}},
                ]
            }
        },
    )
    r.raise_for_status()
    results = r.json().get("results", [])
    if not results:
        return None
    page = results[0]
    content_prop = page["properties"]["投稿文"]["rich_text"]
    return {
        "id": page["id"],
        "content": content_prop[0]["text"]["content"] if content_prop else "",
    }


def print_threads_metrics():
    print("\nThreads 直近の投稿メトリクス")
    print("-" * 80)
    posts = fetch_threads_metrics()
    for i, p in enumerate(posts):
        print(f"{i + 1}. [{p['date']}] {p['content'][:30]}...")
        print(
            f"   インプレ:{p['impressions']} / いいね:{p['likes']} / コメ:{p['comments']} "
            f"/ リポスト:{p['reposts']} / シェア:{p['shares']}"
        )
    return posts


if __name__ == "__main__":
    print("\n直近の投稿一覧")
    print("-" * 60)
    recent = list_recent_posts()
    if not recent:
        print("まだ投稿がありません")
    for i, post in enumerate(recent):
        imp_str = f"インプレ:{post['impressions']}" if post["impressions"] else "数値未入力"
        print(f"{i + 1}. [{post['date']}] {post['content']} ({imp_str})")
