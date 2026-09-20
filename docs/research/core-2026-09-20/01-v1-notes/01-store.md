# 共有ストアの系譜 一次資料調査ノート

作業ディレクトリ: `$WT/tmp/research-core-2026-09-20/`
ローカル資料置き場: `$WT/tmp/research-core-2026-09-20/_src/`

---

## 1. Blackboard アーキテクチャ / Hearsay-II

### 取得状況
- URL: https://mas.cs.umass.edu/Documents/Erman_Hearsay80.pdf
- `curl` 結果: **HTTP 200**
- ローカル保存: `_src/hearsay80.pdf`（3,831,736 bytes, 41ページ, ACM Computing Surveys Vol.12 No.2, June 1980, pp.213-253 の完全版）
- テキスト抽出: `_src/hearsay80.txt`（pypdf でページ番号付き抽出。poppler-utils が環境に無かったため、venv に `pypdf` を pip install して抽出）

### 抽象（何を形式的に定義しているか）
- p.218（`===PAGE 6===`）"Hearsay-II Problem-Solving Model" 節: 独立したプログラム群＝knowledge sources (KSs) が condition-action pair として動作し、共有データベース「blackboard」経由で通信する構図を定義。
- p.219（`===PAGE 6-7===` 境界）: blackboard は level（phrase, word-sequence, word, syllable, segment, parameter 等）に分割され、各 hypothesis はいずれか 1 レベルに置かれる。

### 逐語引用
1. "KSs communicate through a global database called the blackboard." — p.218
2. "it represents intermediate states of problem-solving activity, and it communicates messages" — p.218-219
3. "The blackboard is subdivided into a set of information levels" — p.219
4. "hypotheses at each level aggregate or abstract elements at the adjacent lower level" — p.219
5. 制御割り当て: "a heuristic scheduler which calculates a priority for each action" — p.221（"executes, at each time, the waiting action with the highest priority" と続く）
6. 不変量の明示的否定: "there is no guarantee at any point that a better interpretation cannot be found" — p.236（HWIM の admissible strategy と対比。Hearsay-II 自身のスケジューリング戦略には形式的な保証が無いと論文自身が明言している）
7. 「別の実行主体に注入可能」に相当する記述: "one KS can use data created by a previous KS execution" — p.235-236（原文全体: 「あるKSはそれを作ったKSが誰かを知らずに、また使う側のKSもどのKSがデータを作れるかを知らずに、blackboard上のデータを使える」）

### 不変量
- 探索網羅性・最適性についての形式的保証は **論文自身が明示的に否定**している（引用6）。scheduler は heuristic であり admissible ではない。
- blackboard の同時書き込みに関する排他制御（mutual exclusion）についての記述は本文中に見つからなかった。`concurrent`, `simultaneous`, `atomic`, `lock`, `mutual exclu`, `race` を全文検索したが、"blackboard" の並行アクセスに関する技術的な排他制御の議論は無し（`grep` 結果: 該当行なし）。これは 1980 年当時の Hearsay-II が「1 サイクルにつき 1 activity のみを scheduler が選んで実行する」逐次実行モデルだったため（p.221-222, Figure 4 の説明: "At the start of each cycle, the scheduler...calculates a priority for each activity...The highest priority activity is removed from the queues and executed."）、そもそも並行書き込みの競合が構造的に発生しない。つまり「複数の実行主体が同時に blackboard を取り合う」状況を保証で解決しているのではなく、**単一スケジューラによる逐次実行で回避している**。

### 実装
**規約（論文記述）止まり。** Hearsay-II の実際のソースコードは本調査では確認できず、原論文（ACM Computing Surveys 1980）はコードを掲載していない自然言語＋図による記述のみ。file:line で不変量を強制している実装箇所は提示不能。

