# セッション型系譜 一次資料調査ノート

調査対象ディレクトリ:
- ダウンロード物: `$WT/tmp/research-core-2026-09-20/_raw/`（PDF/HTML原本）、`$WT/tmp/research-core-2026-09-20/_raw/txt/`（テキスト抽出）
- clone/展開したソース: `$WT/tmp/research-core-2026-09-20/_src/`

PDFテキスト抽出には poppler が使えなかったため（`pdftotext`/`pdftoppm` 未インストールで brew install もオーナー権限不足のため失敗）、`$TMPDIR/pdfenv`（venv）に `pypdf` を pip install して抽出した。

---

## 1. Multiparty Session Types — Honda, Yoshida, Carbone, POPL 2008

### 取得
- URL: https://www.doc.ic.ac.uk/~yoshida/multiparty/multiparty.pdf
- 結果: **HTTP 200**、PDFダウンロード成功（12ページ、著者Yoshidaの公式ミラー）
- 保存先: `_raw/mast_popl2008.pdf`、テキスト: `_raw/txt/mast_popl2008.txt`
- 書誌: Honda, Yoshida, Carbone, "Multiparty Asynchronous Session Types", POPL'08, pp.273–284

### 抽象（何を定義しているか）
- **Global type の構文**（Fig.4, p.276相当の直前）: `G ::= p→p′:k⟨U⟩.G′ | p→p′:k{lj:Gj}j∈J | G,G′ | μt.G | t | end`
- **Local type の構文**（Fig.6）: `T ::= k!⟨U⟩;T | k?⟨U⟩;T | k⊕{li:Ti} | k&{li:Ti} | μt.T | t | end`
- **Projection の定義**（Definition 4.1, p.278）: global type Gの参加者pへの射影 G↾p を帰納的に定義。分岐では「全分岐の射影が一致すること」を要求し、一致しなければ undefined。
  > 逐語（p.278）: "When a side condition does not hold the map is undeﬁned."
- **Coherence（整合性）の定義**（Definition 4.2, p.278）: Gがlinearかつ各参加者への射影が全てwell-definedであることをcoherentと呼ぶ。

### 不変量（定理として証明されている性質の逐語引用）
- Abstract（p.273）:
  > "The fundamental properties of the session type discipline such as communication safety, progress and session ﬁdelity are established for general n-party asynchronous interactions."
- **Theorem 4.3**（Coherence, p.279）: "Coherence of G is decidable."
- **Theorem 4.6 / Corollary 4.7**（型付け可能性の決定可能性, p.280）: "it is decidable if there exists Δ such that Γ⊢P⊳Δ or not."
- **Theorem 5.4**（subject congruence and reduction, p.281）: 型付けされたプロセスの簡約が型を保存することを述べる（subject reduction）。
- **Theorem 5.5**（communication safety, p.282）:
  > "Suppose Γ⊢P⊳t̃Δ s.t. Δ is coherent and P has a redex at free s. Then: 1. (linearity) ... 2. (error-freedom) ..."
  （チャネルの線形使用と、受信内容が送信内容と必ず一致することを保証）
- **Corollary 5.6**（session fidelity, p.282）: 型付けプロセスの相互作用が、global typeが規定する遷移 G→G′ と正確に一致することを保証。
- **Theorem 5.12**（progress, p.282）:
  > "Let P be a simple and well-linked program. Then P has the progress property in the sense that P→∗P′ implies either P′≡0 or P′→P′′ for some P′′."
  （デッドロックフリーダムに相当。ただし前提として simple・well-linked・queue-full という条件が必要）

### 実装
本論文自体は理論（型システムと定理の証明）であり実装コードは持たない。実装の強制は §3（Scribble）以降で扱う。

