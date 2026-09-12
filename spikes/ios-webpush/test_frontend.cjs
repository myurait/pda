const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const origin = 'https://pda-web.tailaff53a.ts.net';
const target = '/';

async function simulate(standalone, landing = false) {
  const file = path.join(__dirname, 'app.js');
  assert.ok(fs.existsSync(file), 'The physical-test page controller is not implemented');
  const elements = new Map();
  const events = [];
  const nodes = id => {
    if (!elements.has(id)) elements.set(id, {disabled:true, hidden:false, textContent:'', href:'', addEventListener(kind, fn){this[kind] = fn;}});
    return elements.get(id);
  };
  const manager = {getSubscription:async()=>null, subscribe(options){events.push('subscribe');return Promise.resolve({options, toJSON:()=>({endpoint:'fixture-only',keys:{}})});}};
  const context = {
    document:{getElementById:nodes}, navigator:{standalone}, window:{pushManager:manager},
    isSecureContext:true, matchMedia:()=>({matches:standalone}), Notification:{permission:'default'},
    location:{origin, pathname:'/pda-push-test/'+(landing?'landing':''), search:landing?'?test=abcdef':'', replace(url){events.push(['navigate',url]);}},
    localStorage:{getItem:()=> 'local-test-not-a-real-token'},
    fetch:async(url,options={})=>{events.push(['fetch',url,options.body]);let value={ok:true};
      if(url.endsWith('/config'))value={publicKey:'BA'.repeat(43)+'A',target};
      if(url.endsWith('/status'))value={subscribed:false,latest:{}};
      if(url.endsWith('/send'))value={test_id:'abcdef',send_at:Date.now()/1000+20};
      return {ok:true,status:200,json:async()=>value};
    },
    Uint8Array, ArrayBuffer, URL, URLSearchParams, AbortController, AbortSignal,
    atob:s=>Buffer.from(s,'base64').toString('binary'), Date, console,
    setTimeout(fn,ms){if(ms<=2000)Promise.resolve().then(fn);return 1;},clearTimeout(){},
  };
  context.window.matchMedia = context.matchMedia;
  vm.runInNewContext(fs.readFileSync(file,'utf8'),context);
  for(let i=0;i<20;i++) await Promise.resolve();
  return {nodes,events};
}

test('ordinary Safari tab cannot register the push',async()=>{
  const s=await simulate(false);
  assert.equal(s.nodes('subscribe').disabled,true);
  assert.match(s.nodes('status').textContent,/ホーム画面/);
  assert.ok(!s.events.includes('subscribe'));
});
test('permission is requested directly in the button gesture, before saving',async()=>{
  const s=await simulate(true);
  assert.equal(s.nodes('subscribe').disabled,false);
  s.nodes('subscribe').click();
  assert.equal(s.events.at(-1),'subscribe');
  for(let i=0;i<20;i++) await Promise.resolve();
  assert.ok(s.events.some(x=>Array.isArray(x)&&x[1].endsWith('/subscribe')));
  assert.equal(s.nodes('send').disabled,false);
});
test('tap landing records actual display mode and returns home without chat-dependent copy',async()=>{
  const s=await simulate(true,true);
  const arrival=s.events.find(x=>Array.isArray(x)&&x[1].endsWith('/arrival'));
  assert.equal(JSON.parse(arrival[2]).standalone,true);
  assert.ok(s.events.some(x=>Array.isArray(x)&&x[0]==='navigate'&&x[1]===target));
  assert.doesNotMatch(s.nodes('status').textContent,/この会話|元の会話/);
  for (const name of ['app.js','index.html','server.py']) {
    const content=fs.readFileSync(path.join(__dirname,name),'utf8');
    assert.doesNotMatch(content,/この会話|元の会話|c682eec9|a7d12bd6/);
  }
});
test('legacy service worker displays the fixed notification and opens only same-origin landing',async()=>{
  const file=path.join(__dirname,'sw.js');
  assert.ok(fs.existsSync(file),'The legacy Web Push fallback is not implemented');
  const handlers={},shown=[],opened=[];
  const self={location:{origin},addEventListener:(name,fn)=>handlers[name]=fn,registration:{showNotification:async(title,options)=>shown.push({title,options})},clients:{openWindow:async url=>opened.push(url)}};
  vm.runInNewContext(fs.readFileSync(file,'utf8'),{self,URL,Promise});
  let completed;
  handlers.push({data:{json:()=>({web_push:8030,notification:{title:'PDA ホーム画面テスト',body:'fixed test',navigate:origin+'/pda-push-test/landing?test=abc'}})},waitUntil:value=>completed=value});
  await completed;
  assert.equal(shown.length,1);
  handlers.notificationclick({notification:{data:shown[0].options.data,close(){}},waitUntil:value=>completed=value});
  await completed;
  assert.equal(opened[0],origin+'/pda-push-test/landing?test=abc');
  handlers.notificationclick({notification:{data:{url:'https://evil.example'},close(){}},waitUntil:value=>completed=value});
  await completed;
  assert.equal(opened.at(-1),origin+'/pda-push-test/');
});
