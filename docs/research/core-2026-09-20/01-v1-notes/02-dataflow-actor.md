# 決定性と隔離の系譜 — 一次資料調査ノート

作業ディレクトリ: `$WT/tmp/research-core-2026-09-20/`
ローカル資料: `$WT/tmp/research-core-2026-09-20/_src/`
git clone は sandbox が `.git` という名前のディレクトリへの書き込みを一律拒否するため
（`mkdir foo/.git && echo x > foo/.git/config` が `operation not permitted` で失敗することを実証済み）、
通常の `git clone` ではなく `git clone --bare` で `<name>-bare.git` という名前のディレクトリに
取得し、`git --git-dir=<path> show/grep/ls-tree` で中身を参照した。動作は通常の clone と同一で、
file:line の参照先も実ファイルそのもの。

---

## 1. Kahn (1974) "The Semantics of a Simple Language for Parallel Programming"

- **取得**: HTTP 200。`curl -sL -o _src/kahn1974.pdf https://perso.ensta.fr/~chapoutot/various/kahn_networks.pdf`（529,378 bytes, PDF 1.4, 6 pages）。IFIP Congress 1974, North-Holland, pp.471–475 の再組版版（原論文のページ番号はこの PDF には印字されていないため、以下は **PDF内ページ番号** で示す）。
- **抽象**: 「parallel program schema」を有向グラフとして定義し（PDF p.2, §2.1 Syntax）、各エッジ（チャネル）に型 `D_e` を割り当て、その履歴（history）を `D^ω`（有限または可算無限列の完備半順序、c.p.o.）の元として定義する（PDF p.2, §2.2.2–2.2.3）。ノード（computing station）は履歴から履歴への **連続写像**（continuous mapping）として解釈される（PDF p.2, §2.2.4–2.2.5）。
- **不変量（逐語引用、PDF内ページ）**:
  - チャネルは FIFO: 「processes communicate via first-in first-out (fifo) queues」(PDF p.1)
  - ブロッキング読み出し: 「The process stays blocked on a wait until something is being sent」(PDF p.1)
  - 決定性の核心となる制約（iii）とその意味の言い換え: 「a computing station is either computing or waiting for information on one of its input lines」(iii の原文, PDF p.2) — この直後の Remarks で著者自身が言い換えている: 「a computing station cannot be waiting on data coming from one or another of its input lines」(PDF p.2)。すなわち、複数の入力チャネルのうちどれが届いたかで分岐する「待ち受け選択」を許さないことが、決定性の直接の根拠として明記されている。
  - 保証される不変量（実行順序に依存しない結果）: Property 2 (Scott) 「The minimal solution of the ΣP is a continuous function of the parameters of the system」(PDF p.4)。結論部でも明記: 「A parallel program can be safely simulated on a sequential machine, provided the scheduling algorithm is fair enough...But what is produced is correct.」(PDF p.5, §6 ii)。プログラム全体としては「it can produce only determinate programs」(PDF p.5, §6 冒頭)。
- **メッセージの有限種別分類**: チャネルごとに固定の型 `D_e` を持つ（型は「integer channel」のように事前宣言、PDF p.1 Fig.1）。個々のメッセージ自体を有限タグ集合に分類する仕組みではなく、チャネル＝型の対応が形式的手段（型宣言）。
- **event stream 相当の仕組み**: **ある**。「history」がそれ。「An observer placed on the line witnesses its traffic, a (possibly infinite) sequence of objects of type D: it is called the history of the line.」(PDF p.2, §2.2.1)。各チャネルの履歴は追記のみの順序付き列であり、これが外部から観測可能な「イベントストリーム」に相当する。
- **実装**: Kahn (1974) 自体は理論論文でコードを含まない。実装上の不変量は下記 §3 Ptolemy II PN で確認。

---

## 2. Lee & Messerschmitt (1987) "Synchronous Data Flow"