### 異種の実行主体が参加する場合の扱い
論文中に明示的な記述は無い（「型検査されていない外部プロセスが混ざった場合」を直接論じる節は無い）。ただし各定理の前提が全て「Γ⊢P⊳Δ」という型付けされたプロセスに対してのみ成立する形で書かれており（例: Theorem 5.5, 5.12の前提節）、型付けされていない主体が参加した場合にこれらの保証が及ぶという記述は存在しない。これは推論であり、原文の直接の言及ではない。
関連研究として、related work節（p.283, §6.2）に暗号的に保護する試みへの言及がある:
> "Corin et al. (2007) investigates approaches to cryptographically protecting session execution from both external attackers in networks and malicious session principals."
（MAST自身の保証ではなく、別研究[Corin et al. 2007]が「悪意ある参加者」を扱っていることの紹介に留まる）

### 永続ストア
無し。global type / local type / queueはすべてセッション実行中のみ存在する一時的構造で、セッション終了（end）後に残る永続的な「仕事と成果」のストアという概念はない。

---

## 2. Binary Session Types の起点 — Honda, Vasconcelos, Kubo, ESOP 1998

CONCUR'93 (Honda, "Types for Dyadic Interaction") は **Springer本文が取得不可**（下記参照）だったため、ESOP'98の方を一次資料として採用（タスク指示で「いずれか」と許容されている）。

### 取得
- CONCUR'93版: https://link.springer.com/content/pdf/10.1007%2F3-540-57208-2_35.pdf → **HTTP 200 だが実体はSpringerの論文抄録ランディングページ（HTML）**。レスポンスに `<meta name="access" content="No">` が含まれ、本文PDFではなくペイウォール画面。本文取得は失敗（実質403相当）。
- ESOP'98版: https://www.di.fc.ul.pt/~vv/papers/honda.vasconcelos.kubo_language-primitives.pdf（著者Vasconcelos本人の公開ページ） → **HTTP 200**、正常なPDF取得成功
- 保存先: `_raw/hvk_esop98.pdf`、テキスト: `_raw/txt/hvk_esop98.txt`
- 書誌: Honda, Vasconcelos, Kubo, "Language Primitives and Type Discipline for Structured Communication-Based Programming", ESOP'98, LNCS 1381, pp.122–138

### 抽象
- **Definition 5.1 (Types)**（PDF内印字ページ11–12）: 型の文法と、型 σ から co-type（双対型）σ を導く写像を定義。
  > 逐語: "The co-type of a given type denotes the complementary behaviour of the original type."
- co-type の具体的な変換規則（同Definition内）:  `"[S̃]; = #[S̃];` （出力型の双対は同じ継続を持つ入力型）、`&{li:σi} = ⊕{li:σi}`（分岐の双対は選択）、`1 = 1`（終了の双対は終了）。

### 不変量
- **Definition 5.2 (Type algebra)**（compatibility, 同ページ）:
  > "Compatibility means each common channel k is associated with complementary behaviours, thus ensuring the interaction on k to run without errors."
  （2つのtypingが両立可能＝共通チャネルが双対の型を持つ、という条件がエラーなき通信を保証するという記述。安全性はこの型付け規則＋部分簡約定理の系として本文後半で示される。）

### 実装
理論論文でありコード実装は無い。実装側の対応は §4（Rust `session_types` crate）で扱う。

### 異種の実行主体
記述なし（本論文は2者間の対称的通信のみを扱う）。

### 永続ストア
無し。

---

## 3. Scribble

### 3-1. 仕様

#### 取得
- Scribble Language Reference Version 0.3: http://www.doc.ic.ac.uk/~rhu/scribble/langref.html → **HTTP 200**
- 保存: `_raw/scribble_langref.html` / テキスト化: `_raw/txt/scribble_langref.txt`
- 補助資料（査読論文形式のチュートリアル）: Scribble Tutorial PDF（dmi.unict.it ミラー） → **HTTP 200**、`_raw/scribble_tutorial.pdf` / `_raw/txt/scribble_tutorial.txt`

#### 抽象
- Global protocol / Local protocol の定義（langref, "Grammar" 節冒頭）:
  > "A global protocol is an abstract specification of a conversation. It specifies the communication between roles from a global (neutral) perspective."
  > "A local protocol specifies the local behaviour of a role (i.e. from the perspective of that role)."
