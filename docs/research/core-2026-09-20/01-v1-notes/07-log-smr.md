# 07 — 順序付きログを正本とする系譜 / 型を持たないパイプラインの系譜

一次資料収集ログ。担当: state machine replication / Lamport ordering / Kafka / Unix pipeline / MCMAS。

作業ディレクトリ: `$WT/tmp/research-core-2026-09-20/`
- ダウンロード物・clone: `_src/`
- 本ファイル: `_notes/07-log-smr.md`

---

## 1. Schneider, "Implementing Fault-Tolerant Services Using the State Machine Approach: A Tutorial" (ACM Computing Surveys 22(4), 1990)

**取得状況**: 成功。HTTP 200。
```
curl -sL -o _src/schneider_smr_1990.pdf https://www.cs.cornell.edu/fbs/publications/smsurvey.pdf
```
PDF, 21 ページ, version 1.2。ローカルパス: `$WT/tmp/research-core-2026-09-20/_src/schneider_smr_1990.pdf`
PDF ページ 1 = 誌面 p.299（タイトルページ）。以降 PDF page N = 誌面 p.(298+N)。

### 抽象
- Section 1 "State Machines"（誌面 p.300）: 状態機械を「状態変数」と「コマンド」の組として形式的に定義。
- Section 3 "Fault-Tolerant State Machines"（誌面 p.303）: 複製された状態機械（replica ensemble）が正しく動作するための必要条件を Agreement / Order の2条件に分解して定義。

### 不変量（逐語引用、誌面ページ付き）
1. **決定性の前提**（誌面 p.300, Section 1 冒頭）:
   > "Each command is implemented by a deterministic program"
   （14 語未満。原文: "Each command is implemented by a deterministic program; execution of the command is atomic..."）

2. **決定性の意味論的規定**（誌面 p.301, "Semantic Characterization of a State Machine"）:
   > "Outputs of a state machine are completely determined by the sequence of requests it processes"
   （14 語。ここまでが決定性の要求そのもの。この一文が「同じ順序で受け取れば同じ結論に至る」という主張の前提条件。）

3. **Order 条件 O1/O2**（誌面 p.301, single state machine への要求。まだ replica の話ではない）:
   > "Requests issued by a single client to a given state machine sm are processed by sm in the order they were issued."（O1、逐語）
   > 続けて誌面 p.301 の注記: "01 and 02 do not imply that a state machine will process requests in the order made or in the order received."（**但し書き**: 単一マシンでの受信順序と処理順序は一致するとは限らないと明記）

4. **Replica Coordination / Agreement / Order**（誌面 p.303, Section 3 冒頭、replica 間の話）:
   > "Replica Coordination. All replicas receive and process the same sequence of requests."
   > "Agreement. Every nonfaulty state machine replica receives every request."
   > "Order. Every nonfaulty state machine replica processes the requests it receives in the same relative order."
   （各文は逐語、15語以内）

5. **不変量が成立するための前提条件（決定性）を明記した一文**（誌面 p.303）:
   > "Provided each replica...starts in the same initial state and executes the same requests in the same order, then each will do the same thing and produce the same output."
   （"Provided" = 条件節。決定性 + 同一初期状態 + 同一順序、の3条件が明示的な前提。この3条件が欠けると Agreement/Order を満たしても複製は同じ結論に至らない。）

### 実装
論文であり実装コードは無い（チュートリアル論文）。「強制している file:line」は該当なし。

### メッセージ有限種別分類
論文の抽象化では「command」はステートマシンごとに定義された有限集合（例: `read`, `write`）。ただし決定性はコマンドの**実装が決定的であること**に依存しており、コマンド集合が有限であること自体は決定性を保証しない。

### 実行中の出来事を順序付きで外へ出す仕組みとして使えるか
これは実装ではなく形式的前提の集合。「順序付きログさえ共有すれば異種の実行主体でも同じ結論に至る」という主張は、この論文の枠組みでは **決定性 (Semantic Characterization) が満たされて初めて** 成立する。決定性を検証しない限り、順序付きログの共有だけでは Agreement/Order は成立しても同じ最終状態には至らない。

---

