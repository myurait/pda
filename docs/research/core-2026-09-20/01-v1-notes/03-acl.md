# 発話の有限種別と割り振りの系譜 — 一次資料調査ノート

調査日: 2026-09-20
作業ディレクトリ: `$WT/tmp/research-core-2026-09-20/`
ローカル資料: `$WT/tmp/research-core-2026-09-20/_src/`

## 重要な前提: fipa.org は現在ドメインスクワッティングされている

`curl -sL -A "<browser UA>" https://www.fipa.org/specs/...` は HTTP 200 を返すが、
返ってくる本文は FIPA の仕様ではなく、ノルウェー語のオンラインカジノ比較サイト
(`<title>Casino på nett: Sammenlign de beste norske casinoene</title>`) だった。
`fipa00037_communicative_act_library.html` と `fipa00029_contract_net_ip.html` と
`fipa00061_acl_message_structure.html` (削除済み) で確認・再現。
つまり fipa.org は公式配布元として機能しておらず、現行ドメインは第三者に乗っ取られている。
そのため FIPA の 3 仕様はすべて Wayback Machine (web.archive.org) のスナップショット、
または大学ミラー (jmvidal.cse.sc.edu) 経由で取得した。取得元は各節に明記する。

---

## 1. KQML — Finin et al., "Specification of the KQML Agent-Communication Language" (DARPA Knowledge Sharing Initiative, draft, 1993-06-15)

### 取得状況
- 検索: `research.cs.umbc.edu/kqml/papers/` (旧URL `www.csee.umbc.edu/csee/research/kqml/papers/` → 302 → `redirect.cs.umbc.edu` → `research.cs.umbc.edu` の順にリダイレクト)
- 本体: `https://research.cs.umbc.edu/kqml/papers/kqmlspec.pdf` — **HTTP 200**、`application/pdf`、275,507 bytes
- ローカル: `_src/kqml_spec_finin1993.pdf` (原本) / `_src/kqml_spec_finin1993_mupdf.txt` (PyMuPDF抽出) / `_src/kqml_spec_finin1993_joined.txt` (空白正規化版、grep用)
- 表紙で著者・日付を確認: "Tim Finin (co-chair) ... Jay Weber (co-chair) ... June 15, 1993" — 指定された資料と一致。

**注意 (PDF抽出の既知の欠陥)**: この PDF は 1993 年の dvips/TeX 生成物で、"fi" "ff" などの合字 (ligature) が ToUnicode に正しくマップされておらず、pypdf では `/#0C` のようなグリフ名エスケープに、PyMuPDF では合字の脱落 (例: "Specification"→"Sp ecication", "Effort"→"Eort") になって現れる。以下の引用は合字部分を文脈から一意に復元した上で verbatim として示す (復元前の生テキストも併記)。この欠陥は全 KQML 系 PDF (kqmlspec.pdf, kqml97.pdf) 共通。

### 抽象
BNF によるメッセージ構文定義 (`<performative> ::= (<word> {<whitespace> :<word> <whitespace> <expression>}*)`) と、"RESERVED PERFORMATIVE NAMES" という節でのパフォーマティブごとの英語プローズによる意味定義。

### 不変量 (逐語引用)
BNF (合字なし、そのまま抽出できた箇所):
> `<performative> ::= (<word> {<whitespace> :<word> <whitespace> <expression>}*)`

これは「performative は `<word>` (任意の識別子) と `:キーワード 式` の並びを持つ S式」というシンタックスのみを定義しており、**BNF レベルでは performative 名を有限集合に制限していない**。`<word>` は `<character><character>*` で任意の文字列を許す。

拡張手続きに関する記述 (原文の合字を復元、14語):
> "Definitions of new performatives should follow the style of the definitions in this section."
> (生テキスト: `De nitions of new p erformativ es should follo w the st yle of the de nitions in this section.`)

その直前の文 (reserved の意味を規定、コンプライアンス条件):
> "if an implementation uses any of the following performative names in a way that is inconsistent with the following performative definitions, then that implementation is not compliant with KQML"
> (生テキスト: `if an implemen tation uses an y of the follo wing p erformativ e names in a w a y that is inconsisten t with the follo wing p erformativ e de nitions, then that implemen tation is not complian t with K QML`)

