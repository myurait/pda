"""Task-only real technical work for multi-step entry probes."""
import json
from pathlib import Path

PROGRESS_ONE='公開fixtureを読み取り、検証しています。'
PROGRESS_TWO='検証が終わったので、結果を報告に整理します。'
REPORT={
 'purpose':'公開fixtureの検証は隔離環境で完了しました。','report_type':'complete','export_class':'public',
 'verified_facts':['public-fixture.jsonを実際に読み取りました。','整合性検査は12件すべて合格しました。'],
 'failures_unmet_unknown':['本番のデータは検証していません。'],
 'candidates_reasons':['本番を試す案は、実運用への影響を避けるため採用しませんでした。'],
 'recommendations':['この隔離試験の結果をレビューに使うことを推奨します。'],
 'decisions_required':['本番への適用判断は別途必要です。'],
 'protected':['public-fixture.json','12件']}
REPORT['draft']='ここまでの作業を順にご報告します。'+REPORT['purpose']+''.join(s for key in ('verified_facts','failures_unmet_unknown','candidates_reasons','recommendations','decisions_required') for s in REPORT[key])

def register_check(home):
    from tools.registry import registry
    home=Path(home)
    path=home/'public-fixture.json'
    path.write_text(json.dumps([{'n':n,'square':n*n} for n in range(1,13)]))
    def check(args,**kwargs):
        rows=json.loads(path.read_text())
        passed=sum(type(row.get('n')) is int and row.get('square')==row['n']**2 for row in rows)
        result={'file':'public-fixture.json','checks':len(rows),'passed':passed,'failed':len(rows)-passed,'production_data_touched':False}
        (home/'technical-work-result.json').write_text(json.dumps(result)+'\n')
        return json.dumps({'success':passed==len(rows),'file':'public-fixture.json','checks':len(rows),'passed':passed})
    registry.register(name='public_fixture_check',toolset='report_editor',schema={'name':'public_fixture_check','description':'Read this isolated public JSON fixture and actually validate each integer square. Returns observed checks/passed/failed. No production data or network.','parameters':{'type':'object','properties':{},'additionalProperties':False}},handler=check,check_fn=lambda:True)
