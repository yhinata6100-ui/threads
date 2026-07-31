"""手入力KPI（オプチャ参加数・アポ/相談数など）をダッシュボードに反映するCLI。
ローカルで実行し、書き出したファイルをコミット&プッシュするとダッシュボードに反映される。

使い方:
  python src/kpi_input.py <オプチャ数> <アポ数> [日付]
  ・数字を変えたくない項目は「-」にする
  ・日付を省略すると今日
  例:
    python src/kpi_input.py 42 3
    python src/kpi_input.py 128 - 2026-07-25
"""
import json
import os
import sys
from datetime import datetime

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_PATH = os.path.join(REPO_ROOT, "docs", "kpi_manual.json")


def load(path):
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
            return d if isinstance(d, list) else []
        except Exception:
            return []
    return []


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    chat_in, appt_in = argv[0], argv[1]
    date = argv[2] if len(argv) >= 3 else datetime.now().strftime("%Y-%m-%d")

    data = load(OUTPUT_PATH)
    row = next((r for r in data if r.get("date") == date), None)
    if row is None:
        row = {"date": date}
        data.append(row)
    if chat_in != "-":
        row["chat"] = int(chat_in)
    if appt_in != "-":
        row["appt"] = int(appt_in)
    data.sort(key=lambda r: r.get("date", ""))

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"{date} -> オプチャ:{row.get('chat', '据え置き')} / アポ:{row.get('appt', '据え置き')}")
    print(f"書き出し完了 -> {OUTPUT_PATH}（git add/commit/pushして反映してください）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
