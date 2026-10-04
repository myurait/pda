import fs from 'node:fs';
import {execFileSync} from 'node:child_process';
const mode=process.argv[2];
const isCC=mode.startsWith('claude'), stop=mode.endsWith('stop');
const root='/home/user/pda-v03a/docs/reports/evidence/v0.3-codexia';
const cwd='/home/user/v03/work/codexia/scratch';
const prefix=isCC?(stop?'03-claude-stop':'02-claude-stream'):(stop?'05-codex-stop':'04-codex-stream');
const file=`${root}/${prefix}.txt`;
const prompt='hello.py に、名前を引数で受け取って挨拶する関数を足し、README.md に使い方を 1 行書き足してください。何をしているかを短く書きながら進めてください。';
const stamp=()=>new Date().toISOString();
function redact(v){
 if(Array.isArray(v))return v.map(redact);
 if(v&&typeof v==='object')return Object.fromEntries(Object.entries(v).map(([k,x])=>[k,/^(accessToken|refreshToken|access_token|refresh_token|id_token|api_key|apiKey|password|authorization|deviceToken|device_token)$/i.test(k)?'<redacted>':redact(x)]));
 return v;
}
function log(kind,v){fs.appendFileSync(file,`${stamp()} ${kind} ${JSON.stringify(redact(v))}\n`);}
async function api(path,body){
 log('POST '+path,body);
 const r=await fetch('http://127.0.0.1:5120'+path,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body),signal:AbortSignal.timeout(30000)});
 const t=await r.text();let data;try{data=JSON.parse(t)}catch{data=t}
 log('HTTP '+r.status,data);if(!r.ok)throw new Error(`${path}: ${r.status} ${t}`);return data;
}
const pid=Number(execFileSync('systemctl',['--user','show','v03-codexia.service','-p','MainPID','--value'],{encoding:'utf8'}).trim());
function selected(output){
 const lines=output.trimEnd().split('\n'), rows=lines.slice(1).map(x=>({line:x,pid:Number(x.trim().split(/\s+/)[0]),ppid:Number(x.trim().split(/\s+/)[1])}));
 const ids=new Set([pid]);let size=-1;while(size!==ids.size){size=ids.size;for(const r of rows)if(ids.has(r.ppid))ids.add(r.pid)}
 return [lines[0],...rows.filter(r=>ids.has(r.pid)).map(r=>r.line)].join('\n')+'\n';
}
function snapshot(reason){
 const name=isCC?'06-ps-claude.txt':'06-ps-codex.txt';
 const result=selected(execFileSync('ps',['-eo','pid,ppid,etime,args','--forest'],{encoding:'utf8',maxBuffer:4*1024*1024}));
 fs.appendFileSync(`${root}/${name}`,`${stamp()} ${mode}: ${reason}\n$ ps -eo pid,ppid,etime,args --forest (service descendants only)\n${result}\n`);
 for(const line of result.split('\n').slice(1)){
  const p=Number(line.trim().split(/\s+/)[0]);if(!p)continue;
  try{fs.appendFileSync(`${root}/${name}`,`pid=${p} exe=${fs.readlinkSync('/proc/'+p+'/exe')} cwd=${fs.readlinkSync('/proc/'+p+'/cwd')}\n`)}catch{}
 }
}
function resource(){
 const result=selected(execFileSync('ps',['-eo','pid,ppid,rss,etime,args','--forest'],{encoding:'utf8',maxBuffer:4*1024*1024}));
 fs.appendFileSync(`${root}/07-resources.txt`,`${stamp()} T2; RSS in KiB\n$ ps -eo pid,ppid,rss,etime,args --forest (service descendants only)\n${result}\n`);
}
fs.writeFileSync(file,`Trial=${mode}; attempt=1; timestamps=UTC reception time\nWorkspace=${cwd}\n`);
execFileSync('git',['-C',cwd,'restore','--source=HEAD','--','README.md','hello.py']);
log('PREP','Restored only scratch README.md and hello.py to initial commit.');
let session,thread,turn,done=false,interruptAt=null,interruptPromise=null,observed=false,finishData=null;
let resolveDone;const complete=new Promise(r=>{resolveDone=r});
const ws=new WebSocket('ws://127.0.0.1:5120/ws');
await new Promise((res,rej)=>{ws.addEventListener('open',res,{once:true});ws.addEventListener('error',rej,{once:true})});
log('WEBSOCKET','connected /ws (live events only)');
ws.addEventListener('message',e=>{
 let v;try{v=JSON.parse(e.data)}catch{return}
 const p=v.payload||{};
 if(isCC){if(v.event!=='cc-message'||(session&&p.session_id!==session))return}
 else {if(v.event!=='codex:notification'&&v.event!=='codex:stderr')return;if(thread&&p.params?.threadId&&p.params.threadId!==thread)return}
 log('WS',v);
 const type=p.type, method=p.method;
 const textStart=isCC?type==='assistant'&&(p.message?.content||p.content||[]).some(x=>x.type==='text'&&x.text):method==='item/agentMessage/delta';
 if(textStart&&!observed){
  observed=true;snapshot('first assistant output');
  if(stop){
   interruptAt=performance.now();log('INTERRUPT_SENT',{session,thread,turn});
   interruptPromise=api(isCC?'/api/cc/interrupt':'/api/codex/turn/interrupt',isCC?{sessionId:session}:{threadId:thread,turnId:turn}).then(()=>log('INTERRUPT_ACK',{elapsedSeconds:(performance.now()-interruptAt)/1000})).catch(err=>log('INTERRUPT_ERROR',err.message));
  }
 }
 const finished=isCC?type==='result':method==='turn/completed';
 if(finished){
  done=true;finishData=p;log('COMPLETION',{elapsedAfterInterruptSeconds:interruptAt===null?null:(performance.now()-interruptAt)/1000,observedAssistantOutput:observed});resolveDone();
 }
});
let resourceTimer;
try{
 if(isCC){
  session=await api('/api/cc/new-session',{options:{cwd,permissionMode:'bypassPermissions'}});
  await api('/api/cc/send-message',{sessionId:session,message:prompt});
  if(!stop){resource();resourceTimer=setInterval(resource,2000)}
 }else{
  const t=await api('/api/codex/thread/start',{cwd,approvalPolicy:'never',sandbox:'workspace-write'});
  thread=t.thread.id;
  const r=await api('/api/codex/turn/start',{threadId:thread,input:[{type:'text',text:prompt}]});
  turn=r.turn.id;
 }
 const snapshotTimer=setTimeout(()=>snapshot('three seconds after request'),3000);
 let deadline;await Promise.race([complete,new Promise((_,rej)=>{deadline=setTimeout(()=>rej(new Error('No completion within 180 seconds')),180000)})]);
 clearTimeout(deadline);clearTimeout(snapshotTimer);if(interruptPromise)await interruptPromise;
 snapshot('completion');
 if(!stop){
  const n=isCC?'02-claude-result.txt':'04-codex-result.txt';
  fs.writeFileSync(`${root}/${n}`,`${stamp()}\n$ git -C ${cwd} diff\n`+execFileSync('git',['-C',cwd,'diff'],{encoding:'utf8'}));
 }
 log('RESULT',{done,observed,stopRequested:interruptAt!==null});
 console.log(JSON.stringify({mode,done,observed,stopRequested:interruptAt!==null,finalStatus:finishData?.params?.turn?.status??finishData?.subtype,session,thread,turn}));
}catch(err){log('HARNESS_ERROR',err.message);console.error(err.message);process.exitCode=1}
finally{
 clearInterval(resourceTimer);
 if(session){try{await api('/api/cc/disconnect',{sessionId:session})}catch(err){log('DISCONNECT_ERROR',err.message)}}
 ws.close();
 setTimeout(()=>process.exit(process.exitCode||0),200);
}
