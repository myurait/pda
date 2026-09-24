import { useCallback, useState } from 'react';
import { useNavigate } from 'react-router';
import { Alert, Button, Container, FormField, Header, RadioGroup, Textarea } from '../ui';
import { answerQuestion } from '../mock/actions';
import { currentReport, latestRun, type Question, type Report as ReportModel, type Run, type Task } from '../mock/model';
import { useStore } from '../store';
import { Artifacts } from './Artifacts';
import { Document } from './Document';
import { Flow } from './Flow';

function QuestionForm({ task, report, question, readOnly }: { task: Task; report: ReportModel; question: Question; readOnly: boolean }) {
  const [value, set] = useState(''), { update } = useStore();
  return <div className="question" data-testid={`question-${question.id}`}><FormField label={question.text}>
    {question.answer ? <Alert type="success">返答済み：{question.answer}</Alert> : readOnly ? <p>この実行の問いは参照用です。現在のタスクから次の指示を出せます。</p> : <>
      {question.kind === 'text' ? <Textarea ariaLabel={question.text} value={value} onChange={({ detail }) => set(detail.value)} rows={3}/> : <RadioGroup ariaLabel={question.text} value={value} onChange={({ detail }) => set(detail.value)} items={(question.kind === 'approval' ? ['承認する', '承認しない'] : question.options!).map(v => ({ value: v, label: v }))}/>}
      <div className="form-action"><Button variant="primary" disabled={!value.trim()} onClick={() => update(s => answerQuestion(s.tasks.find(t => t.id === task.id)!, report.id, question.id, value.trim()), '報告への返答を受け付けました。')}>返答を送る</Button></div>
    </>}
  </FormField></div>;
}
export function ReportView({ task, run = latestRun(task), selectedReport, context = false, next }: { task: Task; run?: Run; selectedReport?: string | null; context?: boolean; next?: () => void }) {
  const report = run.reports.find(r => r.id === selectedReport) || currentReport(task, run), navigate = useNavigate();
  const flowLink = useCallback((id: string) => navigate(`/tasks/${task.id}?run=${run.id}&tab=flow&cell=${id}`), [task.id, run.id, navigate]);
  if (!report) return <Container header={<Header variant="h2">途中の要約</Header>}><Alert type="info">途中です。オーナー向けの報告はまだありません。</Alert><p>第 {run.rounds.at(-1)?.number} 回。{run.rounds.flatMap(r => r.branches.flatMap(b => b.cells)).filter(c => c.state === '動いている').map(c => `${c.type} を ${c.executor}`).join('、') || '判定器が次の仕事を決めています。'}</p>{run.rounds.flatMap(r => r.branches.flatMap(b => b.cells)).filter(c => c.state === '動いている').slice(0, 3).map(c => <Document key={c.id} body={c.output}/>)}</Container>;
  const sourceRound = run.rounds.find(r => r.report?.id === report.id);
  const waitingBranches = sourceRound?.branches.filter(b => b.waiting) || [];
  const answered = report.questions.length > 0 && report.questions.every(q => q.answer);
  context = context || report.questions.length > 0;
  return <div className="stack" data-testid="report-view">
    <div className="section-heading"><div><h2>報告</h2><p className="muted">{report.author} · {report.time}</p></div><Button onClick={() => flowLink(report.id)}>フローで報告セルを開く</Button></div>
    <Container><Document body={report.body} toc/></Container>
    {report.questions.length > 0 && <Container header={<Header variant="h2" counter={`(${report.questions.filter(q => !q.answer).length} 問未回答)`}>報告からの問い</Header>}><p>報告と判断の文脈を確認してから返答してください。すべての返答が次の回の入力になります。</p>{context && <a href="#context" onClick={e => { e.preventDefault(); document.getElementById('context')?.scrollIntoView(); }}>初期の指示とオブザーバーの判断を見る</a>}{report.questions.map(q => <QuestionForm key={q.id} question={q} task={task} report={report} readOnly={run.id !== latestRun(task).id || task.state !== '入力待ち'}/>)}{answered && <Alert type="success" action={next && <Button onClick={next}>次の報告へ</Button>}>すべての問いに返答しました。タスクは進行中に戻り、フローに返答のセルが加わりました。</Alert>}</Container>}
    {context && <section id="context" className="stack context" data-testid="question-context"><h2>判断の文脈</h2><Container header={<Header variant="h3">タスクの初期の指示</Header>}><p>{task.initial}</p></Container>
      {waitingBranches.map(b => <Container key={b.id} header={<Header variant="h3">返答待ちで終わった分岐：{b.label}</Header>}><p>{b.cells.find(c => c.id === b.waiting?.observerId)?.output}</p><strong>オブザーバーの判断</strong><p>{b.waiting?.reason}</p><Flow compact run={{ ...run, rounds: [{ ...sourceRound!, owners: [], branches: [b] }] }} onSelect={flowLink}/><Button onClick={() => flowLink(b.waiting!.id)}>フローで返答待ちを開く</Button></Container>)}
      <h3>関わる成果物</h3><Artifacts compact items={task.artifacts.filter(a => report.artifactIds.includes(a.id))}/>
    </section>}
    {next && !report.questions.length && <Button onClick={next}>次の報告へ</Button>}
  </div>;
}
