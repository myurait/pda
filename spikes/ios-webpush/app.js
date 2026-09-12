'use strict';
const BASE = '/pda-push-test';
const el = id => document.getElementById(id);
const standalone = navigator.standalone === true || matchMedia('(display-mode: standalone)').matches;
let config, manager, mode, registration, currentSubscription;
const show = text => { el('status').textContent = text; };
const fail = error => show('確認が必要です: ' + (error.message || String(error)));
const bytes = value => Uint8Array.from(atob(value.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4-value.length%4)%4)), x => x.charCodeAt(0));
const sameKey = subscription => {
  const key = subscription?.options?.applicationServerKey;
  return key && Array.from(new Uint8Array(key)).join(',') === Array.from(bytes(config.publicKey)).join(',');
};
async function api(path, body) {
  const token = localStorage.getItem('token');
  if (!token) throw new Error('ホーム画面版Open WebUIでログインしてから、上部の「通知テスト」を開いてください。');
  const response = await fetch(BASE + '/api/' + path, {method:body === undefined?'GET':'POST', headers:{'Authorization':'Bearer '+token,'Content-Type':'application/json'}, body:body === undefined?undefined:JSON.stringify(body), signal:AbortSignal.timeout(10000), cache:'no-store'});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || ('HTTP '+response.status));
  return data;
}
async function refresh() {
  const status = await api('status');
  let message = '起動先: '+(standalone?'ホーム画面アプリ':'Safari / ブラウザのタブ');
  message += '\n方式: '+(mode === 'declarative'?'Apple標準（Service Worker不要）':'標準Web Push');
  message += '\n通知許可: '+Notification.permission;
  if (status.latest?.state) {
    const states = {scheduled:'送信予約済み',publishing:'Appleへ送信中',sent:'Appleが通知を受け付けました（端末受信は要確認）',failed:'送信失敗', 'cancelled-not-sent':'予約を取り消しました','interrupted-not-resent':'試験サービス停止で中断。自動再送していません','interrupted-delivery-unknown':'送信中断。到着したか不明です。自動再送していません'};
    message += '\n直前のテスト: '+(states[status.latest.state]||status.latest.state);
    if (status.latest.push_status) message += ' / HTTP '+status.latest.push_status;
    if (typeof status.latest.arrival_standalone === 'boolean') message += '\n通知タップ後: '+(status.latest.arrival_standalone?'ホーム画面アプリ内':'Safari / ブラウザのタブ');
  }
  el('send').disabled = !status.subscribed || ['scheduled','publishing'].includes(status.latest?.state);
  el('stop').disabled = !status.subscribed;
  show(message);
}
async function main() {
  config = await api('config');
  el('return').href = config.target;
  if (location.pathname.endsWith('/landing')) {
    el('controls').hidden = true;
    const notificationId = new URLSearchParams(location.search).get('notification');
    if (notificationId) {
      show('通知の対象チャットを開きます…');
      const arrival = await api('notification-arrival', {id:notificationId, standalone});
      if (!/^\/c\/[-_A-Za-z0-9]{1,256}$/.test(arrival.target)) throw new Error('通知の戻り先が無効です。');
      el('return').href = arrival.target;
      el('return').textContent = '通知の対象チャットへ';
      location.replace(arrival.target);
      return;
    }
    show(standalone?'ホーム画面アプリで開きました。Open WebUIのトップへ戻ります…':'Safari / ブラウザのタブで開きました。Open WebUIのトップへ戻ります…');
    try { await api('arrival',{test_id:new URLSearchParams(location.search).get('test'),standalone}); }
    catch (error) { fail(error); }
    setTimeout(()=>location.replace(config.target),1500);
    return;
  }
  if (!standalone) {
    show('今はSafari / ブラウザのタブです。\nホーム画面のOpen WebUIアイコンから開き、上部の「通知テスト」を押してください。\nこのタブでは購読しません。新しいホーム画面アイコンを追加する必要はありません。');
    return;
  }
  if (!isSecureContext || typeof Notification === 'undefined') throw new Error('この端末ではWeb Pushが利用できません。iOSのバージョンを教えてください。');
  if (Notification.permission === 'denied') throw new Error('iPhoneの「設定 → 通知 → Hermes PDA (Open WebUI)」で通知を許可し、このページを開き直してください。');
  if (window.pushManager) {
    manager = window.pushManager;
    mode = 'declarative';
  } else {
    if (!('serviceWorker' in navigator)) throw new Error('Push API非対応です。iOS 16.4以降が必要です。');
    registration = await navigator.serviceWorker.register(BASE+'/sw.js',{scope:BASE+'/',updateViaCache:'none'});
    if (!registration.active) await new Promise((resolve,reject)=>{
      const worker = registration.installing || registration.waiting;
      if (!worker) return reject(new Error('通知用Service Workerを準備できませんでした。'));
      const timer = setTimeout(()=>reject(new Error('通知準備が10秒以内に終わりませんでした。再確認してください。')),10000);
      worker.addEventListener('statechange',()=>{if(worker.state==='activated'){clearTimeout(timer);resolve();}});
    });
    manager = registration.pushManager;
    mode = 'service-worker';
  }
  currentSubscription = await manager.getSubscription();
  if (currentSubscription && !sameKey(currentSubscription)) throw new Error('別機能のPush購読が存在します。上書きせず停止しました。この表示をPDAに伝えてください。');
  el('subscribe').disabled = false;
  el('subscribe').addEventListener('click',async()=>{
    el('subscribe').disabled = true;
    try {
      // Invoke subscribe in the original tap, before any await/network request.
      const pending = manager.subscribe({userVisibleOnly:true,applicationServerKey:bytes(config.publicKey)});
      currentSubscription = await pending;
      await api('subscribe',{subscription:currentSubscription.toJSON(),mode,standalone});
      el('send').disabled = false;
      el('stop').disabled = false;
      show('通知を許可しました。\n次に②を押し、iPhoneをロックしてください。20秒後にテスト通知を1件送ります。');
    } catch(error) { fail(error); }
    finally { el('subscribe').disabled = false; }
  });
  el('send').addEventListener('click',async()=>{
    el('send').disabled = true;
    try {
      await api('send',{});
      show('20秒後の送信を予約しました。\n今すぐiPhoneをロックしてください。\n「PDA ホーム画面テスト」の通知をタップすると、Open WebUIのトップへ戻ります。\n通常の完了通知と同じ購読を使う診断です。');
      setTimeout(()=>refresh().catch(fail),25000);
    } catch(error) { fail(error);el('send').disabled = false; }
  });
  el('stop').addEventListener('click',async()=>{
    try {
      await api('unsubscribe',{});
      const subscription = await manager.getSubscription();
      if (subscription && sameKey(subscription)) await subscription.unsubscribe();
      if (registration && registration.scope === location.origin+BASE+'/') await registration.unregister();
      el('send').disabled = true;el('stop').disabled = true;
      show('ホーム画面版の通知購読と未送信の予約を解除しました。通常の完了通知も停止します。再設定は①を押してください。');
    } catch(error) { fail(error); }
  });
  el('refresh').addEventListener('click',()=>refresh().catch(fail));
  await refresh();
}
main().catch(fail);