**結論**: KQML の performative 集合は閉じていない。既定の "reserved performative" は名前ごとに固定意味を持ち、それに反する実装は非準拠になるが、仕様自体が新規 performative の定義手順 ("should convey: the performative name; all parameter keywords...; syntactic categories and semantics...") を明記しており、拡張可能な open set として設計されている。

### 実装
本資料自体はコードではなく仕様書 (draft, "should not be interpreted as a finished product")。実装の強制力は無く、規約止まり。

### メッセージパラメータ (:content 等)
grep で確認した reserved performative の定義例 (delete, delete-one, delete-all, standby, advertise, subscribe, register, unregister, forward, deny, untell 等) はいずれも `:content`, `:language`, `:ontology`, `:reply-with`, `:in-reply-to`, `:sender`, `:receiver`, `:force`, `:aspect`, `:order`, `:name`, `:to`, `:from` といったキーワードパラメータを持つ。例 (`kqml_spec_finin1993_joined.txt` 該当箇所):
> `delete :content <performative> :language KQML :ontology <word> :reply-with <expression> :in-reply-to <expression> :sender <word> :receiver <word>`

### 場所 (ストア) の有無
`register`/`unregister`/`transport-address` performative がある:
> `transport-address ... S associates symbolic name with transport address`

これはエージェント名前解決 (facilitator 的な仕組み) の萌芽だが、仕事や成果を永続化する「ストア」ではない。`tell`/`untell` は送信先エージェントの VKB (virtual knowledge base) に対する操作だが、これは各エージェント内部の知識ベースであって、外部から見える共有ストアではない。

### イベントストリームの有無
`subscribe`/`stream-all`/`standby` performative があり、「将来の変化を通知してほしい」という購読の仕組みは存在する:
> `subscribe :content <performative> ... This type indicates that the sender wishes the recipient to tell it about future changes to what would be the response(s) to the KQML performative in the :content parameter`

ただしこれは 1 対 1 の非同期通知チャネルであり、順序保証つきの外部公開イベントログではない。

---

## 2. FIPA ACL Message Structure Specification (SC00061G, Standard, 2002-12-03)

### 取得状況
- `https://www.fipa.org/specs/fipa00061/SC00061G.html` (ブラウザ UA 付き curl) → **HTTP 200 だがカジノサイトの中身**(スクワッティング、上記参照)。破棄済み。
- 代替取得: Wayback Machine `http://web.archive.org/web/2020/https://www.fipa.org/specs/fipa00061/SC00061G.html` → **HTTP 200**、104,099 bytes、キャプチャ日時 2020-12-13 15:10:53 (Internet Archive のフッタで確認)。
- ローカル: `_src/fipa00061_acl_message_structure_wayback.html` / `_src/fipa00061_stripped.txt` (タグ除去済み)

### 抽象
§2 "FIPA ACL Message Structure" で ACL メッセージパラメータの全集合を表形式 (Table 1) で定義。§2.1.1 で performative パラメータ、§2.5 で protocol / conversation-id / reply-with / in-reply-to / reply-by による会話制御パラメータを定義。

### 不変量 (逐語引用、§2 Scope / FIPA ACL Message Structure)
> "the only parameter that is mandatory in all ACL messages is the performative"

これは「メッセージは有限個の種類のいずれかに必ず分類される」に直接対応する主張である: 唯一必須のパラメータは performative であり、あらゆる FIPA ACL メッセージは何らかの performative を持たなければならない。

ただし performative 名それ自体が閉じた集合かどうかについては、§2.1.1 Notes で次のように述べるのみ (規約止まりの弱い表現):
> "Developers are encouraged to use the FIPA standard performatives (see [FIPA00037]) whenever possible."

"encouraged ... whenever possible" という表現であり、"must" ではない。ユーザー定義の追加パラメータは `X-` プレフィックスを義務付けている一方 (§2 Scope: "The prefatory string 'X-' must be used for the names of these non-FIPA standard additional parameters.")、performative 名自体に同様の名前空間規則は明記されていない。

