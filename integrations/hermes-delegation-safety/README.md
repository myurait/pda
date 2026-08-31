# Hermes delegation safety patch series

このディレクトリは、`delegate_task`のper-turn spawn上限に達した親agentが誤ってhaltせず、既存child結果・別tool・正確なblocker報告へ同じturn内で切り替えられるようにするHermes用patchとfocused回帰資産です。併せて、structured-output retryもdelegated-child context内で実行し、成功・失敗・例外後に親のKanban所有権へ戻ることを固定します。

適用基点はHermes commit `5112f51749ac744923a702900730149dfc8634da`です。対象ファイルと基点SHA-256、patch SHA-256は`manifest.json`を正本とします。現在のlive Hermes checkoutは未変更です。

## 影響

patchが変更するのは次の2ファイルだけです。

- `agent/tool_guardrails.py`: capを越えるspawn要求を実行前の`reject`として返し、親loopをhaltさせません。batch全体が上限を越える場合もchildを1件も開始せず、完了済みspawn数、上限、今回要求数、発火点をstructured metadataへ残します。
- `tools/delegate_tool.py`: 初回child turnとschema retry turnを同じ`delegated_child_context` helper経由にし、ContextVarを各経路で復元します。

cap値、control action、web-search cap、repeated-failure hard stopは変更しません。`loop_subagent_cap`以外のguardrail halt挙動も維持します。

## 検証

PDA repository rootから次を実行します。

```bash
pytest -q integrations/hermes-delegation-safety/tests
python -m compileall -q integrations/hermes-delegation-safety
```

focused testは同一probeを2回使います。未変更の基点では、cap境界、親loop継続、child retry context＋親Kanban mutationの3シナリオがすべて失敗することを確認します。次に基点2ファイルだけの一時overlayへpatchを適用し、同じ3シナリオが通ること、patch外ファイルを変更しないこと、rendered patch・manifest・source hashが一致することを確認します。一時overlayとscratchはテスト終了時に削除します。

## 適用

適用は、task・head・changed-files・対象・ordered stepsが一致するdigest-boundなオーナー承認後だけ行います。承認時は次の順序を変えません。

1. PDA task branchを承認済みheadのままPDA mainへ統合する。
2. live Hermes HEADと対象2ファイルのhashが`manifest.json`の基点と一致することを確認する。不一致なら適用せず、新しい基点でpatchを再生成して再承認を得る。
3. live checkoutでpatchの事前checkを行い、同じartifactを適用する。
4. focused probeをpatch済みlive sourceへ実行する。
5. Hermes gatewayを再起動し、healthを確認する。

patchは標準の`git apply --check`と`git apply`で扱えるunified mail patchです。承認前のlive適用、gateway再起動、main統合は行いません。

## rollback

runtime rollbackは承認済みpatchをlive checkoutで`git apply --reverse --check`してから`git apply --reverse`し、Hermes gatewayを再起動してhealthを確認します。PDA側の管理artifactは監査・再適用判断のため保持します。逆適用checkが失敗した場合は別修正を加えず停止し、driftとして再判断します。

残存リスクは、patchが指定Hermes基点へ厳密に拘束されるためupstream更新後はそのまま適用できないことと、focused probeがsynthetic agent loopを検証する一方、実gatewayの再起動後healthは最終適用工程で別途確認する必要があることです。