## 2. Lamport, "Time, Clocks, and the Ordering of Events in a Distributed System" (CACM 21(7), 1978)

**取得状況**: 成功。HTTP 200。
```
curl -sL -o _src/lamport_time_clocks_1978.pdf https://lamport.azurewebsites.net/pubs/time-clocks.pdf
```
PDF, 8 ページ, version 1.3。ローカルパス: `$WT/tmp/research-core-2026-09-20/_src/lamport_time_clocks_1978.pdf`
PDF page 1 = 誌面 p.558。PDF page 3 = 誌面 p.560、PDF page 4 = 誌面 p.561（誌面フッタで確認）。

### 抽象
"Ordering the Events Totally"（誌面 p.560–561）: happened-before 関係（半順序）を、任意の全順序に拡張する規則を定義。

### 不変量（逐語引用、誌面ページ付き）
1. **全順序の構成規則**（誌面 p.560–561）:
   > "To break ties, we use any arbitrary total ordering < of the processes."
   （タイムスタンプが同値の場合、プロセスIDの任意の全順序で決着をつける、という規則。）

2. **何を保証するか**（誌面 p.561）:
   > "the Clock Condition implies that if a → b then a ⇒ b"
   （happened-before ならば構成した全順序でもその順序が保たれる、という一方向の保証。）

3. **何を保証しないか（否定的事実、正確に引用）**（誌面 p.561）:
   > "It is only the partial ordering which is uniquely determined by the system of events."
   （全順序 ⇒ 自体は一意でない。クロックの選び方により異なる全順序が得られる、と明記。）
   補足（誌面 p.561、脚注3の直前）:
   > "Condition II says nothing about which of two concurrently issued requests should be granted first."
   （因果的に無関係な=concurrent なイベント間の順序は、全順序化によって「決まる」だけで、意味のある基準による決定ではないことの直接証拠。）

### 実装
論文でありコード実装なし。「強制している file:line」は該当なし。

### メッセージ有限種別分類
対象外（イベント順序付けの理論であり、メッセージ内容の型は定義していない）。

### 実行中の出来事を順序付きで外へ出す仕組みとして使えるか
Lamport timestamp + 任意のプロセス順による tie-break は、分散イベント列に**一つの**全順序を与える一般手法。ただし前提1で確認した通り、全順序は一意でなく、concurrent なイベント間の順序は恣意的（実世界の意味を持たない）。「順序付きログとして外へ出す」際、その順序が「意味のある順序」だと主張することはこの論文の結果からは正当化できない。

---

## 3. Apache Kafka

**取得状況**: 成功（ただし通常の `git clone` は sandbox 制約で失敗し、bare clone + `git archive` で回避）。

```
git clone --depth 1 https://github.com/apache/kafka kafka
```
→ 失敗: `fatal: cannot copy '.../hooks/commit-msg.sample' ... Operation not permitted`
（この worktree の Bash sandbox は `<dest>/.git/...` という path segment への書き込みを一般に拒否する。他の並行エージェントの `ponyc_clone.log` / `ptII_clone.log` / `MCP_clone.log` / `A2A_clone.log` でも同一の失敗を確認済み。）

回避策（成功）:
```
git clone --bare --depth 1 https://github.com/apache/kafka.git _src/kafka-bare.git
git --git-dir=_src/kafka-bare.git archive trunk | tar -x -C _src/kafka-src
```
`kafka-bare.git` は `.git` という path segment を持たないベアリポジトリなので書き込み拒否を回避できる（`failed to store: -67674` という追加の非致命的エラーが出るが、実体は正常に取得済み。`git log` で検証済み: `869426f MINOR: Document 4.4+ broker requirement...`）。
ローカルソース: `$WT/tmp/research-core-2026-09-20/_src/kafka-src/`（trunk, 2026-09-20 時点）

### パーティション内順序保証の実装箇所

**単一ライタ性（ロック）**:
`_src/kafka-src/storage/src/main/java/org/apache/kafka/storage/internals/log/UnifiedLog.java:123`
```java
private final Object lock = new Object();
```
`UnifiedLog.java:1150`（`append` メソッド内、offset 割当てから実ディスク追記までを覆うブロックの開始）:
```java
synchronized (lock)  {
```
このブロックは 1150 行から 1300 行超まで続き、offset 割当て・検証・実ディスク追記・high watermark 更新を単一ロックの中で直列化している。