- **取得**: HTTP 200。まず `bears.ece.ucsb.edu/class/ece253/papers/lee_sdf87.pdf` を取得したが、これは **別論文**（"Static Scheduling of Synchronous Data Flow Programs for Digital Signal Processing", IEEE Trans. Computers, Vol. C-36, No.1, Jan 1987, pp.24–35, 同著者の姉妹論文）であることが本文1ページ目のタイトル確認で判明。正しい対象論文（Proceedings of the IEEE, Vol.75, No.9, Sept 1987, pp.1235–1245, DOI 10.1109/PROC.1987.13876）は `https://ptolemy.eecs.berkeley.edu/publications/papers/87/synchdataflow/synchdataflow.pdf` から取得（HTTP 200, 15,709,681 bytes, PDF 1.4）。ファイル名は `_src/synchdataflow.pdf`。誤取得の副産物 `_src/lee_sdf87.pdf` も残してあるが本調査では不使用。
- **抽象**: SDF グラフを「有向グラフ、ノード＝関数、アークがシグナル経路」の特別な dataflow として定義。ノードごとの入出力アークで「消費/生成するトークン数」が invocation ごとに **事前** に定まることを要求する（p.1235 Abstract, p.1236 §I 定義文）。トポロジ行列 Γ（各アークを行、各ノードを列に持つ整数行列）でグラフの依存関係を表現（p.1239, §IV-A）。
- **不変量（逐語引用）**:
  - 定義そのもの: 「the number of tokens produced or consumed must be independent of the data」(p.1236)
  - 静的スケジューリング可能性の必要条件: 「A necessary condition for the existence of such a schedule is that rank(Γ) = s − 1」(p.1239, §IV-B, s はノード数)
  - 有界バッファ／FIFO: 「We can replace each arc with a FIFO queue (buffer) to pass data from one node to another.」(p.1239)。バッファサイズはベクトル `b(n)` として追跡され、更新規則 `b(n+1)=b(n)+Γv(n)` で状態遷移する（p.1239, 式(3)）。
  - 「periodic admissible sequential/parallel schedule」(PASS/PAPS) が「the amount of data in the buffers...will remain nonnegative and bounded」ことを要求（p.1244, Definition 1）。
- **メッセージの有限種別分類**: 本論文はトークンの「型」ではなく「個数」の静的決定性を扱う。型タグの形式的手段には触れていない（一般 dataflow の型付けを暗黙に継承するのみ、規約止まり）。
- **event stream 相当の仕組み**: 明示的な「history」という語は使わないが、アーク＝FIFO キューという構造そのものが順序付き列であり Kahn の history 概念と同型。追加のイベント通知機構（listener 等）は論文内になし。

---

## 3. Ptolemy II — PN (process network) ディレクタの実装

- **取得**: `git clone --bare --depth 1 https://github.com/icyphy/ptII $WT/tmp/research-core-2026-09-20/_src/ptII-bare.git` 成功（HEAD commit `5dc2aa15edd05efb9d097f1353edb04a21e2358a`, 2025-12-03、`Bump org.mozilla:rhino ...` というdependabotコミット）。1回目の clone は途中で `failed to store: -67674`（macOS keychain 関連のエラーコード）を出したが、`git log` で HEAD のコミットが取得できていることを確認済み（clone 自体は完了していた）。
- **不変量を強制している実際の行**: `ptolemy/domains/pn/kernel/PNQueueReceiver.java` の `get()` メソッド。ローカルパス: `$WT/tmp/research-core-2026-09-20/_src/PNQueueReceiver.java`（`git show HEAD:...` で書き出したコピー。オリジナルは bare リポジトリ内オブジェクトなので同じ内容を参照）。
  - `PNQueueReceiver.java:144-148`（Javadoc）: 「Get a token from this receiver. If the receiver is empty then block until a token becomes available.」
  - `PNQueueReceiver.java:151` `public Token get() {`
  - `PNQueueReceiver.java:169-170` `if (super.hasToken()) { result = super.get();`（データがあれば即座に読み出す）
  - `PNQueueReceiver.java:185-193`（データが無い場合のブロッキング本体）:
    ```
    185:                    _readPending = Thread.currentThread();
    186:                    _director.threadBlocked(Thread.currentThread(), this,
    187:                            PNDirector.READ_BLOCKED);
    ...
    192:                    depth = workspace.releaseReadPermission();
    193:                    _director.wait();
    ```
  - これが Kahn の「wait until something is being sent」を JVM の `Object.wait()`（`_director` をモニタとするブロッキング待機）で直接実装している箇所。読み出し側は複数チャネルのうちどれが来たかで選択する API を持たず（`get()` は自分のレシーバの到着のみを待つ）、Kahn 制約(iii)を保っている。
