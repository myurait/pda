'use strict';
const BASE = '/pda-push-test/';
function destination(value) {
  try {
    const url = new URL(value, self.location.origin);
    if (url.origin === self.location.origin && url.pathname === BASE + 'landing') return url.href;
  } catch (_) {}
  return self.location.origin + BASE;
}
self.addEventListener('push', event => {
  let n = {};
  try { n = event.data.json().notification || {}; } catch (_) {}
  const url = destination(n.navigate);
  event.waitUntil(self.registration.showNotification(n.title || 'PDA ホーム画面テスト', {
    body: n.body || 'ホーム画面版へ戻るテスト通知です。',
    tag: n.tag || 'pda-push-spike',
    navigate: url,
    data: {url},
  }));
});
self.addEventListener('notificationclick', event => {
  event.notification.close();
  event.waitUntil(self.clients.openWindow(destination(event.notification.data?.url)));
});
// No fetch handler, cache, root scope, background sync, or client claiming.
