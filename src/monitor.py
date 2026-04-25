#!/usr/bin/env python3
"""
建材供給モニター メインスクリプト
voip-price-monitor の構成を踏襲

機能:
1. targets.yaml に基づいてメーカーサイトをスクレイピング
2. 前回スナップショットとの差分を検出
3. 「再開」「正常化」「解除」など供給回復を示すキーワードを優先検知
4. 検知結果を Slack に通知
"""

import os
import sys
import json
import yaml
import hashlib
import logging
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

# ==========================================================
# 設定
# ==========================================================
JST = timezone(timedelta(hours=9))
ROOT_DIR = Path(__file__).parent.parent
DATA_DIR = ROOT_DIR / "data"
SNAPSHOT_DIR = DATA_DIR / "snapshots"
HISTORY_FILE = DATA_DIR / "history.json"
TARGETS_FILE = ROOT_DIR / "src" / "targets.yaml"

# 供給回復を示すキーワード(優先度: 高)
RESUMPTION_KEYWORDS = [
    "再開", "正常化", "解除", "復旧", "通常", "回復",
    "受注再開", "出荷再開", "供給再開", "納期正常",
]

# 供給制限を示すキーワード(優先度: 中)
RESTRICTION_KEYWORDS = [
    "受注停止", "受注制限", "出荷停止", "出荷制限",
    "供給制限", "供給停止", "納期遅延", "新規受注",
]

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36 "
    "BuildingMaterialsMonitor/1.0"
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)


# ==========================================================
# データ取得
# ==========================================================
def fetch_page(url: str, timeout: int = 30) -> Optional[str]:
    """ページを取得。失敗してもエラーで止めず None を返す。"""
    try:
        headers = {"User-Agent": USER_AGENT}
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        # エンコーディング自動判定
        if resp.encoding == "ISO-8859-1":
            resp.encoding = resp.apparent_encoding
        return resp.text
    except Exception as e:
        log.warning("Failed to fetch %s: %s", url, e)
        return None


def extract_text(html: str, selector: str = "body") -> str:
    """HTMLから本文テキストを抽出。スクリプト・スタイルは除外。"""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    if selector and selector != "body":
        elements = soup.select(selector)
        text = "\n".join(el.get_text(separator="\n", strip=True) for el in elements)
    else:
        text = soup.get_text(separator="\n", strip=True)

    # 空行・連続スペースを正規化
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)


# ==========================================================
# スナップショット管理
# ==========================================================
def get_snapshot_path(target_id: str) -> Path:
    return SNAPSHOT_DIR / f"{target_id}.txt"


def load_previous(target_id: str) -> Optional[str]:
    path = get_snapshot_path(target_id)
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def save_snapshot(target_id: str, text: str) -> None:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    get_snapshot_path(target_id).write_text(text, encoding="utf-8")


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


# ==========================================================
# 差分検知
# ==========================================================
def detect_changes(previous: str, current: str, keywords: list) -> dict:
    """
    前回と今回のテキストを比較し、変化と検知キーワードを返す。
    """
    if previous is None:
        return {
            "is_first_run": True,
            "changed": False,
            "added_lines": [],
            "resumption_hits": [],
            "restriction_hits": [],
            "keyword_hits": [],
        }

    prev_lines = set(previous.splitlines())
    curr_lines = set(current.splitlines())
    added = curr_lines - prev_lines

    resumption_hits = []
    restriction_hits = []
    keyword_hits = []

    for line in added:
        for kw in RESUMPTION_KEYWORDS:
            if kw in line:
                resumption_hits.append({"keyword": kw, "line": line})
                break
        for kw in RESTRICTION_KEYWORDS:
            if kw in line:
                restriction_hits.append({"keyword": kw, "line": line})
                break
        for kw in keywords:
            if kw in line:
                keyword_hits.append({"keyword": kw, "line": line})
                break

    return {
        "is_first_run": False,
        "changed": len(added) > 0,
        "added_lines": list(added)[:20],  # 最大20行まで保持
        "added_count": len(added),
        "resumption_hits": resumption_hits,
        "restriction_hits": restriction_hits,
        "keyword_hits": keyword_hits,
    }


# ==========================================================
# Slack通知
# ==========================================================
def post_to_slack(webhook_url: str, blocks: list, fallback_text: str) -> bool:
    payload = {"text": fallback_text, "blocks": blocks}
    try:
        resp = requests.post(webhook_url, json=payload, timeout=15)
        resp.raise_for_status()
        return True
    except Exception as e:
        log.error("Slack post failed: %s", e)
        return False