- Well-formedness の定義（langref §4.1「General Conditions」〜§4.1.2「Local Choice Conditions」）:
  > "A well-formed Scribble global protocol observes the following conditions."
  §4.1.2 の choice の条件（逐語、15語以内に分割）:
  > "A should send the first message."
  > "Any participant B ... receiving a message in block i, should also be receiving a message in all other blocks."
  これはMASTの linearity / coherence 条件のScribble版の規約化であり、後述のコード（RoleEnablingChecker / ExtChoiceConsistencyChecker）が実際に強制している規則と一致する。

#### 不変量（チュートリアル論文より）
- 静的型付け方式との対比で書かれた記述（tutorial, p.10–11）:
  > "if the endpoint program for every role is correct, then the correctness of the whole multiparty system is guaranteed."
  > "Analogously to the static typing scenario, if every endpoint is monitored to be correct, the same communication-safety property is guaranteed [4]."
  （＝全ロールが正しいことが前提。1ロールでも未検証だと保証が及ばないことを含意する書き方）
- 動的検証（モニター）が信頼できないネットワーク参加者から自ロールを守る記述（tutorial, p.11）:
  > "each conversation monitor is able to protect the local endpoint within an untrusted network and vice versa."

### 3-2. 実装（scribble-java）

#### 取得
- リポジトリ: https://github.com/scribble/scribble-java
- `git clone` はサンドボックスの書込み制限（`.git/config` への書込みが `Operation not permitted`）で失敗したため、`https://codeload.github.com/scribble/scribble-java/tar.gz/refs/heads/master` のtarballを取得し展開。
- 使用コミット: **723660a81ee40a094163d9c63a93778cbc97af6e**（master HEAD, 2021-05-21, author Raymond Hu）
- 展開先: `_src/scribble-java-master/`

#### well-formedness 検査（projection可能性・role整合性）を実際に行っているコード

1. **Subject/role enabling 検査**
   file: `scribble-core/src/main/java/org/scribble/core/visit/global/RoleEnablingChecker.java`
   - line 51: `throw new ScribException("Subject not enabled: " + n.subj);`
   - line 79: `throw new ScribException("Source role not enabled: " + n.src);`
   （選択の主体・メッセージの送信元ロールが、まだ何も受信していない＝enabledでない状態で行為主体になろうとした場合に例外を投げる。Scribble言語仕様のconnectedness/well-formedness条件の実装）

2. **外部選択（external choice）の一貫性検査**
   file: `scribble-core/src/main/java/org/scribble/core/visit/global/ExtChoiceConsistencyChecker.java`
   - line 70–74:
     ```java
     throw new ScribException(
         "Inconsistent external choice subjects for " + enabled + ": "
             + all.stream().filter(x -> x.getKey().equals(enabled))
                 .collect(Collectors.toList()));
     ```
   （同じロールが分岐ごとに異なる送信元から「有効化」されると例外。langref §4.1.2 の "receiving a message in block i, should also be receiving a message in all other blocks" に対応）

3. **呼び出し元とパイプライン上の位置**
   file: `scribble-core/src/main/java/org/scribble/core/job/Core.java`
   - line 102: `protected void runGlobalSyntaxWfPasses() throws ScribException` （メソッド名自体が"Wf"=well-formednessパスであることを明示）
   - line 160: `unf.checkRoleEnabling(this);`
   - line 174: `inlined.checkExtChoiceConsistency(this);`
   - line 186: `unf.checkConnectedness(this, !unf.isExplicit());`
   - line 98–107 `runPasses()`: `runSyntaxTransformPasses(); runGlobalSyntaxWfPasses(); runProjectionPasses(); ...` の順で呼ばれる。**well-formedness検査はprojection計算より前**に走る。

4. **モデルレベルの安全性・進行性（deadlock-freedom）検査**
   file: `scribble-core/src/main/java/org/scribble/core/model/global/SModel.java`
   - line 48: `public void validate(Core core) throws ScribException`
   - line 77: `throw new ScribException(msg);`（`getSafetyErrors()` と `getProgressErrors()` のいずれかが非空なら例外。EFSM上でsafety/progressを機械的に検査）
   呼び出し元: `Core.java` line 392–394 `verbosePrintPass("Checking " ... "global model: " ...); this.config.mf.global.SModel(graph).validate(this);`