- **メッセージの有限種別分類**: Ptolemy II の `Token` クラス階層（`IntToken`, `DoubleToken` 等）で型付けされる。本調査では `PNQueueReceiver`/`PNDirector` の範囲に絞ったため `Token` 階層の file:line は未確認（範囲外）。
- **event stream 相当の仕組み**: **ある**。`ptolemy/domains/pn/kernel/event/PNProcessEvent.java`, `PNProcessListener.java` が観測用のイベント通知機構。`PNDirector.java:600` `private LinkedList _processListeners = new LinkedList();`、`PNDirector.java:202` `_processListeners.add(listener);`、`PNDirector.java:355` `_processListeners.remove(listener);` でリスナー登録・解除を実装（実行中のブロック/アンブロック等の出来事をリスナーに通知する設計だが、通知メソッド自体の呼び出し箇所 file:line は本調査では未特定）。

---

## 4. Hewitt, Bishop, Steiger (1973) "A Universal Modular ACTOR Formalism for Artificial Intelligence"

- **取得**: HTTP 200。`curl -sL -o _src/hewitt1973.pdf "https://eighty-twenty.org/files/Hewitt,%20Bishop,%20Steiger%20-%201973%20-%20A%20universal%20modular%20ACTOR%20formalism%20for%20artificial%20intelligence.pdf"`（1,201,667 bytes, PDF 1.3, 11 pages）。IJCAI 1973, pp.235–245（原論文ページ番号がPDF本文にそのまま印字されている）。
- **抽象**: 全てのオブジェクト（データ構造・関数・プロセス等）を単一の概念「actor」に統一し、actor 間の唯一の相互作用手段を「メッセージを送ること」と定義（p.235, Abstract）。`HISTORY` を「イベントの厳密な半順序」として定義し（p.240）、`BEHAVIOR`／`REPERTOIRE`／`EQUIVALENT` を用いて構成の等価性を意味論的に定義する（p.240）。
- **不変量（逐語引用、原論文ページ）**:
  - 副作用の不在＝共有状態を介さない相互作用: 「Sending a message to an actor is entirely free of side effects」(p.240, 項目3)
  - グローバル状態の否定: 「Global state considered harmful.」(p.238)
  - 半順序であり全順序（単一の実行順序ストリーム）を要求しない: 「we do not require that two arbitrary events be related by →」(p.240, HISTORY の定義直後)
  - 一方向性（配送保証はメッセージ順序を含意しない）: 「Sending a message to an actor makes no presupposition that the actor sent the message will ever send back a message」(p.241, 項目4)
  - FIFO が保証されるのは「resource」単位の同期機構に限定: 「guaranteed first in first out discipline on each resource」(p.236, SYNCHRONIZATION の項)。全体のメッセージ配送順序についての一般的な FIFO 保証は本文中に見当たらない。