def build_slack_blocks(target: dict, change: dict, current_hash: str) -> list:
    """Slack Block Kit メッセージを組み立て。"""
    name = target["name"]
    url = target["url"]
    category = target["category"]

    # 優先度判定
    if change["resumption_hits"]:
        priority_emoji = "🟢"
        priority_text = "*供給回復の可能性*"
    elif change["restriction_hits"]:
        priority_emoji = "🔴"
        priority_text = "*供給制限の動き*"
    elif change["keyword_hits"]:
        priority_emoji = "🟡"
        priority_text = "*関連キーワード検知*"
    else:
        priority_emoji = "⚪"
        priority_text = "ページ更新検知"

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{priority_emoji} {name} に更新あり",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*カテゴリ:*\n{category}"},
                {"type": "mrkdwn", "text": f"*判定:*\n{priority_text}"},
            ],
        },
    ]

    # 検知キーワードのハイライト
    if change["resumption_hits"]:
        text = "\n".join(
            f"• `{h['keyword']}` → {h['line'][:120]}"
            for h in change["resumption_hits"][:5]
        )
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*🟢 供給回復シグナル:*\n{text}"},
        })

    if change["restriction_hits"]:
        text = "\n".join(
            f"• `{h['keyword']}` → {h['line'][:120]}"
            for h in change["restriction_hits"][:5]
        )
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*🔴 供給制限シグナル:*\n{text}"},
        })

    if change["keyword_hits"] and not (change["resumption_hits"] or change["restriction_hits"]):
        text = "\n".join(
            f"• `{h['keyword']}` → {h['line'][:120]}"
            for h in change["keyword_hits"][:5]
        )
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*🟡 関連キーワード:*\n{text}"},
        })

    blocks.append({
        "type": "context",
        "elements": [
            {"type": "mrkdwn", "text": f"差分行数: {change['added_count']} | hash: `{current_hash}`"},
            {"type": "mrkdwn", "text": f"<{url}|ページを開く>"},
        ],
    })
    blocks.append({"type": "divider"})

    return blocks


# ==========================================================
# 履歴管理
# ==========================================================
def load_history() -> dict:
    if not HISTORY_FILE.exists():
        return {}
    try:
        return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_history(history: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(
        json.dumps(history, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ==========================================================
# メイン処理
# ==========================================================
def run(dry_run: bool = False) -> int:
    log.info("=== Building Materials Supply Monitor ===")
    log.info("Run time: %s", datetime.now(JST).isoformat())

    # 設定読み込み
    if not TARGETS_FILE.exists():
        log.error("targets.yaml not found: %s", TARGETS_FILE)
        return 1

    config = yaml.safe_load(TARGETS_FILE.read_text(encoding="utf-8"))
    targets = config.get("targets", [])
    log.info("Loaded %d targets", len(targets))

    # Slack Webhook
    webhook = os.environ.get("SLACK_WEBHOOK_URL", "")
    if not webhook and not dry_run:
        log.error("SLACK_WEBHOOK_URL not set")
        return 1

    history = load_history()
    notifications_sent = 0
    errors = 0

    for target in targets:
        tid = target["id"]
        log.info("Checking [%s] %s", tid, target["name"])

        html = fetch_page(target["url"])
        if html is None:
            errors += 1
            continue

        current_text = extract_text(html, target.get("selector", "body"))
        current_hash = text_hash(current_text)

        previous_text = load_previous(tid)
        change = detect_changes(
            previous_text,
            current_text,
            target.get("keywords", []),
        )

        # 履歴更新
        history[tid] = {
            "name": target["name"],
            "last_check": datetime.now(JST).isoformat(),
            "last_hash": current_hash,
            "category": target["category"],
        }

        # 初回はスナップショットだけ保存して通知しない
        if change["is_first_run"]:
            log.info("  → first run, saving snapshot only")
            save_snapshot(tid, current_text)
            continue

        if not change["changed"]:
            log.info("  → no change")
            continue

        log.info("  → CHANGED (added %d lines)", change["added_count"])
        log.info("    resumption: %d, restriction: %d, keyword: %d",
                 len(change["resumption_hits"]),
                 len(change["restriction_hits"]),
                 len(change["keyword_hits"]))

        # 通知判定: 何らかのキーワードヒットがある場合のみ通知
        # (単なるページ更新は通知しない設計。必要なら下記条件を変える)
        should_notify = bool(
            change["resumption_hits"]
            or change["restriction_hits"]
            or change["keyword_hits"]
        )

        if should_notify and not dry_run:
            blocks = build_slack_blocks(target, change, current_hash)
            fallback = f"{target['name']} に更新あり"
            if post_to_slack(webhook, blocks, fallback):
                notifications_sent += 1
                log.info("  → Slack notified")
        elif should_notify and dry_run:
            log.info("  → [DRY RUN] would notify Slack")
            notifications_sent += 1

        # スナップショット更新
        save_snapshot(tid, current_text)

    # 履歴保存
    save_history(history)

    log.info("=== Summary ===")
    log.info("Targets:     %d", len(targets))
    log.info("Errors:      %d", errors)
    log.info("Notified:    %d", notifications_sent)

    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Slack通知を送らずに動作確認")
    args = parser.parse_args()
    sys.exit(run(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
