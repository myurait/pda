import { useCallback, useState } from 'react';
import { useNavigate } from 'react-router';
import { Alert, Button, Container, ExpandableSection, FormField, Header, RadioGroup, Textarea } from '../ui';
import { answerQuestions } from '../mock/actions';
import { currentReport, lastUserInput, type Question, type Report as ReportModel, type Task } from '../mock/model';
import { useStore } from '../store';
import { Artifacts } from './Artifacts';
import { Document } from './Document';
import { Flow } from './Flow';

type Draft = { selection: string; text: string };
const answerValue = (question: Question, draft?: Draft) => !draft ? '' : question.kind === 'text' || draft.selection === 'other' ? draft.text.trim() : draft.selection;
function QuestionsForm({ task, report, next }: { task: Task; report: ReportModel; next?: () => void }) {
  const [drafts, setDrafts] = useState<Record<string, Draft>>({}), { update } = useStore();
  const answered = report.questions.every(q => q.answer);
  const readOnly = report.id !== currentReport(task)?.id || task.state !== '入力待ち' || answered;
  const answers = Object.fromEntries(report.questions.map(q => [q.id, answerValue(q, drafts[q.id])]));
  const change = (id: string, patch: Partial<Draft>) => setDrafts(current => ({ ...current, [id]: { ...(current[id] || { selection: '', text: '' }), ...patch } }));
  return <Container header={<Header variant="h2">報告からの問い</Header>}>
    {report.questions.map(question => {
      const draft = drafts[question.id] || { selection: '', text: '' };
      return <div className="question" key={question.id} data-testid={`question-${question.id}`}><FormField label={question.text}>
        {question.answer ? <p className="prompt-text">{question.answer}</p> : readOnly ? <p>未回答</p> : question.kind === 'text' ? <Textarea ariaLabel={question.text} value={draft.text} onChange={({ detail }) => change(question.id, { text: detail.value })} rows={3}/> : <div className="question-options">
          <RadioGroup ariaLabel={question.text} value={draft.selection} onChange={({ detail }) => change(question.id, { selection: detail.value })} items={[...(question.kind === 'approval' ? ['承認する', '承認しない'] : question.options || []).map(v => ({ value: v, label: v })), { value: 'other', label: 'それ以外' }]}/>
          <FormField label="それ以外の返答"><Textarea ariaLabel={`${question.text}：それ以外`} placeholder="それ以外の返答を入力" value={draft.text} onChange={({ detail }) => change(question.id, { selection: 'other', text: detail.value })} rows={3}/></FormField>
        </div>}
      </FormField></div>;
    })}
    {!readOnly && <div className="form-action"><Button variant="primary" disabled={report.questions.some(q => !answers[q.id])} onClick={() => update(s => answerQuestions(s.tasks.find(t => t.id === task.id)!, report.id, answers), '報告への返答をまとめて受け付けました。')}>送信</Button></div>}
    {answered && <Alert type="success" action={next && <Button onClick={next}>次の報告へ</Button>}>返答を送信しました。</Alert>}
  </Container>;
}
export function ReportView({ task, selectedReport, context = false, next }: { task: Task; selectedReport?: string | null; context?: boolean; next?: () => void }) {
  const flow = task.flow, report = flow.reports.find(r => r.id === selectedReport) || currentReport(task), navigate = useNavigate();
  const flowLink = useCallback((id: string) => navigate(`/tasks/${task.id}?tab=flow&cell=${id}`), [task.id, navigate]);
  const userInput = <ExpandableSection variant="container" headerText="最後のユーザー入力"><p className="prompt-text">{lastUserInput(task, report?.id)}</p></ExpandableSection>;
  if (!report) return <div className="stack">{userInput}<Container header={<Header variant="h2">途中の要約</Header>}><Alert type="info">途中です。オーナー向けの報告はまだありません。</Alert><p>第 {flow.rounds.at(-1)?.number} 回。{flow.rounds.flatMap(r => r.branches.flatMap(b => b.cells)).filter(c => c.state === '動作中').map(c => `${c.type} を ${c.executor}`).join('、') || '判定器が次の仕事を決めています。'}</p>{flow.rounds.flatMap(r => r.branches.flatMap(b => b.cells)).filter(c => c.state === '動作中').slice(0, 3).map(c => <Document key={c.id} body={c.output}/>)}</Container></div>;
  const sourceRound = flow.rounds.find(r => r.report?.id === report.id);
  const initialOwner = flow.rounds.flatMap(r => r.owners).find(c => c.kind === 'owner');
  const contextOwners = initialOwner ? [initialOwner, ...(sourceRound?.owners || []).filter(c => c.id !== initialOwner.id)] : sourceRound?.owners || [];
  const contextBranches = sourceRound?.branches.filter(b => b.waiting || b.cells.some(c => c.state === '失敗した')) || [];
  context = context || report.questions.length > 0;
  return <div className="stack" data-testid="report-view">
    <div className="section-heading"><div><h2>{report.title}</h2><p className="muted">{report.author} · {report.time}</p></div><Button onClick={() => flowLink(report.id)}>フローで報告セルを開く</Button></div>
    {userInput}
    <Container><Document body={report.body} toc/></Container>
    {report.artifactIds.length > 0 && <Container header={<Header variant="h2">報告のための成果物</Header>}><Artifacts compact workdir={task.workdir} items={task.artifacts.filter(a => report.artifactIds.includes(a.id))}/></Container>}
    {report.questions.length > 0 && <QuestionsForm key={report.id} task={task} report={report} next={next}/>}
    {context && <section className="stack context" data-testid="question-context"><h2>判断の文脈</h2>
      {contextBranches.map(b => <Container key={b.id} header={<Header variant="h3">{b.label}</Header>}><div className="stack">
        {b.cells.filter(c => c.state === '失敗した').map(c => <ExpandableSection key={c.id} headerText={`失敗したセルの最終応答 · ${c.type} · ${c.executor}`}><Document body={c.output}/></ExpandableSection>)}
        {b.cells.filter(c => c.kind === 'observe').map(c => <ExpandableSection key={c.id} headerText={`オブザーバーの判断 · ${c.executor}`}><Document body={c.output}/>{b.waiting?.observerId === c.id && b.waiting.reason !== c.output && <p>{b.waiting.reason}</p>}</ExpandableSection>)}
        <Flow compact flow={{ ...flow, rounds: [{ ...sourceRound!, owners: contextOwners, branches: [b] }] }} onSelect={flowLink}/>
        {b.waiting && <Button onClick={() => flowLink(b.waiting!.id)}>フローで返答待ちを開く</Button>}
      </div></Container>)}
    </section>}
    {next && !report.questions.length && <Button onClick={next}>次の報告へ</Button>}
  </div>;
}
