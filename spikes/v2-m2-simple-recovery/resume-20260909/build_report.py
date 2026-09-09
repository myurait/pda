"""Build the comparison from recorded observations; never upgrade partial proof."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib, html, json, re, subprocess
import markdown
R=Path(__file__).resolve().parent
E=R/'evidence'
used=set()
def evidence(name):
    used.add(name)
    return json.loads((E/name).read_text())
def table(headers, rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join('---' for _ in headers)+' |']+['| '+' | '.join(str(c).replace('|','／').replace('\n','<br>') for c in row)+' |' for row in rows])

letta=evidence('letta-candidate-summary.json')
assert letta['m2_eligible'] is False
letta_cases=[]
labels={'process-death':'主プロセス強制終了','worker-disappearance':'模擬worker消失','oom':'コンテナ内OOM','model-unavailable':'モデル停止→試験側が再起動','inode-full':'作業領域inode枯渇','byte-full':'作業領域容量枯渇'}
for case in sorted(labels):
    d=evidence('letta-fault-'+case+'@read-only-verdict.json')
    assert d['passed'] and d['native_state_equal'] and d['model']['matches']
    letta_cases.append([labels[case],f"{d['native_state_s']:.3f}秒",f"{d['model_readback_s_from_fault']:.3f}秒",'読取りのみ成立'])
assert len(letta_cases)==6 and letta['read_only_case_count']==6
lrepair=evidence('letta-live-bash-repair-verdict.json');assert lrepair['passed']
lcorrupt=evidence('letta-data-corruption-120s-verdict.json');assert lcorrupt['ready'] is False and lcorrupt['elapsed_s']>=120
for kind in ('bad-update','data-corruption'):
    d=evidence('letta-restore-'+kind+'-continued-verdict.json')
    assert d['checkpoint_equal'] and d['model_matches'] and not d['unattended_recovery_proven']
lquota=evidence('letta-persistent-home-bounded-probe.json')
lq=json.loads(lquota['probe']['stdout']);assert lq['bytes']>lq['work_cap_bytes']
evidence('letta-fault-model-unavailable@read-only-dependency-restored-by-injector.json')

hbase=evidence('r2-hermes-baseline-semantic-verdict.json');assert hbase['passed']
hcrash=evidence('r2-hermes-resumed-crash.json');assert hcrash['recovered']
for kind in ('bytes','inodes','memory-limit'):
    d=evidence('r2-hermes-resumed-'+kind+'.json')
    assert d['preserved'] and d['semantic']['passed']
    if kind=='memory-limit':assert 'oom_kill 1' in d['cgroup_memory_events']
hrepair=evidence('hermes-resumed-live-repair-verdict.json');assert hrepair['native_tool_repair_verified']
hboundary=evidence('hermes-resumed-resource-permission-boundary.json')
hq=json.loads(hboundary['stdout'].splitlines()[0]);assert hq['bytes_written']>hq['work_quota_bytes']
stop=evidence('r2-hermes-resumed-inflight-v2-stop.json')
settled=evidence('r2-hermes-resumed-inflight-v2-settled-stop.json')
orphan=evidence('r2-hermes-resumed-inflight-v2-orphan.json')
assert stop['stop_ack']['http']==200 and stop['stop_ack']['body']['status']=='stopping'
assert stop['native_state_after']['body']['status']=='interrupted' and stop['native_terminal_preserved'] is False
assert settled['native_state_after']['body']['status']=='cancelled'
for d in (stop,settled,orphan):assert d['single_effect'] and d['same_run_replayed'] and not d['delayed_tool_remaining']
hmemory=evidence('r2-hermes-memory-outage-v3.json');hmodel=evidence('r2-hermes-model-outage-v4.json')
for d in (hmemory,hmodel):assert d['saved_session']['http']==200 and d['preserved'] and d['semantic']['passed']
hrest=[]
for kind in ('data-corruption@verified','bad-update'):
    name='hermes-resumed-restore-'+kind
    d=evidence(name+'-verdict.json');o=evidence(name+'-unattended-observation.json')
    assert d['logical_state_preserved'] and d['external_restore_actions_required'] and not d['unattended_recovery_proven']
    assert not o['native_state_by_120s']
    for state in d['saved_native_run_states'].values():
        assert state['same_as_pre_backup'] and state['same_run_replayed'] and state['single_effect']
    hrest.append(['DB破損' if kind.startswith('data') else '起動不能更新＋非互換DB',f"{d['normal_state_after_external_restore_s']:.3f}秒",f"{d['total_from_fault_s']:.3f}秒",'試験側が標準import・正常版起動を実施'])
auth=evidence('managed-auth-boundary-current.json')
assert not any(auth['environment_presence'].values()) and not any(auth['hermes_dotenv_presence'].values())
source=evidence('hermes-source-reverification.json');assert not source['mismatches']
cleanup=evidence('final-dependency-retest-cleanup.json');assert cleanup['left']==[]

candidates=[
 {'id':'hermes-local','name':'Hermes 0.21.1 最小標準構成','capability':'native Runs・停止・idempotency、標準backup/import、Docker再起動','observed':'実プロセス停止・資源故障・依存障害後の読取り、実ツール修復、保存状態を含む外部復元を確認。停止受理直後の状態保持に反例。','custody':'正常版・互換データ・復元を起動する主体、永続領域の保護は自分側に残る。今回のread-only本体では自己更新も未実証。','verdict':'今回構成は未達。M3へ進めない'},
 {'id':'letta-local','name':'Letta Code 0.31.13 ローカル','capability':'公式App Server/local backend、MemFS、標準Docker監督','observed':'4B最小設定で保存状態を読める。読取り専用の故障試験と、別試験の実Bash修復が成立。破損indexでは起動不能。','custody':'ローカル推論と保存データ、正常版・保存データの復元主体、永続領域保護が残る。','verdict':'今回構成は未達。旧「読取り不成立」を理由にしない'},
 {'id':'letta-managed','name':'Letta Cloud 管理sandbox','capability':'状態はCloud、ツールは管理sandboxで実行。[1]','observed':'一次資料・認証境界まで。管理sandbox・履歴照会・復元の実機試験は未実施。','custody':'管理先の可用性・費用・保持/復元・export、送信後の不明結果の照会が必要。[1]','verdict':'認証・利用条件待ち。未検証'},
 {'id':'letta-hybrid','name':'Letta Cloud＋自前runner','capability':'状態はCloudに置き、ツール実行環境を自己管理できる。[1]','observed':'一次資料のみ。自前runner消失とCloud状態の再接続は未試験。','custody':'Cloudだけでなくrunnerの復帰責任も残る。管理型と同じ保証ではない。','verdict':'認証・利用条件待ち。未検証'},
 {'id':'cloudflare-agents','name':'Cloudflare Agents','capability':'Durable Objectsの保存・PITR、durable fiber。復帰フックは利用側コード。[2][3]','observed':'PITRはローカル非対応。fiberのローカル動作は検証可能だが、クラウド復元の代替証拠にはならない。[2][3]','custody':'復帰フック・作用照合等のアプリ責任、Cloudflare依存と退出の検証が残る。','verdict':'実機未検証。枠組みを完成済み本体と扱わない'},
 {'id':'openai-plus-runner','name':'OpenAI保存API＋自前実行機','capability':'Conversationsで会話・tool call/output等の状態を保持できる。[4]','observed':'会話保存の資料確認のみ。提案した実行機・復元主体は未構築。','custody':'本体実行・停止・照合・復帰の接続を新規に保守する案であり、保存API自体の保証と区別する。','verdict':'参考案。本体候補としては未成立'}
]
criteria=[
 ['状態表示120秒','プロセス停止・依存/資源障害では限定確認。DB破損はHTTP200でも保存状態を読めず未達。','読取り専用6ケースは閾値内。index破損では120秒後も起動不能。'],
 ['正常版復帰300秒','外部試験側のimport＋正常版起動なら閾値内。無人復帰は未実証。','読取りの復帰は成立。破損/不良更新の復元試験は観測中断を含み、無人RTO合格に使わない。'],
 ['依頼・記憶・停止・未確定記録','最新の静止点backupから論理状態を保持。任意の古いbackupからの無損失ではない。','nativeメモリを前後一致。静止点コピーの復元も一致。'],
 ['停止の保持','停止受理直後はstopping→interrupted。取消完了後のcancelled保持と分ける。','事前保存した停止印の読取りのみ。実際の停止要求の競合・継続実行は未実証。'],
 ['不明結果・盲目的再送の抑止','実ツールのfsync済み模擬作用で、同じIDの再送は元runを返し追加作用なし。実業務APIではない。','未確定印を返せた。読取り専用呼出しのため実行可能状態での非再送保証ではない。'],
 ['作業による資源侵食の防止','作業用一時領域とOOMの限定試験は成立。永続HOMEへ上限を超えて書けるため保護は未達。','作業領域上限では読取り可。永続HOMEは同様に上限を超えて書ける。'],
 ['オーナー救出・複雑な独自復旧を不要にする','試験者の外部復元を、停止したPDA自身の無人復帰へ読み替えない。未達。','同左。モデル依存の解除も試験側が実施。未達。'],
 ['応答だけでなく修復へ戻る','実ツールによる模擬ファイル修復は成立。本体自己更新は今回構成で未実証。','実Bashによる模擬ファイル修復は成立。自己更新・安全な実仕事再開は未実証。']
]
corrections={
 'external_dependency_restore':'Letta model-unavailableのraw verdictにあるrestoration_observer_calls_after_fault=0は誤り。別の実行記録どおり試験側がOllamaを1回startした。依存解除を含む限定試験として扱い、無人復帰のゼロ介入根拠から除外する。',
 'stale_run_id':'旧Hermes依存障害probeは存在しない旧run IDに404を返した。保存状態の合格根拠から除外。memory-v3/model-v4では実在する取消済みIDのHTTP200を要求して再確認した。',
 'intermediate_stop':'Letta requires_approvalはクライアントturn終端ではない。元の早期終了判定を撤回し、native終端まで追跡。',
 'noop_signal':'LettaのPID1 signal成功だけでは実停止していなかった試行を復帰合格から除外。採用したread-only試行では世代・再起動数変化を要求。',
 'response_wrapper':'有効なJSONが通常文に包まれた応答を誤って失敗とした試行は観測側のparse不備。訂正履歴を残し、再試験と区別。',
 'restore_observer':'再起動中のExitCodeサンプリング、ConnectionResetError、restoreではなくimportを使うCLI差で中断した元試行は通算RTO合格に使わない。Hermesは別名の再試験、Lettaは外部継続復元の証拠として扱う。',
 'early_health_gate':'Hermes model-v3ではComposeのunhealthy判定で観測を早く打ち切った。元の120秒条件を変えず、v4でnative healthを有限時間追跡して再確認。'
}
unresolved=[
 'M3へ渡せる実証済み本体候補が未確定。M2全体は未完了。',
 'Letta Cloud管理型/混成の試験用認証、利用枠、許可済み送信条件。',
 'Cloudflareの実クラウドPITR・復帰責任・退出検証。ローカルfiberだけでは代替不能。',
 '本体停止中に誰が正常版と互換データを戻すかを、ユーザー救出も複雑な独自復旧も要さない形で実証する。',
 '永続状態を作業侵食から守りつつ、必要な本体更新ができる構成の実証。',
 '実業務APIの作用照合、注意/忘却/skill・UI・退出、独立レビュー・本番反映は後続段階で未実施。'
]
assessment={'m2_status':'incomplete','admitted_candidates':[],'thresholds':{'state_s':120,'recovery_s':300},'candidates':candidates,'criteria':criteria,'corrections':corrections,'unresolved':unresolved,'evidence_files':sorted(used)}
(R/'assessment.json').write_text(json.dumps(assessment,ensure_ascii=False,indent=2)+'\n')
now=datetime.now(ZoneInfo('Asia/Tokyo')).strftime('%Y-%m-%d %H:%M JST')
md=f'''# M2は未完了 — 採用候補は未確定

{now} / default board・pda-improvement・t_ec4c52b9

## 判断

M3へ進める候補はまだ確定できません。Hermes最小構成とLettaローカル構成は、今回の試験条件ではM2要件に届きません。管理型・混成は認証と利用条件の境界で未検証です。これは全製品のNO-GOでも、M2完了でもありません。

旧「Hermesを限定M3候補に選定」「Lettaは通常読取り不成立のため不採用」は撤回済みです。この再開資料が現在の判定です。旧報告・添付27の結論は採用根拠に使いません。

推奨する次の実機候補はLetta Cloudの管理sandboxです。状態だけでなく実行環境の管理責任も移せる方式を先に確かめ、ローカルで残った「停止中の本体を誰が復元するか」を比較します。ただし、管理型でこの問題が解決すると判定したわけではありません。

## 候補を同じ軸で比較

共通要求は、保存済み状態を失わず単純な標準復帰で応答・修復へ戻り、停止・不明結果を保留できることです。

{table(['候補','要求に対応する標準能力','実測・証拠水準','残る保守・退出責任','採否'],[[c['name'],c['capability'],c['observed'],c['custody'],c['verdict']] for c in candidates])}

## 元の完了条件との照合

状態表示120秒、正常版復帰300秒を変更していません。HTTP正常だけでは合格にしません。外部試験者による復元を、候補自身の無人復帰や「救出0」に読み替えません。

{table(['条件','Hermes最小構成','Lettaローカル'],criteria)}

## Lettaで確認できたことと限界

公式Letta Code 0.31.13、Ollama qwen3.5:4b・CPU推論を使用しました。標準設定で不要なskillを外し、読取り試験ではツールを禁止した最小入力構成です。診断用fetch hookは採否に使う試験から外しています。旧2B構成の不成立をLetta全体へ一般化しません。

{table(['故障・条件','native状態読取りまで','故障からモデル読取りまで','結果'],letta_cases)}

この{len(letta_cases)}ケースは保存された試験状態を読めたことの確認です。読取り専用なので、誤再開・再送が起きなかったことを、ツール付きの仕事を安全に再開できる証明には使いません。模擬workerも実業務ではありません。モデル停止試験では、試験側がOllamaを再起動しています。

別の実ツール試験では、Bashを通して壊した模擬ファイルを所定内容へ修復できました（{lrepair['wall_s']:.3f}秒）。これは実ファイルの内容で確認した結果であり、本体の自己更新ではありません。

一方、保存済みagent indexの破損では{lcorrupt['elapsed_s']:.3f}秒後も起動できませんでした。正常版と静止点コピーの復元後にはファイル一致・native状態一致・モデル読取りが戻りましたが、試験者の外部操作であり、中断した観測を含むため無人RTO合格にはしません。

永続HOMEへ{lq['bytes']//1048576}MiBを書け、作業領域の{lq['work_cap_bytes']//1048576}MiB上限を超えました。ホストを満杯にはしていません。これは「今回の永続領域に同じ保護がない」証拠であり、すべての公式構成で保護不能という判定ではありません。

## Hermesで確認できたことと限界

公式0.21.1のアーカイブに含まれる{source['archive_files_checked']}ファイルを照合し、不一致なしを確認しました。実モデルはgpt-6-astraです。LettaのCPU小型モデルと性能同条件ではないため、応答時間で製品の優劣を決めません。

主プロセス停止からの復帰は{hcrash['recovery_s']:.3f}秒。容量・inode・OOMの限定試験後にも保存状態を読みました。記憶読取り不可・モデル通信不可の試験では、実在する取消済み仕事のnative状態をそれぞれ{hmemory['control_s']:.3f}秒・{hmodel['control_s']:.3f}秒で表示できました。依存解除後のモデル読取りも成立しましたが、依存解除は試験側の操作です。

停止受理直後の試験では、HTTP200・stopping受理後の実プロセス停止により、復帰後のnative状態がinterruptedになりました。取消完了後の試験ではcancelledが残ります。両者を置き換えて合格にしません。対象の停止/取消済み/結果不明の3ケースでは、同じidempotency keyの再送が元runを返し、模擬のfsync済み作用は増えず、遅延workerも残りませんでした。実業務APIに対する保証ではありません。

DB破損ではhealthがHTTP200でも、保存DBは読めない状態が120秒を超えました。次の数値は、その後に外部試験側が標準importと正常版起動を行った試験です。

{table(['故障','外部復元後の状態復帰まで・故障起点','モデル読取りまで・故障起点','復元主体'],hrest)}

保存DBの論理内容・記憶・模擬作用receipt・native run状態・同じIDの再送結果は保持しました。ただし、受付を止めた直近backupからの復元に限定します。不良更新試験は起動不能版と非互換DBの複合故障であり、起動不能版だけの独立測定とは区別します。

実ツールでの模擬ファイル修復は{hrepair['elapsed_s']:.3f}秒で成立しました。永続HOMEへ{hq['bytes_written']//1048576}MiBを書け、作業用/workの{hq['work_quota_bytes']//1048576}MiB上限を超えた点は未達です。本体はread-onlyマウントで自己更新を書込み拒否しましたが、これは試験構成の境界であり、Hermes製品自体の自己更新不能を示しません。

## 管理型の実際の境界

この実行環境の環境変数・Hermes .env・標準Letta/Wrangler設定を調べた範囲では、利用できるLetta Cloud/Cloudflare/OpenAI APIの試験認証はありません。ユーザーが別の場所にアカウントやブラウザログインを持たないという意味ではありません。認証なしのCloudflare APIはAuthorization欠落、OpenAI APIは401、Letta APIはWAFの403でした。Lettaの403を認証失敗と断定しません。

CloudflareのPITRはローカル非対応で、変更のdurable logがローカルにはないことが公式に明記されています。[2] fiberのローカル復帰は検証可能ですが、PITRやクラウド障害を再現したことにはなりません。[3] 今回はそのローカルデモも未実施です。復帰フックを自作して完成品の標準保証と呼び替えません。

再開に必要なのは、まずLetta Cloud管理sandboxを試せる認証・利用枠・許可済み送信範囲です。試験データは合成に限定し、本番データや本番構成を持ち込みません。認証情報はチャットや報告に貼らず、安全な設定先で用意する必要があります。新規契約・課金条件・権限は勝手に追加していません。

## 観測誤りを合格根拠から除外

{chr(10).join('- '+value for value in corrections.values())}

生の失敗記録は履歴として保存し、上記の訂正をassessment.jsonへ併記しています。スクリプトの終了コードだけで候補の合格を決めていません。

## 残る仕事と再開地点

{chr(10).join('- '+x for x in unresolved)}

実験用m2proof/m2r2コンテナは停止・除去済みです。試験データと再現情報は隔離worktreeに保持しています。M3着手・本番反映・旧scope control v2/dispatcherの再開は行っていません。独立レビューも未実施です。

カード本文の「新候補の実証は未実施」は古い実行状況の表記で、本文へは今回の状況を反映できていません。導入済みCLIのeditは完了済みtaskの結果編集専用です。blockedへの変更もCLIに拒否されたため、未割当triageを維持し、今回の実行状況と認証待ちは添付・コメントへ記録します。本文更新案も保存します。状態を動かすための強制変更やready昇格は行わず、古い未着手表記を再実行の指示にしません。

再開時はこの比較表、assessment.json、CHECKPOINT.mdとカードの現行本文を読み、実行中資源と認証境界を確認します。失敗した旧試行を盲目的に繰り返さず、未検証の管理型へ進みます。

## 生証拠への対応

相対パスの起点はこの資料のフォルダです。assessment.jsonに採否・完了条件・訂正・証拠ファイル名を保存しています。

{chr(10).join('- evidence/'+n for n in sorted(used))}
'''
(R/'M2-RESUME-REPORT.md').write_text(md)
sources='/home/user/.hermes/skills/research/grounded-citations/scripts/sources.py'
r=subprocess.run(['python',sources,'--ledger',str(R/'citations.json'),'render','--replace-in',str(R/'M2-RESUME-REPORT.md')],capture_output=True,text=True);assert r.returncode==0,r.stderr
md=(R/'M2-RESUME-REPORT.md').read_text()
css='''
:root{--ink:#17252b;--muted:#51616b;--line:#cbd4d8;--paper:#fff;--bg:#eef1f2;--accent:#185265}
*{box-sizing:border-box}html{scroll-behavior:auto}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.85 "Noto Sans JP","Hiragino Kaku Gothic ProN",Meiryo,sans-serif}main{max-width:1240px;margin:0 auto;background:var(--paper);padding:36px 44px 64px}h1{font-size:28px;line-height:1.45;margin:14px 0}h2{font-size:21px;line-height:1.5;margin-top:44px;padding-top:18px;border-top:1px solid var(--line)}p{max-width:100ch}nav{font-size:14px;color:var(--muted)}.scroll{overflow-x:auto;margin:24px 0}table{width:100%;border-collapse:collapse;font-size:14px;line-height:1.7;min-width:850px}th,td{text-align:left;vertical-align:top;border-bottom:1px solid var(--line);padding:13px 12px}th{background:#e9eff1}th:first-child,td:first-child{min-width:130px;font-weight:600}td:last-child{background:#f4f6f7}a{color:var(--accent);overflow-wrap:anywhere}li{margin:9px 0;overflow-wrap:anywhere}code{font-size:.88em;overflow-wrap:anywhere}details{margin-top:28px;border-top:1px solid var(--line);padding-top:10px}summary{cursor:pointer;min-height:44px;padding:8px 0;font-weight:600}:focus-visible{outline:3px solid var(--accent);outline-offset:4px}@media(max-width:650px){main{padding:22px 18px 44px}h1{font-size:25px}h2{font-size:20px}body{font-size:15px}table{font-size:14px}.scroll{margin-right:-2px}}@media print{body{background:white;font-size:12pt}main{padding:0}.scroll{overflow:visible}table{min-width:0;font-size:10pt}details{display:block}}
'''
body=markdown.markdown(md,extensions=['tables','fenced_code'])
body=re.sub(r'https://[^\s<]+',lambda m:'<a href="'+m.group(0)+'" rel="noreferrer">'+m.group(0)+'</a>',body)
body=body.replace('<table>','<div class="scroll" tabindex="0" aria-label="横スクロールできる比較表"><table>').replace('</table>','</table></div>')
body=body.replace('<h2>生証拠への対応</h2>','<details><summary>生証拠への対応を開く</summary>').replace('<h2>Sources</h2>','</details><h2>一次資料</h2>')
page='<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>M2再開判定 — 未完了・候補未確定</title><style>'+css+'</style></head><body><main><nav>PDA / M2候補比較 / 現在の判定</nav>'+body+'</main></body></html>'
(R/'M2-RESUME-REPORT.html').write_text(page)
manifest={n:hashlib.sha256((E/n).read_bytes()).hexdigest() for n in sorted(used)}
(R/'evidence-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'candidates':len(candidates),'criteria':len(criteria),'evidence_files':len(used),'m2_status':'incomplete','html_bytes':len(page.encode())}))
