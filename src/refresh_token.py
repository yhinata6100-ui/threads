"""GitHub Actionsから月2回呼ばれる（.github/workflows/refresh-token.yml）。
Threadsの長期アクセストークンをリフレッシュし、
このリポジトリのActions Secret（THREADS_ACCESS_TOKEN）を書き換える。

ローカルで単発実行した場合は .env のTHREADS_ACCESS_TOKENを書き換えるだけで、
GitHub Secretsの更新は行わない（GITHUB_REPOSITORY が無いときはスキップ）。

GitHub Secrets自動更新には、Secrets: Read/Write 権限を持つ
Fine-grained PAT（Actions Secret: GH_ADMIN_TOKEN）が必要。
"""
import base64
import os
import re
import sys

import requests
from dotenv import load_dotenv

load_dotenv()

THREADS_TOKEN = os.getenv("THREADS_ACCESS_TOKEN")
ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")

GH_ADMIN_TOKEN = os.getenv("GH_ADMIN_TOKEN")
GITHUB_REPOSITORY = os.getenv("GITHUB_REPOSITORY")  # "owner/repo"（GitHub Actions実行時に自動設定）


def _update_env_file(new_token: str):
    if not os.path.exists(ENV_PATH):
        return
    with open(ENV_PATH, "r") as f:
        content = f.read()
    new_content = re.sub(r"THREADS_ACCESS_TOKEN=.*", f"THREADS_ACCESS_TOKEN={new_token}", content)
    with open(ENV_PATH, "w") as f:
        f.write(new_content)
    print("ローカル.envのトークンを更新しました")


def _update_github_secret(new_token: str):
    if not GH_ADMIN_TOKEN or not GITHUB_REPOSITORY:
        print("GH_ADMIN_TOKEN または GITHUB_REPOSITORY が未設定のため、GitHub Secretsの更新はスキップします")
        return False

    try:
        from nacl import encoding, public
    except ImportError:
        print("PyNaClが未インストールのため、GitHub Secretsの更新はスキップします（pip install pynacl）")
        return False

    api = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/actions/secrets"
    headers = {
        "Authorization": f"Bearer {GH_ADMIN_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    r = requests.get(f"{api}/public-key", headers=headers)
    r.raise_for_status()
    key_data = r.json()

    public_key = public.PublicKey(key_data["key"].encode("utf-8"), encoding.Base64Encoder())
    sealed_box = public.SealedBox(public_key)
    encrypted = sealed_box.encrypt(new_token.encode("utf-8"))
    encrypted_b64 = base64.b64encode(encrypted).decode("utf-8")

    put = requests.put(
        f"{api}/THREADS_ACCESS_TOKEN",
        headers=headers,
        json={"encrypted_value": encrypted_b64, "key_id": key_data["key_id"]},
    )
    put.raise_for_status()
    print("GitHub Actions Secret（THREADS_ACCESS_TOKEN）を更新しました")
    return True


def refresh_threads_token():
    if not THREADS_TOKEN:
        print("THREADS_ACCESS_TOKENが未設定です")
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
    _update_github_secret(new_token)
    print("トークンリフレッシュ完了")


if __name__ == "__main__":
    refresh_threads_token()
