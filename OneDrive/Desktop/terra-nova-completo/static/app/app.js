(function () {
  const vapid = document.documentElement.dataset.vapid || '';
  const subscribeUrl = document.documentElement.dataset.subscribe || '/m/push/subscribe/';
  const unsubscribeUrl = document.documentElement.dataset.unsubscribe || '/m/push/unsubscribe/';

  const ua = navigator.userAgent || '';
  const isIOS = /iPad|iPhone|iPod/.test(ua) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  const isSafari = /Safari/.test(ua) && !/CriOS|FxiOS|EdgiOS|OPiOS|Chrome/.test(ua);
  const standalone = window.matchMedia('(display-mode: standalone)').matches
    || window.navigator.standalone === true;

  function csrf() {
    const m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : '';
  }

  function u8(b64) {
    const pad = '='.repeat((4 - (b64.length % 4)) % 4);
    const raw = atob((b64 + pad).replace(/-/g, '+').replace(/_/g, '/'));
    const out = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
    return out;
  }

  async function registerSW() {
    if (!('serviceWorker' in navigator)) return null;
    const reg = await navigator.serviceWorker.register('/m/sw.js', { scope: '/m/' });
    if (reg.waiting) reg.waiting.postMessage({ type: 'TN_SKIP_WAITING' });
    return reg;
  }

  function setOfflineBanner(on) {
    const el = document.getElementById('offline-banner');
    if (el) el.classList.toggle('show', on);
  }
  function queueKey() { return 'tn-offline-queue'; }
  function flushOfflineQueue() {
    const raw = localStorage.getItem(queueKey());
    if (!raw) return;
    localStorage.removeItem(queueKey());
    try {
      JSON.parse(raw).forEach((url) => fetch(url, { credentials: 'same-origin' }).catch(() => {}));
    } catch (e) {}
  }
  window.addEventListener('online', () => { setOfflineBanner(false); flushOfflineQueue(); });
  window.addEventListener('offline', () => setOfflineBanner(true));
  if (!navigator.onLine) setOfflineBanner(true);

  function showIosInstall() {
    const bar = document.getElementById('ios-install-bar');
    if (!bar) return;
    if (isIOS && !standalone) bar.classList.add('show');
  }

  let deferred;
  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferred = e;
    const bar = document.getElementById('install-bar');
    if (bar) bar.classList.add('show');
  });
  const installBtn = document.getElementById('install-btn');
  if (installBtn) {
    installBtn.addEventListener('click', async () => {
      if (deferred) {
        deferred.prompt();
        await deferred.userChoice;
        document.getElementById('install-bar').classList.remove('show');
        return;
      }
      if (isIOS) {
        document.getElementById('ios-install-bar')?.classList.add('show');
      }
    });
  }

  async function currentSub() {
    const reg = await navigator.serviceWorker.ready;
    if (!reg.pushManager) return null;
    return reg.pushManager.getSubscription();
  }

  async function subscribePush() {
    if (isIOS && !standalone) {
      throw new Error('No iPhone, instale o app na Tela de Início pelo Safari antes de ativar o push.');
    }
    if (!('Notification' in window) || !('PushManager' in window)) {
      throw new Error('Este Safari/iOS não expõe PushManager. Use iOS 16.4+ e o atalho da Tela de Início.');
    }
    const perm = await Notification.requestPermission();
    if (perm !== 'granted') throw new Error('Permissão recusada');
    const reg = await navigator.serviceWorker.ready;
    if (!reg.pushManager) throw new Error('Push só existe no app instalado no iOS.');
    let sub = await reg.pushManager.getSubscription();
    if (!sub) {
      sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: u8(vapid)
      });
    }
    const payload = sub.toJSON();
    payload.email = (document.getElementById('push-email') || {}).value || '';
    const res = await fetch(subscribeUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
      body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error('Falha ao gravar inscrição');
    if (navigator.setAppBadge) {
      try { await navigator.setAppBadge(1); } catch (e) {}
    }
    return true;
  }

  async function unsubscribePush() {
    const sub = await currentSub();
    if (sub) {
      await fetch(unsubscribeUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
        body: JSON.stringify(sub.toJSON())
      });
      await sub.unsubscribe();
    }
    if (navigator.clearAppBadge) {
      try { await navigator.clearAppBadge(); } catch (e) {}
    }
  }

  function paintPushState(on) {
    const btn = document.getElementById('push-toggle');
    const st = document.getElementById('push-state');
    if (btn) {
      btn.textContent = on ? 'Desativar notificações' : 'Ativar notificações';
      btn.dataset.on = on ? '1' : '0';
    }
    if (st) {
      if (isIOS && !standalone) {
        st.textContent = 'iPhone: instale na Tela de Início pelo Safari para liberar o push.';
      } else {
        st.textContent = on ? 'Notificações ativas neste aparelho.' : 'Desativadas neste aparelho.';
      }
    }
  }

  async function initPushUi() {
    const btn = document.getElementById('push-toggle');
    if (!btn) return;
    const pushOk = 'PushManager' in window && 'Notification' in window;
    if (!vapid || !pushOk) {
      paintPushState(false);
      if (isIOS && !standalone) {
        btn.disabled = false;
        btn.addEventListener('click', () => {
          document.getElementById('ios-install-bar')?.classList.add('show');
          alert('No iPhone o push só funciona depois de Adicionar à Tela de Início, pelo Safari.');
        });
      } else {
        btn.disabled = true;
      }
      return;
    }
    try { paintPushState(!!(await currentSub())); }
    catch (e) { paintPushState(false); }
    btn.addEventListener('click', async () => {
      btn.disabled = true;
      try {
        if (btn.dataset.on === '1') {
          await unsubscribePush();
          paintPushState(false);
        } else {
          await subscribePush();
          paintPushState(true);
        }
      } catch (err) {
        alert(err.message || 'Não foi possível configurar o push.');
      } finally {
        btn.disabled = false;
      }
    });
  }

  async function hydrateOfflineCatalog() {
    const mount = document.getElementById('offline-catalog');
    if (!mount) return;
    try {
      const res = await fetch('/m/catalogo.json');
      const data = await res.json();
      mount.innerHTML = (data.results || []).slice(0, 12).map((p) => (
        `<article class="card"><div class="thumb">${p.emoji}</div><div>${p.name}</div><div class="price">R$ ${p.price}</div></article>`
      )).join('');
    } catch (e) {
      mount.innerHTML = '<p class="muted">Catálogo ainda não foi salvo neste aparelho. Abra os produtos online uma vez.</p>';
    }
  }

  window.TNCompat = {
    isIOS, isSafari, standalone,
    features() {
      return {
        serviceWorker: 'serviceWorker' in navigator,
        cacheAPI: 'caches' in window,
        pushManager: 'PushManager' in window,
        notification: 'Notification' in window,
        badge: 'setAppBadge' in navigator,
        backgroundSync: !!(navigator.serviceWorker && 'SyncManager' in window),
        beforeinstallprompt: 'onbeforeinstallprompt' in window,
        standalone,
        persistentStorage: !!(navigator.storage && navigator.storage.persist),
        estimate: !!(navigator.storage && navigator.storage.estimate)
      };
    }
  };

  showIosInstall();
  async function warmDynamic() {
    try {
      const res = await fetch('/m/catalogo.json');
      const data = await res.json();
      const urls = ['/m/', '/m/produtos/', '/m/relevantes/', '/static/img/icon-180.png'];
      (data.results || []).slice(0, 8).forEach((p) => {
        if (p.slug) urls.push('/m/produto/' + p.slug + '/');
      });
      const reg = await navigator.serviceWorker.ready;
      if (reg.active) reg.active.postMessage({ type: 'TN_WARM', urls: urls });
    } catch (e) {}
  }

  registerSW().then(initPushUi).then(warmDynamic);
  hydrateOfflineCatalog();
})();
