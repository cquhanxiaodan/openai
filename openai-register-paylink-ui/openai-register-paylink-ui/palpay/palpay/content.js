// ChatGPT Session Helper - Content Script (Isolated World)

(function() {
  'use strict';

  // ========== 拖拽逻辑 ==========
  function makeDraggable(btn, storageKey) {
    try {
      const saved = JSON.parse(localStorage.getItem(storageKey) || 'null');
      if (saved && typeof saved.left === 'number' && typeof saved.top === 'number') {
        btn.style.left = saved.left + 'px';
        btn.style.top = saved.top + 'px';
        btn.style.right = 'auto';
        btn.style.bottom = 'auto';
      }
    } catch (_) {}

    btn.style.cursor = 'grab';
    btn.style.touchAction = 'none';

    let startX = 0, startY = 0, originLeft = 0, originTop = 0;
    let dragging = false, moved = false;
    const THRESHOLD = 5;

    btn.addEventListener('pointerdown', (e) => {
      if (e.button !== undefined && e.button !== 0) return;
      dragging = true;
      moved = false;
      const rect = btn.getBoundingClientRect();
      originLeft = rect.left;
      originTop = rect.top;
      startX = e.clientX;
      startY = e.clientY;
      btn.style.cursor = 'grabbing';
      btn.classList.add('dragging');
      btn.setPointerCapture && btn.setPointerCapture(e.pointerId);
    });
    btn.addEventListener('pointermove', (e) => {
      if (!dragging) return;
      const dx = e.clientX - startX;
      const dy = e.clientY - startY;
      if (!moved && Math.hypot(dx, dy) > THRESHOLD) moved = true;
      if (!moved) return;
      const w = btn.offsetWidth, h = btn.offsetHeight;
      const nl = Math.max(0, Math.min(window.innerWidth - w, originLeft + dx));
      const nt = Math.max(0, Math.min(window.innerHeight - h, originTop + dy));
      btn.style.left = nl + 'px';
      btn.style.top = nt + 'px';
      btn.style.right = 'auto';
      btn.style.bottom = 'auto';
    });
    const end = () => {
      if (!dragging) return;
      dragging = false;
      btn.style.cursor = 'grab';
      btn.classList.remove('dragging');
      if (moved) {
        try {
          localStorage.setItem(storageKey, JSON.stringify({
            left: parseFloat(btn.style.left) || 0,
            top: parseFloat(btn.style.top) || 0,
          }));
        } catch (_) {}
      }
    };
    btn.addEventListener('pointerup', end);
    btn.addEventListener('pointercancel', end);
    btn.addEventListener('click', (e) => {
      if (moved) {
        e.preventDefault();
        e.stopImmediatePropagation();
        moved = false;
      }
    }, true);
  }

  // 创建悬浮按钮
  function createFloatingButton() {
    if (document.getElementById('chatgpt-session-helper-btn')) return null;
    const btn = document.createElement('button');
    btn.id = 'chatgpt-session-helper-btn';
    btn.innerHTML = '🚀 获取支付链接';
    btn.title = '点击获取 Session 并创建支付链接（可拖动）';
    document.body.appendChild(btn);

    btn.addEventListener('click', handleClick);
    makeDraggable(btn, 'chatgpt-session-helper-btn-pos');
    return btn;
  }

  // 显示状态提示
  function showToast(message, type = 'info') {
    const existing = document.getElementById('session-helper-toast');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.id = 'session-helper-toast';
    toast.className = `session-helper-toast session-helper-toast-${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => toast.classList.add('show'), 10);
    setTimeout(() => {
      toast.classList.remove('show');
      setTimeout(() => toast.remove(), 300);
    }, 3000);
  }

  function isVisible(el) {
    if (!el) return false;
    const rect = el.getBoundingClientRect();
    const style = getComputedStyle(el);
    return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
  }

  function findButtonByText(texts) {
    const needles = texts.map(text => text.toLowerCase());
    return Array.from(document.querySelectorAll('button')).find(button => {
      const text = (button.textContent || '').trim().toLowerCase();
      return isVisible(button) && needles.some(needle => text.includes(needle));
    }) || null;
  }

  function hasFilledAgeForm() {
    const text = document.body?.innerText || '';
    if (!/How old are you\?/i.test(text)) return false;

    const inputs = Array.from(document.querySelectorAll('input')).filter(isVisible);
    const hasName = inputs.some(input => {
      const label = input.closest('label')?.textContent || document.querySelector(`label[for="${input.id}"]`)?.textContent || '';
      const meta = `${input.name || ''} ${input.id || ''} ${input.placeholder || ''} ${input.getAttribute('aria-label') || ''} ${label}`.toLowerCase();
      const value = String(input.value || '').trim();
      return (/name|full/.test(meta) || /^[a-z][a-z .'-]{1,}$/i.test(value)) && value.length >= 2;
    });
    const hasAge = inputs.some(input => {
      const label = input.closest('label')?.textContent || document.querySelector(`label[for="${input.id}"]`)?.textContent || '';
      const meta = `${input.name || ''} ${input.id || ''} ${input.placeholder || ''} ${input.getAttribute('aria-label') || ''} ${label}`.toLowerCase();
      const value = String(input.value || '').trim();
      const age = Number(value);
      return (/age/.test(meta) || /^\d{1,3}$/.test(value)) && Number.isFinite(age) && age >= 18;
    });

    return hasName && hasAge;
  }

  let ageGateTimer = null;
  let ageGateSubmitted = false;

  function autoFinishAgeGate() {
    if (ageGateSubmitted || ageGateTimer) return;
    const start = Date.now();
    ageGateTimer = setInterval(() => {
      if (Date.now() - start > 20000) {
        clearInterval(ageGateTimer);
        ageGateTimer = null;
        return;
      }

      const button = findButtonByText(['Finish creating account']);
      if (!button || button.disabled || button.getAttribute('aria-disabled') === 'true') return;
      if (!hasFilledAgeForm()) return;

      clearInterval(ageGateTimer);
      ageGateTimer = null;
      ageGateSubmitted = true;
      showToast('正在提交年龄确认...', 'info');
      setTimeout(() => button.click(), 500);
    }, 500);
  }

  function watchAgeGate() {
    autoFinishAgeGate();
    try {
      const observer = new MutationObserver(() => autoFinishAgeGate());
      observer.observe(document.documentElement, { childList: true, subtree: true });
    } catch (_) {}
  }

  // 主点击处理
  async function handleClick() {
    const btn = document.getElementById('chatgpt-session-helper-btn');
    btn.disabled = true;
    btn.textContent = '⏳ 处理中...';

    try {
      // Step 1: 获取 session
      showToast('正在获取 Session...', 'info');
      const sessionResp = await fetch('https://chatgpt.com/api/auth/session', {
        credentials: 'include'
      });

      if (!sessionResp.ok) {
        throw new Error(`Session 请求失败: ${sessionResp.status}`);
      }

      const sessionData = await sessionResp.json();
      const accessToken = sessionData.accessToken;

      if (!accessToken) {
        throw new Error('未获取到 accessToken');
      }

      showToast('Session 获取成功，正在创建支付链接...', 'info');

      // Step 2: 通过 background service worker 发送请求（绕过 CORS）
      const result = await new Promise((resolve, reject) => {
        chrome.runtime.sendMessage(
          { action: 'createPayUrl', accessToken: accessToken },
          (response) => {
            if (chrome.runtime.lastError) {
              reject(new Error(chrome.runtime.lastError.message));
              return;
            }
            if (response.error) {
              reject(new Error(response.error));
              return;
            }
            resolve(response);
          }
        );
      });

      // Step 3: background 已通过 chrome.tabs.create 打开链接
      showToast('支付链接已打开！', 'success');

    } catch (error) {
      console.error('[Session Helper Error]', error);
      showToast(`错误: ${error.message}`, 'error');
    } finally {
      btn.disabled = false;
      btn.textContent = '🚀 获取支付链接';
    }
  }

  // 等待页面加载完成后创建按钮
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      createFloatingButton();
      watchAgeGate();
    });
  } else {
    createFloatingButton();
    watchAgeGate();
  }
})();