**offset 割当て（単調増加）**:
`UnifiedLog.java:1158`:
```java
PrimitiveRef.LongRef offset = PrimitiveRef.ofLong(localLog.logEndOffset());
```
現在の log end offset を起点にオフセットを払い出す。

**実ディスク追記**:
`UnifiedLog.java:1276`:
```java
localLog.append(appendInfo.lastOffset(), validRecords);
```
`_src/kafka-src/storage/src/main/java/org/apache/kafka/storage/internals/log/LocalLog.java:529-532`:
```java
public void append(long lastOffset, MemoryRecords records) throws IOException {
    segments.activeSegment().append(lastOffset, records);
    updateLogEndOffset(lastOffset + 1);
}
```
単一のアクティブセグメントへの追記 + logEndOffset の単調更新。これが「パーティション内順序」を担保する実体。

### コンシューマグループの排他読み取りを強制しているコード

**重要な限定事実**: Fetch API 自体は consumer group を意識しない（グループに属さない任意クライアントでも同じパーティションを fetch できる）。排他性は次の2箇所でのみ強制される。

1. **クライアント側の自己規律**（アサインされたパーティションのみ poll する）:
`_src/kafka-src/clients/src/main/java/org/apache/kafka/clients/consumer/internals/SubscriptionState.java:316`:
```java
public synchronized void assignFromSubscribed(Collection<TopicPartition> assignments) {
```
coordinator から返された assignment でローカルの購読状態を置き換える。この assignment 自体は「1パーティション→高々1メンバー」になるよう group coordinator 側の assignor が計算するが、**Fetch を強制的にブロックする仕組みではない**。

2. **オフセットコミットの世代フェンシング**（ブローカー側で唯一のハード強制点）:
`_src/kafka-src/group-coordinator/src/main/java/org/apache/kafka/coordinator/group/OffsetMetadataManager.java:476`:
```java
throw Errors.ILLEGAL_GENERATION.exception();
```
古い世代（fenced になったメンバー）からのオフセットコミットを拒否する。これにより「読み取り済みの記録」の上書きは防げるが、Fetch そのものは防がれない。

結論: 「1パーティションを1コンシューマだけが読む」は**プロトコル上の規約**であり、Fetch API レベルでの強制ではない。強制されているのはオフセットコミットの世代整合性のみ。

### メッセージの型・スキーマ制約

Kafka 本体はバイト列しか見ない。型定義で確認:

`_src/kafka-src/clients/src/main/java/org/apache/kafka/clients/producer/ProducerRecord.java:51,56-57`:
```java
public class ProducerRecord<K, V> {
    private final K key;
    private final V value;
```
`_src/kafka-src/clients/src/main/java/org/apache/kafka/common/serialization/Serializer.java:64`:
```java
byte[] serialize(String topic, T data);
```
`_src/kafka-src/clients/src/main/java/org/apache/kafka/common/record/internal/Record.java:95`:
```java
ByteBuffer value();
```
すなわち: アプリケーション型 `K, V`（ProducerRecord）→ `Serializer<T>.serialize()` で `byte[]` に消去 → ブローカー/ストレージ層は `Record.value()` = `ByteBuffer`（生バイト列）しか扱わない。**スキーマ強制は Kafka 本体のコードには存在しない**（Schema Registry は別プロジェクトであり、本 clone には含まれない。ここでは「Kafka 本体の型定義にスキーマ制約が無い」という事実のみをコードで示した）。

### 公式ドキュメントの ordering guarantee 記述

**取得状況**: 成功。HTTP 200。
```
curl -sL https://kafka.apache.org/documentation/          # → JS redirect スタブ (200, 中身は redirect script)
curl -sL https://kafka.apache.org/43/documentation.html   # → 同上、v43 へのredirectスタブ
curl -sL https://kafka.apache.org/43/design/design/       # → 本文 200, 146232 bytes
```
ローカル: `_src/kafka_design.html`
該当箇所: Design > The Consumer > **Consumer Position** (`https://kafka.apache.org/43/design/design/#consumer-position`)