### メッセージの分類
- Hypothesis は「level（phrase/word-sequence/word/syllable/segment/parameter等）」+ 「そのレベルに応じたラベル集合から選ばれるラベル」+ 「時間座標」+ 「credibility rating」を持つ、と自然言語で規定されている（p.219）。
- これは有限種別（レベル）に基づく緩やかな階層スキーマだが、**コードでの強制は確認できない**（原論文に実装コード無し）。

### 別の実行主体に注入可能か
- 該当する（引用7）。あるKSの出力（blackboard上のhypothesis）は、変換なしに別のKSの入力条件（condition）にそのままマッチしうる。ただし対象は「同一ホスト内・同一プロセスの1メモリ空間上のデータ構造」であり、シリアライズ／プロセス間転送を伴う「メッセージ」ではない。

---

## 2. Linda / tuple space（Gelernter, "Generative Communication in Linda," ACM TOPLAS 7(1), 1985）

### 取得状況
- **ACM Digital Library** (https://dl.acm.org/doi/pdf/10.1145/2363.2433): **HTTP 403**（Cloudflare のボット対策ページが返る。`_src/linda_acm.pdf` に保存したファイルは実体が Cloudflare のチャレンジページの HTML であり、論文本体ではない）
- **CiteSeerX** (https://citeseerx.ist.psu.edu/document?...): 接続不可。verbose curl でプロキシから "CONNECT tunnel failed, response 502" — CiteSeerX 自体がサーバ側で応答不能（既知の長期障害と一致）。
- 代替一次資料として使用: https://www.cs.unc.edu/~stotts/COMP590-059-f21/slides/lindaGenerative.pdf — **HTTP 200**。中身を確認したところ、これは講義スライドではなく **ACM TOPLAS 掲載論文そのもののスキャン/複製**（1ページ目のタイトル・要旨・ACM分類コードが原論文と完全一致、33ページ、各ページ下部に "ACM Transactions on Programming Languages and Systems, Vol. 7, No. 1, January 1985." のフッタが入っている）。ファイル名パスに `slides/` とあるが内容は原論文本文であることを確認済み。
- ローカル保存: `_src/linda_unc.pdf`（2,463,852 bytes）、テキスト抽出 `_src/linda.txt`

### 抽象
- Part I "Generative Communication" 冒頭（p.82, PDF内 `===PAGE 3===`）、2.1.2節 "Definitions: out( ), in( ), and read( )" で `out` / `in` / `read` の3プリミティブを定義。
- **注記（事実確認）**: 1985年の原論文が定義するプリミティブは **out / in / read の3つのみ**である。全文中に eval という語がプリミティブとして定義されている箇所は見つからなかった（`grep -n "eval" linda.txt` を実行しても該当なし）。eval は後年の C-Linda / "Linda in Context" (Carriero & Gelernter, 1989) 以降で追加された active-tuple 生成プリミティブであり、今回の完了条件で挙げられた「in / out / rd / eval」という4プリミティブ構成は1985年原論文の構成と異なる。また原論文の第3プリミティブの名称は `rd` ではなく `read` である。

### 逐語引用
1. `out` / `in` の役割: "out( ) adds a tuple to TS, in( ) withdraws one" — p.82
2. マッチング規則: "if some type-consonant tuple whose first component is 'N' exists in TS" — p.83（`in` 実行時、名前と型が一致するタプルが1つ見つかれば取り出す、という定義文の一部）
3. **`in` の原子性（核心の逐語引用）**: "The definitions require that tuples be inserted into and withdrawn from TS atomically." — p.83-84
4. 直後の文（競合時に片方だけが勝つ）: "one gets it and the other does not; they cannot split it" — p.84（原文全体: "If two in( ) statements contend for one tuple, one gets it and the other does not; they cannot split it."）
5. 分散共有変数の原子性: "The TS-operator definitions ensure that u will be maintained atomically." — p.86（"p3. Distributed sharing" の節）
6. 生成的通信・独立存在（別実行主体への注入可能性の根拠）: "the tuple generated by A has an independent existence in TS" — p.82

### 不変量
- **in の原子性**: 複数の `in` が同一タプルを取り合った場合、1つだけが取得しタプルを分割できない（引用3・4、p.83-84）。
- **read と in の競合時の順序不定**: "if a read0 statement and an in() statement contend for one tuple, the two statements are served, as always, in arbitrary order"（p.84。read が先ならその後 in が同じタプルを取れる、in が先なら read はブロックする）。
- **分散共有変数の原子的維持**: p3 "Distributed sharing" として、"ensure" という語で明示的に保証を宣言（引用5）。

### 実装
**規約（論文記述）止まり。** 1985年のTOPLAS論文自体はLindaコンパイラ・ランタイムのソースコードを含まない（Part II で仮想マシンの設計を論じるが、実装コードの掲載は無い）。原論文からは file:line で不変量を強制している実装箇所を提示不能。実装レベルの検証をするには C-Linda ランタイム（Yale の S/Net 実装等、非公開/現存困難）や後継OSS実装（後述4節）が必要。

### メッセージの分類
- タプルは `(N, P1, ..., Pj)` という「先頭要素が type `name` のアクチュアル、以降は actual/formal 混在の値列」という構造で定義される（p.82, 2.1.2節）。
- マッチングは "type-consonant"（型が一致すること）が要求される（引用2）。これは緩やかな構造的スキーマ（タプルの要素数・型・先頭要素の名前による一致）であり、有限の「種別」列挙ではなく、名前空間全体に開かれた自由形式（"free naming", p.86-87）。
- コードでの強制は確認できない（原論文に実装コード無し）。

### 別の実行主体に注入可能か
- 該当する。引用6の通り、Aが `out` したタプルはBが変換なしにそのまま `in`/`read` で受け取れる（Fig.1/2: "To send data to B, A generates tuples and adds them to TS; B withdraws them."）。かつ p2 "Time uncoupling"（p.85）により送信側プロセスAが終了した後で受信側プロセスBが起動しても成立する、という時間非同期の注入可能性まで明記されている。

---

## 3. JavaSpaces 仕様 + Apache River (Outrigger) 実装

### 取得状況
- **JavaSpaces Service Specification (HTML)**: https://river.apache.org/release-doc/current/specs/html/js-spec.html — **HTTP 200**。`_src/js-spec.html` に保存、HTMLタグ除去版を `_src/js-spec.txt` に作成（自分の目で読むための前処理。原文はHTMLのまま保存済み）。
- **Apache River ソース**:
  - `https://github.com/apache/river.git` → **git clone 失敗: "remote: Repository not found."**（GitHubにこのリポジトリは存在しない。Apache River は GitHub 移行しておらず Subversion 管理のまま Attic 入りしている）。
  - `svn` コマンド自体が環境に無く（`command not found: svn`）、`http://svn.apache.org/viewvc/river/` は **HTTP 401**、`https://gitbox.apache.org/repos/asf/river.git/...` は **HTTP 404** で断念。
  - 代替として ASF 公式アーカイブの**ソースリリース tarball**を取得: https://archive.apache.org/dist/river/river-3.0.0/apache-river-3.0.0-src.tar.gz — **HTTP 200**（5,446,672 bytes）。これは git clone ではないが、Apache Software Foundation が署名配布する公式のソースコード配布物であり、二次資料ではなく一次資料（コードそのもの）。展開先: `_src/apache-river-3.0.0/`
  - 補足: 素の `git clone`（テンプレート指定なし・空テンプレート指定の両方）は、このサンドボックス環境下で `.git/hooks/*` や `.git/config` への書き込みが `Operation not permitted` で拒否され失敗した（サンドボックスのネスト `.git` 書き込み制限が原因とみられる）。`dangerouslyDisableSandbox` でも `git clone` 自体は成功したが対象リポジトリが GitHub に存在しないため無意味だった。

### 抽象
- **JavaSpace インタフェース**: `net.jini.space.JavaSpace`（`_src/apache-river-3.0.0/src/net/jini/space/JavaSpace.java`, 264行）。`write` / `read` / `readIfExists` / `take` / `takeIfExists` / `notify` / `snapshot` を定義。
- **Entry マーカーインタフェース**: `net.jini.core.entry.Entry`（`_src/apache-river-3.0.0/src/net/jini/core/entry/Entry.java`, 39行）。空のマーカー interface で、Javadoc（18-30行）に "Each field of an entry must be a public reference (object) type. You cannot store primitive types in fields of an Entry." と規定。
- 仕様書 JS.2.2〜JS.2.7（`js-spec.txt` 228-400行）で write/read/take/notify のセマンティクスを規定。JS.3.2（709-724行）で ACID (Atomicity/Consistency/Isolation/Durability) を規定。

### 逐語引用（仕様書）
1. take の原子性（核心）: "Two take operations will never return copies of the same entry" — JS.2.5 "takeIfExists and take" (js-spec.txt:347)
2. トランザクションのAtomicity定義: "All the operations grouped under a transaction occur or none of them do." — JS.3.2 (js-spec.txt:715)
3. ベネフィット節: "They store and retrieve entries atomically." — JS.1.2 "Benefits" (js-spec.txt:123)
4. Lindaからの影響の明記: JS.1.4 "JavaSpaces System Design and Linda Systems" 節（js-spec.txt:148-151）"The JavaSpaces system design is strongly influenced by Linda systems, which support a similar model of entry-based shared concurrent processing."

### 不変量
- **take の原子性**は仕様書自身が明記（引用1）。「2つの take は同一エントリのコピーを絶対に2回返さない」という一意性保証。
- **トランザクション下のACID**が仕様として明記（引用2、JS.3.2）。ただし Persistence（Durability）は実装依存であり必須ではないことも明記（js-spec.txt:724）。
- **操作順序に関する非保証**も明記: JS.2.8 "Operation Ordering"（js-spec.txt:400-406）"Operations on a space are unordered."

### 実装（file:line と該当行のテキスト。ローカル clone パス: `_src/apache-river-3.0.0/`）

**take の原子性を強制している実際のコード**（Outrigger = Apache River の JavaSpaces リファレンス実装）:

- `src/org/apache/river/outrigger/EntryHolder.java:291`
  ```
  synchronized (handle) {
  ```
  （`confirmAvailability` メソッド。この排他区間の中で `handle.removed()` / `isProvisionallyRemoved()` をチェックしてから状態を確定する）

- `src/org/apache/river/outrigger/EntryHolder.java:422-427`（`grab` メソッド内、非トランザクション take の場合）:
  ```java
  synchronized (handle){
      if (handle.removed() || handle.isProvisionallyRemoved())
          // Someone got to it first
          return false;
      handle.provisionallyRemove();
  }
  ```
  これが take の原子性を実際に強制している核心のチェック・アンド・セットである。「同じハンドルの `synchronized` モニタを取れた1スレッドだけが `provisionallyRemove()` を呼べる」という Java の言語機構によって、2つの並行 take が同じエントリを取ることを防いでいる。コメント "// Someone got to it first" は仕様書の "Two take operations will never return copies of the same entry" と対応する。

- `src/org/apache/river/outrigger/EntryHolder.java:186`（`attemptCapture` の Javadoc、コード直近のコメントとして）:
  ```
  * Atomically check to see if the passed entry can be read/taken by
  ```
  ソース中に "Atomically" という語そのものが使われている。

- `src/org/apache/river/outrigger/OutriggerServerImpl.java:2133-2136`（`completeTake` メソッド、永続化後の最終削除）:
  ```java
  if (txn == null) {
      synchronized (handle) {
          contents.remove(handle);
      }
  }
  ```

**Entry のスキーマ制約を強制している実際のコード**（`Entry` マーカーインタフェースの Javadoc 規約「public reference type のみ」「primitive 不可」を実行時に強制）:

- `src/org/apache/river/outrigger/EntryRep.java:345-348`（`ensureValidClass`）:
  ```java
  if (!Modifier.isPublic(c.getModifiers())) {
      throw throwRuntime(new IllegalArgumentException(
          "entry class " + c.getName() + " not public"));
  }
  ```

- `src/org/apache/river/outrigger/EntryRep.java:596-599`（`usableField`）:
  ```java
  if (field.getType().isPrimitive()) {
      throw throwRuntime(new IllegalArgumentException(
          "primitive field, " + field + ", not allowed in an Entry"));
  }
  ```

### メッセージの分類
- **型で強制されている**: 空間に置けるものは `net.jini.core.entry.Entry` を実装したクラスのインスタンスのみ（`JavaSpace.java` の各メソッドシグネチャが `Entry` 型を要求）。
- Entry のフィールドは「public」「非static・非final・非transient」「非primitive」でなければならず、これは **README ではなくコード**（`EntryRep.java` の `ensureValidClass` / `usableField`、上記file:line）が実行時にリフレクションで検査・強制している。Hearsay-II や Linda 原論文と異なり、ここは「コードでの強制」の実例を確認できた。
- マッチングはテンプレート（同じ Entry サブタイプのインスタンスで一部フィールドを null にしたもの）とのフィールド完全一致（null はワイルドカード）で行われる。

### 別の実行主体に注入可能か
- 該当する。あるクライアントが `write` した `Entry` は、別のクライアントが `take`/`read` した戻り値としてそのまま（同一 Entry サブタイプの）オブジェクトとして得られる。仕様書 JS.2.6 "snapshot" 節（js-spec.txt:374）に "the return values of the read and take methods are not snapshots and are usable with any implementation of JavaSpaces technology" とあり、read/take の戻り値がどの JavaSpaces 実装とも変換なしに使える通常の Entry オブジェクトであることを明記。

---

## 4. その他の tuple space 実装・Linda 後継（余力枠）

### GigaSpaces (XAP)
- GitHub organization `Gigaspaces` の全リポジトリを列挙した（`api.github.com/orgs/Gigaspaces/repos`, HTTP 200, 90件超）。`xap-openspaces`（Spring風の上位API層）や `xap-docs`、各種インテグレーション（`xap-cassandra`, `xap-mule` 等）はあるが、**空間の write/take を実装するコア・データグリッドエンジン本体のOSSリポジトリは見当たらなかった**。XAPのコア実装はクローズドソースと判断する。
- 検索語: `GigaSpaces XAP open source take atomicity github`。ドキュメント（`docs.gigaspaces.com`）レベルでは "full ACID compliance" 等の記述があるが、これはコードではなく **規約（ドキュメント）止まり**。
- 判定: **未発見**（コアエンジンのコードが非公開のため、file:line 提示不能）。

### TSpaces (IBM)
- 検索語: `TSpaces IBM source code github`。公式のOSS配布は見当たらず、`github.com/VT-CHCI/User-Game` のような第三者プロジェクトのライブラリ同梱物（`com/ibm/tspaces/ExceptionMsgs.properties` 等）が断片的にヒットするのみで、正規の一次ソースとは言えない。
- 判定: **未発見**。深追いはしていない（余力枠のため探索を打ち切り）。

### LIME (Linda in a Mobile Environment)
- 検索語: `LIME Linda mobile environment source code github` / SourceForge の存在確認のみ（https://lime.sourceforge.net/ がヒット）。
- ダウンロード・コード検証は実施していない（余力枠のため探索を打ち切り、これ以上の一次資料確認は本タスクの時間内では行っていない）。
- 判定: **未検証（未発見扱い）**。

---

## 参考: 抽出・変換に用いたローカルツール
- PDF→テキスト抽出: `python3 -m venv $TMPDIR/pdfvenv && $TMPDIR/pdfvenv/bin/pip install pypdf`（poppler-utils が環境に無かったため代替。pypdf 6.19.0 を使用）
- HTML→テキスト: Python標準ライブラリの正規表現タグ除去 + `html.unescape`（`js-spec.txt` 生成用の簡易処理）