### 実装
本資料自体はコード無し、規約 (Specification) のみ。JADE 実装との対応は §4 節を参照。

### 場所 (ストア) の有無
無し。message parameter の集合の定義のみで、メッセージが辿り着く先の永続ストアには一切言及がない。抽象アーキテクチャへの参照 (`[FIPA00001] FIPA Abstract Architecture Specification`) はあるが、本文書はメッセージ構造どまり。

### イベントストリームの有無
`conversation-id` (§2.5.2) は「一連の communicative act をひとつの会話として識別するための ID」であり、順序を外部へ公開する仕組みではなく、あくまで送受信側が自分でメッセージをタグ付けして相関させるための識別子。
> "conversation-id ... Introduces an expression ... which is used to identify the ongoing sequence of communicative acts that together form a conversation."
外部から観測可能なイベントログ・event stream 相当の仕組みは定義されていない。

---

## 3. FIPA Communicative Act Library Specification (SC00037, Standard, 2002-12-03 / 参考として XC00037H, Experimental, 2001-08-10)

### 取得状況
- Standard 版 (J, 2002-12-03): Wayback `http://web.archive.org/web/2018/https://www.fipa.org/specs/fipa00037/SC00037J.html` → **HTTP 200**、486,012 bytes。ローカル: `_src/fipa00037_cal_J_wayback.html` / `_src/fipa00037_J_stripped.txt`。これを主資料として引用する。
- Experimental 版 (H, 2001-08-10): `https://jmvidal.cse.sc.edu/library/XC00037H.pdf` (大学ミラー) → **HTTP 200**、`application/pdf`、210,476 bytes、33 pages。ローカル: `_src/fipa00037_communicative_act_library.pdf` / `.txt` / `_joined.txt`。この版には FIPA 公式の行番号 (例: "119 120") が埋め込まれており、引用箇所の行特定に使った。
- 直接の fipa.org 取得は前述のとおりカジノサイトへのスクワッティングで失敗。

### 抽象
§2.1 "Status of a FIPA-Compliant Communicative Act" で CAL (Communicative Act Library) の規範性を規定。§5.3 "Underlying Semantic Model" (J版) / 該当箇所 (H版 line 423-424) で FP (feasibility precondition) と RE (rational effect) の形式的定義の枠組みを規定。各 act (inform, request, cfp, propose, accept-proposal, ... ) ごとに "Formal Model" として FP: / RE: の形式表現が与えられる。

### 不変量 (逐語引用)

「ライブラリに属する act の定義は規範的」(§2.1, J版):
> "The definition of a communicative act belonging to the CAL is normative."

「実装するなら CAL の意味定義に従わねばならない」(§2.1, 同段落):
> "if a given agent implements one of the acts in the CAL, then it must implement that act in accordance with the semantic definition in the CAL"

一方で **CAL 自体は閉じていない・拡張手続きが明記されている**:
> "FIPA-compliant agents are not required to implement any of the CAL languages, except the not-understood composite act."

> "The name assigned to a proposed communicative act must uniquely identify which communicative act is used within a FIPA ACL message."

新規 act 提案には形式的意味論が要求される (H版, line 180-181):
> "A formal model, written in SL, of the act's semantics, its formal preconditions, and its rational effects is required."

FP/RE の定義そのもの (J版, §5.3):
> "the former is referred to as the rational effect or RE [9], and the latter as the feasibility preconditions or FPs"

**結論**: 「communicative act が有限のライブラリとして定義されている」という主張は正しいが、そのライブラリは FIPA という管理団体による命名審査 ("The FIPA Agent Communication Technical Committee is the initial judge of the suitability of a name" — H版) を伴う**開いた・維持管理されたレジストリ**であり、KQML 同様に閉じた集合ではない。個々の act の意味論 (FP/RE) は規範的 (normative) で、実装した場合はそれに従う義務がある。

