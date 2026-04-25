# Building Materials Supply Monitor

中東情勢起因の建材供給制約をモニタリング。
voip-price-monitor と同じ思想で構築 (GitHub Actions + Python + Slack)。

## 概要

- 監視対象: 塩ビ管・FRP/ガラスマット/樹脂・防水材・塗料の主要メーカー & 業界団体
- 検知方式: ページスクレイピング + 差分検出 + キーワード抽出
- 通知方式: Slack Webhook (供給回復シグナル🟢を最優先)
- 実行環境: GitHub Actions (平日 朝7時 / 昼12時 JST)

## クイックスタート

詳細手順は @docs/rules/setup.md を参照。

```bash
# ローカル実行 (Dry run)
pip install -r requirements.txt
python src/monitor.py --dry-run
```

## 主要ファイル

- `src/targets.yaml` - 監視対象メーカーの定義
- `src/monitor.py` - メイン監視スクリプト
- `.github/workflows/monitor.yml` - GitHub Actions
- `data/snapshots/` - 前回スナップショット (自動更新)
- `data/history.json` - 監視履歴

## ルール

- 監視対象の追加・変更ルール: @docs/rules/targets.md
- キーワード設計ルール: @docs/rules/keywords.md
- Slack 通知フォーマット: @docs/rules/slack.md
- 運用/トラブルシューティング: @docs/rules/operations.md

## カテゴリ別の監視優先度

| カテゴリ | 重要度 | 備考 |
|---|---|---|
| pvc | 高 | 塩ビ管(クボタケミックス・積水化学・アロン化成) |
| frp | 高 | ユピカ4190 等の不飽和ポリエステル樹脂・ガラスマット |
| waterproof | 中 | 田島ルーフィング等の防水材 |
| paint | 中 | 塗料・シーリング |
| industry | 参考 | 業界団体・横断まとめ |

## 通知ルール

- 🟢 **供給回復シグナル** (再開・正常化・解除等): 即時通知
- 🔴 **供給制限シグナル** (停止・制限等): 即時通知
- 🟡 **関連キーワード**: 即時通知
- ⚪ **単なるページ更新**: 通知しない (ノイズ抑制)
