# セットアップ手順

## 1. リポジトリ作成

GitHubに新規リポジトリ `building-materials-supply-monitor` を作成。
このディレクトリ一式をpush。

```bash
cd building-materials-supply-monitor
git init
git add .
git commit -m "Initial commit"
git remote add origin git@github.com:sgucci0522/building-materials-supply-monitor.git
git branch -M main
git push -u origin main
```

## 2. Slack Webhook の準備

voip-price-monitor で使っている Webhook URL を流用するか、
新規チャンネル(例: `#建材供給モニター`)用に取得する。

**Slack側**:
1. https://api.slack.com/apps から新規アプリ作成 (もしくは既存アプリを利用)
2. Incoming Webhooks を有効化
3. 通知先チャンネルを選択して Webhook URL を取得

## 3. GitHub Secrets に登録

リポジトリ → Settings → Secrets and variables → Actions → New repository secret

| Name | Value |
|---|---|
| `SLACK_WEBHOOK_URL` | `https://hooks.slack.com/services/...` |

## 4. 初回実行 (スナップショットの作成)

GitHub の Actions タブから手動実行:

- Workflow: `Building Materials Supply Monitor`
- Run workflow → `dry_run: true` で実行

→ スナップショットが `data/snapshots/` に保存される。
   (初回はSlack通知は出ない仕様)

## 5. 本番運用開始

スケジュール実行(平日朝7時/昼12時)で自動運用。
手動で確認したい時は workflow_dispatch を使う。

## 6. 動作確認

`data/snapshots/*.txt` が更新されていることを確認。
2回目以降の実行で差分が検知されれば Slack に通知される。

## トラブルシューティング

### サイト取得に失敗する
- `User-Agent` を変える (monitor.py の `USER_AGENT`)
- timeout を伸ばす
- 該当サイトのrobots.txtを確認

### Slackに通知が来ない
- Webhook URL が正しいか
- `--dry-run` で動作確認
- GitHub Actionsログで `Slack post failed` が出ていないか

### 誤検知が多い
- `keywords` をより具体的に絞る
- `selector` でニュース一覧の領域だけに絞る (例: `.news-list`)