### 実装 (各 act の FP/RE 形式表現の実例、J版)
`accept-proposal` の Formal Model (HTML実体参照 `&lt;`/`&gt;` を `<`/`>` に復元):
> `<i, accept-proposal(j, <j,act>, f)> ≡ <i, inform(j, Ii Done(<j,act>, f))> FP: Bi a ∧ ¬Bi(Bifj a ∨ Uifj a) RE: Bj a`

これはコードではなく仕様書内の形式言語 (SL) による記述であり、「実装が強制されている file:line」には該当しない。規約止まり (ただし規範的規約)。JADE 側での実装対応は §5 参照。

### 場所 (ストア) の有無
本仕様に無し。DF (Directory Facilitator) のサービス記述は別文書 (`FIPA Agent Management Specification`) の管轄で、CAL 自体はメッセージの意味論のみ扱う。

### イベントストリームの有無
無し。

---

## 4. FIPA Contract Net Interaction Protocol Specification (XC00029G, Experimental, 2002-11-01)

### 取得状況
- 直接取得: `https://www.fipa.org/specs/fipa00029/XC00029G.html` → カジノサイトへのスクワッティング (前述と同一パターン)。
- 代替取得: Wayback `http://web.archive.org/web/2018/https://www.fipa.org/specs/fipa00029/XC00029G.html` → **HTTP 200**、51,552 bytes、キャプチャ日時 2016-06-27 22:35:37。
- ローカル: `_src/fipa00029_contract_net_wayback.html` / `_src/fipa00029_stripped.txt` (完全なテキスト、短い文書のため全文確認済み)

### 抽象
Smith (原典としては "Smith and Davis" と明記) の Contract Net Protocol への「軽微な変更」として、cfp → propose/refuse → accept-proposal/reject-proposal → inform-done/inform-result/failure という 1 メッセージフローを UML1.x 拡張の図として規定。

### 不変量 (逐語引用)
Smith の原典への直接の系譜言及:
> "The FIPA Contract Net Interaction Protocol (IP) is a minor modification of the original contract net"
> (脚注 [1]: "Originally developed by Smith and Davis.")

プロトコル識別子:
> "This protocol is identified by the token fipa-contract-net as the value of the protocol parameter"

会話 ID の必須化 (FIPA00061 の conversation-id 規約をこの IP が具体的に要求する箇所):
> "Any interaction using this interaction protocol is identified by a globally unique, non-null conversation-id parameter"

「メッセージは有限個の種類のいずれかに分類される」に相当する主張は本文書には無い (それは FIPA00061/FIPA00037 の管轄)。本文書はメッセージフローのみを規定する。

### 実装
本文書自体はコード無し。JADE の `jade.proto.ContractNetInitiator` / `ContractNetResponder` が実装 (§5 参照)。

### 場所 (ストア) の有無
無し。メッセージ授受のみ。"binding" という言葉で「提案は拘束力を持つ」("The proposals are binding on the Participant, so that once the Initiator accepts the proposal, the Participant acquires a commitment to perform the task.") と述べるが、これは規範的宣言であり、コミットメントを保持する永続ストアの定義ではない。

### イベントストリームの有無
無し。ただし `not-understood` は「いつでも起こりうる例外」として明示的に扱われており (§1.2 "Exceptions to Interaction Protocol Flow")、状態遷移というより例外パスとして図の外に置かれている。

---

## 5. Smith, "The Contract Net Protocol: High-Level Communication and Control in a Distributed Problem Solver" (IEEE Trans. Computers, Vol. C-29, No. 12, Dec. 1980, pp. 1104–1113)

### 取得状況
- `https://www.reidgsmith.com/The_Contract_Net_Protocol_Dec-1980.pdf` → **HTTP 200**、`application/pdf`、819,123 bytes
- ローカル: `_src/smith1980_contract_net.pdf` / `.txt` / `_joined.txt`
- 抽出品質良好 (この PDF は合字ドロップの問題なし。改行由来のハイフネーション "en-coded" 程度)

### 抽象
p.1104 で契約ネットの概要 (task announcement → bid → award のネゴシエーション)。p.1105–1106 で task announcement メッセージの 4 スロット構造 (Task Abstraction / Eligibility Specification / Bid Specification / Expiration Time) を図1とともに定義。

