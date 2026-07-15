// ==UserScript==
// @name         UK PayPal address autofill
// @description  Generate a UK address profile and fill the current PayPal form
// @match        https://paypal.com/*
// @match        https://*.paypal.com/*
// @run-at       document-end
// @noframes
// @grant        GM_xmlhttpRequest
// @grant        GM.xmlHttpRequest
// @grant        GM_getValue
// @grant        GM_setValue
// @grant        GM.getValue
// @grant        GM.setValue
// ==/UserScript==

(function () {
  'use strict';

  const DEFAULT_CITY = '';
  const PAYPAL_PHONE_OVERRIDE = '';
  const PANEL_ID = '__pp_us_autofill_panel__';
  const PROFILE_STORAGE_KEY = '__pp_us_autofill_profile__';
  const COUNTRY_STORAGE_KEY = '__pp_us_autofill_country__';
  const SHARED_PROFILE_STORAGE_KEY_PREFIX = 'pp-multi-autofill.profile.';
  const FLOW_STORAGE_KEY = '__pp_us_autofill_flow_id__';
  const FLOW_TOKEN_STORAGE_KEY = '__pp_us_autofill_flow_token__';
  const FLOW_WINDOW_NAME_PREFIX = '__pp_us_autofill_flow__:';
  const PROFILE_TTL_MS = 15 * 60 * 1000;
  const PENDING_FILL_STORAGE_KEY = '__pp_us_autofill_pending_fill__';
  const AUTO_FILL_ON_LOAD = true;
  const PLUGIN_REQUEST_SOURCE = 'pp-uk-autofill';
  const PLUGIN_REQUEST_TYPE = 'opx:request-selected-sms';
  const PLUGIN_RESPONSE_SOURCE = 'opx-paypal-autofill';
  const PLUGIN_RESPONSE_TYPE = 'opx:selected-sms';

  let profile = null;
  let profilePromise = null;
  let profileRequestId = 0;
  let panelClosed = false;
  let statusMessage = '';
  let autoFillInFlight = false;
  let autoFillNeedsReschedule = false;
  let lastAutoFillSignature = '';
  let autoFillTimer = null;
  let activeFlowId = '';
  let selectedCountryCode = 'GB';

  const FIRST_NAMES = [
    'Alex', 'Blake', 'Casey', 'Drew', 'Evan',
    'Jamie', 'Jordan', 'Morgan', 'Riley', 'Taylor'
  ];

  const LAST_NAMES = [
    'Adams', 'Baker', 'Carter', 'Davis', 'Evans',
    'Miller', 'Parker', 'Reed', 'Turner', 'Walker'
  ];

  const COUNTRY_CONFIGS = {
    GB: {
      code: 'GB', label: 'United Kingdom', title: '英国', phonePrefix: '+44', countryAliases: ['GB', 'UK', 'GBR', 'Great Britain', 'United Kingdom'],
      addresses: [
        ['14 King Street', 'London', 'England', 'SW1A 1AA'],
        ['82 Deansgate', 'Manchester', 'England', 'M3 2ER'],
        ['27 Park Row', 'Leeds', 'England', 'LS1 5HD'],
        ['41 Queen Street', 'Cardiff', 'Wales', 'CF10 2GH'],
        ['33 Princes Street', 'Edinburgh', 'Scotland', 'EH2 2ER'],
        ['19 Broad Street', 'Birmingham', 'England', 'B1 2HF']
      ],
      phone: () => `07${randomInteger(3, 9)}${randomDigits(8)}`
    },
    JP: {
      code: 'JP', label: 'Japan', title: '日本', phonePrefix: '+81', countryAliases: ['JP', 'JPN', 'Japan', '日本'],
      addresses: [
        ['神南1-19-11', '渋谷区', '東京都', '150-0041'],
        ['梅田3-1-1', '大阪市北区', '大阪府', '530-0001'],
        ['栄3-5-1', '名古屋市中区', '愛知県', '460-0008'],
        ['大通西2-9', '札幌市中央区', '北海道', '060-0042'],
        ['博多駅中央街1-1', '福岡市博多区', '福岡県', '812-0012']
      ],
      phone: () => `080${randomDigits(8)}`
    },
    BR: {
      code: 'BR', label: 'Brazil', title: '巴西', phonePrefix: '+55', countryAliases: ['BR', 'BRA', 'Brazil', 'Brasil'],
      addresses: [
        ['Avenida Paulista 1578', 'Sao Paulo', 'SP', '01310-200'],
        ['Rua da Assembleia 100', 'Rio de Janeiro', 'RJ', '20011-000'],
        ['Avenida Afonso Pena 4000', 'Belo Horizonte', 'MG', '30130-009'],
        ['Rua XV de Novembro 1299', 'Curitiba', 'PR', '80060-000'],
        ['Avenida Borges de Medeiros 1501', 'Porto Alegre', 'RS', '90110-150']
      ],
      phone: () => `11${randomInteger(6, 9)}${randomDigits(8)}`
    },
    US: {
      code: 'US', label: 'United States', title: '美国', phonePrefix: '+1', countryAliases: ['US', 'USA', 'United States'],
      addresses: [
        ['3110 Sunset Boulevard', 'Los Angeles', 'CA', '90026'],
        ['1200 Market Street', 'San Francisco', 'CA', '94102'],
        ['500 Main Street', 'Austin', 'TX', '78701'],
        ['88 Broadway', 'New York', 'NY', '10007'],
        ['1200 Peachtree St', 'Atlanta', 'GA', '30309']
      ],
      phone: () => `415${randomInteger(2, 9)}${randomDigits(2)}${randomDigits(4)}`
    }
  };

  const FIELD_SELECTORS = {
    email: [
      'input#onboardingFlowEmail',
      'input#email',
      'input[name="login_email"]',
      'input[name="email"]',
      'input[autocomplete="email"]',
      'input[type="email"]'
    ],
    password: [
      'input#password',
      'input[name="password"]',
      'input[autocomplete="new-password"]',
      'input[type="password"]'
    ],
    cardNumber: [
      'input#cardNumber',
      'input#creditCardNumber',
      'input#card_number',
      'input[name="cardNumber"]',
      'input[name="creditCardNumber"]',
      'input[name="card_number"]',
      'input[autocomplete="cc-number"]'
    ],
    cardExpiry: [
      'input#cardExpiry',
      'input#cardExpiration',
      'input#expiryDate',
      'input#expirationDate',
      'input#expiry',
      'input[name="cardExpiry"]',
      'input[name="cardExpiration"]',
      'input[name="expiryDate"]',
      'input[name="expirationDate"]',
      'input[autocomplete="cc-exp"]'
    ],
    cardExpiryMonth: [
      'select#expMonth',
      'select#expiryMonth',
      'select[name="expMonth"]',
      'select[name="expiryMonth"]',
      'select[autocomplete="cc-exp-month"]'
    ],
    cardExpiryYear: [
      'select#expYear',
      'select#expiryYear',
      'select[name="expYear"]',
      'select[name="expiryYear"]',
      'select[autocomplete="cc-exp-year"]'
    ],
    cardCvv: [
      'input#cardCvv',
      'input#cardCVV',
      'input#cvv',
      'input#csc',
      'input#securityCode',
      'input[name="cardCvv"]',
      'input[name="cvv"]',
      'input[name="csc"]',
      'input[name="securityCode"]',
      'input[autocomplete="cc-csc"]'
    ],
    country: [
      'select#country',
      'select[name="country"]',
      'select[name="country.x"]',
      'select[autocomplete="country"]',
      'select[data-testid="countrySelector"]',
      'select[aria-label*="country" i]'
    ],
    phone: [
      'input#phone',
      'input#phoneNumber',
      'input[name="phone"]',
      'input[name="phoneNumber"]',
      'input[autocomplete="tel"]',
      'input[type="tel"]'
    ],
    fullName: [
      'input#full-name',
      'input#fullName',
      'input[name="fullName"]',
      'input[autocomplete="name"]'
    ],
    firstName: [
      'input#firstName',
      'input[name="firstName"]',
      'input[name="givenName"]',
      'input[autocomplete="given-name"]'
    ],
    lastName: [
      'input#lastName',
      'input[name="lastName"]',
      'input[name="familyName"]',
      'input[autocomplete="family-name"]'
    ],
    address1: [
      'input#address1',
      'input#addressLine1',
      'input#billingAddressLine1',
      'input#billingLine1',
      'input[name="address1"]',
      'input[name="addressLine1"]',
      'input[name="billingLine1"]',
      'input[autocomplete="address-line1"]'
    ],
    address2: [
      'input#address2',
      'input#addressLine2',
      'input#billingAddressLine2',
      'input#billingLine2',
      'input[name="address2"]',
      'input[name="addressLine2"]',
      'input[name="billingLine2"]',
      'input[autocomplete="address-line2"]'
    ],
    city: [
      'input#city',
      'input#billingLocality',
      'input#billingCity',
      'input[name="city"]',
      'input[name="billingCity"]',
      'input[autocomplete="address-level2"]'
    ],
    state: [
      'select#state',
      'input#state',
      'select#billingAdministrativeArea',
      'input#billingAdministrativeArea',
      'select#billingState',
      'input#billingState',
      'select[name="state"]',
      'input[name="state"]',
      'select[name="billingState"]',
      'input[name="billingState"]',
      'select[autocomplete="address-level1"]',
      'input[autocomplete="address-level1"]'
    ],
    postalCode: [
      'input#zip',
      'input#postalCode',
      'input#billingPostalCode',
      'input#billingZip',
      'input[name="zip"]',
      'input[name="postalCode"]',
      'input[name="billingPostalCode"]',
      'input[name="billingZip"]',
      'input[autocomplete="postal-code"]'
    ]
  };

  async function requestJson(url, options = {}) {
    const method = options.method || 'GET';
    const headers = options.headers || { Accept: 'application/json' };
    const data = options.data;

    if (typeof GM !== 'undefined' && GM.xmlHttpRequest) {
      return requestWithGm(GM.xmlHttpRequest, { method, url, headers, data });
    }

    if (typeof GM_xmlhttpRequest !== 'undefined') {
      return requestWithGm(GM_xmlhttpRequest, { method, url, headers, data });
    }

    const response = await fetch(url, {
      method,
      headers,
      body: data,
      cache: 'no-store',
      mode: 'cors'
    });

    if (!response.ok) {
      throw new Error(`Address request failed: HTTP ${response.status}`);
    }

    return response.json();
  }

  function requestWithGm(request, options) {
    return new Promise((resolve, reject) => {
      request({
        ...options,
        timeout: 20000,
        onload: response => {
          if (response.status < 200 || response.status >= 300) {
            reject(new Error(`Address request failed: HTTP ${response.status}`));
            return;
          }

          try {
            resolve(JSON.parse(response.responseText));
          } catch (error) {
            reject(new Error('Address API returned invalid JSON'));
          }
        },
        onerror: () => reject(new Error('Address request failed')),
        ontimeout: () => reject(new Error('Address request timed out'))
      });
    });
  }

  function isTopLevelWindow() {
    try {
      return window.top === window.self;
    } catch (error) {
      return false;
    }
  }

  function isPayPalSignupPage() {
    if (!isPayPalHost(location.hostname)) return false;
    return /^\/checkoutweb\/signup(?:\/|$)/.test(location.pathname);
  }

  function isPayPalCheckoutContext() {
    if (!isPayPalHost(location.hostname)) return false;

    const params = new URLSearchParams(location.search);
    const hasCheckoutToken = params.has('token') || params.has('ba_token') || params.get('ul') === '1';

    if (isPayPalSignupPage()) return true;
    if (location.pathname.startsWith('/signin')) return params.get('intent') === 'checkout';
    if (location.pathname.startsWith('/agreements/approve')) return params.has('ba_token');
    if (location.pathname.startsWith('/pay/billing')) return hasCheckoutToken || params.get('fromSignupLite') === 'true';
    if (location.pathname.startsWith('/webapps/hermes')) return hasCheckoutToken || params.get('fromSignupLite') === 'true';
    return location.pathname.startsWith('/pay') && hasCheckoutToken;
  }

  function isPayPalCheckoutEmailPage() {
    return !isPayPalSignupPage() &&
        isPayPalCheckoutContext() &&
        Boolean(getFirstVisibleElement(FIELD_SELECTORS.email));
  }

  function isPayPalAutofillPage() {
    return isPayPalCheckoutContext();
  }

  function isPayPalHost(hostname) {
    return hostname === 'paypal.com' || hostname.endsWith('.paypal.com');
  }

  function getCheckoutTokenFingerprint() {
    const params = new URLSearchParams(location.search);
    const token = params.get('token') || params.get('ba_token') || '';
    if (!token) return '';

    let hash = 2166136261;
    for (const character of token) {
      hash ^= character.charCodeAt(0);
      hash = Math.imul(hash, 16777619);
    }

    return (hash >>> 0).toString(36);
  }

  function getFlowId() {
    try {
      const storedId = sessionStorage.getItem(FLOW_STORAGE_KEY);
      const storedTokenFingerprint = sessionStorage.getItem(FLOW_TOKEN_STORAGE_KEY) || '';
      const currentTokenFingerprint = getCheckoutTokenFingerprint();

      const escapedPrefix = FLOW_WINDOW_NAME_PREFIX.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      const windowMarkerPattern = new RegExp(
          `(?:^|\\|)${escapedPrefix}([a-z0-9-]+)(?::([a-z0-9]+))?(?=\\||$)`
      );
      const windowMarker = windowMarkerPattern.exec(window.name || '');
      const windowFlowId = windowMarker?.[1] || '';
      const windowTokenFingerprint = windowMarker?.[2] || '';
      const tokenChanged = Boolean(
          currentTokenFingerprint &&
          ((storedId && storedTokenFingerprint !== currentTokenFingerprint) ||
              (windowFlowId && windowTokenFingerprint !== currentTokenFingerprint))
      );

      if (tokenChanged) {
        sessionStorage.removeItem(PROFILE_STORAGE_KEY);
        sessionStorage.removeItem(PENDING_FILL_STORAGE_KEY);
      }

      const flowId = tokenChanged
          ? `flow-${randomLettersAndDigits(20)}`
          : storedId || windowFlowId || `flow-${randomLettersAndDigits(20)}`;
      const flowTokenFingerprint = currentTokenFingerprint || storedTokenFingerprint || windowTokenFingerprint;
      const marker = `${FLOW_WINDOW_NAME_PREFIX}${flowId}${flowTokenFingerprint ? `:${flowTokenFingerprint}` : ''}`;

      sessionStorage.setItem(FLOW_STORAGE_KEY, flowId);
      if (flowTokenFingerprint) sessionStorage.setItem(FLOW_TOKEN_STORAGE_KEY, flowTokenFingerprint);
      else sessionStorage.removeItem(FLOW_TOKEN_STORAGE_KEY);

      window.name = windowMarker
          ? (window.name || '').replace(windowMarkerPattern, match => match.startsWith('|') ? `|${marker}` : marker)
          : window.name
              ? `${window.name}|${marker}`
              : marker;

      return flowId;
    } catch (error) {
      console.warn('[UK PayPal autofill] could not initialize flow id', error);
      return 'unscoped';
    }
  }

  function ensureActiveFlow() {
    const flowId = getFlowId();
    if (activeFlowId && activeFlowId !== flowId) {
      profile = null;
      profilePromise = null;
      profileRequestId += 1;
      lastAutoFillSignature = '';
    }

    activeFlowId = flowId;
    return flowId;
  }

  function sharedProfileStorageKey() {
    return `${SHARED_PROFILE_STORAGE_KEY_PREFIX}${selectedCountryCode}.${getFlowId()}`;
  }

  function getCountryConfig(countryCode = selectedCountryCode) {
    return COUNTRY_CONFIGS[countryCode] || COUNTRY_CONFIGS.GB;
  }

  function loadSelectedCountry() {
    try {
      const stored = sessionStorage.getItem(COUNTRY_STORAGE_KEY);
      if (stored && COUNTRY_CONFIGS[stored]) selectedCountryCode = stored;
    } catch (error) {
      console.warn('[UK PayPal autofill] could not load country selection', error);
    }
  }

  function saveSelectedCountry(countryCode) {
    if (!COUNTRY_CONFIGS[countryCode]) return;
    selectedCountryCode = countryCode;
    try {
      sessionStorage.setItem(COUNTRY_STORAGE_KEY, countryCode);
    } catch (error) {
      console.warn('[UK PayPal autofill] could not persist country selection', error);
    }
  }

  function countryStorageKey() {
    return `${PROFILE_STORAGE_KEY}.${selectedCountryCode}`;
  }

  function isStoredProfile(value) {
    return Boolean(
        value &&
        typeof value === 'object' &&
        typeof value.fullName === 'string' &&
        typeof value.line1 === 'string' &&
        typeof value.city === 'string' &&
        typeof value.state === 'string' &&
        typeof value.postalCode === 'string' &&
        typeof value.phone === 'string' &&
        typeof value.email === 'string' &&
        typeof value.password === 'string' &&
        value.creditCard &&
        typeof value.creditCard === 'object' &&
        Number.isFinite(value.fetchedAt) &&
        Date.now() - value.fetchedAt >= 0 &&
        Date.now() - value.fetchedAt <= PROFILE_TTL_MS &&
        value.countryCode === selectedCountryCode
    );
  }

  async function saveProfile(profileData) {
    const serialized = JSON.stringify(profileData);

    try {
      sessionStorage.setItem(countryStorageKey(), serialized);
    } catch (error) {
      console.warn('[UK PayPal autofill] could not persist profile', error);
    }

    try {
      if (typeof GM !== 'undefined' && typeof GM.setValue === 'function') {
        await GM.setValue(sharedProfileStorageKey(), serialized);
        return;
      }

      if (typeof GM_setValue !== 'undefined') {
        GM_setValue(sharedProfileStorageKey(), serialized);
      }
    } catch (error) {
      console.warn('[UK PayPal autofill] could not persist shared profile', error);
    }
  }

  async function loadStoredProfile() {
    try {
      const parsed = JSON.parse(sessionStorage.getItem(countryStorageKey()) || 'null');
      if (isStoredProfile(parsed)) return parsed;
    } catch (error) {
      console.warn('[UK PayPal autofill] could not load stored profile', error);
    }

    try {
      let serialized = '';
      if (typeof GM !== 'undefined' && typeof GM.getValue === 'function') {
        serialized = await GM.getValue(sharedProfileStorageKey(), '');
      } else if (typeof GM_getValue !== 'undefined') {
        serialized = GM_getValue(sharedProfileStorageKey(), '');
      }

      const parsed = JSON.parse(serialized || 'null');
      return isStoredProfile(parsed) ? parsed : null;
    } catch (error) {
      console.warn('[UK PayPal autofill] could not load shared profile', error);
      return null;
    }
  }

  async function markPendingFill(profileData) {
    await saveProfile(profileData);
    try {
      sessionStorage.setItem(PENDING_FILL_STORAGE_KEY, '1');
    } catch (error) {
      console.warn('[UK PayPal autofill] could not persist pending fill', error);
    }
  }

  function hasPendingFill() {
    try {
      return sessionStorage.getItem(PENDING_FILL_STORAGE_KEY) === '1';
    } catch (error) {
      console.warn('[UK PayPal autofill] could not read pending fill state', error);
      return false;
    }
  }

  function clearPendingFill() {
    try {
      sessionStorage.removeItem(PENDING_FILL_STORAGE_KEY);
    } catch (error) {
      console.warn('[UK PayPal autofill] could not clear pending fill state', error);
    }
  }

  async function getProfile(forceNew = false) {
    ensureActiveFlow();
    if (profile && !forceNew) return profile;

    if (!profilePromise || forceNew) {
      const requestId = ++profileRequestId;
      const request = fetchCountryProfile()
          .then(async nextProfile => {
            if (requestId !== profileRequestId) {
              return profilePromise ? profilePromise : (profile || nextProfile);
            }

            profile = nextProfile;
            await saveProfile(profile);
            return profile;
          })
          .catch(async error => {
            if (requestId !== profileRequestId && profilePromise) return profilePromise;
            throw error;
          });

      profilePromise = request;
      request.then(
          () => {
            if (profilePromise === request) profilePromise = null;
          },
          () => {
            if (profilePromise === request) profilePromise = null;
          }
      );
    }

    return profilePromise;
  }

  async function fetchCountryProfile() {
    const config = getCountryConfig();
    const address = normalizeAddress(createCountryAddress(config), `local-${config.code.toLowerCase()}`, config);
    const pluginProfile = await requestPluginPaymentProfile();
    const email = pluginProfile.email || createGmailEmail();
    const overridePhone = normalizeSmsPhoneForCountry(PAYPAL_PHONE_OVERRIDE, config.code);
    if (overridePhone) {
      return {
        ...address,
        phone: overridePhone,
        phoneSource: 'hardcoded',
        email
      };
    }

    if (pluginProfile.phone) {
      return {
        ...address,
        phone: pluginProfile.phone,
        phoneSource: 'plugin-sms',
        email
      };
    }

    return {
      ...address,
      phoneSource: pluginProfile.phoneSource,
      email
    };
  }

  function requestPluginPaymentProfile(timeoutMs = 1200) {
    return new Promise(resolve => {
      const requestId = `${Date.now()}-${randomDigits(10)}`;
      let settled = false;
      let timeout = 0;

      const finish = (phone, countryCode, email, responseReceived) => {
        if (settled) return;
        settled = true;
        window.clearTimeout(timeout);
        window.removeEventListener('message', onMessage);
        const normalizedPhone = normalizeSmsPhoneForCountry(phone, countryCode);
        resolve({
          phone: normalizedPhone,
          email: normalizeGmailEmail(email),
          phoneSource: normalizedPhone
              ? 'plugin-sms'
              : responseReceived
                  ? 'address-no-selected-plugin-sms'
                  : 'address-plugin-bridge-unavailable'
        });
      };

      const onMessage = event => {
        const message = event.data;
        if (
            event.source !== window ||
            event.origin !== location.origin ||
            !message ||
            message.source !== PLUGIN_RESPONSE_SOURCE ||
            message.type !== PLUGIN_RESPONSE_TYPE ||
            message.requestId !== requestId
        ) {
          return;
        }

        finish(message.phone, message.countryCode, message.email, true);
      };

      timeout = window.setTimeout(() => finish('', '', '', false), timeoutMs);
      window.addEventListener('message', onMessage);

      try {
        window.postMessage({
          source: PLUGIN_REQUEST_SOURCE,
          type: PLUGIN_REQUEST_TYPE,
          requestId
        }, location.origin);
      } catch (error) {
        console.warn('[UK PayPal autofill] plugin SMS request failed', error);
        finish('', '', '', false);
      }
    });
  }

  function normalizeAddress(data, source, config = getCountryConfig()) {
    const state = cleanText(data.State || data.state).toUpperCase();
    const city = toTitleCase(cleanText(data.City || data.city));
    const postalCode = cleanText(data.Zip_Code || data.postalCode);
    const line1 = cleanText(data.Trans_Address || data.Address || data.line1);

    if (!state || !city || !postalCode || !line1) {
      throw new Error('Address payload is missing required fields');
    }

    const fullName = cleanText(data.Full_Name || data.fullName) || createName();
    const cardNumber = String(data.Credit_Card_Number || data.cardNumber || '').replace(/\D/g, '');
    const cardCvv = String(data.CVV2 || data.cardCvv || data.cvv || '').replace(/\D/g, '');
    const cardExpiry = parseCardExpiry(data.Expires || data.cardExpiry || data.cardExpiration);

    return {
      id: `${Date.now()}-${randomDigits(6)}`,
      fullName,
      line1,
      line2: cleanText(data.line2),
      city,
      state,
      stateFull: cleanText(data.State_Full || data.stateFull),
      postalCode,
      countryCode: config.code,
      countryLabel: config.label,
      phone: normalizePhoneForCountry(data.Telephone || data.phone, config.code) || config.phone(),
      phoneSource: 'address',
      password: cleanText(data.Password || data.password) || createPassword(),
      creditCard: {
        number: cardNumber,
        expiry: cardExpiry.short,
        expiryMonth: cardExpiry.month,
        expiryYear: cardExpiry.year4,
        cvv: cardCvv
      },
      source,
      fetchedAt: Date.now()
    };
  }

  function cleanText(value) {
    return String(value || '').replace(/\s+/g, ' ').trim();
  }

  function toTitleCase(value) {
    if (!value || /[^a-zA-Z\s-]/.test(value)) return value;
    return value.toLowerCase().replace(/\b[a-z]/g, character => character.toUpperCase());
  }

  function createName() {
    return `${pick(FIRST_NAMES)} ${pick(LAST_NAMES)}`;
  }

  function createCountryAddress(config = getCountryConfig()) {
    const [line1, city, state, postalCode] = pick(config.addresses);
    return {
      Full_Name: createName(),
      Trans_Address: line1,
      City: DEFAULT_CITY || city,
      State: state,
      State_Full: state,
      Zip_Code: postalCode,
      Telephone: config.phone(),
      Password: createPassword(),
      Credit_Card_Number: generateVisaCardNumber(),
      CVV2: randomDigits(3),
      Expires: createCardExpiry()
    };
  }

  function createGmailEmail() {
    return `${randomLettersAndDigits(16)}@gmail.com`;
  }

  function createPassword() {
    return `Aa${randomLettersAndDigits(10)}1!`;
  }

  function randomLettersAndDigits(length) {
    const characters = 'abcdefghijklmnopqrstuvwxyz0123456789';
    const bytes = new Uint8Array(length);
    crypto.getRandomValues(bytes);
    return Array.from(bytes, byte => characters[byte % characters.length]).join('');
  }

  function parseCardExpiry(value) {
    const text = cleanText(value);
    const match = /^(\d{1,2})\s*[\/-]\s*(\d{2,4})$/.exec(text);
    if (!match) {
      return { short: text, month: '', year2: '', year4: '' };
    }

    const month = match[1].padStart(2, '0');
    const year4 = match[2].length === 2 ? `20${match[2]}` : match[2];
    return {
      short: `${month}/${year4.slice(-2)}`,
      month,
      year2: year4.slice(-2),
      year4
    };
  }

  function createCardExpiry() {
    const month = String(randomInteger(1, 12)).padStart(2, '0');
    const year = String(new Date().getFullYear() + randomInteger(2, 5)).slice(-2);
    return `${month}/${year}`;
  }

  function generateVisaCardNumber() {
    const prefix = `4${randomDigits(14)}`;
    return `${prefix}${luhnCheckDigit(prefix)}`;
  }

  function luhnCheckDigit(prefix) {
    const digits = prefix.split('').map(Number);
    let total = 0;
    const parity = (digits.length + 1) % 2;
    digits.forEach((digit, index) => {
      let value = digit;
      if (index % 2 === parity) {
        value *= 2;
        if (value > 9) value -= 9;
      }
      total += value;
    });
    return String((10 - (total % 10)) % 10);
  }

  function normalizePhoneForCountry(value, countryCode = selectedCountryCode) {
    const config = getCountryConfig(countryCode);
    const digits = String(value || '').replace(/\D/g, '');
    if (!digits) return '';

    if (config.code === 'GB') {
      if (digits.length === 12 && digits.startsWith('44')) return `0${digits.slice(2)}`;
      if (digits.length === 11 && digits.startsWith('0')) return digits;
      return digits.length >= 10 ? `0${digits.slice(-10)}` : '';
    }

    if (config.code === 'JP') {
      if (digits.length === 12 && digits.startsWith('81')) return `0${digits.slice(2)}`;
      if (digits.length === 11 && digits.startsWith('0')) return digits;
      return digits.length >= 10 ? `0${digits.slice(-10)}` : '';
    }

    if (config.code === 'BR') {
      if (digits.length === 13 && digits.startsWith('55')) return digits.slice(2);
      if (digits.length === 11) return digits;
      return digits.length >= 10 ? digits.slice(-11) : '';
    }

    if (config.code === 'US') {
      if (digits.length === 11 && digits.startsWith('1')) return digits.slice(1);
      return digits.length >= 10 ? digits.slice(-10) : '';
    }

    return digits;
  }

  function normalizeSmsPhoneForCountry(value, countryCode) {
    const normalizedCountry = cleanText(countryCode).toUpperCase();
    const config = Object.values(COUNTRY_CONFIGS).find(candidate => {
      const aliases = [candidate.code, candidate.label, candidate.phonePrefix.replace('+', ''), ...candidate.countryAliases];
      return aliases.map(alias => cleanText(alias).toUpperCase()).includes(normalizedCountry);
    }) || getCountryConfig();

    if (normalizedCountry && config.code !== selectedCountryCode) return '';

    return normalizePhoneForCountry(value, config.code);
  }

  function normalizeGmailEmail(value) {
    const email = cleanText(value);
    const match = /^([^@\s]+)@([^@\s]+)$/.exec(email);
    if (!match) return '';
    return match[2].toLowerCase() === 'gmail.com' ? email : `${match[1]}@gmail.com`;
  }

  function randomDigits(length) {
    return Array.from({ length }, () => String(randomInteger(0, 9))).join('');
  }

  function randomInteger(min, max) {
    return Math.floor(Math.random() * (max - min + 1)) + min;
  }

  function pick(values) {
    return values[randomInteger(0, values.length - 1)];
  }

  function wait(milliseconds) {
    return new Promise(resolve => window.setTimeout(resolve, milliseconds));
  }

  function isVisible(element) {
    if (!element || !element.isConnected) return false;
    const style = window.getComputedStyle(element);
    const bounds = element.getBoundingClientRect();
    return style.display !== 'none' && style.visibility !== 'hidden' && bounds.width > 0 && bounds.height > 0;
  }

  function hasProtectedChallenge() {
    const dataDomeFrame = document.querySelector(
        'iframe[title*="DataDome" i], iframe[src*="geo.ddc.paypal.com/captcha"], iframe[src*="ct.ddc.paypal.com"]'
    );
    const dataDomeForm = document.querySelector('form#ads-dd-captcha, form input[name="adsddcaptcha"]');
    const dataDomeScript = document.querySelector('script[src*="ct.ddc.paypal.com/c.js"]');
    const sliderContainer = document.querySelector('.sliderContainer');
    const slider = document.querySelector('.slider');

    return Boolean(
        (dataDomeFrame && isVisible(dataDomeFrame)) ||
        dataDomeForm ||
        dataDomeScript ||
        (sliderContainer && slider && isVisible(sliderContainer) && isVisible(slider))
    );
  }

  function removeStandaloneCaptchaComponent() {
    if (hasProtectedChallenge()) return false;

    const component = document.getElementById('captchaComponent');
    if (!component || component.querySelector('.sliderContainer, .slider')) return false;

    component.remove();
    console.info('[UK PayPal autofill] removed standalone #captchaComponent');
    return true;
  }

  function getFirstVisibleElement(selectors) {
    for (const selector of selectors) {
      const element = document.querySelector(selector);
      if (isVisible(element)) return element;
    }

    return null;
  }

  function getNativeSetter(element, property) {
    if (element instanceof HTMLSelectElement) {
      return Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, property)?.set;
    }

    if (element instanceof HTMLTextAreaElement) {
      return Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, property)?.set;
    }

    if (element instanceof HTMLInputElement) {
      return Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, property)?.set;
    }

    return null;
  }

  function fireEvents(element) {
    element.dispatchEvent(new Event('input', { bubbles: true }));
    element.dispatchEvent(new Event('change', { bubbles: true }));
    element.dispatchEvent(new Event('blur', { bubbles: true }));
  }

  function setElementValue(element, value, overwrite = true) {
    if (!element || value == null || value === '') return false;
    if (!(element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement)) return false;
    if (!overwrite && element.value.trim()) return false;

    element.focus();
    const setter = getNativeSetter(element, 'value');
    if (setter) setter.call(element, value);
    else element.value = value;

    fireEvents(element);
    return true;
  }

  function setInput(selectors, value, overwrite = true) {
    return setElementValue(getFirstVisibleElement(selectors), value, overwrite);
  }

  function setSelectBySelectors(selectors, wantedValues) {
    return setSelect(getFirstVisibleElement(selectors), wantedValues);
  }

  function setSelect(element, wantedValues) {
    if (!(element instanceof HTMLSelectElement)) return false;

    const normalized = (Array.isArray(wantedValues) ? wantedValues : [wantedValues])
        .map(value => cleanText(value).toLowerCase())
        .filter(Boolean);

    const options = [...element.options];
    let option = options.find(candidate => {
      const optionValue = cleanText(candidate.value).toLowerCase();
      const optionText = cleanText(candidate.textContent).toLowerCase();
      return normalized.some(value =>
          optionValue === value ||
          optionText === value
      );
    });

    if (!option) {
      option = options.find(candidate => {
        const optionValue = cleanText(candidate.value).toLowerCase();
        const optionText = cleanText(candidate.textContent).toLowerCase();
        return normalized.some(value =>
            value.length > 2 && (optionValue.includes(value) || optionText.includes(value))
        );
      });
    }

    if (!option) return false;

    const setter = getNativeSetter(element, 'value');
    if (setter) setter.call(element, option.value);
    else element.value = option.value;

    fireEvents(element);
    return true;
  }

  async function selectCountry(profileData) {
    const config = getCountryConfig(profileData.countryCode);
    const country = await waitForCountryOrPaymentFields(10000);
    if (!(country instanceof HTMLSelectElement)) {
      if (country && isTargetCountryControl(country, config)) {
        return { found: true, changed: false, refreshed: true };
      }
      throw new Error('PayPal country field is unavailable or not a supported select');
    }

    const previousFields = getPaymentFields();
    const previousValue = country.value;
    const selected = setSelect(country, [profileData.countryCode, profileData.countryLabel, ...config.countryAliases]);
    if (!selected) throw new Error(`Could not select ${profileData.countryLabel} in the country field`);

    const changed = country.value !== previousValue;
    if (!changed) return { found: true, changed: false, refreshed: true };

    await markPendingFill(profileData);
    const refreshed = await waitForCountryRefresh(previousFields, 10000);
    if (!refreshed) {
      throw new Error('PayPal address fields did not finish refreshing after country selection');
    }

    return { found: true, changed: true, refreshed };
  }

  function isTargetCountryControl(element, config = getCountryConfig()) {
    const values = [
      element.value,
      element.getAttribute('data-country'),
      element.getAttribute('aria-label'),
      element.textContent
    ].map(value => cleanText(value).toLowerCase());

    const aliases = [config.code, config.label, ...config.countryAliases].map(value => cleanText(value).toLowerCase());
    return values.some(value => aliases.includes(value));
  }

  function getPaymentFields() {
    return {
      phone: getFirstVisibleElement(FIELD_SELECTORS.phone),
      address1: getFirstVisibleElement(FIELD_SELECTORS.address1),
      city: getFirstVisibleElement(FIELD_SELECTORS.city),
      state: getFirstVisibleElement(FIELD_SELECTORS.state),
      postalCode: getFirstVisibleElement(FIELD_SELECTORS.postalCode)
    };
  }

  function hasPaymentProfileForm() {
    return Boolean(
        getFirstVisibleElement(FIELD_SELECTORS.country) ||
        getFirstVisibleElement(FIELD_SELECTORS.address1) ||
        getFirstVisibleElement(FIELD_SELECTORS.cardNumber)
    );
  }

  function arePaymentFieldsReady(fields) {
    if (!fields.phone || !fields.address1 || !fields.city || !fields.state || !fields.postalCode) {
      return false;
    }

    return !(fields.state instanceof HTMLSelectElement) || fields.state.options.length > 1;
  }

  async function waitForPaymentFields(timeoutMs) {
    const startedAt = Date.now();

    while (Date.now() - startedAt < timeoutMs) {
      if (arePaymentFieldsReady(getPaymentFields())) return true;
      await wait(250);
    }

    return false;
  }

  async function waitForCountryOrPaymentFields(timeoutMs) {
    const startedAt = Date.now();

    while (Date.now() - startedAt < timeoutMs) {
      const country = getFirstVisibleElement(FIELD_SELECTORS.country);
      if (
          country &&
          (!(country instanceof HTMLSelectElement) || country.options.length > 1)
      ) {
        return country;
      }
      if (arePaymentFieldsReady(getPaymentFields())) return null;
      await wait(250);
    }

    return null;
  }

  async function waitForCountryRefresh(previousFields, timeoutMs) {
    const startedAt = Date.now();
    let fieldsWereReplaced = false;

    while (Date.now() - startedAt < timeoutMs) {
      const currentFields = getPaymentFields();
      fieldsWereReplaced ||= Object.keys(currentFields).some(
          key => currentFields[key] && currentFields[key] !== previousFields[key]
      );

      const elapsed = Date.now() - startedAt;
      if (arePaymentFieldsReady(currentFields) && (fieldsWereReplaced || elapsed >= 1500)) {
        return true;
      }

      await wait(250);
    }

    return false;
  }

  function setState(profileData) {
    const stateField = getFirstVisibleElement(FIELD_SELECTORS.state);
    if (stateField instanceof HTMLSelectElement) {
      return setSelect(stateField, [profileData.state, profileData.stateFull]);
    }

    return setElementValue(stateField, profileData.stateFull || profileData.state);
  }

  function splitName(fullName) {
    const parts = cleanText(fullName).split(' ').filter(Boolean);
    if (parts.length < 2) {
      return { firstName: parts[0] || 'Alex', lastName: 'Taylor' };
    }

    return {
      firstName: parts[0],
      lastName: parts.slice(1).join(' ')
    };
  }

  async function fillPayPalForm(forceNew = false) {
    try {
      if (!isTopLevelWindow() || !isPayPalAutofillPage()) {
        throw new Error('Current page is not a supported top-level PayPal checkout page');
      }

      const config = getCountryConfig();
      setStatus(forceNew ? `正在生成新的${config.title}资料...` : '正在填写 PayPal 资料...');
      removeStandaloneCaptchaComponent();

      const profileData = await getProfile(forceNew);
      if (isPayPalCheckoutEmailPage() || !hasPaymentProfileForm()) {
        const filled = profileData.email && setInput(FIELD_SELECTORS.email, profileData.email);
        updatePanel(profileData);
        setStatus(filled ? '已在 PayPal 前置页填写 Gmail 邮箱' : '等待 PayPal 前置页邮箱或资料表单加载');
        return;
      }

      const name = splitName(profileData.fullName);
      const country = await selectCountry(profileData);

      if (!(await waitForPaymentFields(10000))) {
        throw new Error('PayPal address fields are not ready');
      }

      const filled = [];
      if (profileData.email && setInput(FIELD_SELECTORS.email, profileData.email)) filled.push('email');
      if (profileData.password && setInput(FIELD_SELECTORS.password, profileData.password)) filled.push('password');
      if (setInput(FIELD_SELECTORS.phone, profileData.phone)) filled.push('phone');
      if (profileData.creditCard.number && setInput(FIELD_SELECTORS.cardNumber, profileData.creditCard.number)) {
        filled.push('card number');
      }
      if (profileData.creditCard.expiry && setInput(FIELD_SELECTORS.cardExpiry, profileData.creditCard.expiry)) {
        filled.push('card expiry');
      }
      if (profileData.creditCard.expiryMonth && setSelectBySelectors(
          FIELD_SELECTORS.cardExpiryMonth,
          [profileData.creditCard.expiryMonth, String(Number(profileData.creditCard.expiryMonth))]
      )) {
        filled.push('card expiry month');
      }
      if (profileData.creditCard.expiryYear && setSelectBySelectors(
          FIELD_SELECTORS.cardExpiryYear,
          [profileData.creditCard.expiryYear, profileData.creditCard.expiryYear.slice(-2)]
      )) {
        filled.push('card expiry year');
      }
      if (profileData.creditCard.cvv && setInput(FIELD_SELECTORS.cardCvv, profileData.creditCard.cvv)) {
        filled.push('card CVV');
      }
      if (setInput(FIELD_SELECTORS.fullName, profileData.fullName)) filled.push('full name');
      if (setInput(FIELD_SELECTORS.firstName, name.firstName)) filled.push('first name');
      if (setInput(FIELD_SELECTORS.lastName, name.lastName)) filled.push('last name');
      if (setInput(FIELD_SELECTORS.address1, profileData.line1)) filled.push('address line 1');
      if (setInput(FIELD_SELECTORS.address2, profileData.line2)) filled.push('address line 2');
      if (setInput(FIELD_SELECTORS.city, profileData.city)) filled.push('city');
      if (setState(profileData)) filled.push('state');
      if (setInput(FIELD_SELECTORS.postalCode, profileData.postalCode)) filled.push('postal code');

      updatePanel(profileData);
      clearPendingFill();
      const countryMessage = country.changed ? `已切换到${getCountryConfig(profileData.countryCode).title}；` : '';
      setStatus(`${countryMessage}已填写 ${filled.length} 项：${filled.join(', ') || '未找到匹配字段'}`);
    } catch (error) {
      setStatus(`填写失败：${error.message}`);
      console.error('[UK PayPal autofill] fill failed', error);
    }
  }

  function profileText(profileData) {
    const config = getCountryConfig(profileData.countryCode);
    return [
      `Country: ${profileData.countryLabel || config.label}`,
      `Email: ${profileData.email || ''}`,
      `Password: ${profileData.password || ''}`,
      `Name: ${profileData.fullName}`,
      `Phone: ${formatPhoneForDisplay(profileData)}`,
      `Card: ${profileData.creditCard?.number || ''}`,
      `Expiry: ${profileData.creditCard?.expiry || ''}`,
      `CVV: ${profileData.creditCard?.cvv || ''}`,
      `Address: ${profileData.line1}${profileData.line2 ? `, ${profileData.line2}` : ''}`,
      `City: ${profileData.city}`,
      `State: ${profileData.stateFull || profileData.state}`,
      `Postal code: ${profileData.postalCode}`,
      `Source: ${profileData.source}`
    ].join('\n');
  }

  async function copyText(text) {
    try {
      await navigator.clipboard.writeText(text);
      setStatus('资料已复制');
      return;
    } catch (error) {
      const textarea = document.createElement('textarea');
      textarea.value = text;
      textarea.style.position = 'fixed';
      textarea.style.left = '-9999px';
      document.body.appendChild(textarea);
      textarea.focus();
      textarea.select();
      document.execCommand('copy');
      textarea.remove();
      setStatus('资料已复制');
    }
  }

  function setStatus(message) {
    statusMessage = message;
    const status = document.getElementById('__pp_us_status__');
    if (status) status.textContent = message;
  }

  function updatePanel(profileData) {
    const name = document.getElementById('__pp_us_name__');
    if (!name) return;
    const config = getCountryConfig(profileData.countryCode);

    const country = document.getElementById('__pp_us_country__');
    if (country) country.value = profileData.countryCode || selectedCountryCode;
    document.getElementById('__pp_us_email__').value = profileData.email || '';
    document.getElementById('__pp_us_password__').value = profileData.password || '';
    name.value = profileData.fullName || '';
    document.getElementById('__pp_us_phone__').value = formatPhoneForDisplay(profileData);
    document.getElementById('__pp_us_card__').value = profileData.creditCard
        ? [profileData.creditCard.number, profileData.creditCard.expiry, profileData.creditCard.cvv]
            .filter(Boolean)
            .join(' | ')
        : '';
    document.getElementById('__pp_us_address__').value = [
      profileData.line1,
      profileData.line2,
      profileData.city,
      profileData.state,
      profileData.postalCode
    ].filter(Boolean).join(', ');
    const phoneSourceLabels = {
      hardcoded: 'configured override',
      'plugin-sms': 'plugin SMS',
      'address-no-selected-plugin-sms': `address (no selected ${config.title} plugin SMS)`,
      'address-plugin-bridge-unavailable': 'address (plugin bridge unavailable)',
      address: 'address'
    };
    const phoneSource = phoneSourceLabels[profileData.phoneSource] || 'address';
    document.getElementById('__pp_us_source__').textContent = `${config.title}; Address: ${profileData.source}; Phone: ${phoneSource}`;
  }

  function formatPhoneForDisplay(profileData) {
    const phone = cleanText(profileData.phone);
    if (!phone) return '';
    const config = getCountryConfig(profileData.countryCode);
    if (config.code === 'GB' || config.code === 'JP') return `${config.phonePrefix} ${phone.replace(/^0/, '')}`;
    if (config.code === 'BR' || config.code === 'US') return `${config.phonePrefix} ${phone}`;
    return `${config.phonePrefix} ${phone}`;
  }

  function createPanel() {
    if (panelClosed || document.getElementById(PANEL_ID)) return;

    const panel = document.createElement('section');
    panel.id = PANEL_ID;
    panel.style.cssText = [
      'position:fixed',
      'left:12px',
      'bottom:18px',
      'z-index:2147483647',
      'width:min(360px,calc(100vw - 24px))',
      'box-sizing:border-box',
      'padding:12px',
      'border:1px solid #404040',
      'border-radius:8px',
      'background:#161616',
      'color:#f5f5f5',
      'font:13px/1.4 Arial,sans-serif',
      'box-shadow:0 8px 28px rgba(0,0,0,.34)'
    ].join(';');

    const countryOptions = Object.values(COUNTRY_CONFIGS)
        .map(config => `<option value="${config.code}">${config.title}</option>`)
        .join('');

    panel.innerHTML = `
      <div style="font-weight:700;margin-bottom:8px;">PayPal 资料生成</div>
      <label style="display:block;margin:6px 0 3px;">Country</label>
      <select id="__pp_us_country__" style="width:100%;box-sizing:border-box;padding:7px;border:1px solid #565656;border-radius:4px;background:#252525;color:#fff;">${countryOptions}</select>
      <label style="display:block;margin:6px 0 3px;">Email</label>
      <input id="__pp_us_email__" readonly style="width:100%;box-sizing:border-box;padding:7px;border:1px solid #565656;border-radius:4px;background:#252525;color:#fff;">
      <label style="display:block;margin:6px 0 3px;">Password</label>
      <input id="__pp_us_password__" readonly style="width:100%;box-sizing:border-box;padding:7px;border:1px solid #565656;border-radius:4px;background:#252525;color:#fff;">
      <label style="display:block;margin:6px 0 3px;">Name</label>
      <input id="__pp_us_name__" readonly style="width:100%;box-sizing:border-box;padding:7px;border:1px solid #565656;border-radius:4px;background:#252525;color:#fff;">
      <label style="display:block;margin:6px 0 3px;">Phone</label>
      <input id="__pp_us_phone__" readonly style="width:100%;box-sizing:border-box;padding:7px;border:1px solid #565656;border-radius:4px;background:#252525;color:#fff;">
      <label style="display:block;margin:6px 0 3px;">Card</label>
      <input id="__pp_us_card__" readonly style="width:100%;box-sizing:border-box;padding:7px;border:1px solid #565656;border-radius:4px;background:#252525;color:#fff;">
      <label style="display:block;margin:6px 0 3px;">Address</label>
      <textarea id="__pp_us_address__" readonly rows="2" style="width:100%;box-sizing:border-box;padding:7px;border:1px solid #565656;border-radius:4px;background:#252525;color:#fff;resize:none;"></textarea>
      <div id="__pp_us_source__" style="margin-top:6px;color:#bdbdbd;"></div>
      <div id="__pp_us_status__" style="min-height:18px;margin-top:6px;color:#a7e3b5;"></div>
      <div style="display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;margin-top:9px;">
        <button id="__pp_us_fill__" type="button" style="padding:8px 4px;border:0;border-radius:4px;cursor:pointer;">Fill</button>
        <button id="__pp_us_new__" type="button" style="padding:8px 4px;border:0;border-radius:4px;cursor:pointer;">New</button>
        <button id="__pp_us_copy__" type="button" style="padding:8px 4px;border:0;border-radius:4px;cursor:pointer;">Copy</button>
        <button id="__pp_us_close__" type="button" style="padding:8px 4px;border:0;border-radius:4px;cursor:pointer;">Close</button>
      </div>
    `;

    document.body.appendChild(panel);

    document.getElementById('__pp_us_country__').value = selectedCountryCode;
    document.getElementById('__pp_us_country__').onchange = async event => {
      const nextCountryCode = event.target.value;
      saveSelectedCountry(nextCountryCode);
      profile = null;
      profilePromise = null;
      profileRequestId += 1;
      lastAutoFillSignature = '';
      try {
        const nextProfile = await getProfile(true);
        updatePanel(nextProfile);
        await fillPayPalForm(false);
      } catch (error) {
        setStatus(`生成失败：${error.message}`);
      }
    };

    document.getElementById('__pp_us_fill__').onclick = () => fillPayPalForm(false);
    document.getElementById('__pp_us_new__').onclick = () => {
      profile = null;
      fillPayPalForm(true);
    };
    document.getElementById('__pp_us_copy__').onclick = async () => {
      try {
        const profileData = await getProfile(false);
        await copyText(profileText(profileData));
      } catch (error) {
        setStatus(`复制失败：${error.message}`);
      }
    };
    document.getElementById('__pp_us_close__').onclick = () => {
      panelClosed = true;
      panel.remove();
    };

    if (profile) updatePanel(profile);
    if (statusMessage) setStatus(statusMessage);
  }

  function getAutofillSignature() {
    return [
      location.href,
      Boolean(getFirstVisibleElement(FIELD_SELECTORS.email)),
      hasPaymentProfileForm(),
      Boolean(getFirstVisibleElement(FIELD_SELECTORS.country)),
      Boolean(getFirstVisibleElement(FIELD_SELECTORS.phone)),
      Boolean(getFirstVisibleElement(FIELD_SELECTORS.address1)),
      Boolean(getFirstVisibleElement(FIELD_SELECTORS.state)),
      Boolean(getFirstVisibleElement(FIELD_SELECTORS.postalCode)),
      Boolean(getFirstVisibleElement(FIELD_SELECTORS.password)),
      Boolean(getFirstVisibleElement(FIELD_SELECTORS.cardNumber)),
      Boolean(getFirstVisibleElement(FIELD_SELECTORS.cardExpiry)),
      Boolean(getFirstVisibleElement(FIELD_SELECTORS.cardExpiryMonth)),
      Boolean(getFirstVisibleElement(FIELD_SELECTORS.cardExpiryYear)),
      Boolean(getFirstVisibleElement(FIELD_SELECTORS.cardCvv))
    ].join('|');
  }

  function scheduleAutofill() {
    if (!AUTO_FILL_ON_LOAD) return;
    if (autoFillInFlight) {
      autoFillNeedsReschedule = true;
      return;
    }

    const signature = getAutofillSignature();
    if (signature === lastAutoFillSignature) return;

    if (autoFillTimer) window.clearTimeout(autoFillTimer);
    autoFillTimer = window.setTimeout(async () => {
      autoFillTimer = null;
      const currentSignature = getAutofillSignature();
      if (autoFillInFlight) {
        autoFillNeedsReschedule = true;
        return;
      }
      if (currentSignature === lastAutoFillSignature) return;

      lastAutoFillSignature = currentSignature;
      autoFillInFlight = true;
      try {
        await fillPayPalForm(false);
      } finally {
        autoFillInFlight = false;
        if (autoFillNeedsReschedule) {
          autoFillNeedsReschedule = false;
          scheduleAutofill();
        }
      }
    }, 200);
  }

  async function bootstrap() {
    if (!isTopLevelWindow() || !isPayPalAutofillPage()) return;

    loadSelectedCountry();
    ensureActiveFlow();
    profile = await loadStoredProfile();

    removeStandaloneCaptchaComponent();
    createPanel();

    const observer = new MutationObserver(() => {
      removeStandaloneCaptchaComponent();
      createPanel();
      scheduleAutofill();
    });

    observer.observe(document.documentElement, {
      childList: true,
      subtree: true
    });

    try {
      const nextProfile = await getProfile(false);
      updatePanel(nextProfile);
      setStatus(`已生成${getCountryConfig(nextProfile.countryCode).title}资料（${nextProfile.source}）`);

      if (AUTO_FILL_ON_LOAD || hasPendingFill()) {
        scheduleAutofill();
      }
    } catch (error) {
      setStatus(`资料加载失败：${error.message}`);
      console.error('[UK PayPal autofill] bootstrap failed', error);
    }
  }

  void bootstrap();
})();