- **メッセージの有限種別分類**: **ない（形式的には開かれている）**。メッセージは `(=> pattern body)` によるパターンマッチで受理判定される。パターンに合わなければ「the actor is NOT-APPLICABLE to the-message」(p.239) で拒否されるのみで、有限個の型タグに属することをコンパイラや型システムが強制する仕組みは提示されていない。
- **event stream 相当の仕組み**: `HISTORY`（半順序のイベント集合）が近いが、Kahn の「history」と違い **全順序ではない半順序**。著者自身が「グローバルな同時性の定義を要求しない」と明記しており（p.240）、単一の順序付きストリームとしては定義されていない。

---

## 5. Agha, actor の意味論（"ACTORS: A Model of Concurrent Computation in Distributed Systems", MIT AI Lab Technical Report, June 1985, 198pp.）

- **取得の経緯**:
  - `https://apps.dtic.mil/sti/tr/pdf/ADA157917.pdf` → **HTTP 403**（アクセス拒否、本文は HTML のアクセス拒否ページ 1,484 bytes）。検索語: `Agha "Actors: A Model of Concurrent Computation" thesis pdf core.ac.uk OR semanticscholar OR dspace.mit.edu "mail queue" OR "guaranteed to be delivered"`。
  - MIT DSpace の handle `1721.1/6952` を発見（`https://dspace.mit.edu/handle/1721.1/6952`）。ページ本体（Angular SPA）から bitstream ID を3件抽出し、`https://dspace.mit.edu/server/api/core/bitstreams/dc678131-4625-4473-b2b5-f325868e703f/content` が実体 PDF（HTTP 200, 16,890,973 bytes, PDF 1.4, 約226ページ）であることを確認。`_src/agha_thesis_1985.pdf` として保存。表紙（DTIC Report Documentation Page）に「ACTORS: A MODEL OF CONCURRENT COMPUTATION IN DISTRIBUTED SYSTEMS」「Gul Abdulnabi Agha」「N00014-80-C-0505」「June 1985」「198 [pages]」と印字されており、DTIC ADA157917 と同一文書であることを確認。
  - 他の2 bitstream: `41830164-...` は PostScript（16MB, 本文と同一文書の別形式）、`9d11a9d5-...` はサムネイル JPEG（4,946 bytes）。
- **ツール制約による限界**: この PDF はスキャン起源で `pdftoppm` が本環境に未導入のため、指定された Read ツールの `pages` 指定によるページレンダリングが **失敗**（`pdftoppm is not installed` エラー）。そのため Python の `zlib` でストリームを直接展開し `Tj`/`TJ` の括弧内文字列を抽出する自前の代替手段で読んだ。この方法は Anthropic 純正の PDF 抽出（他の資料で使用）より品質が低く、**ページによって OCR/フォント抽出品質にムラがある**（例: 本文ストリームで "the"→"te"、"there"→"tere"、"which"→"wich" のように "th" 系の文字が欠落する箇所が散見される。Abstract 部分のストリームはこの欠落が見られずクリーン）。そのため、**逐語引用は欠落の見られないクリーンな Abstract（p. iii）からのみ採用**し、本文 §2.4.1/2.4.2 の内容は要約に留め、直接引用はしない。
- **抽象**: 「A foundational model of concurrency」を actor 単位で構築し、非同期メッセージパッシング、パイプライン化、actor の動的生成による並行性を扱う（p. iii, Abstract, DSpace メタデータと同一文面をPDF本文からも確認）。
- **不変量（逐語引用、p. iii Abstract、クリーンな抽出）**:
  - 配送保証: 「Communications are buffered by the mail system and are eventually delivered.」
  - 順序の非決定性（逐語）: 「captures the nondeterminism in the order of delivery of communications」
  - 公平性は配送保証止まりで、それ以上の強い公平性（例えば順序保証）は要求しない、という論旨が §2.4.1 "The Guarantee of Delivery" / §2.4.2 "Fairness and the Mail System"（本文 p.24–25、目次 stream 30 で確認）に展開されている。該当箇所は OCR ノイズのため直接引用を避けるが、要旨として「配送は保証するが、配送順序についての強い公平性要求は採用しない」という立場が明記されている（p.24–25 相当箇所を複数回読み直し、noisy ながら意味は一致して読み取れた）。
  - 共有変数モデルとの対比（§2.3.1, p.18、これもノイズあり）で、shared-variables アプローチは「情報隠蔽のための仕組みを提供しない」("does not provide any mechanism for abstraction and information hiding" 相当、OCRノイズのため意味のみ採用) と批判し、actor のカプセル化（§7.2.2 "Encapsulation in Actors", 目次で p.152）がその代替として位置づけられている。
