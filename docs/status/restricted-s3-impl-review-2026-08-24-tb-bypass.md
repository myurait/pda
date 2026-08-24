# 束縛変更の反証レビュー（レンズ: tb-bypass、2026-08-24）

- 対象コミット: `bc32ca1`（`6d49aa0..HEAD`）。
- レンズ: ホスト供給の task アンカー（`HERMES_KANBAN_TASK`）優先化により、実行主体が束縛を偽装して上限を広げられないか。env 不在経路の後方互換が実際に成立するか。closeout（S1 live）挙動が変わっていないか。
- 再現環境: `./tmp/probe-envbind/`（`probe.py` / `probe2.py` / `probe3.py`、比較用の変更前ツリーは `before/`）。実行は `./tmp/venv-scope/bin/python`。git fixture は `tempfile.mkdtemp` 上の合成リポジトリ（ハーネスがワークツリー内での `.git` 作成を禁じるため）。リポジトリ本体・実機状態には触れていない。
- **本書は取扱制限。迂回手法の具体形を含む。** 親セッションへの戻り値には ID と抽象名のみを返す。

確証と推測を明示的に分ける。「確証」はこのラウンドで実際にコードを走らせて観測した事実、「推測」は観測していない前提を含む経路。

---

## TB-01（major）アンカーが契約を引けないとき、payload 側の契約が無言で消える

### 確証部分

`resolve_task_binding` はアンカーを**無条件**に優先し、アンカーが何も引けなかった場合に payload 識別子へ戻らない。結果として、payload が seed 済みカードを名指しているターンで、アンカーに別値が入っているだけで強制が解除される。

`./tmp/probe-envbind/probe2.py`（payload = seed 済みカード `t_real0001`、アンカー = seed の無い `t_stale9999`）:

```
  before  anchor ABSENT   state=locked           origin='assignment'  out-of-scope write: denied (write-scope)
  before  anchor STALE    state=locked           origin='assignment'  out-of-scope write: denied (write-scope)
  after   anchor ABSENT   state=locked           origin='assignment'  out-of-scope write: denied (write-scope)
  after   anchor STALE    state=audit            origin=''            out-of-scope write: ALLOWED (not-enforced)
```

変更前はアンカーの値が何であれ `locked` を維持し、write scope 外の書込を拒否した。変更後、アンカーが seed を引けない値であるときだけ `state=audit` / `contract_origin=''` になり、**write scope 外の書込が `not-enforced` として許可される**。

機序は `start_turn` の照会が単一の解決値しか受け取らないことにある。`get_contract_seed(task_id, session_id=...)` は task と session の二段で探すが、渡される task はアンカーで置き換えられた値であり、payload の task 識別子はこの時点で失われている。`record_contract_seed` は `session_id=""` 既定で記録されるため（`operations/improvement/scope_seed.py`）、session 側フォールバックも当たらない。

### 設計との衝突

設計ノート §「host 識別子の解決順序」第3項は次を明言している。

- 「実行主体はこれを書き換えて別カードの契約を引き当てることはできない — 書き換えれば**契約が見つからないか**別カードの上限が当たるだけで、いずれも自分の上限を広げる方向には働かない。」
- 「ホスト側の供給が失われた場合の挙動は fail-closed のままである: 結合できないターンで seed 済みカードの変異は『契約はあるが呼び出しを束縛できない』として拒否される（**監査のみへは落ちない**）。」

前者の「契約が見つからない」枝は安全側ではない。契約が見つからないことは、payload が供給していた `locked` 上限より**厳密に広い** `not-enforced` へ落ちることを意味する。後者の主張は「供給が失われた（アンカー不在）」場合には成立するが、「供給が誤っている（アンカーが別値）」場合には成立せず、実測では監査のみへ落ちる。設計文書はこの 2 条件を区別していない。

fail-closed が成立するのは `admit_without_turn` 経路（ターンが立たない場合）だけである。本件はターンが立つ経路であり、そこには同等の二重照会が無い。

### 新規テストが本件を覆っていない理由

`test_host_task_binding.py::test_the_anchor_wins_over_a_payload_task_that_carries_its_own_seed` は**両方の識別子が契約を引ける**場合を構成している（コメント: "Both identifiers resolve to a real contract, so the precedence is observable rather than inferred from one lookup failing."）。優先順位の観測性を確保する意図は妥当だが、その結果として「アンカーが引けず payload が引ける」組み合わせが集合から抜けている。抜けた組み合わせが唯一の fail-open 方向である。