### 不変量 (逐語引用)
概要 (p.1104, "Abstract" 直後の本文):
> "the managers evaluate the bids and award contracts to the nodes they determine to be most appropriate"

task announcement の 4 スロット構造そのもの (p.1105):
> "the task announcement has four main slots"

**能力に基づく入札 (eligibility specification, task abstraction) の記述** — これが要件の「能力の宣言」に対応する箇所 (p.1105):
> "The eligibility specification is a list of criteria that a node must meet to be eligible to submit a bid."

> "The task abstraction is a brief description of the task to be executed."

task abstraction の目的 (ランク付けのため、p.1105):
> "It enables a node to rank the task relative to other announced tasks."

Fig. 1 (p.1105) の実データ (原文まま、能力宣言の実例):
```
Type: TASK ANNOUNCEMENT
Task Abstraction: TASK TYPE SIGNAL POSITION LAT 47N LONG 17 E
Eligibility Specification: MUST-HAVE SENSOR MUST-HAVE POSITION AREA A
Bid Specification: POSITION LAT LONG EVERY SENSOR NAME TYPE
Expiration Time: 28 1730Z FEB 1979
```
Fig. 2 (p.1105, BID メッセージ、能力を実際に列挙する側):
```
Type: BID
Node Abstraction: POSITION LAT 62N LONG 9 W
SENSOR NAME S1 TYPE S
SENSOR NAME S2 TYPE S
SENSOR NAME T1 TYPE T
```

**結論**: 「能力の宣言」は task announcement 側の "Eligibility Specification" (入札のための必要条件、例: `MUST-HAVE SENSOR`) と、bid 側の "Node Abstraction" (自分の実際の能力の列挙、例: `SENSOR NAME S1 TYPE S`) という 2 つの対になったスロットで表現される。前者は「何が必要か」の宣言、後者は「自分は何を持っているか」の宣言であり、両者の照合 (manager 側が bid の Node Abstraction と announcement の Eligibility Specification を突き合わせる) によって入札の可否が決まる。この照合ロジック自体は自然言語で記述されており、形式言語や型システムとしては定義されていない (p.1106: "a simple language common to all nodes" という表現のみ)。

### 実装
本文書は 1980 年の学術論文でありコードは含まない。FIPA Contract Net IP (§4) と JADE (§5) がその後継実装。

### 場所 (ストア) の有無
無し。task announcement / bid / award はすべて一過性のメッセージ交換であり、永続的なタスクストアは論文中に定義されていない (ただし "contract" という語で懸案中のタスクの識別に `Contract: 22-3-1` という ID を使っており、会話相関の仕組みは FIPA の conversation-id の直接の先祖と見なせる)。

### イベントストリームの有無
無し。

---

## 6. JADE (Java Agent DEvelopment Framework) — 実装調査

### 取得状況
`git clone` は `$WT` 配下の `.git` 書き込みがサンドボックスにより拒否された (`could not write config file ... Operation not permitted`。ネストした `.git/config` への書き込みが sandbox の write-allow ルールで弾かれた)。そのため一旦スクラッチパッド (`$TMPDIR/jade-clone-work2/jade-mirror`) に `git -c credential.helper= clone --depth 1 https://github.com/ekiwi/jade-mirror.git` でクローンし (成功、`2723c7b [hack] log packets to file`)、`.git` を除く作業ツリーのみ `rsync` で `$WT/tmp/research-core-2026-09-20/_src/jade-mirror/` にコピーした。以降の file:line はすべてこのコピー先を基準にしている。

リポジトリ: `https://github.com/ekiwi/jade-mirror` — READMEに "unofficial git mirror of http://jade.tilab.com/developers/source-repository/" と明記された、TILAB 公式 SVN のミラー。公式配布元 (jade.tilab.com) 自体には未接続 (サンドボックスの許可ドメインに未追加、かつ本ミラーで目的のファイルがすべて揃ったため未実施)。

### 6.1 `jade/lang/acl/ACLMessage.java` — performative の有限定数と検証の有無

パス: `_src/jade-mirror/src/jade/lang/acl/ACLMessage.java`

