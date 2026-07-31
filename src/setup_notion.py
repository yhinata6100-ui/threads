"""投稿管理DBとリサーチ（バズ）DBをNotion上に一括作成する（初回のみ実行）。
列名は日本語のまま（main.py / post_scheduled.py 等が日本語プロパティ名を参照しているため変えないこと）。

【事前準備】.env に以下を設定
  NOTION_API_KEY        … Notionインテグレーションのシークレット
  NOTION_PARENT_PAGE_ID … DBを作る親ページのURL or ID（その親ページをインテグレーションに「接続」しておく）

【実行】
  cd threads
  pip install -r requirements.txt
  python src/setup_notion.py

実行後に表示される DB ID を .env（ローカル）や
GitHub Secrets（NOTION_DATABASE_ID / NOTION_RESEARCH_DB_ID）に設定する。
"""
import os
import re

import requests
from dotenv import load_dotenv

load_dotenv()

API = "https://api.notion.com/v1"
TOKEN = os.getenv("NOTION_API_KEY")
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}


def _extract_id(value):
    if not value:
        return value
    head = str(value).split("?")[0].replace("-", "")
    ids = re.findall(r"[0-9a-fA-F]{32}", head)
    return ids[-1] if ids else str(value).strip()


def create_db(parent_id, title, properties):
    r = requests.post(
        f"{API}/databases",
        headers=HEADERS,
        json={
            "parent": {"type": "page_id", "page_id": parent_id},
            "title": [{"type": "text", "text": {"content": title}}],
            "properties": properties,
        },
    )
    r.raise_for_status()
    return r.json()["id"]


POST_DB_PROPS = {
    "リンク 1": {"title": {}},
    "投稿文": {"rich_text": {}},
    "投稿日": {"date": {}},
    "投稿済み": {"checkbox": {}},
    "投稿URL": {"url": {}},
    "時間帯": {
        "select": {
            "options": [
                {"name": "朝"},
                {"name": "昼"},
                {"name": "夕方"},
                {"name": "夜"},
                {"name": "深夜"},
            ]
        }
    },
    "インプレッション": {"number": {}},
    "いいね数": {"number": {}},
    "コメント数": {"number": {}},
    "メモ": {"rich_text": {}},
}

RESEARCH_DB_PROPS = {
    "投稿名": {"title": {}},
    "リンク": {"url": {}},
    "媒体": {
        "select": {
            "options": [
                {"name": "Threads"},
                {"name": "X"},
                {"name": "Instagram"},
                {"name": "その他"},
            ]
        }
    },
    "いいね数": {"number": {}},
    "インプレッション": {"number": {}},
    "追加日": {"date": {}},
}


if __name__ == "__main__":
    parent = _extract_id(os.getenv("NOTION_PARENT_PAGE_ID"))
    if not TOKEN or not parent:
        raise SystemExit("先に .env の NOTION_API_KEY と NOTION_PARENT_PAGE_ID を設定してください。")

    post_db = create_db(parent, "投稿管理DB", POST_DB_PROPS)
    print("投稿管理DB 作成")
    research_db = create_db(parent, "リサーチDB", RESEARCH_DB_PROPS)
    print("リサーチ（バズ）DB 作成")

    print("\n=== 完了。以下を .env / GitHub Secrets に設定してください ===")
    print(f"NOTION_DATABASE_ID={post_db}")
    print(f"NOTION_RESEARCH_DB_ID={research_db}")
