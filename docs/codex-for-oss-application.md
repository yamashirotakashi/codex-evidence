# Codex for Open Source 申請パケット

確認日: 2026-06-06

## 公式フォーム情報

- 申請フォーム: https://openai.com/ja-JP/form/codex-for-oss/
- フォームからリンクされている公式プログラムページ: https://developers.openai.com/codex-for-oss/
- フォーム上には Program Terms へのリンクがある。ただし、このセッションでは規約本文までは取得できていないため、規約本文の詳細は断定しない。

## 現在確認できた公式フォーム項目

OpenAI フォーム上で確認した必須項目:

- 姓
- 名
- ChatGPT アカウントのメールアドレス
- GitHub ユーザー名。公開プロフィールであること
- GitHub リポジトリ URL。公開リポジトリであること
- メンテナー種別: メインメンテナーまたはコアメンテナー
- リポジトリが対象にふさわしい理由。500文字以内
- 希望項目: Codex Security、API credits、または両方
- OpenAI Organization ID
- API credits の用途。500文字以内

任意項目:

- 補足事項。500文字以内

フォーム上では、申請は rolling basis、つまり随時審査と説明されている。

## 適格性の読み取り

公式フォーム上で確認した審査観点:

- active open-source maintainer、つまり継続的に OSS を保守している人が対象。
- プロジェクトは、実際に使われている、広く採用されている、またはソフトウェア ecosystem にとって重要であることが期待されている。
- 審査では、利用状況、ecosystem 上の重要性、継続的なメンテナンス状況が見られる。
- メンテナー作業の例として、pull request review、issue triage、release management が挙げられている。

`codex-evidence` の正直で強い訴求点は、現時点の adoption metrics ではない。Codex を使う OSS メンテナーが、長時間作業で失われがちな保守文脈を安全に保持・検索・再利用できるようにする ecosystem importance で押す。

## 申請前ブロッカー

以下が揃うまでフォーム送信はしない。

- GitHub リポジトリ URL: `https://github.com/yamashirotakashi/codex-evidence`
- GitHub プロフィールと対象リポジトリが public であること
- OpenAI Organization ID: チャットで受領済み。公開リポジトリに入る文書には完全な値を記載しない
- メンテナー種別: メインメンテナー
- 希望項目: API credits
- public push: 承認済み。ただし 2026-06-06 時点ではローカル Git 認証が `irdtechbook` として扱われ、`yamashirotakashi/codex-evidence` への権限不足で push 未完了
- release / form submission: 追加の明示承認待ち

## X 検索メモ

取得方法: 2026-06-06 に local Responses gateway 経由の Grok X Search を使用。X Search call は 3 回。

確認した投稿:

- OpenAI Developers による公式告知: https://x.com/OpenAIDevs/status/2029998202934677938
- OpenAI staff の Vaibhav Srivastav による紹介 thread: https://x.com/reach_vb/status/2029998272945717553
- 最近の周知・申請ガイド投稿:
  - https://x.com/0x_beni_/status/2063253087402205543
  - https://x.com/denysdovhan/status/2062881723449241688
  - https://x.com/exploraX_/status/2062807962251304983
  - https://x.com/Nahid_bnb/status/2062855566658257155
  - https://x.com/miftaikyy/status/2062147165623873776
  - https://x.com/very_reserved/status/2062457500570448179

X 検索からの推論:

- 多くの投稿は benefit package として紹介している。申請文は「得をしたい」方向ではなく、具体的なメンテナー作業価値を前面に出す。
- 最近の投稿には申請ガイドや承認報告があり、プログラムは継続中と見てよい。
- 強い申請文に必要なのは、公開リポジトリ、メンテナー作業、dogfood proof、安全境界、API credits の具体的用途。

## フォーム入力案

### GitHub リポジトリ URL

```text
https://github.com/yamashirotakashi/codex-evidence
```

### メンテナー種別

```text
メインメンテナー
```

### このリポジトリが対象にふさわしい理由

文字数: 249

```text
codex-evidenceは、個人のローカルなセッション運用から、Codexとの共同作業でOSSメンテナー向けに抽出・再設計したlocal-first evidence toolkitです。current-state/handoff/ログ断片をSQLiteに取り込み、検索可能なevidence_cardと再開用context-packへ圧縮します。ほぼ全工程をCodex支援で仕様化・実装・検証し、公開hygiene gateとdogfood proofで個人履歴を読まない境界も確認済みです。
```

### 希望項目

```text
API credits
```

Codex Security は今回は選択しない。必要になった場合だけ、公開後の security scanning 目的として別途検討する。

### OpenAI Organization ID

送信時にフォームへ入力する。公開リポジトリに含まれる文書には完全な値を記載しない。

### API credits の用途

文字数: 196

```text
API creditsは、実際のメンテナー作業を想定したdogfoodに使います。長いIssue/PR対応後の再開context生成、テスト失敗・セキュリティ警告の根拠カード化、リリース前チェックリストの生成、MCP経由のread-only検索品質評価を、公開fixtureとCIで再現できる形にします。プロジェクト本体はlocal-firstで、個人データを外部送信しない設計を維持します。
```

### 補足事項

文字数: 146

```text
この申請は、Codexを単に使うためではなく、Codex利用者自身の保守文脈を安全に残すOSS基盤を作るためのものです。私的な作業メモから公共性のあるプロダクトを抽出し、仕様化、実装、公開前衛生検査までCodexと反復した実証でもあります。未実装のPR自動レビューや広域自動化は主張しません。
```

## 公開後にフォームから参照できる証跡

- `docs/dogfood-proof.md`
- `examples/dogfood-ingest.json`
- `examples/dogfood-context-pack.json`
- `.github/workflows/ci.yml`
- `scripts/check_public_hygiene.py`
- `docs/privacy.md`
- `docs/architecture.md`
- `docs/release-checklist-v0.1.0.md`

## 主張してよいこと

- local-first evidence ingestion
- SQLite/FTS search
- `evidence_card.v1` context-pack generation
- read-only MCP
- opt-in and reversible runtime registration
- public hygiene gate
- 個人の Codex sessions/logs を除外した dogfood proof

## 主張しないこと

- automated pull request review
- issue triage automation
- broad cross-repository orchestration
- 実績が出る前の production adoption や usage metrics
- OpenAI に承認される前の Codex Security access