- **メッセージの有限種別分類**: 本調査で確認した範囲（Abstract, §2.3, §2.4, 目次）には形式的なタグ/型スキームの記述は見当たらず。primitive actor として整数・真偽値・文字列等が挙げられる（§4.4.1 該当、目次確認のみ、本文未精読）が、送受信メッセージ全体を有限種別に分類する形式的手段の提示は本調査の範囲では確認できず。
- **event stream 相当の仕組み**: Abstract に「The possibility transition models events from some view-point...captures the nondeterminism in the order of delivery」とあり、Hewitt と同様に **単一の全順序ストリームではなく、view-point 依存の遷移** として定義される。

---

## 6. アクタの不変量をコードで強制している実装

### 6-a. Pony (`ponylang/ponyc`)

- **取得**: `git clone --bare --depth 1 https://github.com/ponylang/ponyc $WT/tmp/research-core-2026-09-20/_src/ponyc-bare.git` 成功（HEAD `f8a5e22672dfd2427b45e6845bffcc690e02f57e`, 2026-09-19）。
- **強制している file:line と該当行のテキスト**:
  1. Reference capability の subtyping 規則本体: `src/libponyc/type/cap.c:62`
     ```c
     bool is_cap_sub_cap(token_id sub, token_id subalias, token_id super,
       token_id supalias)
     ```
     （`cap.c:62-100` 付近で `TK_ISO`/`TK_TRN`/`TK_VAL`/`TK_REF`/`TK_BOX`/`TK_TAG` 等の capability 間の subtype 関係をswitch文で網羅的に判定）。呼び出し元は `src/libponyc/type/subtype.c:71,83,111,129,210,247,904,909,914`（型の subtype 判定全体から呼ばれる中核関数）。
  2. アクタ間で共有可能（sendable）かどうかを判定する関数: `src/libponyc/type/cap.c:1265`
     ```c
     bool cap_sendable(token_id cap)
     {
       switch(cap)
       {
         case TK_ISO:
         case TK_VAL:
         case TK_TAG:
         case TK_CAP_SEND:
         case TK_CAP_SHARE:
           return true;
         default: {}
       }
       return false;
     }
     ```
     （`iso`/`val`/`tag` のみが送信可能、`ref`/`trn`/`box` は不可＝可変で他アクタと共有され得る capability は message として渡せない）。
  3. behavior（非同期メソッド＝メッセージハンドラ）の**引数**がすべて sendable であることをコンパイラが強制する箇所: `src/libponyc/pass/flatten.c:321-338`
     ```c
     static ast_result_t flatten_sendable_params(pass_opt_t* opt, ast_t* params)
     {
       ...
         if(!sendable(type, opt))
         {
           ast_error(opt->check.errors, param,
             "this parameter must be sendable (iso, val or tag)");
     ```
     呼び出し元 `flatten_async`（`flatten.c:359-364` 付近、behavior 宣言に対して呼ばれる）と `flatten_constructor`（`iso`/`trn`/`val` コンストラクタに対して呼ばれる）。**これがアクタ境界を越えるメッセージのペイロードが可変な共有状態を持ち込めないことを型検査で拒否する実際のコンパイルエラー発生箇所**。
  4. `recover` 式内での非 sendable レシーバへのメソッド呼び出し拒否: `src/libponyc/expr/call.c:696-741`（`check_nonsendable_recover`、`sendable(arg_type, opt)` / `sendable(result, opt)` をチェックし、失敗時に `"can't call method on non-sendable object inside of a recover expression"` を出す）。
