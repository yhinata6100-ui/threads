"""GitHub Actionsから定期的に呼ばれる（.github/workflows/post-scheduled.yml）。
・当日分のみ対象
・1日最大10件まで（事故防止の安全装置）
・時刻付きdatetimeの投稿日のみ対象（日付だけのレコードはスキップ）
"""
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))

import requests
from dotenv import load_dotenv

load_dotenv()

NOTION_TOKEN = os.getenv("NOTION_API_KEY")
THREADS_TOKEN = os.getenv("THREADS_ACCESS_TOKEN")
THREADS_API = "https://graph.threads.net/v1.0"

DAILY_POST_LIMIT = int(os.getenv("DAILY_POST_LIMIT", "10"))


def _extract_id(val):
    m = re.search(r"([a-f0-9]{32})", (val or "").replace("-", ""))
    return m.group(1) if m else val


DB_ID = _extract_id(os.getenv("NOTION_DATABASE_ID", ""))

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

JST = timezone(timedelta(hours=9))


def main():
    now = datetime.now(JST)
    today = now.strftime("%Y-%m-%d")
    now_str = now.isoformat()

    r_done = requests.post(
        f"https://api.notion.com/v1/databases/{DB_ID}/query",
        headers=HEADERS,
        json={
            "filter": {
                "and": [
                    {"property": "投稿済み", "checkbox": {"equals": True}},
                    {"property": "投稿日", "date": {"on_or_after": today}},
                    {"property": "投稿日", "date": {"before": today + "T23:59:59+09:00"}},
                ]
            }
        },
    )
    r_done.raise_for_status()
    posted_today = len(r_done.json().get("results", []))

    if posted_today >= DAILY_POST_LIMIT:
        print(f"[{now.strftime('%H:%M')}] 本日の投稿上限（{DAILY_POST_LIMIT}件・事故防止用）に達しています（投稿済み:{posted_today}件）")
        return

    r = requests.post(
        f"https://api.notion.com/v1/databases/{DB_ID}/query",
        headers=HEADERS,
        json={
            "filter": {
                "and": [
                    {"property": "投稿済み", "checkbox": {"equals": False}},
                    {"property": "投稿日", "date": {"on_or_after": today}},
                    {"property": "投稿日", "date": {"on_or_before": now_str}},
                ]
            },
            "sorts": [{"property": "投稿日", "direction": "ascending"}],
        },
    )
    r.raise_for_status()
    results = r.json().get("results", [])

    if not results:
        print(f"[{now.strftime('%H:%M')}] 投稿予定なし")
        return

    published_any = False

    for page in results:
        date_val = page["properties"].get("投稿日", {}).get("date", {}) or {}
        scheduled_at_str = date_val.get("start", "")
        if "T" not in scheduled_at_str:
            print(f"スキップ（時刻なし）: {scheduled_at_str}")
            continue

        if posted_today >= DAILY_POST_LIMIT:
            print(f"[{now.strftime('%H:%M')}] 投稿上限（{DAILY_POST_LIMIT}件）に達したため停止")
            break

        page_id = page["id"]
        content_prop = page["properties"].get("投稿文", {}).get("rich_text", [])
        content = content_prop[0]["text"]["content"] if content_prop else ""

        if not content:
            print(f"投稿文が空: {page_id}")
            continue

        # "---" のみの行で区切ると連結投稿（スレッド返信チェーン）になる
        parts = [p.strip() for p in re.split(r"\n\s*---\s*\n", content) if p.strip()]

        try:
            reply_to_id = None
            first_url = None
            for i, part in enumerate(parts):
                r1 = requests.post(
                    f"{THREADS_API}/me/threads",
                    params={
                        "media_type": "TEXT",
                        "text": part,
                        "access_token": THREADS_TOKEN,
                        **({"reply_to_id": reply_to_id} if reply_to_id else {}),
                    },
                )
                r1.raise_for_status()
                container_id = r1.json()["id"]

                time.sleep(3)

                r2 = requests.post(
                    f"{THREADS_API}/me/threads_publish",
                    params={"creation_id": container_id, "access_token": THREADS_TOKEN},
                )
                r2.raise_for_status()
                thread_id = r2.json()["id"]
                reply_to_id = thread_id
                if i == 0:
                    try:
                        rp = requests.get(
                            f"{THREADS_API}/{thread_id}",
                            params={"fields": "permalink", "access_token": THREADS_TOKEN},
                        )
                        rp.raise_for_status()
                        first_url = rp.json().get("permalink") or f"https://www.threads.net/post/{thread_id}"
                    except Exception:
                        first_url = f"https://www.threads.net/post/{thread_id}"
                if i < len(parts) - 1:
                    time.sleep(3)

            thread_url = first_url

            requests.patch(
                f"https://api.notion.com/v1/pages/{page_id}",
                headers=HEADERS,
                json={
                    "properties": {
                        "投稿済み": {"checkbox": True},
                        "投稿URL": {"url": thread_url},
                        "リンク 1": {"title": [{"text": {"content": thread_url}}]},
                    }
                },
            ).raise_for_status()

            posted_today += 1
            published_any = True
            print(f"投稿完了（{len(parts)}件連結） [{now.strftime('%H:%M')}] -> {thread_url}")
            print(f"   内容: {content[:40]}...")

        except Exception as e:
            print(f"投稿失敗: {e}")

    if published_any:
        try:
            from export_kpi import export_kpi

            export_kpi()
        except Exception as e:
            print(f"ダッシュボード更新をスキップ: {e}")


if __name__ == "__main__":
    main()