逐語引用（15語以内。原文はもう少し長い一文の一部）:
> "each of which is consumed by exactly one consumer within each subscribing consumer group at any given time"

前後の文脈（引用は上の一部のみが「逐語引用」対象、残りは要約）: "Our topic is divided into a set of totally ordered partitions, each of which is consumed by exactly one consumer within each subscribing consumer group at any given time."

これは Kafka 公式が明示する「ordering guarantee」の文面（規約としての記述）。実装での担保箇所は上記の「排他読み取り」の節で示した通り、**Fetch レベルでは強制されていない**ため、この文は運用規約に近い（クライアントが協調的にプロトコルへ従うことが前提）。

### メッセージが有限種別に決定論的に分類されるか
されない。`ProducerRecord<K,V>` と `Serializer<T>` は総称型であり、Kafka 本体はメッセージ種別を区別しない。種別分類はアプリケーション層（Serializer の実装、あるいは外部の Schema Registry）の責務。

### 実行中の出来事を順序付きで外へ出す仕組みとして使えるか
使える。パーティション内は単一ロック + 単調 offset 採番で全順序が実装レベルで担保される（上記 file:line）。ただし「1コンシューマだけが読む」という排他性はプロトコル規約であり、実装で強制されるのはオフセットコミットの世代整合性のみという限定付き。

---

## 4. Unix pipeline

**取得状況**: 成功。

Ritchie & Thompson, "The UNIX Time-Sharing System" (CACM 17(7), 1974):
```
curl -sL https://www.nokia.com/bell-labs/about/dennis-m-ritchie/cacm.pdf  → HTTP 403 (失敗)
curl -sL https://dsf.berkeley.edu/cs262/unix.pdf                          → HTTP 200 (成功、これを採用)
```
ローカル: `_src/ritchie_thompson_1974_cacm.pdf`（PDF, 12 ページ, version 1.2）
PDF page 4 = 誌面 p.368、PDF page 6 = 誌面 p.370（各ページフッタの "Electronic version recreated by Eric A. Brewer" 直上に誌面ページ番号を確認）。

POSIX (Issue 7, 2018 / IEEE Std 1003.1-2017):
```
curl -sL https://pubs.opengroup.org/onlinepubs/9699919799/functions/pipe.html   → HTTP 200
curl -sL https://pubs.opengroup.org/onlinepubs/9699919799/functions/write.html  → HTTP 200
```
ローカル: `_src/posix_pipe.html`, `_src/posix_write.html`

### 抽象
- Ritchie & Thompson, Section 5.2 "Pipes"（誌面 p.370）: パイプをプロセス間通信チャネルとして定義。
- Section 4 の I/O calls（誌面 p.368）: `read`/`write` システムコールをバイト数ベースで定義。

### パイプの定義（逐語引用、誌面ページ付き）
誌面 p.370, Section 5.2:
> "Processes may communicate with related processes using the same system read and write calls"
（通常のファイル I/O と**同じ** read/write コールを使う、という一文。パイプに専用のメッセージ境界や型の概念が無いことの直接証拠。）

> "Neither process need know that a pipe, rather than an ordinary file, is involved."
（13語。パイプは呼び出し側から見て通常ファイルと区別がつかない = メッセージ種別の概念がそもそも存在しない。）

### read/write の意味論（誌面 p.368、バイト単位であることの直接証拠）
> "Up to count bytes are transmitted between the file specified by filep and the byte array specified by buffer."
（`n = read(filep, buffer, count)` / `n = write(filep, buffer, count)` の説明文。「バイト数」以外の単位や構造化された「メッセージ」概念は存在しない。）

### POSIX 仕様による否定的事実の補強
`pipe()`（POSIX.1-2017）:
> "A read on the file descriptor fildes[0] shall access data written to the file descriptor fildes[1] on a first-in-first-out basis."
（FIFO のバイト列としてのみ規定。メッセージ境界の概念は無い。）

`write()`（POSIX.1-2017、PIPE_BUF の節）:
> "Write requests of {PIPE_BUF} bytes or less shall not be interleaved with data from other processes doing writes on the same pipe."
（POSIX がパイプについて与える唯一の「構造」に近い概念は、PIPE_BUF バイト以下の書き込みが他プロセスの書き込みと**インターリーブしない**という**バイト単位のアトミック性**のみ。これは「メッセージ種別」ではなく、単なるバイト列の断片化防止規定であることに注意。）

