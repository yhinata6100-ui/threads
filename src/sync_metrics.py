"""GitHub Actionsから定期的に呼ばれる（.github/workflows/sync-metrics.yml）。
Threadsの投稿メトリクス（インプレッション・いいね等）をNotionに同期する。
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

import requests
from dotenv import load_dotenv

from main import DB_ID, HEADERS, THREADS_API, THREADS_TOKEN

load_dotenv()


def sync_metrics():
    r = requests.get(
        f"{THREADS_API}/me/threads",
        params={"fields": "id,text,permalink,timestamp", "limit": 20, "access_token": THREADS_TOKEN},
    )
    r.raise_for_status()

    updated = 0
    added = 0

    for post in r.json().get("data", []):
        text = post.get("text", "")
        permalink = post.get("permalink", "")
        timestamp = post.get("timestamp", "")
        date = timestamp[:10] if timestamp else ""

        ir = requests.get(
            f"{THREADS_API}/{post['id']}/insights",
            params={"metric": "views,likes,replies,reposts,shares", "access_token": THREADS_TOKEN},
        )
        impressions, likes, replies, reposts, shares = None, None, None, None, None
        if ir.status_code == 200:
            for item in ir.json().get("data", []):
                v = item.get("values", [])
                val = v[0]["value"] if v else None
                if item["name"] == "views":
                    impressions = val
                if item["name"] == "likes":
                    likes = val
                if item["name"] == "replies":
                    replies = val
                if item["name"] == "reposts":
                    reposts = val
                if item["name"] == "shares":
                    shares = val

        nr = requests.post(
            f"https://api.notion.com/v1/databases/{DB_ID}/query",
            headers=HEADERS,
            json={"filter": {"property": "投稿文", "rich_text": {"contains": text[:50]}}},
        )
        results = nr.json().get("results", [])

        if not results:
            props = {
                "リンク 1": {"title": [{"text": {"content": permalink}}]},
                "投稿文": {"rich_text": [{"text": {"content": text[:2000]}}]},
                "投稿日": {"date": {"start": date}},
                "投稿済み": {"checkbox": True},
                "投稿URL": {"url": permalink},
            }
            if impressions is not None:
                props["インプレッション"] = {"number": impressions}
            if likes is not None:
                props["いいね数"] = {"number": likes}
            if replies is not None:
                props["コメント数"] = {"number": replies}
            if reposts or shares:
                props["メモ"] = {"rich_text": [{"text": {"content": f"リポスト:{reposts} / シェア:{shares}"}}]}
            requests.post(
                "https://api.notion.com/v1/pages",
                headers=HEADERS,
                json={"parent": {"database_id": DB_ID}, "properties": props},
            ).raise_for_status()
            print(f"新規追加: {text[:30]}")
            added += 1
        else:
            page_id = results[0]["id"]
            props = {}
            if impressions is not None:
                props["インプレッション"] = {"number": impressions}
            if likes is not None:
                props["いいね数"] = {"number": likes}
            if replies is not None:
                props["コメント数"] = {"number": replies}
            props["メモ"] = {"rich_text": [{"text": {"content": f"リポスト:{reposts} / シェア:{shares}"}}]}
            requests.patch(
                f"https://api.notion.com/v1/pages/{page_id}", headers=HEADERS, json={"properties": props}
            ).raise_for_status()
            updated += 1
            print(f"更新: {text[:30]}... | インプレ:{impressions} いいね:{likes}")

        time.sleep(0.3)

    print(f"同期完了 — 更新:{updated}件 / 新規追加:{added}件")

    try:
        from export_kpi import export_kpi

        export_kpi()
    except Exception as e:
        print(f"ダッシュボード更新をスキップ: {e}")


if __name__ == "__main__":
    sync_metrics()