### 到達条件と現時点の live 露出（推測を含む）

- 前提は「payload の task 識別子が seed 済みカードを名指し、かつアンカーが別値」。実機で計測された dispatcher 形状（payload の両欄が会話 ID）ではこの前提が成立しないため、**現行 dispatcher レーンの live 露出は無い**（確証: 実機計測結果と probe P2）。
- 露出面は、設計文書自身が正規のフォールバックとして残した「dispatcher が起動しない経路」である。当該経路が実カード ID を payload に載せる実装であり、かつプロセス環境にアンカーが残留している場合に発火する。アンカー残留は dispatcher が worker へ export する値の継承・ラッパ・プロファイル設定などで起こり得る（推測: 具体的な残留経路は本ラウンドで実測していない）。
- ホスト配線が改善して payload にもカード ID が載るようになった時点で、本件は live 化する。すなわち現状は潜在 fail-open である。

### 塞ぐ方向（抽象）

解決を単一値へ畳む前に契約照会を行うか、照会をアンカーと payload の両識別子に対して行う。あるいは両者が食い違い、かつアンカー側が契約を引けない場合を「束縛不能」として `admit_without_turn` と同じ fail-closed 経路へ落とす。いずれもアンカー優先そのものは維持できる。帰属は司令塔判断。

---

## TB-02（minor）env 不在経路は「完全な後方互換」ではない

### 確証部分

新しい解決関数が payload 側に `.strip()` を導入したため、空白のみの task 識別子で記録内容と turn key が変わる。`./tmp/probe-envbind/probe.py` P8（payload task_id = `'   '`、アンカー不在）:

```
    after: rows=[{'turn_id': '20260824_122848_9e31b9:8db10ad9dec68b34', 'task_id': ''}]
    before: rows=[{'turn_id': '   :8db10ad9dec68b34', 'task_id': '   '}]
```

turn key の scope 半分が task 由来から session 由来へ移り、`turns.task_id` の保存値も変わる。

### 評価

方向は改善である。変更前は `get_contract_seed` / `scope_key` が内部で strip する一方 `start_turn` は未 strip の値を保存しており、同一識別子が照会と保存で別物になり得た。変更後は一貫する。したがって安全性への影響は無く、欠陥は修正報告の「env 不在経路の完全な後方互換」という主張の正確性に限る。実運用上、空白のみの識別子をホストが送る経路は観測していない（推測）。

---

## TB-03（minor）カード単位の turn fallback がプロセス境界を越えて共有される

### 確証部分

`resolve_turn_id` は task 識別子を session より先に試す。アンカー優先化により、同一カードの全 worker が同じ task 識別子を共有するようになったため、後続セッションの呼び出しが先行セッションのターンへ解決され得る。`./tmp/probe-envbind/probe.py` P6:

```
[PASS] P6 spoofer's later call now resolves to the NEWEST card turn, not its own  -- resolved=t_victim0001 spoof_turn=t_victim0001
```

先に立っていたセッションの後続呼び出しが、後から立った別プロセスのターンへ解決された。

### 変更前との差

変更前の dispatcher worker は task 識別子が自セッション ID であったため、同一カードの worker 同士でも fallback キーが衝突しなかった。変更後は衝突する。`_FALLBACK_TURN_ORDER` が「開いている強制ターン優先 → 新しい順」であるため、通常は自分の新しいターンが勝ち、逐次ディスパッチ規律の下では実害が出にくい。露出するのは、先行ターンが開いたまま残り（異常終了で `on_session_end` 未発火）、後続 worker の `pre_llm_call` 登録が成立しなかった場合（`WorktreeProbeError` 経路は意図的にターンを立てずに戻る）である。

### 評価

scope 面は fail-closed（同一カードの契約なので admit されるパス集合は同じ）。影響はターン単位予算の相互消費と監査帰属の混線に限る。`expansion_permits` は `turn_id` キーであり、カード横断の permit 消費は起きない（確証: スキーマと probe P6）。

---

## TB-04（minor）seed 済みカードでは closeout クラスが抑止される

### 確証部分

`./tmp/probe-envbind/probe.py` P9（closeout 分類メッセージ、アンカー供給あり）:

```
    [card has NO seed] class=repository-closeout state=discovering task_id=t_dec48aee push=lock-required/False
    [card HAS a seed]  class=artifact-change      state=locked      task_id=t_dec48aee push=git-subcommand/False
```

アンカーがカードを指し、そのカードが seed を持つとき、closeout 分類のメッセージは `locked` な artifact-change になる。push はいずれの形でも拒否される。

### 評価

`start_turn` の「契約記録は分類器より優越する」という設計方針の文字どおりの帰結であり、意図された挙動である。ただし変更前の dispatcher レーンでは seed が結合しなかったため closeout が保たれていた。したがってこれは dispatcher レーンにおける live 挙動の変化であり、修正報告の「env 優先が closeout 挙動を変えない」という主張の射程は「アンカー不在時、または当該カードが未 seed のとき」に限られる。方向は fail-closed（push が使えなくなる）であり、安全性の後退は無い。closeout を要する作業が seed 済みカードへ割り当てられた場合に詰まる可能性がある点のみ運用上の含意がある。

---

## 偽装面について確証できた否定的結果（欠陥ではない）

以下は「攻撃面が開いていない」ことの確証であり、記録目的で残す。

- **実行主体は自プロセスの env を書けない。** アンカーは `os.environ` をフック時に読むが、worker のツール語彙にインプロセスでコードを評価する面が無い。子プロセスの export は親へ届かない（probe P7: `host_task_binding() == ''`）。
- **locked ターンは env に触れ得る面をすべて閉じている。** `./tmp/probe-envbind/probe3.py`:

```
-- tool admission in a LOCKED artifact-change turn --
   terminal+env field     allowed=False terminal-argument-unlisted
   cronjob                allowed=False expansion-required
   skill_manage           allowed=False expansion-required
   delegate_task          allowed=False expansion-required
   memory                 allowed=False expansion-required
```

- **seed は worker から作れない。** `scope_gate` 制御ツールの action は lock / review / complete のみで、`record_contract_seed` は露出していない。
- **監査レーンでの束縛偽装は制限方向にしか働かない。** 未強制ターンの既定は `not-enforced`（全許可）であるため、他カードの seed へ束縛すると `locked` かつ有界になる（probe P5: seed 外書込が `write-scope` で拒否、seed 内のみ許可）。「seed は上限であり束縛は制限方向のみ」は**この経路については成立する**。成立しないのは TB-01 の経路（払い出し済み契約が消える方向）のみである。
- **他カードへの実害は監査帰属に留まる。** 偽装束縛は被害カードの `consumed_turn_id` と `contract_scope_uses` に自ターンを刻む（probe P6）が、`consumed_at` にはテスト以外の読み手が無く、正規 worker は後から同じカードで `locked` を取得できる（seed の DoS は無い）。

ただし未強制ターンでは `cronjob` / `skill_manage` / `memory` / `delegate_task` がすべて許可される（probe3 後半）。これは未強制レーンの既存性質であり本変更が作ったものではないが、アンカーが契約を選ぶようになった結果、その既存能力に「後続プロセスのアンカーを選ぶ」という新しい帰結が付いた点は記録しておく。

---

## テスト・空回り検出の独立確認

- スイート: `./tmp/venv-scope/bin/python -m pytest integrations/hermes-scope-gate/tests -q --ignore=integrations/hermes-scope-gate/tests/test_hermes_integration.py` → **614 passed**（修正報告と一致）。
- 空回り検出の再現: `resolve_task_binding` のアンカー優先を payload 優先へ入れ替えると **8 failed / 606 passed**。修正報告の「16 件中 8 件が落ちる」と一致し、新規テストが load-bearing であることを確認した。検証後にソースは復元済み（`git status` clean）。
- 逆転の実測: アンカー供給時にカード ID 束縛と `locked` 生成が成立（probe P1、`task_id=t_dec48aee` / `state=locked` / `origin=assignment`、scope 内書込 allow・scope 外 deny）。アンカー不在＋実機 payload 形状では未強制のまま（probe P2、変更前後で一致）であり、修正が実際に結合欠陥を塞いでいることを確認した。
- closeout の後方互換: アンカー不在で変更前後が一致（probe P4、`discovering` / `inventory-status` allow / `lock-required` deny）。
