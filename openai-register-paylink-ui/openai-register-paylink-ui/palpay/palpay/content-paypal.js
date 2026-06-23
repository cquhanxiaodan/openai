// PayPal Signup Auto Fill - Content Script
// 在 https://www.paypal.com/checkoutweb/signup* 页面上注入一个悬浮面板

(function () {
  'use strict';

  // ========== 样式 ==========
  const style = document.createElement('style');
  style.textContent = `
    #ppaf-btn {
      position: fixed; top: 20px; right: 20px; z-index: 2147483647;
      width: 56px; height: 56px; border-radius: 50%; border: 3px solid #fff;
      background: linear-gradient(135deg, #0070ba, #003087);
      cursor: pointer; box-shadow: 0 4px 16px rgba(0,112,186,0.5);
      display: flex; align-items: center; justify-content: center;
      transition: all 0.3s ease; user-select: none; padding: 0; color: #fff;
      font-weight: 800; font-family: system-ui, sans-serif; font-size: 20px;
    }
    #ppaf-btn:hover { transform: scale(1.1); box-shadow: 0 6px 24px rgba(0,112,186,0.7); }
    #ppaf-btn:active { transform: scale(0.95); }

    .ppaf-overlay {
      position: fixed; inset: 0; z-index: 999999;
      background: rgba(0,0,0,0.55); backdrop-filter: blur(4px);
      display: flex; align-items: center; justify-content: center;
    }
    .ppaf-modal {
      background: #0d1b2a; color: #e0e0e0; padding: 24px 28px;
      border-radius: 14px; width: 560px; max-width: 92vw;
      box-shadow: 0 16px 48px rgba(0,0,0,0.5);
      border: 1px solid rgba(0,112,186,0.4);
      font-family: system-ui, -apple-system, sans-serif;
      max-height: 90vh; overflow-y: auto;
    }
    .ppaf-modal h3 { margin: 0 0 14px; color: #4fc3f7; font-size: 18px; }
    .ppaf-modal label {
      display: block; font-size: 12px; color: #8fb3d1; margin: 12px 0 6px;
      font-weight: 600; letter-spacing: 0.3px;
    }
    .ppaf-modal input, .ppaf-modal textarea {
      width: 100%; background: #0a1320; color: #e0e0e0;
      border: 1px solid rgba(79,195,247,0.25); border-radius: 8px;
      padding: 10px 12px; font-size: 13px; box-sizing: border-box; outline: none;
      font-family: 'Cascadia Code', 'Fira Code', monospace;
    }
    .ppaf-modal textarea { height: 70px; resize: vertical; }
    .ppaf-modal input:focus, .ppaf-modal textarea:focus { border-color: #4fc3f7; }
    .ppaf-hint { font-size: 11px; color: #7a93a8; margin-top: 4px; line-height: 1.5; }

    .ppaf-btns { display: flex; gap: 10px; margin-top: 18px; flex-wrap: wrap; }
    .ppaf-btn {
      padding: 10px 18px; border-radius: 8px; border: none;
      font-size: 13px; font-weight: 600; cursor: pointer;
      transition: all 0.2s; font-family: system-ui, sans-serif;
    }
    .ppaf-btn-cancel { background: #2a3342; color: #aaa; }
    .ppaf-btn-cancel:hover { background: #3a4452; }
    .ppaf-btn-primary { background: linear-gradient(135deg, #0070ba, #4fc3f7); color: #fff; flex: 1; }
    .ppaf-btn-primary:hover { opacity: 0.9; }
    .ppaf-btn-warn { background: linear-gradient(135deg, #e65100, #ff9800); color: #fff; }
    .ppaf-btn-warn:hover { opacity: 0.9; }

    .ppaf-toast {
      position: fixed; top: 20px; right: 90px; z-index: 9999999;
      background: #0d1b2a; color: #fff; padding: 14px 18px;
      border-radius: 10px; font-size: 13px; line-height: 1.7;
      box-shadow: 0 8px 32px rgba(0,0,0,0.4);
      border: 1px solid rgba(79,195,247,0.5);
      max-width: 420px; font-family: system-ui, sans-serif;
    }
  `;
  document.head.appendChild(style);

  // ========== 工具函数 ==========
  const sleep = ms => new Promise(r => setTimeout(r, ms));

  function showToast(msg, duration = 0) {
    const t = document.createElement('div');
    t.className = 'ppaf-toast';
    t.innerHTML = `<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;">
      <div style="flex:1;">${msg}</div>
      <button style="background:none;border:none;color:#4fc3f7;font-size:18px;cursor:pointer;padding:0 4px;line-height:1;flex-shrink:0;" title="关闭">✕</button>
    </div>`;
    t.querySelector('button').onclick = () => t.remove();
    document.body.appendChild(t);
    if (duration > 0) setTimeout(() => t.remove(), duration);
  }

  // 模拟人工键盘输入 - 完整键盘事件序列 + 原生 setter
  async function humanType(input, value) {
    if (!input) return;
    // 滚动到视口中间，方便观察填写进度
    try {
      input.scrollIntoView({ behavior: 'smooth', block: 'center' });
      await sleep(250);
    } catch (_) {}
    input.focus();
    input.dispatchEvent(new Event('focus', { bubbles: true }));
    // 用原生 setter 清为空，再触发 input 事件（对 React 更稳）
    const proto = input instanceof HTMLTextAreaElement
      ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    const desc = Object.getOwnPropertyDescriptor(proto, 'value');
    if (desc && desc.set) desc.set.call(input, '');
    else input.value = '';
    input.dispatchEvent(new Event('input', { bubbles: true }));

    let currentValue = '';
    for (const char of String(value)) {
      const charCode = char.charCodeAt(0);
      // keydown
      input.dispatchEvent(new KeyboardEvent('keydown', {
        key: char, code: 'Key' + char.toUpperCase(), charCode, keyCode: charCode, which: charCode,
        bubbles: true, cancelable: true,
      }));
      // keypress
      input.dispatchEvent(new KeyboardEvent('keypress', {
        key: char, code: 'Key' + char.toUpperCase(), charCode, keyCode: charCode, which: charCode,
        bubbles: true, cancelable: true,
      }));
      // 更新值
      currentValue += char;
      if (desc && desc.set) desc.set.call(input, currentValue);
      else input.value = currentValue;
      // input event
      input.dispatchEvent(new InputEvent('input', {
        bubbles: true, inputType: 'insertText', data: char,
      }));
      // keyup
      input.dispatchEvent(new KeyboardEvent('keyup', {
        key: char, code: 'Key' + char.toUpperCase(), charCode, keyCode: charCode, which: charCode,
        bubbles: true, cancelable: true,
      }));
      // 每字符 80-220ms 随机，偶尔停顿更长模拟思考
      let d = 80 + Math.random() * 140;
      if (Math.random() < 0.08) d += 200 + Math.random() * 300;
      await sleep(d);
    }
    input.dispatchEvent(new Event('change', { bubbles: true }));
    input.dispatchEvent(new Event('blur', { bubbles: true }));
  }

  // 字段之间的随机间隔（模拟人思考切换）
  const fieldPause = () => sleep(350 + Math.random() * 500);

  // 给受控 select 设置值
  function setNativeValue(el, value) {
    const proto = el instanceof HTMLSelectElement
      ? HTMLSelectElement.prototype
      : (el instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype);
    const desc = Object.getOwnPropertyDescriptor(proto, 'value');
    if (desc && desc.set) desc.set.call(el, value);
    else el.value = value;
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  }

  function elementVisible(el) {
    if (!el) return false;
    const rect = el.getBoundingClientRect();
    const style = getComputedStyle(el);
    return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
  }

  function getElementContextText(el) {
    if (!el) return '';
    const label = el.id ? (document.querySelector(`label[for="${el.id}"]`)?.textContent || '') : '';
    const describedBy = (el.getAttribute('aria-describedby') || '')
      .split(/\s+/)
      .map(id => document.getElementById(id)?.textContent || '')
      .join(' ');
    return [
      el.name,
      el.id,
      el.placeholder,
      el.getAttribute('aria-label'),
      el.getAttribute('title'),
      el.getAttribute('data-testid'),
      el.textContent,
      label,
      describedBy,
      el.closest('label')?.textContent,
      el.parentElement?.textContent,
    ].filter(Boolean).join(' ');
  }

  function setTrackedNativeValue(el, value) {
    const previousValue = el.value;
    setNativeValue(el, value);
    try {
      if (el._valueTracker) el._valueTracker.setValue(previousValue);
    } catch (_) {}
    el.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertText', data: value }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  }

  async function ensureInputValue(input, value, attempts = 3) {
    if (!input) return false;
    const expected = String(value || '').trim();
    for (let i = 0; i < attempts; i += 1) {
      await humanType(input, expected);
      await sleep(250);
      if (String(input.value || '').trim() === expected) return true;
      setTrackedNativeValue(input, expected);
      try { input.setAttribute('value', expected); } catch (_) {}
      try { input.defaultValue = expected; } catch (_) {}
      input.dispatchEvent(new Event('blur', { bubbles: true }));
      await sleep(250);
      if (String(input.value || '').trim() === expected) return true;
    }
    return String(input.value || '').trim() === expected;
  }

  // 根据多种线索查找字段（优先 name / id，其次 placeholder / aria-label / label 文案）
  function findField({ names = [], placeholders = [], labels = [], tag = 'input' }) {
    // name
    for (const n of names) {
      const el = document.querySelector(`${tag}[name="${n}"]`);
      if (el) return el;
    }
    // id
    for (const n of names) {
      const el = document.getElementById(n);
      if (el && el.tagName.toLowerCase() === tag) return el;
    }
    // placeholder
    const all = Array.from(document.querySelectorAll(tag));
    for (const p of placeholders) {
      const el = all.find(e => (e.placeholder || '').toLowerCase().includes(p.toLowerCase()));
      if (el) return el;
    }
    // aria-label
    for (const p of placeholders.concat(labels)) {
      const el = all.find(e => (e.getAttribute('aria-label') || '').toLowerCase().includes(p.toLowerCase()));
      if (el) return el;
    }
    // 通过 label 文案
    for (const text of labels) {
      const label = Array.from(document.querySelectorAll('label'))
        .find(l => l.textContent.trim().toLowerCase().includes(text.toLowerCase()));
      if (label) {
        const forId = label.getAttribute('for');
        if (forId) {
          const el = document.getElementById(forId);
          if (el) return el;
        }
        const inner = label.querySelector(tag);
        if (inner) return inner;
      }
    }
    return null;
  }

  function findSelectByKeywords(keywords) {
    return Array.from(document.querySelectorAll('select')).find(select => {
      const context = getElementContextText(select).toLowerCase();
      return keywords.some(keyword => context.includes(keyword));
    }) || null;
  }

  function findCountrySelect() {
    return document.querySelector('select[name="country"]') ||
      document.querySelector('select[name="countryCode"]') ||
      document.querySelector('select[name="country.x"]') ||
      document.querySelector('select[aria-label*="Country" i]') ||
      document.querySelector('select[aria-label*="Region" i]') ||
      findSelectByKeywords(['country or region', 'country', 'region']);
  }

  function setCountryToJapan() {
    const select = findCountrySelect();
    if (!select) return 'notfound';

    const matched = Array.from(select.options || []).find(opt => {
      const value = (opt.value || '').trim().toUpperCase();
      const text = (opt.textContent || '').trim().toLowerCase();
      return value === 'JP' || text === 'japan' || text.includes('japan') || text.includes('日本');
    });

    if (!matched) return 'notfound';
    if ((select.value || '').toUpperCase() === (matched.value || '').toUpperCase()) return 'already';

    setNativeValue(select, matched.value);
    return 'changed';
  }

  function simulateClick(el) {
    const rect = el.getBoundingClientRect();
    const x = rect.left + rect.width / 2;
    const y = rect.top + rect.height / 2;
    el.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, clientX: x, clientY: y }));
    el.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, clientX: x, clientY: y }));
    el.dispatchEvent(new PointerEvent('pointerup', { bubbles: true, clientX: x, clientY: y }));
    el.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, clientX: x, clientY: y }));
    el.dispatchEvent(new MouseEvent('click', { bubbles: true, clientX: x, clientY: y }));
  }

  function findCountryComboboxButton() {
    return document.querySelector('button[aria-controls="country-select-sheet"][role="combobox"]') ||
      document.querySelector('button[aria-label="Country select"]') ||
      Array.from(document.querySelectorAll('button[role="combobox"], button, a[role="button"], [aria-haspopup]')).find(button => {
        const meta = `${button.getAttribute('aria-label') || ''} ${button.getAttribute('name') || ''} ${button.id || ''} ${button.className || ''} ${button.getAttribute('data-testid') || ''} ${button.textContent || ''}`.toLowerCase();
        return meta.includes('country select') || meta.includes('country selector') || meta.includes('country or region') || meta.includes('change country') || meta.includes('locale selector');
      }) || null;
  }

  function findJapanOption() {
    const candidates = Array.from(document.querySelectorAll([
      '[role="option"]',
      '[role="menuitem"]',
      'button',
      'a',
      'li',
      '[data-value]',
      '[data-country-code]'
    ].join(',')));

    return candidates.find(el => {
      const value = `${el.getAttribute('value') || ''} ${el.getAttribute('data-value') || ''} ${el.getAttribute('data-country-code') || ''} ${el.getAttribute('href') || ''}`.toUpperCase();
      const text = `${el.textContent || ''} ${el.getAttribute('aria-label') || ''}`.trim().toLowerCase();
      if (value.split(/\s+/).includes('JP') || value.includes('COUNTRY.X=JP') || value.includes('LOCALE.X=JA_JP')) return true;
      return text === 'japan' || text.includes('japan') || text.includes('日本');
    }) || null;
  }

  function findComboboxByKeywords(keywords) {
    const normalizedKeywords = keywords.map(keyword => keyword.toLowerCase());
    return Array.from(document.querySelectorAll('button[role="combobox"], [role="combobox"], button[aria-haspopup="listbox"], button[aria-haspopup="menu"]'))
      .find(el => elementVisible(el) && normalizedKeywords.some(keyword => getElementContextText(el).toLowerCase().includes(keyword))) || null;
  }

  async function selectComboboxOptionByText(button, targetNames) {
    if (!button || !targetNames.length) return false;
    const names = targetNames.map(name => String(name || '').trim()).filter(Boolean);
    if (!names.length) return false;
    const currentText = `${button.textContent || ''} ${button.getAttribute('aria-label') || ''}`;
    if (names.some(name => currentText.includes(name))) return true;

    try { button.scrollIntoView({ behavior: 'smooth', block: 'center' }); } catch (_) {}
    await sleep(150);
    simulateClick(button);

    for (let i = 0; i < 20; i += 1) {
      await sleep(150);
      const option = Array.from(document.querySelectorAll('[role="option"], [role="menuitem"], li, button, [data-value]'))
        .find(el => elementVisible(el) && names.some(name => {
          const text = `${el.textContent || ''} ${el.getAttribute('aria-label') || ''}`.trim();
          const value = `${el.getAttribute('value') || ''} ${el.getAttribute('data-value') || ''}`.trim();
          return text === name || text.includes(name) || value === name || value.includes(name);
        }));
      if (!option) continue;
      simulateClick(option);
      return true;
    }
    return false;
  }

  async function setCountryToJapanFromSheet() {
    const button = findCountryComboboxButton();
    if (!button) return 'notfound';

    const currentLabel = `${button.textContent || ''} ${button.getAttribute('aria-label') || ''}`.toLowerCase();
    if (currentLabel.includes('japan') || currentLabel.includes('日本')) return 'already';

    simulateClick(button);
    for (let i = 0; i < 20; i += 1) {
      await sleep(250);
      const japanOption = findJapanOption();
      if (!japanOption) continue;
      simulateClick(japanOption);
      return 'changed';
    }
    return 'notfound';
  }

  function findPayWithCardSubmitButton() {
    return document.querySelector('button[data-atomic-wait-intent="Pay_With_Card"][type="submit"]') ||
      document.querySelector('button[data-atomic-wait-task="login_create_account"][data-atomic-wait-viewname="email"][type="submit"]') ||
      Array.from(document.querySelectorAll('button[type="submit"]')).find(button => {
        const meta = `${button.getAttribute('data-atomic-wait-intent') || ''} ${button.getAttribute('data-atomic-wait-task') || ''} ${button.getAttribute('data-atomic-wait-domain') || ''} ${button.getAttribute('data-atomic-wait-viewname') || ''}`;
        return meta.includes('Pay_With_Card') && meta.includes('login_create_account');
      }) || null;
  }

  function genEmail() {
    const chars = 'abcdefghijklmnopqrstuvwxyz0123456789';
    let local = 'japanpaypal';
    for (let i = 0; i < 18; i += 1) {
      local += chars[Math.floor(Math.random() * chars.length)];
    }
    return `${local}${Date.now().toString(36)}@gmail.com`;
  }

  function findLoginEmailInput() {
    return document.querySelector('input#login_email[type="email"]') ||
      document.querySelector('input[name="login_email"][type="email"]') ||
      document.querySelector('input[autocomplete*="username"][type="email"]') ||
      findField({
        tag: 'input',
        names: ['login_email', 'email'],
        placeholders: ['メールアドレス', 'email', 'mail'],
        labels: ['メールアドレス', 'email', 'mail']
      });
  }

  function isVisibleEditableInput(input) {
    if (!input || input.disabled || input.readOnly) return false;
    const rect = input.getBoundingClientRect();
    const style = getComputedStyle(input);
    return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
  }

  async function waitForStableLoginEmailInput(timeout = 20000) {
    const start = Date.now();
    let lastInput = null;
    let stableSince = 0;
    while (Date.now() - start < timeout) {
      const input = findLoginEmailInput();
      if (isVisibleEditableInput(input)) {
        if (input === lastInput) {
          if (!stableSince) stableSince = Date.now();
          if (Date.now() - stableSince >= 1200) return input;
        } else {
          lastInput = input;
          stableSince = Date.now();
        }
      } else {
        lastInput = null;
        stableSince = 0;
      }
      await sleep(250);
    }
    return null;
  }

  async function typeEmailCharByChar(input, email) {
    const value = String(email || '');
    try { input.closest('.pe-2, .relative, label, div')?.scrollIntoView({ behavior: 'smooth', block: 'center' }); } catch (_) {}
    await sleep(250);

    try { simulateClick(input.closest('.pe-2') || input.closest('.relative') || input); } catch (_) {}
    await sleep(120);
    input.focus();
    input.dispatchEvent(new FocusEvent('focus', { bubbles: true }));
    input.dispatchEvent(new FocusEvent('focusin', { bubbles: true }));

    try { input.select(); } catch (_) {}
    input.dispatchEvent(new KeyboardEvent('keydown', { bubbles: true, cancelable: true, key: 'Backspace', code: 'Backspace', keyCode: 8, which: 8 }));
    setTrackedNativeValue(input, '');
    input.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true, cancelable: true, key: 'Backspace', code: 'Backspace', keyCode: 8, which: 8 }));
    await sleep(150);

    for (const char of value) {
      input.focus();
      const charCode = char.charCodeAt(0);
      const before = input.value || '';
      input.dispatchEvent(new KeyboardEvent('keydown', {
        key: char, code: 'Key' + char.toUpperCase(), charCode, keyCode: charCode, which: charCode,
        bubbles: true, cancelable: true,
      }));
      input.dispatchEvent(new KeyboardEvent('keypress', {
        key: char, code: 'Key' + char.toUpperCase(), charCode, keyCode: charCode, which: charCode,
        bubbles: true, cancelable: true,
      }));
      input.dispatchEvent(new InputEvent('beforeinput', {
        bubbles: true, cancelable: true, inputType: 'insertText', data: char,
      }));

      let inserted = false;
      try { inserted = document.execCommand('insertText', false, char); } catch (_) {}
      if (!inserted || input.value === before) {
        const start = input.selectionStart ?? before.length;
        const end = input.selectionEnd ?? before.length;
        try {
          input.setRangeText(char, start, end, 'end');
        } catch (_) {
          const next = before.slice(0, start) + char + before.slice(end);
          const trackerValue = input.value;
          const desc = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value');
          if (desc && desc.set) desc.set.call(input, next);
          else input.value = next;
          try { if (input._valueTracker) input._valueTracker.setValue(trackerValue); } catch (_) {}
        }
      }

      input.dispatchEvent(new InputEvent('input', {
        bubbles: true, inputType: 'insertText', data: char,
      }));
      input.dispatchEvent(new KeyboardEvent('keyup', {
        key: char, code: 'Key' + char.toUpperCase(), charCode, keyCode: charCode, which: charCode,
        bubbles: true, cancelable: true,
      }));
      await sleep(90 + Math.random() * 90);
    }

    input.dispatchEvent(new Event('change', { bubbles: true }));
    await sleep(300);
    return (input.value || '').trim() === value;
  }

  async function setEmailInputValue(input, email) {
    if (await typeEmailCharByChar(input, email)) return true;
    return ensureInputValue(input, email, 2);
  }

  function findContinueToPaymentButton() {
    return document.querySelector('button[data-atomic-wait-intent="Continue_To_Payment"][data-testid="continueButton"]') ||
      document.querySelector('button[data-atomic-wait-task="login_create_account"][data-atomic-wait-viewname="guest_checkout_request"][data-testid="continueButton"]') ||
      Array.from(document.querySelectorAll('button')).find(button => {
        const meta = `${button.getAttribute('data-atomic-wait-intent') || ''} ${button.getAttribute('data-atomic-wait-task') || ''} ${button.getAttribute('data-atomic-wait-viewname') || ''} ${button.getAttribute('data-testid') || ''} ${button.textContent || ''}`;
        return meta.includes('Continue_To_Payment') || meta.includes('Continue to Payment') || meta.includes('支払いを続ける');
      }) || null;
  }

  async function clickContinueToPaymentAfterEmail() {
    for (let i = 0; i < 40; i += 1) {
      await sleep(250);
      const button = findContinueToPaymentButton();
      if (!button || button.disabled || button.getAttribute('aria-disabled') === 'true') continue;
      try { button.scrollIntoView({ behavior: 'smooth', block: 'center' }); } catch (_) {}
      await sleep(150);
      simulateClick(button);
      showToast('✅ 已点击 支払いを続ける 按钮', 3000);
      return true;
    }
    showToast('⚠️ 未检测到 支払いを続ける 按钮', 5000);
    return false;
  }

  function findCreateAccountAndContinueButton() {
    return document.querySelector('button[data-atomic-wait-intent="click_select_create_account_and_continue"][data-testid="submit-button"]') ||
      document.querySelector('button[data-atomic-wait-task="review_your_payment"][data-atomic-wait-viewname="review_your_payment"][type="submit"]') ||
      Array.from(document.querySelectorAll('button[type="submit"], button')).find(button => {
        const meta = `${button.getAttribute('data-atomic-wait-intent') || ''} ${button.getAttribute('data-atomic-wait-task') || ''} ${button.getAttribute('data-testid') || ''} ${button.textContent || ''}`;
        return meta.includes('click_select_create_account_and_continue') || meta.includes('同意して続行');
      }) || null;
  }

  async function clickCreateAccountAndContinueAfterFill() {
    for (let i = 0; i < 40; i += 1) {
      await sleep(250);
      const button = findCreateAccountAndContinueButton();
      if (!button || button.disabled || button.getAttribute('aria-disabled') === 'true') continue;
      try { button.scrollIntoView({ behavior: 'smooth', block: 'center' }); } catch (_) {}
      await sleep(150);
      await rememberPaypalSmsBaseline();
      paypalSmsRequestedAt = Date.now();
      simulateClick(button);
      showToast('✅ 已点击 同意して続行 按钮', 3000);
      startPaypalSmsCodeWatcher();
      return true;
    }
    showToast('⚠️ 未检测到 同意して続行 按钮', 5000);
    return false;
  }

  let paypalSmsRequestedAt = 0;
  let paypalSmsCodeWatcherStarted = false;
  let paypalSmsBaselineTime = 0;
  let paypalSmsBaselineCode = '';
  const paypalSmsPageStartedAt = Date.now();

  async function getSavedPaypalSmsUrl() {
    const stored = await getChromeStorage(['paypalSmsUrl']);
    let smsUrl = '';
    try {
      smsUrl = localStorage.getItem('ppaf_sms_url') || localStorage.getItem('opencode_paypal_sms_url') || '';
    } catch (_) {}
    if (!smsUrl) smsUrl = stored.paypalSmsUrl || '';
    return String(smsUrl || '').trim();
  }

  function findPaypalSmsCodeDialog() {
    return Array.from(document.querySelectorAll('[role="dialog"], [aria-modal="true"], [data-testid="sca-confirm-multi-field"], .xo-rc__open-interstitial, section, div')).find(el => {
      const text = (el.textContent || '').trim();
      if (!/enter your code|sent a 6[- ]digit code|コードを入力|6桁のコード/i.test(text)) return false;
      const inputs = Array.from(el.querySelectorAll('input')).filter(isVisibleEditableInput);
      const hasCodeInputs = inputs.length >= 6 || inputs.some(input => /^ciBasic-\d+$/.test(input.name || '') || /^ci-ciBasic-\d+$/.test(input.id || ''));
      if (!hasCodeInputs) return false;
      const rect = el.getBoundingClientRect();
      const style = getComputedStyle(el);
      return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
    }) || null;
  }

  function findPaypalSmsCodeInputs() {
    const dialog = findPaypalSmsCodeDialog();
    const globalPpCodeInputs = Array.from(document.querySelectorAll('input')).filter(input => {
      return isVisibleEditableInput(input) && (/^ciBasic-\d+$/.test(input.name || '') || /^ci-ciBasic-\d+$/.test(input.id || ''));
    });
    if (globalPpCodeInputs.length >= 6) {
      return globalPpCodeInputs.sort((a, b) => {
        const ai = Number((a.name || a.id || '').match(/(\d+)$/)?.[1] || 0);
        const bi = Number((b.name || b.id || '').match(/(\d+)$/)?.[1] || 0);
        return ai - bi;
      }).slice(0, 6);
    }
    if (!dialog) return [];

    const root = dialog;
    const inputs = Array.from(root.querySelectorAll('input')).filter(isVisibleEditableInput);
    if (inputs.length >= 6) {
      const codeLikeInputs = inputs.filter(input => {
        const aria = input.getAttribute('aria-label') || '';
        const meta = `${input.name || ''} ${input.id || ''} ${aria} ${input.type || ''}`.toLowerCase();
        return /^\d\s*-\s*6$/.test(aria) || meta.includes('cibasic') || meta.includes('tel');
      });
      if (codeLikeInputs.length >= 6) return codeLikeInputs.slice(0, 6);
    }
    const ppCodeInputs = inputs.filter(input => /^ciBasic-\d+$/.test(input.name || '') || /^ci-ciBasic-\d+$/.test(input.id || ''));
    if (ppCodeInputs.length >= 6) {
      return ppCodeInputs.sort((a, b) => {
        const ai = Number((a.name || a.id || '').match(/(\d+)$/)?.[1] || 0);
        const bi = Number((b.name || b.id || '').match(/(\d+)$/)?.[1] || 0);
        return ai - bi;
      }).slice(0, 6);
    }
    const singleInput = inputs.find(input => {
      const meta = `${input.name || ''} ${input.id || ''} ${input.placeholder || ''} ${input.getAttribute('aria-label') || ''} ${input.getAttribute('autocomplete') || ''}`.toLowerCase();
      return input.maxLength >= 6 || meta.includes('one-time-code') || meta.includes('verification') || meta.includes('security code');
    });
    if (singleInput) return [singleInput];
    return inputs.filter(input => {
      const meta = `${input.name || ''} ${input.id || ''} ${input.getAttribute('aria-label') || ''} ${input.getAttribute('inputmode') || ''}`.toLowerCase();
      return input.maxLength === 1 || meta.includes('digit') || meta.includes('numeric') || meta.includes('code');
    }).slice(0, 6);
  }

  async function fillPaypalSmsCode(code) {
    const value = String(code || '').trim();
    if (!/^\d{6}$/.test(value)) return false;
    const inputs = findPaypalSmsCodeInputs();
    if (inputs.length === 1) {
      await humanType(inputs[0], value);
      return String(inputs[0].value || '').trim() === value;
    }
    if (inputs.length < 6) return false;

    try {
      inputs[0].focus();
      const data = new DataTransfer();
      data.setData('text/plain', value);
      inputs[0].dispatchEvent(new ClipboardEvent('paste', { bubbles: true, cancelable: true, clipboardData: data }));
      await sleep(400);
      if (inputs.slice(0, 6).map(input => input.value || '').join('') === value) return true;
    } catch (_) {}

    for (let i = 0; i < 6; i += 1) {
      const input = inputs[i];
      try { input.scrollIntoView({ behavior: 'smooth', block: 'center' }); } catch (_) {}
      try { input.focus(); } catch (_) {}
      try { input.select(); } catch (_) {}
      input.dispatchEvent(new KeyboardEvent('keydown', { bubbles: true, cancelable: true, key: value[i], code: 'Digit' + value[i], keyCode: value.charCodeAt(i), which: value.charCodeAt(i) }));
      input.dispatchEvent(new InputEvent('beforeinput', { bubbles: true, cancelable: true, inputType: 'insertText', data: value[i] }));
      let inserted = false;
      try { inserted = document.execCommand('insertText', false, value[i]); } catch (_) {}
      if (!inserted || input.value !== value[i]) setTrackedNativeValue(input, value[i]);
      try { input.setAttribute('value', value[i]); } catch (_) {}
      input.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertText', data: value[i] }));
      input.dispatchEvent(new Event('change', { bubbles: true }));
      input.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true, key: value[i], code: 'Digit' + value[i], keyCode: value.charCodeAt(i), which: value.charCodeAt(i) }));
      await sleep(80);
    }
    return inputs.slice(0, 6).map(input => input.value || '').join('') === value;
  }

  function parseSmsReceiveTime(value) {
    const match = String(value || '').trim().match(/^(\d{4})[\/-](\d{1,2})[\/-](\d{1,2})\s+(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?/);
    if (!match) return 0;
    const [, y, mo, d, h, mi, s = '0'] = match;
    const time = new Date(Number(y), Number(mo) - 1, Number(d), Number(h), Number(mi), Number(s)).getTime();
    return Number.isFinite(time) ? time : 0;
  }

  function normalizeSmsDigits(value) {
    return String(value || '').replace(/[０-９]/g, ch => String.fromCharCode(ch.charCodeAt(0) - 0xFEE0));
  }

  function extractSixDigitCode(value) {
    const text = normalizeSmsDigits(value).replace(/[\s-]+/g, '');
    return text.match(/(?:^|\D)(\d{6})(?:\D|$)/)?.[1] || '';
  }

  function normalizeSmsRecords(payload) {
    if (typeof payload === 'string') {
      try { return normalizeSmsRecords(JSON.parse(payload)); } catch (_) {}
    }
    if (Array.isArray(payload)) return payload;
    if (payload && payload.data && Array.isArray(payload.data.sms_content)) return payload.data.sms_content;
    if (payload && payload.data && Array.isArray(payload.data.smsContent)) return payload.data.smsContent;
    if (payload && payload.data && Array.isArray(payload.data.messages)) return payload.data.messages;
    if (payload && payload.data && Array.isArray(payload.data.list)) return payload.data.list;
    if (payload && Array.isArray(payload.data)) return payload.data;
    if (payload && Array.isArray(payload.sms_content)) return payload.sms_content;
    if (payload && Array.isArray(payload.smsContent)) return payload.smsContent;
    if (payload && Array.isArray(payload.messages)) return payload.messages;
    if (payload && Array.isArray(payload.list)) return payload.list;
    if (payload && typeof payload === 'object') return [payload];
    return [];
  }

  function getPaypalSmsRecords(payload) {
    return normalizeSmsRecords(payload)
      .map(record => {
        const content = String(record?.SmsContent || record?.smsContent || record?.sms_content || record?.content || record?.message || record?.text || '');
        const code = String(record?.SmsCode || record?.smsCode || record?.sms_code || record?.code || extractSixDigitCode(content) || '').trim();
        const time = parseSmsReceiveTime(record?.ReciveTime || record?.ReceiveTime || record?.receiveTime || record?.recv_time || record?.take_time || record?.time || record?.date);
        return { code: normalizeSmsDigits(code), content, time };
      })
      .filter(record => /^\d{6}$/.test(record.code) && record.time);
  }

  function extractPaypalSmsCode(payload, minTime) {
    const records = getPaypalSmsRecords(payload);
    if (paypalSmsBaselineTime > 0) {
      const newRecords = records.filter(record => record.time > paypalSmsBaselineTime || (record.time === paypalSmsBaselineTime && record.code !== paypalSmsBaselineCode));
      newRecords.sort((a, b) => b.time - a.time);
      return newRecords[0]?.code || '';
    }

    const recordsAfterStart = records.filter(record => record.time >= minTime);
    if (recordsAfterStart.length > 0) {
      recordsAfterStart.sort((a, b) => b.time - a.time);
      return recordsAfterStart[0]?.code || '';
    }

    if (!paypalSmsRequestedAt) {
      records.sort((a, b) => b.time - a.time);
      return records[0]?.code || '';
    }

    return '';
  }

  async function rememberPaypalSmsBaseline() {
    paypalSmsBaselineTime = 0;
    paypalSmsBaselineCode = '';
    const smsUrl = await getSavedPaypalSmsUrl();
    if (!smsUrl) return;
    const result = await fetchPaypalSmsPayload(smsUrl);
    if (!result.ok || !result.text) return;
    let payload = result.text;
    try { payload = JSON.parse(result.text); } catch (_) {}
    const records = getPaypalSmsRecords(payload).sort((a, b) => b.time - a.time);
    if (records[0]) {
      paypalSmsBaselineTime = records[0].time;
      paypalSmsBaselineCode = records[0].code;
    }
  }

  async function fetchPaypalSmsPayload(smsUrl) {
    return new Promise(resolve => {
      try {
        chrome.runtime.sendMessage({ action: 'fetchSmsLink', url: smsUrl }, res => {
          if (chrome.runtime.lastError) {
            resolve({ error: chrome.runtime.lastError.message });
            return;
          }
          resolve(res || {});
        });
      } catch (e) {
        resolve({ error: e.message });
      }
    });
  }

  async function startPaypalSmsCodeWatcher() {
    if (paypalSmsCodeWatcherStarted) return;
    const smsUrl = await getSavedPaypalSmsUrl();
    if (!smsUrl) return;

    paypalSmsCodeWatcherStarted = true;
    const startedAt = paypalSmsRequestedAt || Date.now();
    const minTime = (paypalSmsRequestedAt || paypalSmsPageStartedAt) - 5000;

    while (true) {
      if (findPaypalSmsCodeInputs().length > 0) {
        const result = await fetchPaypalSmsPayload(smsUrl);
        if (result.ok && result.text) {
          let payload = result.text;
          try { payload = JSON.parse(result.text); } catch (_) {}
          const code = extractPaypalSmsCode(payload, minTime);
          if (code && await fillPaypalSmsCode(code)) {
            showToast('✅ PayPal 验证码已自动填入: ' + code, 5000);
            return;
          }
        }
      }
      await sleep(5000);
    }
  }

  async function fillRandomLoginEmail() {
    if (sessionStorage.getItem('ppaf_pay_email_submitted') === '1') return '';
    const input = await waitForStableLoginEmailInput();
    if (input) {
      const email = genEmail();
      if (await setEmailInputValue(input, email)) {
        showToast('✅ 已填写随机邮箱: ' + email, 5000);
        if (await clickContinueToPaymentAfterEmail()) {
          sessionStorage.setItem('ppaf_pay_email_submitted', '1');
          return email;
        }
      }
    }
    showToast('⚠️ 未检测到邮箱输入框 login_email', 5000);
    return '';
  }

  async function clickPayWithCardAfterJapan() {
    for (let i = 0; i < 20; i += 1) {
      await sleep(250);
      const button = findPayWithCardSubmitButton();
      if (!button || button.disabled || button.getAttribute('aria-disabled') === 'true') continue;
      try { button.scrollIntoView({ behavior: 'smooth', block: 'center' }); } catch (_) {}
      await sleep(150);
      simulateClick(button);
      showToast('✅ 已点击 Pay With Card 按钮', 3000);
      await fillRandomLoginEmail();
      return true;
    }
    return clickCreateAccountOnPayPageAfterJapan();
  }

  function findCreateAccountOnPayPageButton() {
    return Array.from(document.querySelectorAll('button, a[role="button"], input[type="submit"]')).find(button => {
      const meta = `${button.getAttribute('aria-label') || ''} ${button.getAttribute('value') || ''} ${button.getAttribute('data-testid') || ''} ${button.id || ''} ${button.className || ''} ${button.textContent || ''}`.toLowerCase();
      return meta.includes('create an account') || meta.includes('create account') || meta.includes('signup') || meta.includes('sign up') || meta.includes('アカウントを作成') || meta.includes('新規登録');
    }) || null;
  }

  async function clickCreateAccountOnPayPageAfterJapan() {
    for (let i = 0; i < 20; i += 1) {
      await sleep(250);
      const button = findCreateAccountOnPayPageButton();
      if (!button || button.disabled || button.getAttribute('aria-disabled') === 'true') continue;
      try { button.scrollIntoView({ behavior: 'smooth', block: 'center' }); } catch (_) {}
      await sleep(150);
      simulateClick(button);
      showToast('✅ 已点击 Create an Account 按钮', 3000);
      return true;
    }
    return false;
  }

  async function autoSwitchJapanOnPayPage() {
    if (location.hostname !== 'www.paypal.com' || location.pathname !== '/pay') return;
    if (sessionStorage.getItem('ppaf_pay_email_submitted') === '1') return;

    const emailInput = await waitForStableLoginEmailInput(5000);
    const continueButton = findContinueToPaymentButton();
    if (emailInput && continueButton) {
      await fillRandomLoginEmail();
      return;
    }

    const start = Date.now();
    while (Date.now() - start < 20000) {
      const result = setCountryToJapan();
      if (result === 'notfound') {
        const sheetResult = await setCountryToJapanFromSheet();
        if (sheetResult === 'changed') {
          showToast('✅ Country or Region 已切换为 Japan', 3000);
          await clickPayWithCardAfterJapan();
          return;
        }
        if (sheetResult === 'already') {
          await clickPayWithCardAfterJapan();
          return;
        }
      }
      if (result === 'changed') {
        showToast('✅ Country or Region 已切换为 Japan', 3000);
        await clickPayWithCardAfterJapan();
        return;
      }
      if (result === 'already') {
        await clickPayWithCardAfterJapan();
        return;
      }
      await sleep(500);
    }
  }

  async function switchCountryToJapanOnCurrentPage(timeout = 20000) {
    const start = Date.now();
    while (Date.now() - start < timeout) {
      const result = setCountryToJapan();
      if (result === 'changed' || result === 'already') return result;

      const sheetResult = await setCountryToJapanFromSheet();
      if (sheetResult === 'changed' || sheetResult === 'already') return sheetResult;

      await sleep(500);
    }
    return 'notfound';
  }

  function isPaypalSignupPage() {
    return location.hostname === 'www.paypal.com' && location.pathname.startsWith('/checkoutweb/signup');
  }

  function isPaypalHermesPage() {
    return location.hostname === 'www.paypal.com' && location.pathname.startsWith('/webapps/hermes');
  }

  function isVisibleElement(el) {
    if (!el) return false;
    const rect = el.getBoundingClientRect();
    const style = getComputedStyle(el);
    return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
  }

  function findHermesAgreeContinueButton() {
    return Array.from(document.querySelectorAll('button, input[type="submit"], a[role="button"]')).find(el => {
      if (!isVisibleElement(el) || el.disabled || el.getAttribute('aria-disabled') === 'true') return false;
      const text = `${el.textContent || ''} ${el.getAttribute('value') || ''} ${el.getAttribute('aria-label') || ''}`.trim().toLowerCase();
      if (/cancel|return|back|キャンセル|戻る/.test(text)) return false;
      return text.includes('agree and continue') || text.includes('agree & continue') || text.includes('同意して続行') || text.includes('同意して続ける');
    }) || null;
  }

  let hermesAutoContinueStarted = false;

  async function autoClickHermesContinuePage() {
    if (hermesAutoContinueStarted || !isPaypalHermesPage()) return;
    hermesAutoContinueStarted = true;
    await sleep(5000);

    for (let i = 0; i < 20; i += 1) {
      const button = findHermesAgreeContinueButton();
      if (button) {
        try { button.scrollIntoView({ behavior: 'smooth', block: 'center' }); } catch (_) {}
        await sleep(150);
        simulateClick(button);
        showToast('✅ 已点击 PayPal 同意继续按钮', 3000);
        return;
      }
      await sleep(500);
    }
  }

  function getChromeStorage(keys) {
    return new Promise(resolve => {
      try {
        chrome.storage.local.get(keys, res => resolve(res || {}));
      } catch (_) {
        resolve({});
      }
    });
  }

  async function getSavedPaypalAutofillInput() {
    const stored = await getChromeStorage(['lastCardInput', 'lastPhone']);
    let phone = stored.lastPhone || '';
    let cardText = stored.lastCardInput || '';

    try {
      if (!phone) phone = localStorage.getItem('ppaf_phone') || '';
      if (!cardText) cardText = localStorage.getItem('ppaf_card') || '';
    } catch (_) {}

    return { phone, cardText };
  }

  let signupAutoFillStarted = false;

  async function autoSwitchJapanAndFillOnSignupPage() {
    if (signupAutoFillStarted || !isPaypalSignupPage()) return;
    signupAutoFillStarted = true;

    const countryResult = await switchCountryToJapanOnCurrentPage();
    if (countryResult === 'changed') {
      showToast('✅ Country or Region 已切换为 Japan', 3000);
    } else if (countryResult === 'notfound') {
      showToast('⚠️ 未检测到 Country or Region，5 秒后仍尝试自动填写', 5000);
    }

    await sleep(5000);

    const { phone, cardText } = await getSavedPaypalAutofillInput();
    if (!cardText) {
      showToast('⚠️ 未检测到已保存的 PayPal 自动填写数据', 5000);
      return;
    }

    let card;
    try {
      card = parseCard(cardText);
    } catch (e) {
      showToast('❌ 自动填写数据解析失败: ' + e.message, 8000);
      return;
    }

    const password = genPassword(14);
    showToast('⏳ 已等待 5 秒，开始自动填写...', 3000);

    try {
      const results = await fillAll({ phone: phone || card.phone, card, password });
      results.push('<br>🔑 随机密码: <code style="background:#0a1320;padding:2px 6px;border-radius:4px;color:#4fc3f7">' + password + '</code>');
      if (autoCaptchaRemoved > 0) {
        results.push('🛡️ 移除人机成功（共 ' + autoCaptchaRemoved + ' 次）');
      }
      showToast(results.join('<br>'), 15000);
    } catch (e) {
      showToast('❌ 自动填写失败: ' + e.message, 8000);
    }
  }

  function autoStartPaypalSmsWatcherIfNeeded() {
    if (paypalSmsCodeWatcherStarted || !isPaypalSignupPage()) return;
    if (findPaypalSmsCodeInputs().length === 0) return;
    if (!paypalSmsRequestedAt) paypalSmsRequestedAt = Date.now();
    startPaypalSmsCodeWatcher();
  }

  function normalizeCountryCode(value) {
    const text = String(value || '').trim();
    if (!text) return '';
    const upper = text.toUpperCase();
    if (upper === 'US' || upper === 'USA' || text === '美国' || text === '美國' || /united states/i.test(text)) return 'US';
    if (upper === 'JP' || text === '日本' || /japan/i.test(text)) return 'JP';
    return upper.length === 2 ? upper : '';
  }

  function hasJapaneseText(value) {
    return /[\u3040-\u30ff\u3400-\u9fff]/.test(String(value || ''));
  }

  function looksLikeJapanesePostalCode(value) {
    return /^\d{3}-\d{4}$/.test(String(value || '').trim());
  }

  function extractJapanesePostalCode(value) {
    const match = String(value || '').match(/(\d{3})\s*[-ー−－]?\s*(\d{4})/);
    return match ? `${match[1]}-${match[2]}` : '';
  }

  const JP_PREFECTURE_MAP = {
    'ホッカイドウ': 'Hokkaido',
    'アオモリ': 'Aomori',
    'イワテ': 'Iwate',
    'ミヤギ': 'Miyagi',
    'アキタ': 'Akita',
    'ヤマガタ': 'Yamagata',
    'フクシマ': 'Fukushima',
    'イバラキ': 'Ibaraki',
    'トチギ': 'Tochigi',
    'グンマ': 'Gunma',
    'サイタマ': 'Saitama',
    'チバ': 'Chiba',
    'トウキョウ': 'Tokyo',
    'カナガワ': 'Kanagawa',
    'ニイガタ': 'Niigata',
    'トヤマ': 'Toyama',
    'イシカワ': 'Ishikawa',
    'フクイ': 'Fukui',
    'ヤマナシ': 'Yamanashi',
    'ナガノ': 'Nagano',
    'ギフ': 'Gifu',
    'シズオカ': 'Shizuoka',
    'アイチ': 'Aichi',
    'ミエ': 'Mie',
    'シガ': 'Shiga',
    'キョウト': 'Kyoto',
    'オオサカ': 'Osaka',
    'ヒョウゴ': 'Hyogo',
    'ナラ': 'Nara',
    'ワカヤマ': 'Wakayama',
    'トットリ': 'Tottori',
    'シマネ': 'Shimane',
    'オカヤマ': 'Okayama',
    'ヒロシマ': 'Hiroshima',
    'ヤマグチ': 'Yamaguchi',
    'トクシマ': 'Tokushima',
    'カガワ': 'Kagawa',
    'エヒメ': 'Ehime',
    'コウチ': 'Kochi',
    'フクオカ': 'Fukuoka',
    'サガ': 'Saga',
    'ナガサキ': 'Nagasaki',
    'クマモト': 'Kumamoto',
    'オオイタ': 'Oita',
    'ミヤザキ': 'Miyazaki',
    'カゴシマ': 'Kagoshima',
    'オキナワ': 'Okinawa'
  };

  function resolveAdministrativeAreaName(value, country) {
    const text = String(value || '').trim();
    if (!text) return '';
    if (country === 'JP') {
      return JP_PREFECTURE_MAP[text] || text;
    }
    return text;
  }

  const JP_PREFECTURE_JA_MAP = {
    Hokkaido: '北海道', Aomori: '青森県', Iwate: '岩手県', Miyagi: '宮城県', Akita: '秋田県', Yamagata: '山形県', Fukushima: '福島県',
    Ibaraki: '茨城県', Tochigi: '栃木県', Gunma: '群馬県', Saitama: '埼玉県', Chiba: '千葉県', Tokyo: '東京都', Kanagawa: '神奈川県',
    Niigata: '新潟県', Toyama: '富山県', Ishikawa: '石川県', Fukui: '福井県', Yamanashi: '山梨県', Nagano: '長野県', Gifu: '岐阜県',
    Shizuoka: '静岡県', Aichi: '愛知県', Mie: '三重県', Shiga: '滋賀県', Kyoto: '京都府', Osaka: '大阪府', Hyogo: '兵庫県',
    Nara: '奈良県', Wakayama: '和歌山県', Tottori: '鳥取県', Shimane: '島根県', Okayama: '岡山県', Hiroshima: '広島県', Yamaguchi: '山口県',
    Tokushima: '徳島県', Kagawa: '香川県', Ehime: '愛媛県', Kochi: '高知県', Fukuoka: '福岡県', Saga: '佐賀県', Nagasaki: '長崎県',
    Kumamoto: '熊本県', Oita: '大分県', Miyazaki: '宮崎県', Kagoshima: '鹿児島県', Okinawa: '沖縄県'
  };

  const JP_RANDOM_ADDRESS_AREAS = [
    { zip: '160-0022', state: '東京都', city: '新宿区', towns: ['新宿', '西新宿', '歌舞伎町'], buildings: ['パークハイツ', 'グリーンコート', 'サンライズ'] },
    { zip: '150-0002', state: '東京都', city: '渋谷区', towns: ['渋谷', '神南', '代々木'], buildings: ['ヒカリエレジデンス', 'メゾン渋谷', '青山ハイツ'] },
    { zip: '530-0001', state: '大阪府', city: '大阪市北区', towns: ['梅田', '中津', '芝田'], buildings: ['大阪駅前ハイツ', '梅田レジデンス', 'ノースコート'] },
    { zip: '460-0008', state: '愛知県', city: '名古屋市中区', towns: ['栄', '錦', '丸の内'], buildings: ['サカエマンション', '名古屋ハイツ', 'セントラルコート'] },
    { zip: '812-0012', state: '福岡県', city: '福岡市博多区', towns: ['博多駅中央街', '博多駅前', '住吉'], buildings: ['博多ハイツ', 'リバーサイド博多', '駅前レジデンス'] }
  ];

  function randomInt(min, max) {
    return min + Math.floor(Math.random() * (max - min + 1));
  }

  function randomPick(items) {
    return items[Math.floor(Math.random() * items.length)];
  }

  function pickRandomJapaneseAddress() {
    const area = randomPick(JP_RANDOM_ADDRESS_AREAS);
    const town = randomPick(area.towns);
    const building = randomPick(area.buildings);
    return {
      zip: area.zip,
      state: area.state,
      city: area.city,
      line1: `${town}${randomInt(1, 5)}-${randomInt(1, 28)}-${randomInt(1, 18)}`,
      line2: `${building}${randomInt(101, 1208)}`
    };
  }

  function normalizeJapanesePrefectureForSelect(value) {
    const text = String(value || '').trim();
    if (!text) return '';
    if (JP_PREFECTURE_JA_MAP[text]) return JP_PREFECTURE_JA_MAP[text];
    const resolved = JP_PREFECTURE_MAP[text] || text;
    return JP_PREFECTURE_JA_MAP[resolved] || resolved;
  }

  function genJapaneseDob() {
    const year = 1975 + Math.floor(Math.random() * 26);
    const month = String(1 + Math.floor(Math.random() * 12)).padStart(2, '0');
    const day = String(1 + Math.floor(Math.random() * 28)).padStart(2, '0');
    return { year: String(year), month, day };
  }

  function getDobInputMeta(input) {
    const label = input.id ? (document.querySelector(`label[for="${input.id}"]`)?.textContent || '') : '';
    const describedBy = (input.getAttribute('aria-describedby') || '')
      .split(/\s+/)
      .map(id => document.getElementById(id)?.textContent || '')
      .join(' ');
    return [
      input.placeholder,
      input.getAttribute('aria-label'),
      input.getAttribute('title'),
      input.getAttribute('pattern'),
      input.getAttribute('data-format'),
      input.getAttribute('data-date-format'),
      input.name,
      input.id,
      label,
      describedBy,
      input.parentElement?.textContent,
    ].filter(Boolean).join(' ');
  }

  function getDobOrderFromLocale() {
    let locale = '';
    try { locale = new URLSearchParams(location.search).get('locale.x') || ''; } catch (_) {}
    locale = (locale || document.documentElement.lang || navigator.language || '').replace('_', '-');
    if (!locale) return '';

    try {
      return new Intl.DateTimeFormat(locale)
        .formatToParts(new Date(2000, 10, 22))
        .filter(part => ['year', 'month', 'day'].includes(part.type))
        .map(part => part.type[0])
        .join('');
    } catch (_) {
      return '';
    }
  }

  function formatDobByOrder(order, dob) {
    const parts = { y: dob.year, m: dob.month, d: dob.day };
    return String(order || 'mdy').split('').map(part => parts[part]).join('/');
  }

  function formatDobForInput(input, dob) {
    const meta = getDobInputMeta(input);
    const compact = meta.toLowerCase().replace(/\s+/g, '');
    if (input.type === 'date') return `${dob.year}-${dob.month}-${dob.day}`;
    if (/d{1,2}[^a-z0-9]?m{1,2}[^a-z0-9]?y{2,4}|day[^a-z0-9]*month[^a-z0-9]*year/.test(compact)) return formatDobByOrder('dmy', dob);
    if (/y{2,4}[^a-z0-9]?m{1,2}[^a-z0-9]?d{1,2}|year[^a-z0-9]*month[^a-z0-9]*day/.test(compact)) return formatDobByOrder('ymd', dob);
    if (/m{1,2}[^a-z0-9]?d{1,2}[^a-z0-9]?y{2,4}|month[^a-z0-9]*day[^a-z0-9]*year/.test(compact)) return formatDobByOrder('mdy', dob);
    if (/生年月日|年.*月.*日/.test(meta)) return formatDobByOrder('ymd', dob);
    return formatDobByOrder(getDobOrderFromLocale() || 'mdy', dob);
  }

  function genKanaName() {
    const firstNames = ['タロウ', 'ハナコ', 'ユウタ', 'サクラ', 'ケンタ', 'ミユキ', 'ダイスケ', 'アカリ'];
    const lastNames = ['ヤマダ', 'サトウ', 'スズキ', 'タナカ', 'ワタナベ', 'イトウ', 'ナカムラ', 'コバヤシ'];
    return {
      firstName: firstNames[Math.floor(Math.random() * firstNames.length)],
      lastName: lastNames[Math.floor(Math.random() * lastNames.length)]
    };
  }

  // 州缩写映射
  const STATE_MAP = {
    'AL':'Alabama','AK':'Alaska','AZ':'Arizona','AR':'Arkansas','CA':'California',
    'CO':'Colorado','CT':'Connecticut','DE':'Delaware','FL':'Florida','GA':'Georgia',
    'HI':'Hawaii','ID':'Idaho','IL':'Illinois','IN':'Indiana','IA':'Iowa','KS':'Kansas',
    'KY':'Kentucky','LA':'Louisiana','ME':'Maine','MD':'Maryland','MA':'Massachusetts',
    'MI':'Michigan','MN':'Minnesota','MS':'Mississippi','MO':'Missouri','MT':'Montana',
    'NE':'Nebraska','NV':'Nevada','NH':'New Hampshire','NJ':'New Jersey','NM':'New Mexico',
    'NY':'New York','NC':'North Carolina','ND':'North Dakota','OH':'Ohio','OK':'Oklahoma',
    'OR':'Oregon','PA':'Pennsylvania','RI':'Rhode Island','SC':'South Carolina',
    'SD':'South Dakota','TN':'Tennessee','TX':'Texas','UT':'Utah','VT':'Vermont',
    'VA':'Virginia','WA':'Washington','WV':'West Virginia','WI':'Wisconsin','WY':'Wyoming'
  };
  const ZIP_PREFIX_TO_STATE = {
    '35':'Alabama','99':'Alaska','85':'Arizona','72':'Arkansas',
    '90':'California','91':'California','92':'California','93':'California','94':'California','95':'California',
    '80':'Colorado','81':'Colorado','06':'Connecticut','19':'Delaware',
    '32':'Florida','33':'Florida','34':'Florida','30':'Georgia','31':'Georgia',
    '83':'Idaho','60':'Illinois','61':'Illinois','62':'Illinois',
    '46':'Indiana','47':'Indiana','50':'Iowa','51':'Iowa','52':'Iowa',
    '66':'Kansas','67':'Kansas','40':'Kentucky','41':'Kentucky','42':'Kentucky',
    '70':'Louisiana','71':'Louisiana','04':'Maine','20':'Maryland','21':'Maryland',
    '01':'Massachusetts','02':'Massachusetts','48':'Michigan','49':'Michigan',
    '55':'Minnesota','56':'Minnesota','38':'Mississippi','39':'Mississippi',
    '63':'Missouri','64':'Missouri','65':'Missouri','59':'Montana',
    '68':'Nebraska','69':'Nebraska','88':'Nevada','89':'Nevada',
    '03':'New Hampshire','07':'New Jersey','08':'New Jersey','87':'New Mexico',
    '10':'New York','11':'New York','12':'New York','13':'New York','14':'New York',
    '27':'North Carolina','28':'North Carolina','58':'North Dakota',
    '43':'Ohio','44':'Ohio','45':'Ohio','73':'Oklahoma','74':'Oklahoma',
    '97':'Oregon','15':'Pennsylvania','16':'Pennsylvania','17':'Pennsylvania','18':'Pennsylvania',
    '29':'South Carolina','57':'South Dakota',
    '37':'Tennessee','75':'Texas','76':'Texas','77':'Texas','78':'Texas','79':'Texas',
    '84':'Utah','05':'Vermont','22':'Virginia','23':'Virginia','24':'Virginia',
    '98':'Washington','25':'West Virginia','26':'West Virginia',
    '53':'Wisconsin','54':'Wisconsin','82':'Wyoming'
  };

  // 解析步骤2的卡信息
  function parseCard(text) {
    const parts = text.trim().split(/----/);
    if (parts.length < 7) throw new Error('格式错误，需要7个字段用 ---- 分隔');
    const [card, expiry, cvv, phone, smsToken, name, addressStr] = parts.map(s => s.trim());
    const addrParts = addressStr.split(/[,，]/).map(s => s.trim()).filter(Boolean);
    let street = '';
    let city = '';
    let state = '';
    let zip = '';
    let country = normalizeCountryCode(addrParts[addrParts.length - 1]);

    const inferredJapan =
      (addrParts.length >= 4 && looksLikeJapanesePostalCode(addrParts[country ? addrParts.length - 2 : addrParts.length - 1])) ||
      addrParts.some(hasJapaneseText);

    if (inferredJapan) {
      if (!country) country = 'JP';
      const core = country ? addrParts.slice(0, -1) : addrParts.slice();
      zip = core.map(extractJapanesePostalCode).find(Boolean) || '';
      const partsWithoutZip = core
        .map(part => String(part || '').replace(/\d{3}\s*[-ー−－]?\s*\d{4}/g, '').trim())
        .filter(Boolean);
      state = partsWithoutZip[0] || core[0] || '';
      city = partsWithoutZip[1] || core[1] || '';
      street = partsWithoutZip[2] || core[2] || '';
    } else {
      street = addrParts[0]?.trim() || '';
      const cityZip = addrParts[1]?.trim() || '';
      if (!country) country = 'US';
      const czMatch = cityZip.match(/^(.+?)\s+(\d{5}(?:-\d{4})?)$/);
      city = czMatch ? czMatch[1].trim() : cityZip;
      zip = czMatch ? czMatch[2] : '';
    }

    const nameParts = name.trim().split(/\s+/);
    const firstName = nameParts[0] || '';
    const lastName = nameParts.slice(1).join(' ') || '';
    return { card, expiry, cvv, phone, smsToken, name, firstName, lastName, street, city, state, zip, country };
  }

  // 生成 PayPal 友好的强密码：大小写 + 数字 + 唯一允许的符号 "+"（已测试可通过 signup）
  function genPassword(len = 14) {
    const up = 'ABCDEFGHJKLMNPQRSTUVWXYZ';
    const lo = 'abcdefghijkmnopqrstuvwxyz';
    const nu = '23456789';
    const sy = '+';
    const all = up + lo + nu + sy;
    const pick = s => s[Math.floor(Math.random() * s.length)];
    // 保证至少各有一位大写、小写、数字、+ 号
    let pwd = pick(up) + pick(lo) + pick(nu) + sy;
    for (let i = 0; i < len - 4; i++) pwd += pick(all);
    return pwd.split('').sort(() => Math.random() - 0.5).join('');
  }

  // 统计自动移除的人机元素次数（供执行日志展示）
  let autoCaptchaRemoved = 0;

  // ========== 跳过人机验证 ==========
  function skipCaptcha() {
    let removed = 0;
    const selectors = [
      '#captchaComponent',
      '.captcha-overlay',
      '.captcha-container',
      '.appChallengeNS',
      'iframe[src*="recaptcha"]',
      'iframe[title*="recaptcha" i]',
      'div[id^="challenge"]',
      '#g-anomalydetection-div',
    ];
    for (const sel of selectors) {
      document.querySelectorAll(sel).forEach(el => { el.remove(); removed++; });
    }
    // 宽松兜底：任何含 recaptcha 关键字的 iframe / div
    document.querySelectorAll('iframe').forEach(f => {
      if (/recaptcha|captcha|challenge/i.test(f.src || '') || /recaptcha|captcha|challenge/i.test(f.title || '')) {
        f.remove(); removed++;
      }
    });
    // 移除可能挡住页面的全屏 overlay
    document.querySelectorAll('div').forEach(d => {
      const cs = getComputedStyle(d);
      if (cs.position === 'fixed' && /visible/i.test(cs.visibility) &&
          parseInt(cs.zIndex || '0') > 1000000 &&
          /captcha|challenge/i.test((d.className || '') + ' ' + (d.id || ''))) {
        d.remove(); removed++;
      }
    });
    // 解锁滚动
    document.documentElement.style.overflow = '';
    document.body.style.overflow = '';
    return removed;
  }

  // 启动自动监控：只要 DOM 里出现人机验证相关节点就立刻移除
  function startCaptchaWatcher() {
    // 页面加载先跑一次
    autoCaptchaRemoved += skipCaptcha();
    const mo = new MutationObserver(() => {
      const hit = document.getElementById('captchaComponent') ||
        document.querySelector('.captcha-overlay, .captcha-container, .appChallengeNS') ||
        document.querySelector('iframe[src*="recaptcha"]');
      if (hit) autoCaptchaRemoved += skipCaptcha();
    });
    mo.observe(document.documentElement, { childList: true, subtree: true });
    // 再加一个 2s 的兜底轮询，防止 MutationObserver 被页面重置
    setInterval(() => { autoCaptchaRemoved += skipCaptcha(); }, 2000);
  }

  // ========== 主流程：一键填写 ==========
  async function fillAll({ phone, card, password }) {
    const fillOnceKey = 'ppaf_signup_fill_once:' + location.origin + location.pathname;
    if (sessionStorage.getItem(fillOnceKey) === '1') return ['ℹ️ PayPal 注册页已自动填写过，本次跳过'];
    sessionStorage.setItem(fillOnceKey, '1');

    const steps = [];
    const fallbackJpAddress = pickRandomJapaneseAddress();
    const useRandomJpAddress = isPaypalSignupPage() || card.country === 'JP';
    if (useRandomJpAddress) {
      steps.push(`ℹ️ 随机日本地址: ${fallbackJpAddress.zip} ${fallbackJpAddress.state}${fallbackJpAddress.city}${fallbackJpAddress.line1} ${fallbackJpAddress.line2}`);
    }

    const emailInput = document.querySelector('input#email[type="email"]') ||
      document.querySelector('input[name="email"][autocomplete="email"]') ||
      findField({
        tag: 'input',
        names: ['email'],
        placeholders: ['email', 'メール'],
        labels: ['email', 'メール']
      });
    if (emailInput) {
      const email = genEmail();
      if (await typeEmailCharByChar(emailInput, email)) {
        steps.push('✅ メール: ' + email);
        await fieldPause();
      }
    }

    // 手机号
    const phoneInput = findField({
      tag: 'input',
      names: ['phone', 'phoneNumber', 'telephone'],
      placeholders: ['phone'],
      labels: ['phone number']
    });
    if (phoneInput && phone) {
      await humanType(phoneInput, phone);
      steps.push('✅ 手机号: ' + phone);
      await fieldPause();
    } else if (!phoneInput) {
      steps.push('⚠️ 未找到手机号输入框');
    }

    // 卡号
    const cardInput = findField({
      tag: 'input',
      names: ['cardNumber', 'creditCardNumber'],
      placeholders: ['card number'],
      labels: ['card number']
    });
    if (cardInput) {
      await humanType(cardInput, card.card);
      steps.push('✅ 卡号: ' + card.card.replace(/(\d{4})(?=\d)/g, '$1 '));
      await fieldPause();
    }

    // 有效期
    const expInput = findField({
      tag: 'input',
      names: ['expirationDate', 'expiry', 'cardExpiry'],
      placeholders: ['expiration', 'mm / yy', 'mm/yy'],
      labels: ['expiration']
    });
    if (expInput) {
      // 转成 MM/YY
      const [y, m] = card.expiry.split('/');
      const mm = (m || '').padStart(2, '0');
      const yy = (y || '').slice(-2);
      await humanType(expInput, `${mm}/${yy}`);
      steps.push('✅ 有效期: ' + `${mm}/${yy}`);
      await fieldPause();
    }

    // CVV
    const cvvInput = findField({
      tag: 'input',
      names: ['cvv', 'cvc', 'securityCode', 'cardCvv'],
      placeholders: ['cvv', 'cvc', 'security code'],
      labels: ['cvv', 'cvc', 'security code']
    });
    if (cvvInput) {
      await humanType(cvvInput, card.cvv);
      steps.push('✅ CVV: ' + card.cvv);
      await fieldPause();
    }

    // First name / Last name
    const firstInput = findField({
      tag: 'input',
      names: ['firstName', 'givenName'],
      placeholders: ['first name'], labels: ['first name']
    });
    if (firstInput) {
      await humanType(firstInput, card.firstName);
      steps.push('✅ First name: ' + card.firstName);
      await fieldPause();
    }

    const lastInput = findField({
      tag: 'input',
      names: ['lastName', 'familyName', 'surname'],
      placeholders: ['last name'], labels: ['last name']
    });
    if (lastInput) {
      await humanType(lastInput, card.lastName);
      steps.push('✅ Last name: ' + card.lastName);
      await fieldPause();
    }

    const kanaName = genKanaName();
    const kanaFirstInput = document.getElementById('countrySpecificFirstName') ||
      document.querySelector('input[name="fname"][aria-describedby="use-kana-names"]') ||
      document.querySelector('[data-testid="kana-names"] input[autocomplete="given-name"]');
    if (kanaFirstInput) {
      await humanType(kanaFirstInput, kanaName.firstName);
      steps.push('✅ かな名: ' + kanaName.firstName);
      await fieldPause();
    }

    const kanaLastInput = document.getElementById('countrySpecificLastName') ||
      document.querySelector('input[name="lname"][aria-describedby="use-kana-names"]') ||
      document.querySelector('[data-testid="kana-names"] input[autocomplete="family-name"]');
    if (kanaLastInput) {
      await humanType(kanaLastInput, kanaName.lastName);
      steps.push('✅ かな姓: ' + kanaName.lastName);
      await fieldPause();
    }

    // 街道
    const streetInput = findField({
      tag: 'input',
      names: ['addressLine1', 'streetAddress', 'line1', 'billingAddressLine1', 'billingLine1', 'billingAddressLine', 'street', 'address1'],
      placeholders: ['street address', 'address line 1', 'street', '番地'],
      labels: ['street address', 'address', '番地', '住所1']
    });
    if (streetInput) {
      const street = useRandomJpAddress ? fallbackJpAddress.line1 : (card.street || fallbackJpAddress.line1);
      await humanType(streetInput, street);
      steps.push('✅ 街道: ' + street);
      await fieldPause();
    }

    const line2Input = document.getElementById('billingLine2') ||
      document.querySelector('input[name="billingLine2"]') ||
      findField({
        tag: 'input',
        names: ['addressLine2', 'line2', 'billingAddressLine2', 'billingLine2', 'address2'],
        placeholders: ['address line 2', 'building', 'apartment', 'unit', '建物名', '部屋番号'],
        labels: ['address line 2', 'building', 'apartment', '建物名', '部屋番号']
      });
    if (line2Input) {
      await humanType(line2Input, fallbackJpAddress.line2);
      steps.push('✅ 建物名: ' + fallbackJpAddress.line2);
      await fieldPause();
    }

    // 城市
    const cityInput = findField({
      tag: 'input',
      names: ['city', 'locality', 'billingLocality', 'billingCity', 'municipality'],
      placeholders: ['city', '市区町村'], labels: ['city', '市区町村']
    });
    if (cityInput) {
      const city = useRandomJpAddress ? fallbackJpAddress.city : (card.city || fallbackJpAddress.city);
      await humanType(cityInput, city);
      steps.push('✅ 城市: ' + city);
      await fieldPause();
    }

    // 州（select）
    const stateSelect = document.querySelector('select[name="state"]') ||
      document.querySelector('select[name="stateCode"]') ||
      document.querySelector('select[name="billingState"]') ||
      document.getElementById('billingState') ||
      document.querySelector('select[name="billingAdministrativeArea"]') ||
      findSelectByKeywords(['prefecture', '都道府県', '県', 'state', 'province']) ||
      Array.from(document.querySelectorAll('select')).find(s => {
        const opts = Array.from(s.options || []);
        return opts.some(o => /California|Texas|New York|東京都|大阪府|北海道/.test(o.textContent));
      });
    if (stateSelect) {
      try { stateSelect.scrollIntoView({ behavior: 'smooth', block: 'center' }); await sleep(250); } catch (_) {}
      const targetName = useRandomJpAddress
        ? fallbackJpAddress.state
        : card.country === 'JP'
        ? normalizeJapanesePrefectureForSelect(card.state)
        : (resolveAdministrativeAreaName(card.state, card.country) || ZIP_PREFIX_TO_STATE[card.zip.substring(0, 2)] || '');
      const targetNames = useRandomJpAddress
        ? [targetName]
        : card.country === 'JP'
        ? [targetName, resolveAdministrativeAreaName(card.state, 'JP'), card.state]
          .map(v => String(v || '').trim())
          .filter(Boolean)
        : [targetName].filter(Boolean);
      let matched = null;
      for (const opt of stateSelect.options) {
        const txt = (opt.textContent || '').trim();
        const val = (opt.value || '').trim();
        if (!val) continue;
        if (!targetNames.length) continue;
        if (targetNames.some(name => txt === name || STATE_MAP[val] === name || txt.includes(name) || val === name)) {
          matched = opt; break;
        }
      }
      if (matched) {
        setNativeValue(stateSelect, matched.value);
        steps.push(`✅ ${card.country === 'JP' ? '都道府县' : '州'}: ` + matched.textContent.trim());
        await fieldPause();
      }
    } else {
      const targetName = useRandomJpAddress
        ? fallbackJpAddress.state
        : card.country === 'JP'
        ? normalizeJapanesePrefectureForSelect(card.state)
        : '';
      const stateCombobox = findComboboxByKeywords(['prefecture', '都道府県', '県', 'state', 'province']);
      if (stateCombobox && await selectComboboxOptionByText(stateCombobox, [targetName])) {
        steps.push(`✅ 都道府县: ${targetName}`);
        await fieldPause();
      }
    }

    // 邮编
    const zipInput = findField({
      tag: 'input',
      names: ['postalCode', 'zip', 'zipCode', 'billingPostalCode', 'postcode'],
      placeholders: ['zip', 'postal', 'postal code', '郵便番号'], labels: ['zip', 'postal', 'postal code', '郵便番号']
    });
    if (zipInput) {
      const zip = useRandomJpAddress ? fallbackJpAddress.zip : (card.zip || fallbackJpAddress.zip);
      await humanType(zipInput, zip);
      steps.push('✅ 邮编: ' + zip);
      await fieldPause();
    }

    const dobInput = document.getElementById('dateOfBirth') || document.querySelector('input[name="dateOfBirth"]');
    if (dobInput) {
      const dob = formatDobForInput(dobInput, genJapaneseDob());
      await humanType(dobInput, dob);
      steps.push('✅ 生年月日: ' + dob);
      await fieldPause();
    }

    // 密码
    const pwdInput = findField({
      tag: 'input',
      names: ['password', 'createPassword', 'newPassword'],
      placeholders: ['create password', 'password'], labels: ['create password', 'password']
    });
    if (pwdInput) {
      await humanType(pwdInput, password);
      steps.push('✅ 密码: <code style="background:#0a1320;padding:2px 6px;border-radius:4px;color:#4fc3f7">' + password + '</code>');
    }

    if (await clickCreateAccountAndContinueAfterFill()) {
      steps.push('✅ 已点击 同意して続行');
    }

    return steps;
  }

  // ========== 弹窗 ==========
  function showModal() {
    const overlay = document.createElement('div');
    overlay.className = 'ppaf-overlay';

    overlay.innerHTML = `
      <div class="ppaf-modal">
        <h3>PayPal 注册自动填写</h3>

        <label>手机号（按国家填写，可含国家码）</label>
        <input id="ppaf-phone" type="text" placeholder="+819012345678 或 9498756109" />

        <label>卡信息（步骤2格式）</label>
        <textarea id="ppaf-card" placeholder="卡号----有效期----CVV----电话----sms-token----姓名----街道,城市 邮编,国家 或 都道府县,城市,街道,邮编[,国家]"></textarea>
        <div class="ppaf-hint">
          示例: 4859540169598884----2030/1----729----+19498756109----sms-token:xxx----TERRY SCHULTZ----18440 COUNTRY CLUB DR,MACOMB 48042-6217,US<br>
          日本示例: 4859540169598884----2030/1----729----+819012345678----sms-token:xxx----TARO YAMADA----ホッカイドウ,サッポロシテイネク,カナヤマ1ジョウ,298-1221
        </div>

        <div class="ppaf-btns">
          <button class="ppaf-btn ppaf-btn-cancel" id="ppaf-cancel">取消</button>
          <button class="ppaf-btn ppaf-btn-warn" id="ppaf-skip">跳过人机验证</button>
          <button class="ppaf-btn ppaf-btn-primary" id="ppaf-fill">一键填写</button>
        </div>
      </div>
    `;

    document.body.appendChild(overlay);

    // 从 chrome.storage (步骤2共享) 优先回填，失败再 fallback 到 localStorage
    try {
      chrome.storage.local.get(['lastCardInput', 'lastPhone'], (res) => {
        if (res) {
          const cardBox = overlay.querySelector('#ppaf-card');
          const phoneBox = overlay.querySelector('#ppaf-phone');
          if (res.lastCardInput && !cardBox.value) cardBox.value = res.lastCardInput;
          if (res.lastPhone && !phoneBox.value) phoneBox.value = res.lastPhone;
        }
      });
    } catch (_) {}

    // 从 localStorage 回填上次输入（兜底，同域快速缓存）
    try {
      const lastPhone = localStorage.getItem('ppaf_phone');
      const lastCard = localStorage.getItem('ppaf_card');
      const phoneBox = overlay.querySelector('#ppaf-phone');
      const cardBox = overlay.querySelector('#ppaf-card');
      if (lastPhone && !phoneBox.value) phoneBox.value = lastPhone;
      if (lastCard && !cardBox.value) cardBox.value = lastCard;
    } catch (_) {}

    overlay.querySelector('#ppaf-cancel').onclick = () => overlay.remove();

    overlay.querySelector('#ppaf-skip').onclick = () => {
      const n = skipCaptcha();
      showToast(n > 0 ? `✅ 已移除 ${n} 个人机验证元素` : '⚠️ 未发现人机验证元素', 4000);
    };

    overlay.querySelector('#ppaf-fill').onclick = async () => {
      const phone = overlay.querySelector('#ppaf-phone').value.trim();
      const cardText = overlay.querySelector('#ppaf-card').value.trim();
      if (!cardText) { showToast('❌ 请先粘贴卡信息'); return; }

      let card;
      try { card = parseCard(cardText); } catch (e) { showToast('❌ ' + e.message); return; }

      try {
        localStorage.setItem('ppaf_phone', phone);
        localStorage.setItem('ppaf_card', cardText);
      } catch (_) {}
      try {
        chrome.storage.local.set({
          lastCardInput: cardText,
          lastPhone: phone,
          lastCardSavedAt: Date.now(),
        });
      } catch (_) {}

      const password = genPassword(14);
      overlay.remove();
      showToast('⏳ 开始自动填写...', 3000);

      try {
        const results = await fillAll({ phone, card, password });
        results.push('<br>🔑 随机密码: <code style="background:#0a1320;padding:2px 6px;border-radius:4px;color:#4fc3f7">' + password + '</code>');
        if (autoCaptchaRemoved > 0) {
          results.push('🛡️ 移除人机成功（共 ' + autoCaptchaRemoved + ' 次）');
        }
        showToast(results.join('<br>'), 15000);
      } catch (e) {
        showToast('❌ 执行失败: ' + e.message, 8000);
      }
    };

    setTimeout(() => {
      const el = overlay.querySelector('#ppaf-phone');
      if (el && !el.value) el.focus();
      else overlay.querySelector('#ppaf-card').focus();
    }, 100);
  }

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

  // ========== 创建按钮 ==========
  function createButton() {
    if (document.getElementById('ppaf-btn')) return;
    const btn = document.createElement('button');
    btn.id = 'ppaf-btn';
    btn.title = 'PayPal 自动填写（可拖动）';
    btn.textContent = 'PP';
    btn.addEventListener('click', showModal);
    document.body.appendChild(btn);
    makeDraggable(btn, 'ppaf-btn-pos');
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      createButton();
      startCaptchaWatcher();
      autoSwitchJapanOnPayPage();
      autoSwitchJapanAndFillOnSignupPage();
      autoStartPaypalSmsWatcherIfNeeded();
      autoClickHermesContinuePage();
    });
  } else {
    createButton();
    startCaptchaWatcher();
    autoSwitchJapanOnPayPage();
    autoSwitchJapanAndFillOnSignupPage();
    autoStartPaypalSmsWatcherIfNeeded();
    autoClickHermesContinuePage();
  }

  // PayPal 是 SPA，表单可能后加载，监听变化重新确保按钮存在
  const mo = new MutationObserver(() => {
    if (!document.getElementById('ppaf-btn') && document.body) createButton();
    autoSwitchJapanAndFillOnSignupPage();
    autoStartPaypalSmsWatcherIfNeeded();
    autoClickHermesContinuePage();
  });
  mo.observe(document.documentElement, { childList: true, subtree: true });
})();