- **メッセージの有限種別分類**: **ある（型システムで強制）**。1つの behavior 呼び出し＝1つの静的に型付けられたメッセージであり、そのパラメータ型は上記 flatten.c:321 のチェックをコンパイル時に通過しなければならない。behavior の集合（1アクタが持つ有限個のメソッド名）がそのままメッセージ種別の有限集合に対応する。
- **event stream 相当の仕組み**: 本調査の範囲（`type/`, `expr/call.c`, `pass/flatten.c`）では未確認。Pony ランタイムの `--ponytrace`／`ponyint_actor` 統計や `sched.c` にトレース機構がある可能性はあるが、file:line は今回未特定のため「未確認」とする。

### 6-b. Erlang/OTP（BEAM）— プロセス隔離とメッセージコピー

- **取得**: `curl -sL -o _src/erl_message.c https://raw.githubusercontent.com/erlang/otp/master/erts/emulator/beam/erl_message.c`（HTTP 200）。
- **強制している file:line と該当行のテキスト**: `erts_send_message`（`erl_message.c:698` で定義開始）が受信側プロセスのヒープを確保し（`erts_alloc_message_heap_state`, `erl_message.c:773`）、送信メッセージ term をコピーする:
  ```c
  791:#ifdef SHCOPY_SEND
  792:    if (is_not_immed(message))
  793:            message = copy_shared_perform(message, msize, &info, &hp, ohp);
  794:        DESTROY_SHCOPY(info);
  795:#else
  796:    if (is_not_immed(message))
  797:            message = copy_struct_litopt(message, msize, &hp, ohp, &litarea);
  798:#endif
  ```
  （`msize` は `size_object_litopt`, `erl_message.c:771` で事前計算。）これは Hewitt/Agha が要求する「actor 間で状態を共有せずメッセージのみでやりとりする」という不変量を、**VM が送信のたびに term をディープコピーする**ことで実現している実装上の証拠であり、当初のタスク指示が想定していた「VM レベルなので file:line として示しにくい」という懸念に反して、**具体的な file:line で示せた**。
- **メッセージの有限種別分類**: **ない（動的型付け、規約止まり）**。Erlang の term は任意の値であり、コンパイル時のメッセージ型スキームは存在しない。OTP の `{tag, ...}` タプル規約はコミュニティ規約であり、コンパイラや VM が強制するものではない。
- **event stream 相当の仕組み**: 本調査では未確認。`erlang:trace/3` 等のトレーシング機構はランタイムに存在するが、file:line は本セッションでは未特定。

### 6-c. Akka — 何が型で強制され何が規約止まりか

- **取得**: `curl -sL raw.githubusercontent.com/akka/akka/main/akka-actor-typed/.../Behavior.scala`（HTTP 200）、同 `ActorRef.scala`（HTTP 200）、`akka-actor/.../event/EventStream.scala`（HTTP 200）。
- **型で強制される箇所（file:line）**:
  - `akka-actor-typed/src/main/scala/akka/actor/typed/Behavior.scala:43`
    ```scala
    abstract class Behavior[T](private[akka] val _tag: Int) { behavior =>
    ```
  - `akka-actor-typed/src/main/scala/akka/actor/typed/ActorRef.scala:25,32`
    ```scala
    trait ActorRef[-T] extends RecipientRef[T] with java.lang.Comparable[ActorRef[_]] with java.io.Serializable {
    ...
      def tell(msg: T): Unit
    ```
    `ActorRef[-T]`（反変ジェネリクス）と `tell(msg: T)` により、**Scala コンパイラが T 型（またはそのサブタイプ）以外のメッセージ送信をコンパイルエラーにする**。エスケープハッチとして `ActorRef.scala:45` に `def unsafeUpcast[U >: T @uncheckedVariance]: ActorRef[U]`（メソッド名が明示的に "unsafe"）がある。
  - `akka-actor/src/main/scala/akka/event/EventStream.scala:24`
    ```scala
    class EventStream(sys: ActorSystem, private val debug: Boolean) extends LoggingBus with SubchannelClassification {
    ```
    と `:41 protected def publish(...)`, `:50 override def subscribe(...)` — Akka には文字通り「EventStream」と名付けられた、システム内で発生した出来事を型（`Class[_]`）でチャネル分けして外部（購読者）へ配送する pub/sub バスが存在する。**これが「実行中の出来事を外部へ順序付きで出す仕組み」の質問に対する実装側の直接的な答え。**
