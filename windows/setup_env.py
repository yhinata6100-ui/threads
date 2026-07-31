"""Windows用セットアップ: 対話式でAPIキーを入力し、.envに保存する。

  python windows\\setup_env.py

（setup.bat から呼ばれる）
入力した値はこのPC上の .env にのみ保存される。.env は .gitignore 済みなので
Gitにコミットされることはなく、他人に見られることもない。
"""
import getpass
import os

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(REPO_ROOT, ".env")

# (キー名, 説明, 入力を隠すか)
FIELDS = [
    ("NOTION_API_KEY", "Notion インテグレーションのシークレットキー", True),
    ("NOTION_PARENT_PAGE_ID", "NotionのDB作成先ページのURLまたはID", False),
    ("NOTION_DATABASE_ID", "投稿管理DBのID（setup_notion.py実行前なら空Enterで後回しでOK）", False),
    ("NOTION_RESEARCH_DB_ID", "リサーチDBのID（同上、空Enterで後回しでOK）", False),
    ("THREADS_ACCESS_TOKEN", "Threadsの長期アクセストークン", True),
]


def _load_existing():
    values = {}
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                values[k] = v
    return values


def main():
    print("=== Threads自動投稿 セットアップ（Windows）===")
    print(f"入力した値はこのPCの次の場所にのみ保存されます（Gitには含まれません）:\n  {ENV_PATH}\n")

    values = _load_existing()

    for key, label, is_secret in FIELDS:
        current = values.get(key, "")
        shown = "（設定済み・変更する場合のみ入力、そのままならEnter）" if current else "（未設定）"
        prompt = f"{label} {shown}: "
        entered = getpass.getpass(prompt) if is_secret else input(prompt)
        if entered.strip():
            values[key] = entered.strip()

    with open(ENV_PATH, "w", encoding="utf-8") as f:
        for key, _, _ in FIELDS:
            f.write(f"{key}={values.get(key, '')}\n")

    print(f"\n保存しました -> {ENV_PATH}")
    print("次は windows\\run_setup_notion.bat（初回のみ）→ windows\\run_post_scheduled.bat で動作確認してください。")


if __name__ == "__main__":
    main()