**検査のタイミング**: いずれもJavaプログラムの実行時ではなく、**Scribbleツール（scribblec等）がプロトコル定義（.scr）を処理する時点**＝「プロトコルのコンパイル時」に相当する静的検査。プログラマのJava/Pythonエンドポイントコードのコンパイル前に行われる。

#### 生成されるendpoint APIが「各状態で許された送受信だけを型として公開する」形になっているか

Scribbleは protocol の各EFSM状態ごとに専用のJavaクラス（state channel API）を生成する。

- file: `scribble-codegen/src/main/java/org/scribble/codegen/java/statechanapi/OutputSockGen.java`
  - line 64: `for (EAction a : curr.getDetActions())  // (Scribble ensures all "a" are input or all are output)`
  - line 68–92: 現在の状態`curr`から到達可能な各アクション`a`ごとに`send`/`request`/`disconnect`/`wrapClient`メソッドを1つずつ生成し、`setNextSocketReturnType`（line 92）で戻り値の型を後続状態のソケット型に設定する。
  → その状態で許可された操作の集合＝生成メソッドの集合、次に呼べる型＝戻り値の型、という対応になっている。

- file: `scribble-codegen/src/main/java/org/scribble/codegen/java/statechanapi/EndSockGen.java`
  - line 43–47:
    ```java
    protected void addMethods()
    {

    }
    ```
    （終了状態のソケットクラスにはメソッドが一切生成されない＝終了後は何も呼べない）

**検査のタイミング**: 生成されたJavaクラスに対する誤用（違う状態のメソッドを呼ぶ等）は、生成コードを使うエンドポイントプログラムを**javacがコンパイルする時点**でコンパイルエラーになる（該当メソッドが型上存在しないため）。実行時チェックではない。

### 異種の実行主体（Scribbleにおける扱い、実測）
tutorialの記述どおり、Scribbleは静的型付けできない言語（Python等）のエンドポイントに対して**実行時モニター**（ローカルFSA）で代替し、「全エンドポイントが型検査/モニター検証されていれば」安全性が成立すると明記している（上記3-1引用）。裏を返せば、モニターも型検査もされていない参加者が交じった場合の保証について、原文はそのケースを保証対象外として扱っている（"if every endpoint is..." という条件文の形でしか安全性を述べていない）。

### 永続ストア
Scribbleのconversation runtime / monitorはセッション実行中のFSA状態とメッセージキューを保持するのみで、セッション終了後に残る仕事・成果の永続ストアは無い。

---

## 4. 他言語のMPST実装 — Rust `rumpsteak`

### 取得
- リポジトリ: https://github.com/zakcutner/rumpsteak
- tarball経由取得（理由は§3と同じ。`git clone`が`.git/config`書込み拒否で失敗）
- 使用コミット: **0ecfa0d31e98b707150b97c3e57b80b77b68c141**（master HEAD, 2024-04-17, author Martin Vassor）
- 展開先: `_src/rumpsteak-master/`

### 型でプロトコル準拠を強制している箇所
file: `src/lib.rs`

- line 109–124: `End<'r, R: Role>` — 終了状態。`Session`実装のみで、それ以外のメソッドは無い。
- line 127–158: `Send<'q, Q, R, L, S>`
  - line 150:
    ```rust
    pub async fn send(self, label: L) -> Result<S, SendError<Q, R>> {
        self.state.role.route().send(Message::upcast(label)).await?;
        Ok(FromState::from_state(self.state))
    }
    ```
    `self`を消費（Rustの所有権移動）して戻り値型`S`（後続状態）を返す。同じ`Send`値に対して`send`を2度呼ぶことはコンパイルできない。
- line 161–190: `Receive<'q, Q, R, L, S>`
  - line 184: `pub async fn receive(self) -> Result<(L, S), ReceiveError> { ... }` （同様に`self`消費、`S`を返す）
- `Choice`/`Select`（line196–235）、`Branch`（line237–278）も同型の状態遷移パターン。