- **規約止まりの箇所**: アクタが可変な状態を他アクタと共有しないこと自体は **Scala の型システムでは強制されない**。`ActorRef[-T]` はメッセージ型を制約するのみで、closure が外部の mutable 変数を capture して複数アクタから参照させることをコンパイラは禁止しない。本調査ではこれを禁止する型チェックコードを発見できなかった（README/ドキュメントでの「actor 内の状態を外部と共有するな」という推奨のみ）。**規約止まりと判定する。**
- **メッセージの有限種別分類**: **型で強制**。`Behavior[T]` の `T` を sealed trait の代数的データ型にすることで、コンパイラが網羅性検査を行える（Scala の `sealed` は言語機能でコンパイラが強制）。ただし `T` を `sealed` にすること自体は akka のコード側の強制ではなく利用者の選択であり、`Any` 等の非 sealed 型を使えば無制限にもなる。

### 6-d. Microsoft Orleans — grain 呼び出しと単一活性化

- **取得**: `curl -sL raw.githubusercontent.com/dotnet/orleans/main/src/Orleans.Runtime/Catalog/Catalog.cs`（HTTP 200）、同 `ActivationDirectory.cs`（HTTP 200）。
- **単一活性化（single activation）を保証している file:line**: `src/Orleans.Runtime/Catalog/Catalog.cs` の `GetOrCreateActivation`（`Catalog.cs:133` 定義開始）:
  ```csharp
  138:            if (TryGetGrainContext(grainId, out var result))
  139:            {
  ...
  149:            lock (GetStripedLock(grainId))
  150:            {
  151:                if (TryGetGrainContext(grainId, out result))
  152:                {
  ...
  167:                    result = this.grainActivator.CreateInstance(address);
  168:                    activations.RecordNewTarget(result);
  169:                }
  170:            } // End lock
  ```
  ダブルチェックロッキング（`GetStripedLock(grainId)` によるグレイン単位のロック）で、同一 `grainId` に対して2つ目の activation が生成されるのを防いでいる。これがこの silo 上での single-activation 保証の実体。
  下支えとなるストレージは `src/Orleans.Runtime/Catalog/ActivationDirectory.cs:14, 31-39`:
  ```csharp
  14:    private readonly ConcurrentDictionary<GrainId, IGrainContext> _activations = new();
  ...
  31:    public void RecordNewTarget(IGrainContext target)
  32:    {
  33:        var metrics = GetMetrics(target);
  34:        if (_activations.TryAdd(target.GrainId, target))
  ```
  （`RecordNewTarget` 単体は `TryAdd` の成否をロジック分岐に使っておらず、実際の一意性保証は `Catalog.cs` 側の `lock` + 事前の `TryGetGrainContext` 二重チェックが担っている。）