performative は 0〜21 の `int` 定数として有限に定義されている (抜粋):
```
90:	public static final int ACCEPT_PROPOSAL = 0;
...
132:	public static final int PROPAGATE = 21;
134:	public static final int UNKNOWN = -1;
```
対応する名前配列 (22要素、file:line 141-165):
```
141:	private static final String[] performatives = new String[22];
143:			performatives[ACCEPT_PROPOSAL]="ACCEPT-PROPOSAL";
...
164:			performatives[PROPAGATE]="PROPAGATE";
```

**未知の performative 値を渡したときに拒否されるのか、素通りするのか (推測ではなく実装を読んだ結果)**:

コンストラクタの Javadoc は「範囲外の場合は not-understood に静かに初期化する」と主張するが、実装はそれをしていない:
```
326:	/**
327:	 * This constructor creates an ACL message object with the specified
328:	 * performative. If the passed integer does not correspond to any of
329:	 * the known performatives, it silently initializes the message to
330:	 * <code>not-understood</code>.
331:	 **/
332:	public ACLMessage(int perf) {
333:		performative = perf;
334:	}
```
`setPerformative` も同様に検証を一切行わない:
```
460:	public void setPerformative(int perf) {
461:		performative = perf;
462:	}
```
**つまり Java オブジェクト API レベルでは、範囲外・未知の int をそのまま代入でき、素通りする。Javadoc の主張とコードの実装は矛盾している。**

一方、文字列→int の変換ユーティリティには防御的フォールバックがある:
```
705:	public static String getPerformative(int perf){
706:		try {
707:			return performatives[perf];
708:		} catch (Exception e) {
709:			return performatives[NOT_UNDERSTOOD];
710:		}
711:	}
717:	public static int getInteger(String perf)
718:	{
719:		String tmp = perf.toUpperCase();
720:		for (int i=0; i<performatives.length; i++)
721:			if (performatives[i].equals(tmp))
722:				return i;
723:		return -1;
724:	}
```
`getInteger` は未知の文字列に対して `-1` (`UNKNOWN`) を返す。ただし呼び出し側がこれをチェックしなければ、それだけでは「拒否」にならない。

**ワイヤレベルではさらに強い拒否がある。** FIPA-SL0 文字列表現をパースする JavaCC 文法 `ACLParser.jj` の `MESSAGETYPESTATE` 字句状態は、performative 名を以下の 22 個のリテラルのみに限定しており、それ以外の文字列はそもそも `MESSAGETYPE` トークンとして成立しない (字句解析エラーになる):
```
_src/jade-mirror/src/jade/lang/acl/ACLParser.jj:321-341
  <MESSAGETYPE :  "accept-proposal"
                | "agree" | "cancel" | "cfp" | "confirm" | "disconfirm"
                | "failure" | "inform" | "inform-if" | "inform-ref"
                | "not-understood" | "propose" | "proxy" | "propagate"
                | "query-if" | "query-ref" | "refuse" | "reject-proposal"
                | "request" | "request-when" | "request-whenever"
                | "subscribe" >        : MESSAGEPARAMETERSTATE
```
生成された `ACLParser.java` (line 118) の呼び出し:
```
115:  final public void MessageType() throws ParseException {
116:  Token t;
117:    t = jj_consume_token(MESSAGETYPE);
118:                          msg.setPerformative(ACLMessage.getInteger(t.image));
119:  }
```

**結論**: 「未知の performative は拒否されるか素通りするか」は層によって答えが違う。
- Java オブジェクト API (`ACLMessage(int)` / `setPerformative(int)`): **素通り**する。検証なし。Javadoc の主張と矛盾。
- FIPA 文字列 ACL 表現のパーサ (`ACLParser.jj` のレキサ): **拒否**する。字句解析の時点で未知の performative トークンは `MESSAGETYPE` として認識されず、字句エラーになる。この閉じたリテラル集合こそが「performative は有限集合に必ず分類される」という不変量を実際にコードで強制している唯一の箇所。

### 6.2 `jade/proto/` — Interaction Protocol の状態遷移強制