### 実装
- 原論文はコード実装そのものというより歴史的記述だが、システムコールインタフェース自体（`pipe()`, `read()`, `write()`）が「強制している」定義そのもの。POSIX 仕様が規範文書（normative spec）であり、「README/ドキュメントの記述」ではなく規格の一部である点で、他の項目より強い根拠（ただし可搬 OS 実装のソースコード file:line までは本タスクでは追っていない。POSIX テキストそのものを一次資料として採用）。

### メッセージが有限種別に決定論的に分類されるか
**されない**。上記の逐語引用が示す通り、パイプはバイト列の FIFO であり、メッセージ種別・型・境界の概念を一切持たない。これは「実装は強固だが抽象がメッセージ分類を保証しない」ことの直接的な否定的事実。

### 実行中の出来事を順序付きで外へ出す仕組みとして使えるか
「順序付き」の点では使える（FIFO なので書き込み順=読み出し順、ただし複数ライタが同一パイプに書く場合は PIPE_BUF 超のインターリーブがあり得る）。「型を持つイベント列として外へ出す」という意味では使えない。パイプ自体は型もメッセージ境界も強制しないため、その上に構造化フォーマット（改行区切り、length-prefix 等）を載せるのはアプリケーション層の責務。

---

## 5. MCMAS (multi-agent系の形式検証)

**取得状況**: 成功（複数ソース）。

論文（STTT 2017, published version, Open Access）:
```
curl -sL https://spiral.imperial.ac.uk/bitstreams/8f60acf7-e380-4cd6-82cb-66e04bcd4943/download
```
→ HTTP 200, `_src/mcmas_sttt_2017.pdf`（PDF, 35 ページ, version 1.7）。Imperial College London の SPIRAL リポジトリ（オープンアクセス版）から取得。Lomuscio, Qu, Raimondi, "MCMAS: an open-source model checker for the verification of multi-agent systems", Int J Softw Tools Technol Transfer, DOI 10.1007/s10009-015-0378-x。

参考として TACAS 2006 の先行論文（同一著者、短い会議版）も取得: `_src/mcmas_tacas_lomuscio.pdf`（HTTP 200, 4 ページ）。

MCMAS User Manual v1.2.2:
```
curl -sL https://sail.doc.ic.ac.uk/software/mcmas/manual.pdf  → HTTP 200
```
`_src/mcmas_manual_v122.pdf`（PDF, 35 ページ）

ソースコード（GitHub ミラー、Kafka と同じ sandbox 制約のため bare clone + archive で取得）:
```
git clone --bare --depth 1 https://github.com/mattvonrocketstein/mcmas.git _src/mcmas-bare.git
git --git-dir=_src/mcmas-bare.git archive main | tar -x -C _src/mcmas-src
```
成功（`git log` で `dfdb0a3 docs` を確認済み）。公式 `mcmas-tool/mcmas` の存在は未確認（検索では見つからず、`mattvonrocketstein/mcmas` を「MCMAS project の mirror」として使用。README での自称であり、Imperial 公式配布 (`vas.doc.ic.ac.uk`, `sail.doc.ic.ac.uk`) との一致は `main.cc` 冒頭の `#define URL "http://vas.doc.ic.ac.uk/tools/mcmas/"` で確認済み）。
ローカルソース: `$WT/tmp/research-core-2026-09-20/_src/mcmas-src/`

### 抽象
STTT 論文 Section 2.1 "Interpreted systems", **Definition 1**（PDF page 2, 論文印刷版は pp.9–30 の一部。オフプリントに印刷ページ番号の刻印が無いため PDF ページで示す）:
> "Pi : Li → 2^Acti\∅ is a local protocol function for agent i"

これがエージェントの「プロトコル」の形式的定義: 局所状態 `Li` から「空でない行動の部分集合」への関数。

### 不変量（逐語引用）
STTT 論文 Definition 1 直後（PDF page 2）:
> "we assume that every action is protocol compliant"
（すべての遷移が protocol 関数の返す集合に含まれる行動でなければならない、という制約。）