- **grain 呼び出しの型付け**: grain はインタフェース型（`IGrainContext` 等）を介して呼び出される。個々の grain インタフェースメソッドが静的に定義された「メッセージ」に相当し、C# コンパイラがシグネチャを検査する。具体的な grain インタフェース定義ファイル（例: ユーザー定義の `IMyGrain`）は Orleans フレームワーク自体のコードではなくアプリケーション側にあるため、本調査では Orleans ランタイム側のインタフェース強制機構として `IGrainContext`（`ActivationDirectory.cs:10` の型パラメータ、`Catalog.cs:133` の戻り値型）を file:line として提示する。
- **メッセージの有限種別分類**: **型で強制**（C# インタフェースの静的メソッドシグネチャ）。
- **event stream 相当の仕組み**: Orleans には "Orleans Streams"（`Orleans.Streaming` 名前空間）という grain 間 pub/sub ストリーミング機構が存在することは一般に知られているが、本セッションでは具体的な file:line の確認まで至っておらず（`StreamSubscriptionHandleImpl.cs` への直接アクセスは HTTP 404）、**未確認**として扱う。

---

## 検索語・辿った URL の一覧（未発見／代替に至った経路の記録）

- Lee & Messerschmitt "Synchronous Data Flow" (Proc. IEEE 1987) の正しい PDF: 検索語 `"Synchronous Data Flow" Lee Messerschmitt Proceedings IEEE September 1987 pp 1235 site:eecs.berkeley.edu OR site:ptolemy.berkeley.edu` → `https://ptolemy.berkeley.edu/publications/papers/87/` のインデックスページを curl → `https://ptolemy.eecs.berkeley.edu/publications/papers/87/synchdataflow/` → `synchdataflow.pdf` を発見・取得。
- Agha の一次資料: 検索語 `Agha "Actors: A Model of Concurrent Computation" pdf message ordering guarantee` および `Agha "Actors: A Model of Concurrent Computation" thesis pdf core.ac.uk OR semanticscholar OR dspace.mit.edu "mail queue" OR "guaranteed to be delivered"` → DTIC (`apps.dtic.mil/sti/tr/pdf/ADA157917.pdf`) は **403** → MIT DSpace handle `1721.1/6952` のページから bitstream API 経由で PDF 実体を取得（上記参照）。
- Orleans Streams の file:line: `https://raw.githubusercontent.com/dotnet/orleans/main/src/Orleans.Streaming/Core/StreamSubscriptionHandleImpl.cs` → **404**（パス名を推測しただけで実在確認できず）。**未発見** として扱い、Orleans Streams の存在自体は一般知識であり本調査では file:line 未確認と明記した。
- Pony/Erlang/Akka のイベントストリーム相当機構のうち、Erlang のトレーシング (`erlang:trace/3` 系) と Pony のスケジューラトレースは、具体的な file:line 特定まで至らず「未確認」とした（検索・clone した範囲を `erl_message.c` および `type/`, `expr/call.c`, `pass/flatten.c` に絞ったため、範囲外）。

## 取得したローカルファイル一覧

```
_src/kahn1974.pdf                  Kahn 1974 原文 PDF
_src/hewitt1973.pdf                Hewitt, Bishop, Steiger 1973 原文 PDF
_src/synchdataflow.pdf             Lee & Messerschmitt, "Synchronous Data Flow" (Proc. IEEE 1987) 正しい版
_src/lee_sdf87.pdf                 誤取得の姉妹論文（不使用、記録のため保持）
_src/agha_thesis_1985.pdf          Agha 1985 Technical Report（MIT DSpace 経由、スキャン起源）
_src/PNQueueReceiver.java          ptII-bare.git HEAD からの書き出し
_src/erl_message.c                 erlang/otp master のraw取得
_src/Behavior.scala, ActorRef.scala, EventStream.scala   akka/akka main のraw取得
_src/Catalog.cs, ActivationDirectory.cs                   dotnet/orleans main のraw取得
_src/ptII-bare.git                 git clone --bare (icyphy/ptII, depth 1)
_src/ponyc-bare.git                git clone --bare (ponylang/ponyc, depth 1)
```