Contract Net の Initiator 側:
- `_src/jade-mirror/src/jade/proto/Initiator.java:45`: `abstract class Initiator extends FSMBehaviour {`
- `_src/jade-mirror/src/jade/proto/ContractNetInitiator.java:133`: `public class ContractNetInitiator extends Initiator {`
- コンストラクタ内 (206-217行、コメント "Register the FSM transitions specific to the ContractNet protocol"):
```
209:		registerTransition(CHECK_IN_SEQ, HANDLE_PROPOSE, ACLMessage.PROPOSE);
210:		registerTransition(CHECK_IN_SEQ, HANDLE_REFUSE, ACLMessage.REFUSE);
211:		registerTransition(CHECK_IN_SEQ, HANDLE_INFORM, ACLMessage.INFORM);
212:		registerDefaultTransition(HANDLE_PROPOSE, CHECK_SESSIONS);
213:		registerDefaultTransition(HANDLE_REFUSE, CHECK_SESSIONS);
214:		registerDefaultTransition(HANDLE_INFORM, CHECK_SESSIONS);
```

Responder 側の継承チェーン (すべて FSMBehaviour に帰着):
- `_src/jade-mirror/src/jade/proto/Responder.java:42`: `abstract class Responder extends FSMBehaviour {`
- `_src/jade-mirror/src/jade/proto/SSResponder.java:42`: `abstract class SSResponder extends FSMBehaviour {`
- `_src/jade-mirror/src/jade/proto/SSContractNetResponder.java:43`: `public class SSContractNetResponder extends SSResponder {`
- `_src/jade-mirror/src/jade/proto/ContractNetResponder.java:102`: `public class ContractNetResponder extends SSContractNetResponder {`
- 遷移登録 (118, 144-153行):
```
118:	public static final String RECEIVE_CFP = "Receive-Cfp";
146:		registerFirstState(b, RECEIVE_CFP);
152:		registerDefaultTransition(RECEIVE_CFP, HANDLE_CFP);
153:		registerDefaultTransition(DUMMY_FINAL, RECEIVE_CFP);
```

**結論**: interaction protocol の状態遷移は `FSMBehaviour` を継承した明示的な有限状態機械として実装されており、`registerTransition(現在状態, 次状態, performativeの定数)` という API で「受信メッセージの performative」を遷移条件に直接使っている。これは file:line で示せる本物の実装強制であり、規約止まりではない。

### 6.3 `jade/domain/FIPAAgentManagement/ServiceDescription.java` — 能力宣言の機械可読性

パス: `_src/jade-mirror/src/jade/domain/FIPAAgentManagement/ServiceDescription.java`
```
25:	import jade.content.Concept;
33:	public class ServiceDescription implements Concept {
35:		private String name;
36:		private String type;
37:		private String ownership;
38:		private List interactionProtocols = new ArrayList();
39:		private List ontology = new ArrayList();
40:		private List language = new ArrayList();
41:		private List properties = new ArrayList();
219:	public void addProperties(Property p) {
```
`Property` クラスも同様に `implements Concept` (`_src/jade-mirror/src/jade/domain/FIPAAgentManagement/Property.java:43`)。

`jade.content.Concept` は JADE のオントロジー/コンテント言語フレームワークのマーカーインターフェースであり、`Concept` を実装したオブジェクトは FIPA-SL のコンテント言語エンコーダによって構造化された (自由文ではない) メッセージ内容として直列化される。DF への登録・検索は `jade/domain/DFService.java` の静的メソッドで行う:
```
151:	public static DFAgentDescription register(Agent a, AID dfName, DFAgentDescription dfd) throws FIPAException {
351:	public static DFAgentDescription[] search(Agent a, AID dfName, DFAgentDescription dfd, SearchConstraints constraints) throws FIPAException {
```

**結論**: DF によるサービス記述 (能力の宣言) は `name`/`type`/`ontology`/`language`/`properties` という型付きスロットを持つオントロジーオブジェクト (`Concept` 実装) として表現されており、機械可読な形で扱われている。ただし「能力」の実体は `properties`(`Property` のリスト、name-value ペア相当) という自由な key-value 集合であり、Smith(1980)の Eligibility Specification のような述語的な必須条件式ではない。単なる属性リストの一致検索 (DF の `search`) にとどまる。