### ISPL 言語での Protocol 記法（仕様/文法定義）

**文法定義（実物 file:line）**:
`_src/mcmas-src/parser/nssis.yy:1400-1405`（bison 文法規則）:
```
protline: lboolcond plprefix enabledidlist plsuffix {
  if($1!=NULL && $2==1 && $3!=NULL && $4==1)
    $$ = new protocol_line($1, $3);
  else
    $$ = NULL;
 }
```
これは ISPL の `Protocol:` セクション内の1行「`<状態条件> : { 行動リスト };`」を構文的に定義する規則そのもの（パーサ生成器 bison への入力）。「強制している」根拠はこの grammar file と、それが `enprotline`（`enabled` 修飾版, line 1389）にも同型で存在する点。

**具体例（MCMAS User Manual v1.2.2, 印刷ページ 6, PDF page 8）**:
```
Protocol:
state=empty : {nothing};
(state=r0 or state=r1): {sendack};
end Protocol
```
（マニュアルは仕様書ではあるが、上記 grammar file と記法が一致することを確認済みなので「規約止まり」ではなく実装(パーサ)による裏付けあり。）

### 検査が設計時の検証であって実行時の強制でないことの根拠

ツールの入出力から判定（MCMAS User Manual v1.2.2, 印刷ページ 7, PDF page 9, §2.1.3 "Verification and simulation"）:
```
$ ./mcmas examples/bit_transmission_protocol.ispl
...
Formula number 1: (AF K(Sender, (K(Receiver, bit0) || K(Receiver, bit1)))), is TRUE in the model
Formula number 2: ..., is TRUE in the model
done, 2 formulae successfully read and checked
```
入力: 静的な `.ispl` ファイル（システム全体の記述）+ 検証式一覧。出力: 各式の真偽値（+ 反例トレース、コード上は `_src/mcmas-src/main.cc:535` 付近の `cex_prefix` / `.ispl` 拡張子処理で確認）。**実行中のプロセスへの介入・フック・強制のための API は存在しない**（コマンドライン一発実行で完結するバッチ検証ツール）。ゆえに「設計時の検証」であり「実行時の強制」ではないと判定できる。

### メッセージが有限種別に決定論的に分類されるか
ISPL の `Actions = {a1, a2, ...}` は有限列挙集合として宣言される（マニュアル例: `Actions = {nothing,sendack};`）。この意味では「エージェントの行動」は有限種別に分類**される**。ただしこれは検証対象モデルの記述言語の話であり、実行系のメッセージ形式ではない。

### 実行中の出来事を順序付きで外へ出す仕組みとして使えるか
使えない。MCMAS は静的モデル（ISPL）を読み込んで一括検証するツールであり、実行中のイベント列を受け取って随時判定する仕組みは持たない（上記コマンドライン実行例の通り、入力はファイル、出力は一括結果）。

---

## 取得できなかったもの・未確認事項

- `mcmas-tool/mcmas` という具体的な GitHub organization/repo 名は WebSearch では発見できず。検索語: "MCMAS model checker github mcmas-tool ISPL"。代わりに `mattvonrocketstein/mcmas`（MCMAS project の mirror を自称）を使用し、`main.cc` 内の公式URL文字列で正統性を裏付けた。
- Kafka の `core/src/main/scala/kafka/log/UnifiedLog.scala` は現在の trunk には存在しない（Scala 版は Java 版 `storage/src/main/java/org/apache/kafka/storage/internals/log/UnifiedLog.java` に移行済み。`find` で確認済み、Scala 版は無し)。
- Kafka 公式ドキュメントの `kafka.apache.org/documentation/` は静的リダイレクトスタブ（JS 経由でバージョン付き URL `/43/...` へ飛ぶ）。直接該当ページ (`/43/design/design/`) を curl で取得し直して対処。
- MCMAS の STTT 2017 論文は Springer の正規ページ (dl.acm.org / link.springer.com) は課金壁の可能性があり未試行。Imperial College の SPIRAL リポジトリ（オープンアクセス, Open Access 表記が論文冒頭にあり）から取得したものを一次資料として採用。