**検査のタイミング**: Rustコンパイラの型検査（コンパイル時）。`Send<...>`型の値に対して`receive()`を呼ぶコードはそもそもそのメソッドが存在しないためコンパイルエラーになる。実行時チェックは無い。

### 異種の実行主体
`rumpsteak`は同一プロセス内の非同期タスク間通信（`Route`トレイトで抽象化されたチャネル）を対象としており、外部の型検査されていないプロセスが同じセッションに混在するケースへの言及はコード上に見当たらない（README等のドキュメント記述に留まる場合は「規約止まり」と扱う）。

### 永続ストア
無し。

---

## 5. Process calculi とチャネル実装

### 5-1. π計算（Milner, Parrow, Walker, "A Calculus of Mobile Processes, I", Information and Computation 100, 1992）

#### 取得
- URL: https://www.cis.upenn.edu/~stevez/cis670/pdfs/pi-calculus.pdf → **HTTP 200**
- 保存: `_raw/milner_picalculus_partI.pdf` / `_raw/txt/milner_picalculus.txt`
- 備考: 元がスキャンOCRのため本文中盤の記号部分は文字化けが多いが、Abstract/Introductionは正確に抽出できた。

#### 名前の受け渡し（mobility）の定義（逐語、Abstract/p.1）
> "communication links are identified by names, and computation is represented purely as the communication of names across links."

および Introduction（p.2）:
> "we shall instead achieve it by allowing references to processes, i.e., links, to be communicated."

（チャネル＝名前とし、通信によって名前＝リンクの参照自体を運ぶ、というのがmobilityの定義）

### 5-2. CSP（Hoare, "Communicating Sequential Processes", CACM 21(8), 1978）

#### 取得結果: **原文取得に失敗**
試行したURLとHTTPコード:
- `https://dl.acm.org/doi/pdf/10.1145/359576.359585` → **HTTP 403**（Cloudflareボットチャレンジ、実体はHTML "Just a moment..."）
- `https://cacm.acm.org/research/communicating-sequential-processes-2/` → **HTTP 403**（同様）
- `https://link.springer.com/...` 系はCSP原論文（CACM）自体はSpringer収録ではないため対象外
- `https://www2.cs.uh.edu/~paris/6360/SUMMARIES/csp.pdf` → HTTP 200だが、これは原文ではなく講義用の**要約（パラフレーズ）**（ファイル名も"SUMMARIES"）であり、末尾に "The author considered allowing..." のような要約者の地の文が混じるため逐語引用の資料として不適格と判断し不採用。
- `https://biblio.cerist.dz/hrbdonf5214/ouvrages/00000000000000592420000000_2.pdf` → 接続失敗（HTTP 000、応答なし）

検索語: `"Communicating sequential processes" hoare 1978 pdf original`, `hoare1978.pdf OR hoare-csp-1978.pdf communicating sequential processes site:edu`, `archive.org "Communications of the ACM" volume 21 1978 hoare communicating sequential processes`

**結論: 1978年CACM原文の入出力コマンド定義・同期規則の逐語引用は未発見（ACM側の有料壁/ボットブロックのため）。**

参考として、Hoareの自著によるCSPの体系だった書籍（2004年版、Oxford大学が自ホスト、著者本人による資料）は取得できた:
- URL: https://www.cs.ox.ac.uk/ucs/hoarebook.pdf → **HTTP 200**（保存: `_raw/hoare_csp_book_2004.pdf`, 260ページ）
- ただしこれは1978年のCACM論文とは異なる版（後年の代数的トレースモデルへの全面改訂版）であり、「1978年原文の入出力コマンド定義」の代替として引用するのは不正確なため、今回は本文の逐語引用には使用していない（存在の記録のみ）。

### 5-3. Go channel — 型は持つがプロトコル準拠は非強制

#### 取得
- URL: https://go.dev/ref/spec → **HTTP 200**
- 保存: `_raw/go_spec.html`

#### 該当箇所（"Channel types"節）
文法定義:
> `ChannelType = ( "chan" | "chan" "<-" | "<-" "chan" ) ElementType .`