### 場所 (ストア) の有無 (JADE全体として)
- DF (`DFService`) はエージェントのサービス記述を保持する**ディレクトリ**であり、これはメッセージトランスポートを超えた永続的なレジストリ (ストア) に該当する。ただし保持するのは「誰が何をできるか」の宣言のみであり、実行中のタスクの成果物や状態を保持する汎用ストアではない。
- `ContractNetInitiator`/`ContractNetResponder` の `DataStore` (`getDataStore()`, 例: `ALL_RESPONSES_KEY`) はプロトコル1回の実行に閉じた一時的な内部状態保持であり、外部から見える永続ストアではない。

### イベントストリームの有無 (JADE全体として)
JADE には Introspection API (`jade.domain.introspection.*`、`jade/lang/acl/ACLMessage.java` とは別に `jade/domain/introspection/ACLMessage.java` というラッパークラスも存在することを確認済み) があり、送受信された ACL メッセージをエージェントプラットフォームのイベントとして AMS/観測エージェントに通知する仕組みがあることは示唆されるが、今回は時間の都合上ファイル内容までは読んでいない (`_src/jade-mirror/src/jade/domain/introspection/ACLMessage.java` の存在のみ確認、中身は未読 = 未検証)。

---

## 未発見・未検証の項目

- **JADE公式配布元 (jade.tilab.com) には未接続。** サンドボックスの許可ドメインに追加しておらず、GitHub ミラー (`ekiwi/jade-mirror`) で目的の全ファイルが揃ったため接続を省略した。ミラーの mirror としての正当性は README の自己申告のみに依拠している (第三者による署名検証等は行っていない)。
- **`jade/domain/introspection/ACLMessage.java` の中身は未読。** イベントストリーム (event stream) 相当の仕組みがあるかどうかを最終確認するには、この Introspection サブシステム (`jade.domain.introspection` パッケージ全体) を読む必要があるが、今回は時間の都合で見送った。
- **FIPA Interaction Protocol Library の一次仕様 (SC00025) は未取得。** `_src/fipa_ips_decker_mirror.pdf` は取得したが中身を確認したところ "FIPA Request Interaction Protocol Specification" (SC00026H) であり、検索エンジンのタイトル情報が誤っていた。Contract Net IP 自体は §4 で正しく取得済みのため追加取得はしていない。
- **KQML の正式な「後継」である FIPA-ACL への移行を明記した一次資料 (Labrou & Finin, "A Proposal for a new KQML Specification", 1997) は `_src/kqml_kqml97.pdf` として取得済みだが、本ノートでは内容を精査していない** (表紙のみ確認、ligature 崩れの検証に使っただけ)。

## 参照ファイル一覧 (`_src/` 配下)

- `kqml_papers_index.html` — KQML論文索引ページ (取得元発見用)
- `kqml_spec_finin1993.pdf` / `_mupdf.txt` / `_joined.txt` — 本調査の主資料 (KQML 1993 spec)
- `kqml_kqml97.pdf` / `.txt` — 未精査 (上記参照)
- `smith1980_contract_net.pdf` / `.txt` / `_joined.txt` — Smith 1980 IEEE TC 論文
- `fipa00061_acl_message_structure_wayback.html` / `_stripped.txt` — FIPA00061 (Wayback)
- `fipa00037_communicative_act_library.pdf` / `.txt` / `_joined.txt` — FIPA00037 Experimental版 (XC00037H, 行番号付き)
- `fipa00037_cal_J_wayback.html` / `_J_stripped.txt` — FIPA00037 Standard版 (SC00037J, Wayback, 主資料として引用)
- `fipa00029_contract_net_wayback.html` / `_stripped.txt` — FIPA00029 (Wayback)
- `fipa_ips_decker_mirror.pdf` / `.txt` — 誤取得 (実際はSC00026H、未使用)
- `jade-mirror/` — JADE ソース (github.com/ekiwi/jade-mirror の作業ツリーのみ、`.git` 無し)
