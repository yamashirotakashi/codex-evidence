# Codex for Open Source Application Packet

Verified on 2026-06-06.

## Official Form Source

- Form: https://openai.com/ja-JP/form/codex-for-oss/
- Official program page linked from the form: https://developers.openai.com/codex-for-oss/
- Program terms are linked from the form, but the terms page body was not retrieved in this session. Do not claim details from the terms beyond the form text.

## Current Official Fields

Required fields observed on the OpenAI form:

- Last name
- First name
- Email address for the ChatGPT account
- GitHub username, with public profile
- GitHub repository URL, with public repository
- Maintainer role: main maintainer or core maintainer
- Why the repository qualifies, 500 characters max
- Interests: Codex Security, API credits, or both
- OpenAI organization ID
- How API credits will be used, 500 characters max

Optional field:

- Anything else to share, 500 characters max

The form says applications are reviewed on a rolling basis.

## Eligibility Reading

Observed official eligibility and review emphasis:

- Active open-source maintainers can apply.
- Projects should be used, broadly adopted, or clearly important to a software ecosystem.
- Review considers repository usage, ecosystem importance, and ongoing maintenance.
- Maintainer work examples include pull request review, issue triage, and release management.

For `codex-evidence`, the strongest honest angle is not current adoption metrics. It is ecosystem importance: helping Codex-using OSS maintainers preserve and recover maintenance context safely across long-running work.

## Submission Blockers

Do not submit until these are resolved:

- Public GitHub repository URL is available.
- GitHub profile and repository are public.
- OpenAI organization ID is known.
- User confirms whether to select main maintainer or core maintainer.
- User approves public push/release as a separate action.

## X Search Notes

Source: Grok X Search through the local Responses gateway on 2026-06-06. The search made 3 X Search calls.

Observed posts:

- Official announcement by OpenAI Developers: https://x.com/OpenAIDevs/status/2029998202934677938
- OpenAI staff thread by Vaibhav Srivastav: https://x.com/reach_vb/status/2029998272945717553
- Recent awareness and application guide posts:
  - https://x.com/0x_beni_/status/2063253087402205543
  - https://x.com/denysdovhan/status/2062881723449241688
  - https://x.com/exploraX_/status/2062807962251304983
  - https://x.com/Nahid_bnb/status/2062855566658257155
  - https://x.com/miftaikyy/status/2062147165623873776
  - https://x.com/very_reserved/status/2062457500570448179

Inference from X search:

- Many posts frame the program as a benefit package. The application should not sound benefit-seeking.
- Recent posts include application guides and at least one approval report, so the program appears active.
- A strong application should be concrete: public repo, maintainer workflow, proof artifact, safety boundary, and API-credit usage.

## Draft Answers

### Repository URL

`<public GitHub repository URL>`

### Maintainer Role

Recommended selection after public repo creation: `Main maintainer`, if the user owns and maintains the new repository.

### Why This Repository Qualifies

Character count: 230.

```text
codex-evidenceは、Codexを使うOSSメンテナーが、ローカルのcurrent-state/handoff/ログ断片をSQLiteに取り込み、検索可能なevidence_cardと再開用context-packへ圧縮するCLI/MCPツールです。レビューやリリース前後の長時間作業で失われる文脈を、read-only MCPと公開hygiene gateで安全に再利用できます。公開MVPはdogfood済みで、個人履歴を読まない実証も含みます。
```

### Interested Items

Recommended:

- API credits
- Codex Security, only if the repository is public and security scanning access is appropriate

### OpenAI Organization ID

`<OpenAI organization ID>`

### API Credit Usage

Character count: 196.

```text
API creditsは、実際のメンテナー作業を想定したdogfoodに使います。長いIssue/PR対応後の再開context生成、テスト失敗・セキュリティ警告の根拠カード化、リリース前チェックリストの生成、MCP経由のread-only検索品質評価を、公開fixtureとCIで再現できる形にします。プロジェクト本体はlocal-firstで、個人データを外部送信しない設計を維持します。
```

### Anything Else

Character count: 176.

```text
この申請は、Codexを単に使うためではなく、Codex利用者自身の保守文脈を安全に残すOSS基盤を作るためのものです。現時点の公開範囲はlocal-first CLI、SQLite/FTS検索、context-pack、read-only MCP、reversible runtime登録に限定し、未実装のPR自動レビューや広域自動化は主張しません。
```

## Evidence To Link After Publication

- `docs/dogfood-proof.md`
- `examples/dogfood-ingest.json`
- `examples/dogfood-context-pack.json`
- `.github/workflows/ci.yml`
- `scripts/check_public_hygiene.py`
- `docs/privacy.md`
- `docs/architecture.md`

## Claim Guardrails

Use these claims:

- local-first evidence ingestion
- SQLite/FTS search
- `evidence_card.v1` context-pack generation
- read-only MCP
- opt-in and reversible runtime registration
- public hygiene gate
- dogfood proof with private Codex sessions/logs excluded

Avoid these claims:

- automated pull request review
- issue triage automation
- broad cross-repository orchestration
- production adoption or usage metrics before they exist
- Codex Security access approval before OpenAI grants it
