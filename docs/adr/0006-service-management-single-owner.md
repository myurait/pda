# ADR-0006: サービス管理はsingle-owner原則（ネイティブ=systemd user unit、コンテナ=Docker restart policy）とする

- Status: Accepted
- Date: 2026-07-20
- 対応Decision: D-6
- 関連: [design/07 §1](../design/07-deployment-operations-and-recovery.md)、[design/02 §2.3](../design/02-current-state-and-gaps.md)（欠陥G-1〜G-3）

## Context

2026-07-20時点の記録で、Open WebUIは「systemd user unit＋Dockerのrestart policy」の二重管理に
なっており、user unit側は `Requires=docker.service` がuser manager上not-found・実行ユーザーが
docker socketへアクセス不可のため機能していない（G-1/G-2）。imageは可変タグ `main` で
再構築同一性がない（G-3）。reboot後の全サービスhealthは未実証。

## Decision

1. **single-owner rule**: 各サービスのライフサイクル管理者を1つに固定する
   - Hermes系ネイティブプロセス（gateway/dashboard）: systemd user unit＋linger（現行踏襲）
   - PDA系ネイティブプロセス（ingest timer、将来pda-spined）: systemd user unit
     （transitionで `pda` ユーザーのuser unitへ）
   - コンテナ（Open WebUI、Firecrawl）: Docker daemonの `restart: unless-stopped` のみ。
     systemdでラップしない
2. 壊れたopenwebui user unitは削除する（M0）
3. ユーザーをdocker groupへ追加しない（root相当権限のため）。コンテナ操作は `sudo docker compose`
4. composeファイル・unitテンプレートはsecretレスでリポジトリ `infra/` にgit管理し、
   imageは **digest固定** とする
5. rootless Docker / Podman（Quadlet）への移行は現時点で行わない

## Alternatives considered

### systemd system unitでcomposeをラップ — 棄却

- Docker restart policyと管理者が二重になる（現行欠陥の再生産）。起動順序の要件は
  docker.service自体のboot起動で満たせる

### rootless Dockerへ移行 — 保留（棄却ではない）

- 利点: daemon権限の縮小
- 保留理由: Firecrawlスタック（FoundationDB等7コンテナ級）のrootless動作が未検証で、
  移行検証コストが現時点の便益を上回る。**ホスト再構築時（OQ-8のLUKS化と同時）に再評価する**

### Podman Quadlet — 保留

- systemd統合として筋は良いが、compose資産の書き換えと検証コストが先行する。再構築時に再評価

### ユーザーをdocker groupへ追加してuser unitを直す — 棄却

- docker groupはroot相当権限であり、runtime（Hermes等）が同一ユーザーで動く現構成では
  T-8（compromised runtime）の権限昇格経路になる

## Consequences

- (+) 「このサービスは誰が起動・再起動するか」が一意になり、reboot drill（T-REBOOT-HEALTH）が
  検証可能になる
- (+) digest固定＋IaC化でfresh-host復元（[design/07 §6](../design/07-deployment-operations-and-recovery.md)）が
  再現可能になる
- (−) コンテナの起動失敗はsystemdの `OnFailure` 通知に乗らないため、doctor／監視スクリプト側で
  container healthを見る必要がある（[design/07 §6.4](../design/07-deployment-operations-and-recovery.md)）
- (−) `sudo docker compose` 運用は操作ログが分散しがち → 運用操作もaudit記録へ残す規約で補う

## Revisit conditions

1. ホスト再構築イベント（rootless / Quadletの再評価、LUKS化と同時）
2. コンテナ数・更新頻度が増え、digest更新の手動運用が負荷閾値（A-05）を超えたとき
3. Docker Engine自体の重大な脆弱性・ライセンス変化
