// 採取補助の控え。T9 の過去 child key の待ち合わせ不備は 00-method.txt を参照。
import {Client,safe,sleep} from './00-capture-client.mjs';
import {appendFileSync,writeFileSync,readlinkSync} from 'node:fs';
import {execFileSync} from 'node:child_process';
import {randomUUID} from 'node:crypto';
const [kind,attempt='1']=process.argv.slice(2);
const agent=kind.includes('codex')?'codex':'claude';
const stopping=kind.startsWith('stop-');
const handoff=kind.startsWith('handoff-');
const dir='/home/user/pda-v03a/docs/reports/evidence/v0.3-openclaw/';
const scratch='/home/user/v03/work/openclaw/scratch';
const num=handoff?'09':stopping?(agent==='claude'?'03':'05'):(agent==='claude'?'02':'04');
const file=dir+(handoff?'09-handoff.txt':`${num}-${agent}-${stopping?'stop':'stream'}.txt`);
const started=performance.now();
function stamp(){return {utc:new Date().toISOString(),elapsedSeconds:+((performance.now()-started)/1000).toFixed(3)};}
function log(type,data){appendFileSync(file,JSON.stringify({...stamp(),type,data:safe(data)})+'\n');}
const run=(cmd,args)=>execFileSync(cmd,args,{encoding:'utf8',maxBuffer:8*1024*1024});
const pid=Number(run('systemctl',['--user','show','v03-openclaw.service','-p','MainPID','--value']).trim());
let sampleCount=0,firstOutput=null,abortAt=null,terminal=null,terminalAt=null,done=false,abortPromise=null;
const tracked=new Set();
function processes() {
  const all=run('ps',['-ww','-eo','pid,ppid,etime,args','--forest']).split('\n');
  const rows=all.slice(1).map(line=>({line,m:line.match(/^\s*(\d+)\s+(\d+)\s+(\S+)\s+(.*)$/)})).filter(r=>r.m);
  const ids=new Set([pid]);let changed=true;
  while(changed){changed=false;for(const r of rows)if(ids.has(+r.m[2])&&!ids.has(+r.m[1])){ids.add(+r.m[1]);changed=true;}}
  const selected=rows.filter(r=>ids.has(+r.m[1]));
  for(const r of selected)tracked.add(+r.m[1]);
  return {ids,selected,text:all[0]+'\n'+selected.map(r=>r.line).join('\n')+'\n'};
}
function sample(reason){
  const p=processes();
  const when=JSON.stringify({...stamp(),reason})+'\n';
  const cwd=p.selected.map(r=>{try{return `${r.m[1]} cwd=${readlinkSync('/proc/'+r.m[1]+'/cwd')}`;}catch{return `${r.m[1]} cwd=exited`;}}).join('\n');
  const native=p.selected.some(r=>/\bclaude\b|\/codex(?:\s|$)/.test(r.m[4]));
  if(stopping||handoff)log('process-snapshot',{reason,ps:p.text,cwd});
  else if(native&&sampleCount<5){appendFileSync(dir+`06-ps-${agent}.txt`,when+'$ ps -ww -eo pid,ppid,etime,args --forest (unit の MainPID と子孫を抽出)\n'+p.text+cwd+'\n');sampleCount++;}
  if(!stopping&&!handoff&&agent==='claude'){
    const rss=run('ps',['-ww','-p',[...p.ids].join(','),'-o','pid,ppid,rss,etime,comm']);
    appendFileSync(dir+'07-resources.txt',when+'$ ps -ww -p <Gateway と子孫 PID> -o pid,ppid,rss,etime,comm\n'+rss+'\n');
  }
}
const sessionKey=`agent:${agent}:v03-${kind}-${attempt}-${Date.now()}`;
const prompt='hello.py に、名前を引数で受け取って挨拶する関数を足し、README.md に使い方を 1 行書き足してください。何をしているかを短く書きながら進めてください。';
const target=agent==='codex'?'claude':'codex';
const message=handoff?`OpenClaw の製品標準の sessions_spawn を使い、agentId="${target}", runtime="subagent", context="isolated", cwd="${scratch}" で別のエージェントへ次の仕事を渡してください。自分で実装せず、別の CLI を exec せず、acpx は使わないでください。渡した先の結果を受け取って報告してください。依頼: ${prompt}`:prompt;
log('trial-start',{kind,attempt,sessionKey,agent,message,scratch,mainPid:pid});
let client;
const childKeys=new Set();
const childTerminals=new Set();
client=new Client((type,m)=>{
  if(m.type==='event'&&['tick','presence','health'].includes(m.event))return;
  if(m.type==='res'&&m.payload?.type==='hello-ok')log('connected',{protocol:m.payload.protocol,server:m.payload.server,auth:safe(m.payload.auth)});
  else log(type,m);
});
client.handlers.push(m=>{
  if(m.type!=='event')return;
  const p=m.payload??{};
  if(handoff && childKeys.has(p.sessionKey) && m.event==='chat' && ['final','aborted','error'].includes(p.state)){
    childTerminals.add(p.sessionKey);log('child-terminal',{key:p.sessionKey,state:p.state});
    if(terminal && [...childKeys].every(key=>childTerminals.has(key)))done=true;
  }
  if(handoff){
    const txt=JSON.stringify(p);
    for(const key of txt.match(/agent:(?:claude|codex):subagent:[A-Za-z0-9-]+/g)??[]){
      if(childKeys.has(key))continue;childKeys.add(key);
      client.request('sessions.messages.subscribe',{key}).then(x=>log('child-subscribed',{key,result:x})).catch(e=>log('child-subscribe-error',{key,error:e.message}));
    }
  }
  const isOwn=p.sessionKey===sessionKey;
  const output=isOwn&&((m.event==='agent'&&(['assistant','tool'].includes(p.stream)||(p.stream==='item'&&p.data?.progressText)))||(m.event==='chat'&&p.state==='delta'));
  if(output&&!firstOutput){
    firstOutput=stamp();log('first-output',firstOutput);sample('first-output');
    if(stopping){
      abortAt=performance.now();log('abort-request-start',{sessionKey});
      abortPromise=client.request('chat.abort',{sessionKey}).then(x=>{log('abort-response',{result:x,secondsSinceAbort:(performance.now()-abortAt)/1000});}).catch(e=>log('abort-error',e.message));
    }
  }
  if(isOwn&&m.event==='chat'&&['final','aborted','error'].includes(p.state)){
    terminal=p.state;terminalAt=performance.now();log('terminal',{state:terminal,secondsSinceAbort:abortAt?(terminalAt-abortAt)/1000:null});
    done=!handoff || [...childKeys].every(key=>childTerminals.has(key));
  }
});
let timer;
try {
  await client.connect();
  await client.request('sessions.patch',{key:sessionKey,verboseLevel:'on'});
  await client.request('sessions.messages.subscribe',{key:sessionKey,includeApprovals:true});
  const ack=await client.request('chat.send',{sessionKey,message,idempotencyKey:randomUUID()});
  log('send-ack',ack);
  sample('after-send');timer=setInterval(()=>{try{sample('periodic');}catch(e){log('sample-error',e.message);}},5000);
  const deadline=performance.now()+360000;
  while(!done&&performance.now()<deadline)await sleep(200);
  if(!done){log('deadline',{seconds:360});await client.request('chat.abort',{sessionKey});}
  if(abortPromise)await abortPromise;
  await sleep(2000);
  log('history-after',await client.request('chat.history',{sessionKey,limit:4}));
  sample('after-terminal');
  const diff=run('git',['-C',scratch,'diff','--','README.md','hello.py']);
  if(!stopping&&!handoff)appendFileSync(dir+`${num}-${agent}-result.txt`,`\nATTEMPT ${attempt} ${new Date().toISOString()}\n$ git -C ${scratch} diff -- README.md hello.py\n`+diff);
  else log('git-diff',diff);
  log('trial-summary',{kind,attempt,sessionKey,terminal,firstOutput,abortLatencySeconds:abortAt&&terminalAt?(terminalAt-abortAt)/1000:null,childKeys:[...childKeys]});
  console.log(JSON.stringify({kind,attempt,sessionKey,terminal,firstOutput,abortLatencySeconds:abortAt&&terminalAt?(terminalAt-abortAt)/1000:null,childKeys:[...childKeys],file}));
}catch(e){log('trial-error',{error:e.stack});console.error(e.message);process.exitCode=1;}
finally{if(timer)clearInterval(timer);client.close();}