説明文（逐語、15語以内に区切って引用）:
> "communicate by sending and receiving values of a specified element type"

**分析**: Go の `ChannelType` 文法は要素型（ElementType）ひとつだけを保持し、送受信の順序や許可される操作列を型として表現する構文が存在しない。occam の `PROTOCOL`（下記）のような「チャネルが運ぶメッセージ列の形」を型に埋め込む仕組みはGoの言語仕様に無い。したがって「型は持つが、通信順序（プロトコル）は強制しない」と言える。これは仕様の記述（不在の確認）であり、コードのfile:lineではない。

### 5-4. 順序まで強制しているチャネル実装

#### (a) Rust `session_types` crate（Munksgaard/session-types）— 型で双対性と使用順序を強制

##### 取得
- リポジトリ: https://github.com/Munksgaard/session-types
- tarball経由取得（理由は§3, §4と同じ）
- 使用コミット: **86d45aec3c1700f189e69ba7fc580c6938c9cc50**（master HEAD, 2023-01-29, author Philip Munksgaard）
- 展開先: `_src/session-types-master/`

##### 双対性（duality）の実装
file: `src/lib.rs`
- line 135–137:
  ```rust
  pub trait HasDual: private::Sealed {
      type Dual;
  }
  ```
- line 143–145: `impl<A, P: HasDual> HasDual for Send<A, P> { type Dual = Recv<A, P::Dual>; }`
- line 147–149: `impl<A, P: HasDual> HasDual for Recv<A, P> { type Dual = Send<A, P::Dual>; }`

##### 順序（プロトコル）の強制
- line 209–218: `impl<E, P, A> Chan<E, Send<A, P>> { pub fn send(self, v: A) -> Chan<E, P> { ... } }`
- line 221–230: `impl<E, P, A> Chan<E, Recv<A, P>> { pub fn recv(self) -> (Chan<E, P>, A) { ... } }`
  → `send`は`Chan<E, Send<A,P>>`型にしか実装されておらず、`recv`は`Chan<E, Recv<A,P>>`型にしか実装されていない。したがって現在の型が要求する操作以外は**そもそもメソッドが存在せずコンパイルできない**。

##### コンパイル時検査であることの直接証拠（compile-failテスト）
file: `tests/compile-fail/send-on-recv.rs`
- line 7: `type Proto = Send<u8, Eps>;`
- line 13–14:
  ```rust
  fn cli(c: Chan<(), <Proto as HasDual>::Dual>) {
      c.send(42).close(); //~ ERROR
  }
  ```
  （`Proto`の双対は`Recv<u8, Eps>`なので、`cli`が受け取るチャネルには`send`メソッドが無く、コンパイルエラーになることを期待するテスト。`//~ ERROR`はcompiletest形式のアノテーション）

**検査のタイミング**: 完全にRustコンパイラの型検査（コンパイル時）。実行時チェックは無い。

#### (b) occam / occam-pi の `PROTOCOL` 宣言 — 仕様の節で順序強制を確認

##### 取得
- occam 3 reference manual (draft, Geoff Barrett, March 31, 1992): https://www.wotug.org/occam/documentation/oc3refman.pdf → **HTTP 200**（203ページ、保存: `_raw/occam3_refman.pdf`）
- occam-pi固有のwiki（Kent大学 PLAS研究室）: https://www.cs.kent.ac.uk/research/groups/plas/wiki/OccamPiReference → **HTTP 403**（アクセス不可）
- "Two-Way Protocols for occam-π" (core.ac.uk): → **HTTP 404**（ミラー切れ）

##### 該当箇所（occam3 refman, §6.4.3 "Sequential protocol", 印字ページ48–49）
逐語引用:
> "A sequential protocol is one or more simple protocols separated by semi-colons."

> "The communication on a channel with a sequential protocol is valid provided the type of each item input or output is compatible with the corresponding component of the protocol."

（`PROTOCOL X IS INT16; [14]BYTE:` のように、1本のチャネルが運ぶメッセージの**型と順序を並べた列**として`PROTOCOL`を宣言し、そのチャネルへの入出力はこの列の順序どおりでなければ不正となる、という規則）

