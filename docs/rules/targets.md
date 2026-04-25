# 監視対象の追加・変更ルール

## 追加方法

`src/targets.yaml` に新規エントリを追加するだけ。

```yaml
- id: meaker_id              # 一意のID (英数+アンダースコア)
  name: メーカー表示名
  category: pvc              # pvc / frp / waterproof / paint / industry
  url: https://example.com/news/
  type: scrape
  selector: "body"           # CSS selector (推奨: ニュース一覧領域に絞る)
  keywords:                  # 監視対象キーワード
    - "受注"
    - "供給"
```

## ベストプラクティス

### URLの選び方

- **トップページよりも「お知らせ」「ニュース」ページ**を優先
- メーカーによってはRSSがある場合もあるので、その場合は将来的にRSS対応化

### selector の絞り込み

- `body` 全体を見ると誤検知が多い (フッターの更新日付等で発火)
- 可能ならニュース一覧の `<ul>` や `<div class="news">` に絞る
- 例: `selector: "main article"` `selector: ".news-list"`

### キーワードの設計

- メーカー固有の製品名 (例: ユピカ4190、エスロン、HIVP) は強力
- 「受注」「供給」「再開」「停止」は基本セット
- 詳細は @docs/rules/keywords.md 参照

## 削除・無効化

監視を一時停止したい場合は、targets.yaml の対象を `#` でコメントアウト。
完全に消すと、過去のスナップショットも整理が必要になる。
