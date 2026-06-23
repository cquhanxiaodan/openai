// Stripe Checkout Auto Fill - Content Script

(function () {
  'use strict';

  // ========== 样式 ==========
  const style = document.createElement('style');
  style.textContent = `
    #stripe-autofill-btn {
      position: fixed; top: 20px; right: 20px; z-index: 2147483647;
      width: 56px; height: 56px; border-radius: 50%; border: 3px solid #fff;
      background: linear-gradient(135deg, #635bff, #80e9ff);
      cursor: pointer; box-shadow: 0 4px 16px rgba(99,91,255,0.5);
      display: flex; align-items: center; justify-content: center;
      transition: all 0.3s ease; user-select: none; padding: 0;
    }
    #stripe-autofill-btn:hover { transform: scale(1.1); box-shadow: 0 6px 24px rgba(99,91,255,0.7); }
    #stripe-autofill-btn:active { transform: scale(0.95); }
    #stripe-autofill-btn svg { width: 36px; height: 36px; pointer-events: none; }

    .saf-overlay {
      position: fixed; inset: 0; z-index: 999999;
      background: rgba(0,0,0,0.6); backdrop-filter: blur(4px);
      display: flex; align-items: center; justify-content: center;
    }
    .saf-modal {
      background: #1a1a2e; color: #e0e0e0; padding: 28px 32px;
      border-radius: 16px; width: 520px; max-width: 92vw;
      box-shadow: 0 16px 48px rgba(0,0,0,0.5);
      border: 1px solid rgba(99,91,255,0.3);
      font-family: system-ui, -apple-system, sans-serif;
    }
    .saf-modal h3 { margin: 0 0 16px; color: #80e9ff; font-size: 18px; }
    .saf-modal textarea {
      width: 100%; height: 80px; background: #0d0d1a; color: #e0e0e0;
      border: 1px solid rgba(99,91,255,0.3); border-radius: 8px;
      padding: 12px; font-size: 13px; font-family: 'Cascadia Code', 'Fira Code', monospace;
      resize: vertical; box-sizing: border-box; outline: none;
    }
    .saf-modal textarea:focus { border-color: #635bff; }
    .saf-hint { font-size: 11px; color: #888; margin-top: 6px; line-height: 1.5; }
    .saf-btns { display: flex; gap: 12px; margin-top: 20px; justify-content: flex-end; }
    .saf-btn {
      padding: 10px 24px; border-radius: 8px; border: none;
      font-size: 14px; font-weight: 600; cursor: pointer;
      transition: all 0.2s;
    }
    .saf-btn-cancel { background: #2a2a3e; color: #aaa; }
    .saf-btn-cancel:hover { background: #3a3a4e; }
    .saf-btn-ok { background: linear-gradient(135deg, #635bff, #80e9ff); color: #fff; }
    .saf-btn-ok:hover { opacity: 0.9; }

    .saf-toast {
      position: fixed; top: 20px; right: 20px; z-index: 9999999;
      background: #1a1a2e; color: #fff; padding: 16px 20px;
      border-radius: 12px; font-size: 13px; line-height: 1.8;
      box-shadow: 0 8px 32px rgba(0,0,0,0.3);
      border: 1px solid rgba(99,91,255,0.5);
      max-width: 400px; font-family: system-ui, sans-serif;
    }
  `;
  document.head.appendChild(style);

  const catSVG = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="36" height="36">
    <defs><linearGradient id="sg" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" style="stop-color:#635bff"/><stop offset="100%" style="stop-color:#80e9ff"/></linearGradient></defs>
    <circle cx="32" cy="36" r="24" fill="url(#sg)"/>
    <polygon points="14,20 18,8 28,18" fill="url(#sg)" stroke="#fff" stroke-width="1.5"/>
    <polygon points="50,20 46,8 36,18" fill="url(#sg)" stroke="#fff" stroke-width="1.5"/>
    <circle cx="24" cy="32" r="3" fill="#fff"/><circle cx="40" cy="32" r="3" fill="#fff"/>
    <circle cx="25" cy="31" r="1.2" fill="#333"/><circle cx="41" cy="31" r="1.2" fill="#333"/>
    <ellipse cx="32" cy="38" rx="2" ry="1.5" fill="#ff6b81"/>
    <path d="M30,38 Q32,41 34,38" fill="none" stroke="#ff6b81" stroke-width="1" stroke-linecap="round"/>
  </svg>`;

  // ========== 工具函数 ==========
  const sleep = ms => new Promise(r => setTimeout(r, ms));

  // 用原生 setter 修改受 React 控制的 <select> / <input> 值，保证 onChange 被触发
  function setNativeValue(el, value) {
    const proto = el instanceof HTMLSelectElement
      ? HTMLSelectElement.prototype
      : (el instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype);
    const desc = Object.getOwnPropertyDescriptor(proto, 'value');
    if (desc && desc.set) {
      desc.set.call(el, value);
    } else {
      el.value = value;
    }
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  }

  const COUNTRY_LABELS = {
    US: ['United States', 'USA', '美国', '美國'],
    JP: ['Japan', '日本'],
    BR: ['Brazil', 'Brasil', '巴西']
  };

  function normalizeCountryCode(value) {
    const text = String(value || '').trim();
    if (!text) return '';
    const upper = text.toUpperCase();
    if (upper === 'US' || upper === 'USA' || text === '美国' || text === '美國' || /united states/i.test(text)) return 'US';
    if (upper === 'JP' || text === '日本' || /japan/i.test(text)) return 'JP';
    if (upper === 'BR' || text === '巴西' || /brazil|brasil/i.test(text)) return 'BR';
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

  function normalizePostalCandidates(value, country) {
    const text = String(value || '').trim();
    if (!text) return [];
    if (country === 'JP') {
      const normalized = extractJapanesePostalCode(text);
      if (!normalized) return [text];
      return [normalized];
    }
    return [text];
  }

  function normalizePostalValue(value, country) {
    const text = String(value || '').trim();
    if (!text) return '';
    if (country === 'JP') return text.replace(/\D/g, '');
    return text;
  }

  function extractBrazilPostalCode(value) {
    const match = String(value || '').match(/(\d{5})\s*[-‐‑‒–—―]?\s*(\d{3})/);
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

  const BR_STATE_MAP = {
    AC: 'Acre', AL: 'Alagoas', AP: 'Amapa', AM: 'Amazonas', BA: 'Bahia', CE: 'Ceara',
    DF: 'Distrito Federal', ES: 'Espirito Santo', GO: 'Goias', MA: 'Maranhao', MT: 'Mato Grosso',
    MS: 'Mato Grosso do Sul', MG: 'Minas Gerais', PA: 'Para', PB: 'Paraiba', PR: 'Parana',
    PE: 'Pernambuco', PI: 'Piaui', RJ: 'Rio de Janeiro', RN: 'Rio Grande do Norte', RS: 'Rio Grande do Sul',
    RO: 'Rondonia', RR: 'Roraima', SC: 'Santa Catarina', SP: 'Sao Paulo', SE: 'Sergipe', TO: 'Tocantins'
  };

  function resolveAdministrativeAreaName(value, country) {
    const text = String(value || '').trim();
    if (!text) return '';
    if (country === 'JP') {
      return JP_PREFECTURE_MAP[text] || text;
    }
    if (country === 'BR') {
      const upper = text.toUpperCase();
      return BR_STATE_MAP[upper] || text;
    }
    return text;
  }

  function normalizeBrazilDocument(value) {
    const digits = String(value || '').replace(/\D/g, '');
    if (digits.length === 11) return digits.replace(/(\d{3})(\d{3})(\d{3})(\d{2})/, '$1.$2.$3-$4');
    if (digits.length === 14) return digits.replace(/(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})/, '$1.$2.$3/$4-$5');
    return String(value || '').trim();
  }

  function findInputByKeywords(keywords) {
    return Array.from(document.querySelectorAll('input')).find(input => {
      const meta = `${input.name || ''} ${input.id || ''} ${input.placeholder || ''} ${input.getAttribute('aria-label') || ''}`.toLowerCase();
      const nearby = `${input.parentElement?.textContent || ''} ${input.closest('label')?.textContent || ''}`.toLowerCase();
      return keywords.some(keyword => meta.includes(keyword) || nearby.includes(keyword));
    }) || null;
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

  async function getSavedCardData() {
    const stored = await getChromeStorage(['lastCardInput', 'lastCardData']);
    const rawInput = stored.lastCardInput || (() => {
      try {
        return localStorage.getItem('opencode_paypal_card') || localStorage.getItem('lastCardInput') || localStorage.getItem('ppaf_card') || '';
      } catch (_) {
        return '';
      }
    })();

    if (rawInput) {
      try { return parseInput(rawInput); } catch (_) {}
    }
    if (stored.lastCardData && stored.lastCardData.zip) return stored.lastCardData;
    return null;
  }

  function findSelectByKeywords(keywords) {
    return Array.from(document.querySelectorAll('select')).find(select => {
      const meta = `${select.name || ''} ${select.id || ''} ${select.getAttribute('aria-label') || ''}`.toLowerCase();
      const text = (select.parentElement?.textContent || '').toLowerCase();
      const nearby = (select.closest('label')?.textContent || '').toLowerCase();
      return keywords.some(keyword => meta.includes(keyword) || text.includes(keyword) || nearby.includes(keyword));
    }) || null;
  }

  // 返回 'changed' | 'already' | 'notfound'
  async function setCountry(targetCountry) {
    const normalizedCountry = COUNTRY_LABELS[targetCountry] ? targetCountry : 'US';
    const select = document.querySelector('select[name="billingCountry"]') || findSelectByKeywords(['country', 'billing country', '国']);
    if (!select) return 'notfound';
    if ((select.value || '').toUpperCase() === normalizedCountry) return 'already';

    const hasTarget = Array.from(select.options).some(o => (o.value || '').toUpperCase() === normalizedCountry);
    if (!hasTarget) return 'notfound';

    setNativeValue(select, normalizedCountry);
    await sleep(1200);
    return 'changed';
  }

  // 页面加载后如果已保存上次卡信息，则按地址国家自动切换。
  async function autoSwitchCountryOnLoad() {
    let targetCountry = '';
    try {
      targetCountry = (await getSavedCardData())?.country || '';
    } catch (_) {}
    if (!targetCountry) return;

    for (let i = 0; i < 30; i++) {
      const res = await setCountry(targetCountry);
      if (res === 'changed') {
        showToast(`✅ 已自动将账单国家改为 ${(COUNTRY_LABELS[targetCountry] && COUNTRY_LABELS[targetCountry][0]) || targetCountry}`, 2500);
        return;
      }
      if (res === 'already') return;
      await sleep(500);
    }
  }

  // 模拟人工键盘输入 - 完整键盘事件序列 + 原生 setter，带随机延迟
  async function humanType(input, value) {
    if (!input) return;
    // 先滚到视口中间，方便观察
    try {
      input.scrollIntoView({ behavior: 'smooth', block: 'center' });
      await sleep(250);
    } catch (_) {}
    input.focus();
    input.dispatchEvent(new Event('focus', { bubbles: true }));
    // 用原生 setter 先清空，兼容 React
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
      // 每字符 80-220ms 随机，偶尔额外停顿（像人停下想一下）
      let d = 80 + Math.random() * 140;
      if (Math.random() < 0.08) d += 200 + Math.random() * 300;
      await sleep(d);
    }
    input.dispatchEvent(new Event('change', { bubbles: true }));
    input.dispatchEvent(new Event('blur', { bubbles: true }));
  }

  async function ensureInputValue(input, value, attempts = 3) {
    if (!input) return false;
    const expected = String(value || '').trim();
    for (let i = 0; i < attempts; i += 1) {
      await humanType(input, expected);
      await sleep(250);
      const actual = String(input.value || '').trim();
      if (actual === expected) return true;
      setNativeValue(input, expected);
      try { input.setAttribute('value', expected); } catch (_) {}
      try { input.defaultValue = expected; } catch (_) {}
      input.dispatchEvent(new Event('blur', { bubbles: true }));
      await sleep(250);
      if (String(input.value || '').trim() === expected) return true;
    }
    return String(input.value || '').trim() === expected;
  }

  function postalValueMatches(actual, expected, country) {
    return normalizePostalValue(actual, country) === normalizePostalValue(expected, country);
  }

  function postalCandidateMatches(actual, expected, country) {
    const actualText = String(actual || '').trim();
    const expectedText = String(expected || '').trim();
    if (country === 'JP' && expectedText === extractJapanesePostalCode(expectedText)) return actualText === expectedText;
    return postalValueMatches(actualText, expectedText, country);
  }

  function findBillingPostalInput() {
    return document.getElementById('billingPostalCode') ||
      document.querySelector('input[name="billingPostalCode"]') ||
      document.querySelector('input[autocomplete="billing postal-code"]') ||
      document.querySelector('input[placeholder="ZIP"]') ||
      document.querySelector('input[placeholder="Postal code"]') ||
      document.querySelector('input[aria-label="Postal code"]') ||
      findInputNearText(['postal code', 'postal']) ||
      Array.from(document.querySelectorAll('input')).find(input => {
        const meta = `${input.name || ''} ${input.id || ''} ${input.placeholder || ''} ${input.getAttribute('aria-label') || ''} ${input.getAttribute('autocomplete') || ''}`.toLowerCase();
        const nearby = `${input.parentElement?.textContent || ''} ${input.closest('label')?.textContent || ''}`.toLowerCase();
        return /postal|zip/.test(meta) || /postal code|zip/.test(nearby);
      }) || null;
  }

  function findInputNearText(texts) {
    const labels = Array.from(document.querySelectorAll('label, div, span, p'));
    for (const node of labels) {
      const text = (node.textContent || '').trim().toLowerCase();
      if (!texts.some(item => text === item || text.includes(item))) continue;
      const parent = node.parentElement;
      if (!parent) continue;
      const candidates = parent.querySelectorAll('input');
      for (const input of candidates) {
        const rect = input.getBoundingClientRect();
        const style = getComputedStyle(input);
        if (rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden') return input;
      }
      let sibling = node.nextElementSibling;
      while (sibling) {
        const input = sibling.querySelector?.('input') || (sibling.tagName === 'INPUT' ? sibling : null);
        if (input) return input;
        sibling = sibling.nextElementSibling;
      }
    }
    return null;
  }

  // 字段之间的随机间隔（模拟人思考/切换）
  const fieldPause = () => sleep(350 + Math.random() * 500);

  // 等待某个选择器出现并可见，最多等 timeout ms
  async function waitFor(selector, timeout = 10000) {
    const start = Date.now();
    while (Date.now() - start < timeout) {
      const el = typeof selector === 'function' ? selector() : document.querySelector(selector);
      if (el) return el;
      await sleep(200);
    }
    return null;
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

  function showToast(msg, duration = 5000) {
    const t = document.createElement('div');
    t.className = 'saf-toast';
    t.innerHTML = msg;
    document.body.appendChild(t);
    setTimeout(() => t.remove(), duration);
  }

  // ========== 解析用户输入 ==========
  // 格式: 卡号----有效期----CVV----电话----sms-token----姓名----地址
  // 地址格式: 街道,城市 邮编,国家 或 都道府县,城市,街道,邮编[,国家]
  function parseInput(text) {
    const parts = text.trim().split(/----/);
    if (parts.length < 7) throw new Error('格式错误，需要7个字段用 ---- 分隔');

    if (parts.length >= 9 && normalizeCountryCode(parts[parts.length - 1]) === 'BR') {
      const [cpf, name, line1, line2, neighborhood, city, state, postalCode, countryRaw] = parts.map(s => s.trim());
      return {
        card: '',
        expiry: '',
        expMonth: '',
        expYear: '',
        cvv: '',
        phone: '',
        smsToken: '',
        cpf: normalizeBrazilDocument(cpf),
        name,
        street: line1,
        line2,
        neighborhood,
        city,
        state,
        zip: extractBrazilPostalCode(postalCode) || postalCode,
        country: normalizeCountryCode(countryRaw) || 'BR',
        paymentMethod: 'PIX'
      };
    }

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
      const hasExplicitCountry = !!country;
      if (!country) country = 'JP';
      const core = hasExplicitCountry ? addrParts.slice(0, -1) : addrParts.slice();
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

    // 解析有效期 "2030/1" → month=01, year=2030
    const expParts = expiry.split('/');
    const expMonth = expParts[1]?.padStart(2, '0') || '';
    const expYear = expParts[0] || '';

    return { card, expiry, expMonth, expYear, cvv, phone, smsToken, name, street, city, state, zip, country, paymentMethod: 'PAYPAL' };
  }

  async function fillBrazilPix(data, steps) {
    const pixButton = Array.from(document.querySelectorAll('button, label, [role="button"]')).find(el => /pix/i.test((el.textContent || '').trim()));
    if (pixButton) {
      simulateClick(pixButton);
      steps.push('✅ 已选择 Pix');
      await sleep(600);
    }

    const cpfInput = findInputByKeywords(['cpf', 'cnpj', '000.000.000-00']);
    if (cpfInput && data.cpf) {
      await humanType(cpfInput, data.cpf);
      steps.push('✅ CPF/CNPJ: ' + data.cpf);
      await fieldPause();
    }

    const nameInput = document.querySelector('input[name="billingName"]') ||
      document.querySelector('input[autocomplete="name"]') ||
      findInputByKeywords(['full name', 'first and last name', 'name']);
    if (nameInput) {
      await humanType(nameInput, data.name);
      steps.push('✅ 姓名: ' + data.name);
      await fieldPause();
    }

    const line1Input = findInputByKeywords(['address line 1', 'billingaddressline1', 'address']);
    if (line1Input) {
      await humanType(line1Input, data.street);
      steps.push('✅ 地址1: ' + data.street);
      await fieldPause();
    }

    const line2Input = findInputByKeywords(['address line 2', 'billingaddressline2']);
    if (line2Input && data.line2) {
      await humanType(line2Input, data.line2);
      steps.push('✅ 地址2: ' + data.line2);
      await fieldPause();
    }

    const neighborhoodInput = findInputByKeywords(['neighborhood']);
    if (neighborhoodInput && data.neighborhood) {
      await humanType(neighborhoodInput, data.neighborhood);
      steps.push('✅ Neighborhood: ' + data.neighborhood);
      await fieldPause();
    }

    const cityInput = document.querySelector('input[name="billingLocality"]') ||
      document.querySelector('input[placeholder="City"]') ||
      findInputByKeywords(['city']);
    if (cityInput) {
      await humanType(cityInput, data.city);
      steps.push('✅ 城市: ' + data.city);
      await fieldPause();
    }

    const stateSelect = document.querySelector('select[name="billingAdministrativeArea"]') || findSelectByKeywords(['state']);
    if (stateSelect) {
      const targetState = resolveAdministrativeAreaName(data.state, 'BR');
      for (const opt of stateSelect.options) {
        const optText = (opt.textContent || '').trim();
        const optValue = (opt.value || '').trim();
        if (optText === targetState || optValue.toUpperCase() === String(data.state || '').toUpperCase() || optText.toLowerCase().includes(String(targetState || '').toLowerCase())) {
          stateSelect.value = opt.value;
          stateSelect.dispatchEvent(new Event('change', { bubbles: true }));
          steps.push('✅ 州: ' + optText);
          await fieldPause();
          break;
        }
      }
    }

    const postalInput = document.querySelector('input[name="billingPostalCode"]') ||
      document.querySelector('input[placeholder="Postal code"]') ||
      findInputByKeywords(['postal code', 'postal', 'zip']);
    if (postalInput && data.zip) {
      await humanType(postalInput, data.zip);
      steps.push('✅ 邮编: ' + data.zip);
      await fieldPause();
    }
  }

  async function fillVerifiedPostalCode(getInput, zip, steps, country = 'JP') {
    const input = typeof getInput === 'function' ? getInput() : getInput;
    if (!input || !zip) return false;
    const candidates = normalizePostalCandidates(zip, country);
    let ok = false;
    for (const candidate of candidates) {
      const currentInput = typeof getInput === 'function' ? getInput() : input;
      if (!currentInput) continue;
      await ensureInputValue(currentInput, candidate, 4);
      await sleep(900);
      const latestInput = typeof getInput === 'function' ? getInput() : currentInput;
      if (postalCandidateMatches(latestInput?.value, candidate, country)) {
        ok = true;
        break;
      }
    }
    steps.push((ok ? '✅' : '⚠️') + ' 邮编: ' + zip + (ok ? '' : '（页面可能又清空，建议提交前确认）'));
    await fieldPause();
    return ok;
  }

  async function stabilizeJapaneseAddress(data, steps, options = {}) {
    const silent = !!options.silent;
    const findPrefectureSelect = () => document.querySelector('select[name="billingAdministrativeArea"]') || findSelectByKeywords(['prefecture', 'state', 'province', '都道府県']);

    const start = Date.now();
    let postalLogged = false;
    let stateLogged = false;
    while (Date.now() - start < 8000) {
      const stateSelect = findPrefectureSelect();
      const targetState = resolveAdministrativeAreaName(data.state, 'JP');
      if (stateSelect && targetState) {
        const currentText = (stateSelect.options[stateSelect.selectedIndex]?.textContent || '').trim();
        if (!currentText || (!currentText.includes(targetState) && currentText !== targetState)) {
          for (const opt of stateSelect.options) {
            const optText = (opt.textContent || '').trim();
            const optValue = (opt.value || '').trim();
            if (optText === targetState || optValue === targetState || optText.includes(targetState)) {
              stateSelect.value = opt.value;
              stateSelect.dispatchEvent(new Event('change', { bubbles: true }));
              if (!silent && !stateLogged) {
                steps.push('✅ 都道府县: ' + optText);
                stateLogged = true;
              }
              break;
            }
          }
        }
      }

      const postalInput = findBillingPostalInput();
      if (postalInput && data.zip) {
        const candidates = normalizePostalCandidates(data.zip, 'JP');
        const current = String(postalInput.value || '').trim();
        const matches = candidates.some(candidate => postalCandidateMatches(current, candidate, 'JP'));
        if (!matches) {
          let ok = false;
          for (const candidate of candidates) {
            await ensureInputValue(postalInput, candidate, 2);
            await sleep(350);
            const latestPostalInput = findBillingPostalInput();
            ok = postalCandidateMatches(latestPostalInput?.value, candidate, 'JP');
            if (ok) break;
          }
          if (!silent && !postalLogged) {
            steps.push((ok ? '✅' : '⚠️') + ' 邮编: ' + data.zip + (ok ? '' : '（持续回填中）'));
            postalLogged = true;
          }
        }
      }
      await sleep(700);
    }
  }

  async function autoFillPostalCodeOnLoad() {
    const data = await getSavedCardData();
    if (!data?.zip) return;

    const start = Date.now();
    while (Date.now() - start < 20000) {
      const postalInput = findBillingPostalInput();
      if (postalInput) {
        const steps = [];
        const ok = await fillVerifiedPostalCode(() => findBillingPostalInput(), data.zip, steps, data.country || 'JP');
        if (ok) {
          showToast('✅ 已自动填写邮编: ' + data.zip, 3000);
          return;
        }
      }
      await sleep(700);
    }
  }

  async function clickSubscribeAfterFill() {
    const findSubscribeButton = () => document.querySelector('[data-testid="hosted-payment-submit-button"]') ||
      Array.from(document.querySelectorAll('button')).find(b => {
        const text = (b.textContent || '').trim();
        const meta = `${b.getAttribute('type') || ''} ${b.getAttribute('data-testid') || ''}`;
        return text.includes('Subscribe') || text.includes('Continue') || meta.includes('hosted-payment-submit-button');
      });

    for (let i = 0; i < 40; i += 1) {
      const button = findSubscribeButton();
      if (button && !button.disabled && button.getAttribute('aria-disabled') !== 'true') {
        try { button.scrollIntoView({ behavior: 'smooth', block: 'center' }); } catch (_) {}
        await sleep(200);
        simulateClick(button);
        try { button.click(); } catch (_) {}
        return true;
      }
      await sleep(250);
    }
    return false;
  }

  function findCheckoutReadyElement() {
    return document.querySelector('button[data-testid="paypal-accordion-item-button"]') ||
      document.querySelector('select[name="billingCountry"]') ||
      document.querySelector('input[name="billingName"]') ||
      document.querySelector('[data-testid="hosted-payment-submit-button"]') ||
      Array.from(document.querySelectorAll('button, label, [role="button"]')).find(el => /pix|paypal/i.test((el.textContent || '').trim())) ||
      null;
  }

  async function waitForCheckoutReady(timeout = 30000) {
    const start = Date.now();
    while (Date.now() - start < timeout) {
      const el = findCheckoutReadyElement();
      if (el) return el;
      await sleep(500);
    }
    return null;
  }

  // ========== 主流程 ==========
  async function run(data, options = {}) {
    const shouldSubmit = options.submit !== false;
    const steps = [];

    // 0. 先按输入地址切换账单国家
    const countryRes = await setCountry(data.country);
    if (countryRes === 'changed') {
      steps.push('✅ 账单国家已改为 ' + ((COUNTRY_LABELS[data.country] && COUNTRY_LABELS[data.country][0]) || data.country));
      await sleep(500);
    } else if (countryRes === 'already') {
      steps.push('✅ 账单国家已是 ' + ((COUNTRY_LABELS[data.country] && COUNTRY_LABELS[data.country][0]) || data.country));
    } else {
      steps.push('⚠️ 未找到账单国家下拉框（稍后继续尝试）');
    }

    if (data.country === 'BR' || data.paymentMethod === 'PIX') {
      await fillBrazilPix(data, steps);
    } else {
    // 1. 点击 PayPal accordion 按钮（不可见 overlay 按钮，必须用 .click()）
    const paypalBtn = document.querySelector('button[data-testid="paypal-accordion-item-button"]');
    if (paypalBtn) {
      paypalBtn.click();
      steps.push('✅ 已选择 PayPal');
    } else {
      steps.push('❌ 未找到 PayPal 选项');
      return steps;
    }

    // 1b. 等待 PayPal 面板展开 + 地址表单加载（最多 15s）
    steps.push('⏳ 等待 PayPal 地址表单加载...');
    const addressReady = await waitFor(() => {
      const line1 = document.querySelector('input[name="billingAddressLine1"], input[placeholder="Address"]');
      return line1 && line1.offsetParent !== null ? line1 : null;
    }, 15000);

    if (!addressReady) {
      // 再点一次展开 accordion，并再等一次
      paypalBtn.click();
      await sleep(1200);
      const retry = await waitFor(() => {
        const l = document.querySelector('input[name="billingAddressLine1"], input[placeholder="Address"]');
        return l && l.offsetParent !== null ? l : null;
      }, 10000);
      if (!retry) {
        steps.push('❌ 等待地址表单超时');
        return steps;
      }
      steps.push('✅ 地址表单已加载（重试后）');
    } else {
      steps.push('✅ 地址表单已加载');
    }
    await fieldPause();

    if (data.country === 'JP') {
      const countryResAfterLoad = await setCountry('JP');
      if (countryResAfterLoad === 'changed') {
        steps.push('✅ 地址表单加载后已切到 Japan');
        await sleep(1200);
      }
    }

    // 2. 点击 "Enter address manually"（如果存在）
    const allBtns = document.querySelectorAll('button');
    for (const btn of allBtns) {
      if (btn.textContent.includes('Enter address manually') || btn.textContent.includes('手动输入地址')) {
        simulateClick(btn);
        steps.push('✅ 已切换手动输入地址');
        await sleep(800);
        break;
      }
    }

    // 3. 填写姓名
    const nameInput = document.querySelector('input[name="billingName"]') ||
      document.querySelector('input[autocomplete="name"]');
    if (nameInput) {
      await humanType(nameInput, data.name);
      steps.push('✅ 姓名: ' + data.name);
      await fieldPause();
    }

    // 4. 填写地址 - 使用 name 属性精确定位，备选 placeholder
    const line1 = document.querySelector('input[name="billingAddressLine1"]') ||
      document.querySelector('input[placeholder="Address"]');
    if (line1) {
      await humanType(line1, data.street);
      steps.push('✅ 街道: ' + data.street);
      await fieldPause();
    } else {
      steps.push('❌ 未找到地址输入框');
    }

    const cityInput = document.querySelector('input[name="billingLocality"]') ||
      document.querySelector('input[placeholder="City"]');
    if (cityInput) {
      await humanType(cityInput, data.city);
      steps.push('✅ 城市: ' + data.city);
      await fieldPause();
    }

    const findPostalInput = findBillingPostalInput;

    // 选择州
    const stateSelect = document.querySelector('select[name="billingAdministrativeArea"]') || findSelectByKeywords(['prefecture', 'state', 'province', '都道府県']) || findSelectByKeywords(['北海道', 'tokyo', 'osaka', 'hokkaido']);
    if (stateSelect) {
      // 根据邮编匹配州
      const stateMap = {
        'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas',
        'CA': 'California', 'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware',
        'FL': 'Florida', 'GA': 'Georgia', 'HI': 'Hawaii', 'ID': 'Idaho',
        'IL': 'Illinois', 'IN': 'Indiana', 'IA': 'Iowa', 'KS': 'Kansas',
        'KY': 'Kentucky', 'LA': 'Louisiana', 'ME': 'Maine', 'MD': 'Maryland',
        'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota', 'MS': 'Mississippi',
        'MO': 'Missouri', 'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada',
        'NH': 'New Hampshire', 'NJ': 'New Jersey', 'NM': 'New Mexico', 'NY': 'New York',
        'NC': 'North Carolina', 'ND': 'North Dakota', 'OH': 'Ohio', 'OK': 'Oklahoma',
        'OR': 'Oregon', 'PA': 'Pennsylvania', 'RI': 'Rhode Island', 'SC': 'South Carolina',
        'SD': 'South Dakota', 'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah',
        'VT': 'Vermont', 'VA': 'Virginia', 'WA': 'Washington', 'WV': 'West Virginia',
        'WI': 'Wisconsin', 'WY': 'Wyoming'
      };
      // 邮编前缀到州的映射
      const zipPrefixMap = {
        '35': 'Alabama', '99': 'Alaska', '85': 'Arizona', '72': 'Arkansas',
        '90': 'California', '91': 'California', '92': 'California', '93': 'California', '94': 'California', '95': 'California', '96': 'California',
        '80': 'Colorado', '81': 'Colorado', '06': 'Connecticut', '19': 'Delaware',
        '32': 'Florida', '33': 'Florida', '34': 'Florida', '30': 'Georgia', '31': 'Georgia',
        '96': 'Hawaii', '83': 'Idaho', '60': 'Illinois', '61': 'Illinois', '62': 'Illinois',
        '46': 'Indiana', '47': 'Indiana', '50': 'Iowa', '51': 'Iowa', '52': 'Iowa',
        '66': 'Kansas', '67': 'Kansas', '40': 'Kentucky', '41': 'Kentucky', '42': 'Kentucky',
        '70': 'Louisiana', '71': 'Louisiana', '04': 'Maine', '20': 'Maryland', '21': 'Maryland',
        '01': 'Massachusetts', '02': 'Massachusetts', '48': 'Michigan', '49': 'Michigan',
        '55': 'Minnesota', '56': 'Minnesota', '38': 'Mississippi', '39': 'Mississippi',
        '63': 'Missouri', '64': 'Missouri', '65': 'Missouri', '59': 'Montana',
        '68': 'Nebraska', '69': 'Nebraska', '88': 'Nevada', '89': 'Nevada',
        '03': 'New Hampshire', '07': 'New Jersey', '08': 'New Jersey', '87': 'New Mexico',
        '10': 'New York', '11': 'New York', '12': 'New York', '13': 'New York', '14': 'New York',
        '27': 'North Carolina', '28': 'North Carolina', '58': 'North Dakota',
        '43': 'Ohio', '44': 'Ohio', '45': 'Ohio', '73': 'Oklahoma', '74': 'Oklahoma',
        '97': 'Oregon', '15': 'Pennsylvania', '16': 'Pennsylvania', '17': 'Pennsylvania', '18': 'Pennsylvania', '19': 'Pennsylvania',
        '02': 'Rhode Island', '29': 'South Carolina', '57': 'South Dakota',
        '37': 'Tennessee', '38': 'Tennessee', '75': 'Texas', '76': 'Texas', '77': 'Texas', '78': 'Texas', '79': 'Texas',
        '84': 'Utah', '05': 'Vermont', '22': 'Virginia', '23': 'Virginia', '24': 'Virginia',
        '98': 'Washington', '99': 'Washington', '24': 'West Virginia', '25': 'West Virginia', '26': 'West Virginia',
        '53': 'Wisconsin', '54': 'Wisconsin', '82': 'Wyoming', '83': 'Wyoming'
      };
      const zip2 = data.zip.substring(0, 2);
      const autoState = zipPrefixMap[zip2] || '';
      let targetState = resolveAdministrativeAreaName(data.state, data.country) || autoState;

      // 找到匹配的州选项
      for (const opt of stateSelect.options) {
        const optText = (opt.textContent || '').trim();
        const optValue = (opt.value || '').trim();
        if (optText === targetState || optValue === targetState || optText.includes(targetState)) {
          stateSelect.value = opt.value;
          stateSelect.dispatchEvent(new Event('change', { bubbles: true }));
          steps.push(`✅ ${data.country === 'JP' ? '都道府县' : '州'}: ` + optText);
          break;
        }
      }
      if (!targetState && stateSelect.options.length > 1) {
        // fallback: 选第一个非空选项
        for (const opt of stateSelect.options) {
          if (opt.value) {
            stateSelect.value = opt.value;
            stateSelect.dispatchEvent(new Event('change', { bubbles: true }));
            steps.push('✅ 州: ' + opt.textContent + ' (自动选择)');
            break;
          }
        }
      }
      await fieldPause();
    }

    await fillVerifiedPostalCode(findPostalInput, data.zip, steps, data.country);

    // 5. 再次确保国家仍是目标国家（某些交互会重置）
    const countrySelect = document.querySelector('select[name="billingCountry"]');
    if (countrySelect && (countrySelect.value || '').toUpperCase() !== data.country) {
      setNativeValue(countrySelect, data.country);
      steps.push('✅ 国家已重新设为 ' + ((COUNTRY_LABELS[data.country] && COUNTRY_LABELS[data.country][0]) || data.country));
      await sleep(500);
    }

    if (data.country === 'JP') {
      await stabilizeJapaneseAddress(data, steps, { silent: true });
      const finalPostalInput = findPostalInput();
      const finalPostalOk = finalPostalInput && postalCandidateMatches(finalPostalInput.value, data.zip, 'JP');
      if (!finalPostalOk) {
        const forced = await fillVerifiedPostalCode(findPostalInput, data.zip, steps, 'JP');
        if (!forced) {
          steps.push('❌ 日本邮编仍未填入，已停止自动提交');
          return steps;
        }
      }
    }
    }

    // 6. 勾选服务条款
    const termsCb = document.getElementById('termsOfServiceConsentCheckbox');
    if (termsCb && !termsCb.checked) {
      simulateClick(termsCb);
      steps.push('✅ 已勾选服务条款');
    } else if (termsCb?.checked) {
      steps.push('✅ 服务条款已勾选');
    }
    await sleep(500);

    // 7. 点击 Subscribe 提交按钮
    if (shouldSubmit) {
      if (await clickSubscribeAfterFill()) {
        steps.push('✅ 已点击 Subscribe 提交');
      } else {
        steps.push('❌ 未找到 Subscribe 按钮');
      }
    } else {
      steps.push('⏸️ 已自动填写完成，未自动点击 Subscribe');
    }

    return steps;
  }

  // ========== 弹窗 ==========
  function showModal() {
    const overlay = document.createElement('div');
    overlay.className = 'saf-overlay';

    overlay.innerHTML = `
      <div class="saf-modal">
        <h3>Stripe 自动填写</h3>
        <textarea id="saf-input" placeholder="粘贴信息: 卡号----有效期----CVV----电话----sms-token----姓名----地址"></textarea>
        <div class="saf-hint">
          格式: 卡号----有效期----CVV----电话----sms-token----姓名----街道,城市 邮编,国家 或 都道府县,城市,街道,邮编[,国家]<br>
          示例: 4859540169598884----2030/1----729----+19498756109----sms-token:xxx----TERRY SCHULTZ----18440 COUNTRY CLUB DR,MACOMB 48042-6217,US<br>
          日本示例: 4859540169598884----2030/1----729----+819012345678----sms-token:xxx----TARO YAMADA----ホッカイドウ,サッポロシテイネク,カナヤマ1ジョウ,298-1221<br>
          巴西 Pix 示例: 12345678901----TARO YAMADA----Rua A 123----Apto 5----Centro----Sao Paulo----SP----01234-567----BR
        </div>
        <div class="saf-btns">
          <button class="saf-btn saf-btn-cancel" id="saf-cancel">取消</button>
          <button class="saf-btn saf-btn-ok" id="saf-ok">确定</button>
        </div>
      </div>
    `;

    document.body.appendChild(overlay);

    overlay.querySelector('#saf-cancel').onclick = () => overlay.remove();

    // 回填上次输入（跨页面共享，用 chrome.storage.local）
    try {
      chrome.storage.local.get(['lastCardInput'], (res) => {
        if (res && res.lastCardInput) {
          overlay.querySelector('#saf-input').value = res.lastCardInput;
        }
      });
    } catch (_) {}

    try {
      const localCard = localStorage.getItem('opencode_paypal_card') || localStorage.getItem('ppaf_card') || '';
      if (localCard && !overlay.querySelector('#saf-input').value) {
        overlay.querySelector('#saf-input').value = localCard;
      }
    } catch (_) {}

    overlay.querySelector('#saf-ok').onclick = async () => {
      const input = overlay.querySelector('#saf-input').value.trim();
      if (!input) return;

      let data;
      try {
        data = parseInput(input);
      } catch (e) {
        showToast('❌ 用户输入解析失败: ' + e.message);
        return;
      }

      // 保存原始输入 + 解析后的结构化数据，供 PayPal 页共享
      try {
        chrome.storage.local.set({
          lastCardInput: input,
          lastCardData: data,
          lastCardSavedAt: Date.now(),
        });
      } catch (_) {}

      overlay.remove();
      showToast('⏳ 开始自动填写...');

      try {
        const results = await run(data);
        showToast(results.join('<br>'), 8000);
      } catch (e) {
        showToast('❌ 执行失败: ' + e.message, 8000);
      }
    };

    // 自动聚焦
    setTimeout(() => overlay.querySelector('#saf-input').focus(), 100);
  }

  async function autoRunSavedDataOnLoad() {
    const data = await getSavedCardData();
    if (!data) return;

    const ready = await waitForCheckoutReady();
    if (!ready) {
      showToast('⚠️ 自动填写等待超时：未检测到支付表单', 5000);
      return;
    }

    await sleep(1000);

    showToast('⏳ 检测到已保存数据，开始自动填写并继续...', 3000);
    try {
      const results = await run(data);
      showToast(results.join('<br>'), 8000);
    } catch (e) {
      showToast('❌ 自动填写失败: ' + e.message, 8000);
    }
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
    if (document.getElementById('stripe-autofill-btn')) return;
    const btn = document.createElement('button');
    btn.id = 'stripe-autofill-btn';
    btn.title = '自动填写支付信息（可拖动）';
    btn.innerHTML = catSVG;
    btn.addEventListener('click', showModal);
    document.body.appendChild(btn);
    makeDraggable(btn, 'stripe-autofill-btn-pos');

  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      createButton();
      autoSwitchCountryOnLoad();
      setTimeout(autoFillPostalCodeOnLoad, 10000);
      setTimeout(autoRunSavedDataOnLoad, 1500);
    });
  } else {
    createButton();
    autoSwitchCountryOnLoad();
    setTimeout(autoFillPostalCodeOnLoad, 10000);
    setTimeout(autoRunSavedDataOnLoad, 1500);
  }
})();