**位置づけ**: occam-pi は occam 2/3 の `PROTOCOL`機構をそのまま継承している（occam-piのドキュメント側で "occam-π contains several significant extensions to occam 2.1"、"Each client-server interface requires two protocols" と説明されており、`PROTOCOL`自体は据え置きの機構）。ただしoccam-pi固有の一次資料ページは403で取得できなかったため、**ここでの逐語引用の出典は occam 3 リファレンスマニュアル（1992年草稿）の該当節であり、コード実装のfile:lineではなく仕様の節どまり**である。
実際のoccamコンパイラのソースコードには当たれていないため、「コンパイル時に検査している」という主張はこのマニュアル自身の記述（"is valid provided..."という静的な適合性条件の言い回し）からの推定であり、コンパイラ実装のfile:line根拠は無い。

### 異種の実行主体（§5共通）
- π計算・CSPの原論文レベルでは「型検査されていない参加者」という概念自体が想定されていない（型システムの導入前の基礎計算のため）。
- Go channel: 型検査自体はコンパイラが行うが、その型は要素型のみなので「順序を守らない相手」を型システムで排除する機構が最初から無い。異種／悪意ある送信者が来ても、値の型が合っていればコンパイラは常に許可する。
- Rust `session_types` crate: 同一プロセス内のスレッド間通信を前提とした型であり、外部プロセスとの通信や型検査されていない相手の混在は扱っていない。
- occam: マニュアル上、`PROTOCOL`宣言に反する入出力は「valid でない」とされるのみで、それを外部プロセス（型検査対象外）が行った場合にどうなるかの記述は見当たらない。

### 永続ストア
上記いずれの系譜（π計算、CSP、Go channel、Rust session_types、occam PROTOCOL）も、仕事や成果を置く永続ストアという概念を持たない。すべてプロセス間・チャネル間の一時的な通信の型付け／規律に閉じている。

---

## 資料取得の可否 一覧（サマリ）

| # | 資料 | 取得可否 | 備考 |
|---|---|---|---|
|1|Honda/Yoshida/Carbone, MAST, POPL2008|**成功 (200)**|doc.ic.ac.uk公式ミラー|
|2|Honda, Types for Dyadic Interaction, CONCUR93|**失敗**（Springerはペイウォールのランディングページ、実質403相当）|代替としてESOP98を採用|
|2'|Honda/Vasconcelos/Kubo, ESOP1998|**成功 (200)**|著者Vasconcelos本人のホームページ|
|3a|Scribble Language Reference v0.3|**成功 (200)**|projection定義自体はこの版には記載なし、well-formednessは有り|
|3b|Scribble Tutorial (査読論文PDF)|**成功 (200)**|projection・動的検証の記述あり|
|3c|scribble-java (GitHub)|**成功**（tarball経由、`git clone`はサンドボックス制約で失敗）|commit 723660a|
|4|rumpsteak (Rust, GitHub)|**成功**（tarball経由）|commit 0ecfa0d|
|5a|Milner/Parrow/Walker, Calculus of Mobile Processes I|**成功 (200)**|OCRスキャン、Abstract/Introは可読|
|5b|Hoare, CSP, CACM 1978|**失敗**（ACM 403 ×2、要約サイトは逐語引用不適格、他1件は接続不可）|未発見として報告|
|5b'|Hoare, CSP book (2004年版、代替参考)|**成功 (200)**|1978年原文とは別版のため引用未使用|
|5c|Go言語仕様 (channel types)|**成功 (200)**|go.dev/ref/spec|
|5d|Rust session_types crate (Munksgaard, GitHub)|**成功**（tarball経由）|commit 86d45ae|
|5e|occam3 reference manual (wotug.org)|**成功 (200)**|203ページ、§6.4.3に該当記述|
|5e'|occam-pi wiki (Kent大学)|**失敗 (403)**|occam-pi固有の一次資料は未取得|
|5e''|Two-Way Protocols for occam-π (core.ac.uk)|**失敗 (404)**|ミラー切れ|
