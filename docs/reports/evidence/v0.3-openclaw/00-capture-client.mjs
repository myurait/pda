import {generateKeyPairSync, createHash, sign, randomUUID} from 'node:crypto';
export const sleep = ms => new Promise(r=>setTimeout(r,ms));
export function safe(value) {
  if (Array.isArray(value)) return value.map(safe);
  if (value && typeof value==='object') return Object.fromEntries(Object.entries(value).map(([k,v])=>[k, /^(deviceTokens?|access_token|refresh_token|id_token|token|password|secret|apiKey|authorization|signature|nonce|recoveryScope)$/i.test(k)?'[REDACTED]':safe(v)]));
  if(typeof value==='string') return value.replace(/\bsk-[A-Za-z0-9_-]{15,}/g,'[REDACTED]').replace(/\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/g,'[REDACTED]').replace(/(Bearer\s+)\S+/gi,'$1[REDACTED]');
  return value;
}
export class Client {
  constructor(log=()=>{}) {this.log=log;this.pending=new Map();this.handlers=[];}
  async connect() {
    const {publicKey,privateKey}=generateKeyPairSync('ed25519');
    const pub=publicKey.export({type:'spki',format:'der'}).subarray(-32);
    const deviceId=createHash('sha256').update(pub).digest('hex');
    this.ws=new WebSocket('ws://127.0.0.1:5114/');
    const challenge=await new Promise((resolve,reject)=>{
      const timeout=setTimeout(()=>reject(new Error('challenge timeout')),15000);
      this.ws.addEventListener('error',()=>reject(new Error('websocket error')));
      this.ws.addEventListener('message',ev=>{
        const m=JSON.parse(ev.data);
        if(m.event==='connect.challenge'){clearTimeout(timeout);resolve(m.payload);return;}
        if(m.type==='res') {
          const p=this.pending.get(m.id);
          if(p){clearTimeout(p.timer);this.pending.delete(m.id);m.ok?p.resolve(m.payload):p.reject(new Error(JSON.stringify(m.error)));}
        }
        this.log('receive',safe(m));
        for(const h of this.handlers)h(m);
      });
    });
    const scopes=['operator.read','operator.write','operator.admin','operator.approvals','operator.pairing'];
    const payload=['v3',deviceId,'cli','cli','operator',scopes.join(','),String(challenge.ts),'',challenge.nonce,'linux',''].join('|');
    const hello=await this.request('connect',{minProtocol:4,maxProtocol:4,client:{id:'cli',version:'v03-rerun',platform:'linux',mode:'cli'},role:'operator',scopes,caps:['tool-events'],device:{id:deviceId,publicKey:pub.toString('base64url'),signature:sign(null,Buffer.from(payload),privateKey).toString('base64url'),signedAt:challenge.ts,nonce:challenge.nonce}});
    this.hello=hello;return hello;
  }
  request(method,params={}) {
    const id=randomUUID();this.log('send',safe({type:'req',id,method,params}));
    return new Promise((resolve,reject)=>{
      const timer=setTimeout(()=>{this.pending.delete(id);reject(new Error(method+' timeout'));},45000);
      this.pending.set(id,{resolve,reject,timer});this.ws.send(JSON.stringify({type:'req',id,method,params}));
    });
  }
  close(){this.ws.close();}
}
if(process.argv[2]==='probe') {
  const c=new Client((kind,x)=>{if(x.type==='res'&&!x.ok)console.log(kind,JSON.stringify(x));});
  try {const h=await c.connect();console.log(JSON.stringify({protocol:h.protocol,server:h.server,auth:safe(h.auth),methods:h.features.methods.filter(x=>/^(chat|sessions|agent)/.test(x))},null,2));}finally{c.close();}
}
