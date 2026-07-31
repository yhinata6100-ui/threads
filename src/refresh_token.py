"""Windowsのタスクスケジューラから月2回呼ばれる（windows/run_refresh_token.bat）。
Threadsの長期アクセストークンをリフレッシュし、ローカルの .env を書き換える。
"""
import os
import re
import sys

import requests
from dotenv import load_dotenv

load_dotenv()

THREADS_TOKEN = os.getenv("THREADS_ACCESS_TOKEN")
ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")


def _update_env_file(new_token: str):
    if not os.path.exists(ENV_PATH):
        return
    with open(ENV_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    new_content = re.sub(r"THREADS_ACCESS_TOKEN=.*", f"THREADS_ACCESS_TOKEN={new_token}", content)
    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.write(new_content)
    print(f"ローカル.envのトークンを更新しました -> {ENV_PATH}")


def refresh_threads_token():
    if not THREADS_TOKEN:
        print("THREADS_ACCESS_TOKENが未設定です。windows\\setup_env.py で先に設定してください。")
        sys.exit(1)

    r = requests.get(
        "https://graph.threads.net/refresh_access_token",
        params={"grant_type": "th_refresh_token", "access_token": THREADS_TOKEN},
    )

    if r.status_code != 200:
        print(f"リフレッシュ失敗: {r.status_code} {r.text}")
        sys.exit(1)

    new_token = r.json().get("access_token")
    if not new_token:
        print(f"トークン取得失敗: {r.text}")
        sys.exit(1)

    _update_env_file(new_token)
    print("トークンリフレッシュ完了")


if __name__ == "__main__":
    refresh_threads_token()
