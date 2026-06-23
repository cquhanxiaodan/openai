// Hotmail / Outlook 实时接码服务
// 账户格式: email----password----client_id----refresh_token
//
// 流程：
//   1. 用 refresh_token 向 login.live.com 换取 access_token
//   2. 用 XOAUTH2 登录 outlook.office365.com:993 IMAP
//   3. IDLE + 轮询拉取最近邮件，提取验证码，通过 SSE 实时推送到前端

import express from 'express';
import fsSync from 'fs';
import fs from 'fs/promises';
import path from 'path';
import { fileURLToPath } from 'url';
import { createHash, createHmac, randomBytes, randomUUID } from 'crypto';
import { ImapFlow } from 'imapflow';
import { simpleParser } from 'mailparser';
import makeFetchCookie from 'fetch-cookie';
import { CookieJar } from 'tough-cookie';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

loadDotEnv(path.join(__dirname, '.env'));

const app = express();
app.use(express.json({ limit: '5mb' }));
app.get('/', (_req, res) => res.sendFile(path.join(__dirname, 'public', 'user.html')));
app.get(['/admin', '/admin.html', '/index.html'], handleAdminPage);
app.use(express.static(path.join(__dirname, 'public')));

app.get('/api/public-config', (_req, res) => {
  res.json({
    ok: true,
    ui: {
      eyebrow: process.env.USER_HERO_EYEBROW || 'Self Service',
      title: process.env.USER_HERO_TITLE || '账号自助取码',
      subtitle: process.env.USER_HERO_SUBTITLE || '请将购买到的账号信息粘贴到导入框，验证通过后即可自助使用相关功能。数据仅保存在当前浏览器。',
    },
  });
});

const PORT = process.env.PORT || 3000;
const DATA_DIR = process.env.DATA_DIR || path.join(__dirname, 'data');
const DB_FILE = process.env.ACCOUNTS_DB_FILE || path.join(DATA_DIR, 'accounts-db.json');
const ADMIN_KEY = String(process.env.ADMIN_KEY || '').trim();
const ACTION_TOKEN_SECRET = String(process.env.ACTION_TOKEN_SECRET || randomBytes(32).toString('hex'));
const ADMIN_COOKIE_NAME = 'email_server_admin';
const ADMIN_SESSION_TTL_MS = 12 * 60 * 60 * 1000;

function loadDotEnv(filePath) {
  if (!fsSync.existsSync(filePath)) return;
  const content = fsSync.readFileSync(filePath, 'utf8');
  for (const line of content.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const index = trimmed.indexOf('=');
    if (index <= 0) continue;
    const key = trimmed.slice(0, index).trim();
    let value = trimmed.slice(index + 1).trim();
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1);
    }
    if (!(key in process.env)) process.env[key] = value;
  }
}

let dbState = { version: 1, updatedAt: '', accounts: [] };
let dbWriteQueue = Promise.resolve();
const dbReady = initDatabase();

function nowIso() {
  return new Date().toISOString();
}

function normalizeEmail(value) {
  return String(value || '').trim().toLowerCase();
}

function stripExportNamePrefix(value) {
  return String(value || '').trim().replace(/^\([^)]*\)/, '').trim();
}

function maskPhone(value) {
  const text = String(value || '').trim();
  if (!text) return '';
  if (text.length <= 7) return text;
  return `${text.slice(0, 4)}***${text.slice(-4)}`;
}

function normalizeDbAccount(value = {}) {
  const email = stripExportNamePrefix(value.email);
  const createdAt = String(value.createdAt || value.created_at || nowIso());
  const raw = String(value.raw || '').trim();
  return {
    id: String(value.id || '').trim() || randomUUID(),
    email,
    emailKey: normalizeEmail(email),
    password: String(value.password || ''),
    client_id: String(value.client_id || value.clientId || '').trim(),
    refresh_token: String(value.refresh_token || value.refreshToken || '').trim(),
    raw,
    openai_rt: String(value.openai_rt || value.openaiRt || value.rt_token || '').trim(),
    auth_phone_number: String(value.auth_phone_number || value.authPhoneNumber || '').trim(),
    auth_phone_sms_url: String(value.auth_phone_sms_url || value.authPhoneSmsUrl || '').trim(),
    status: String(value.status || '').trim(),
    last_sms_code: String(value.last_sms_code || value.lastSmsCode || '').trim(),
    last_sms_at: String(value.last_sms_at || value.lastSmsAt || '').trim(),
    createdAt,
    updatedAt: String(value.updatedAt || value.updated_at || createdAt),
  };
}

function publicAccountView(account) {
  return {
    id: account.id,
    email: account.email,
    status: account.status || (account.openai_rt ? '已导入RT' : '邮箱已导入'),
    hasMailboxToken: Boolean(account.client_id && account.refresh_token),
    hasOpenAiRt: Boolean(account.openai_rt),
    hasSmsUrl: Boolean(account.auth_phone_sms_url),
    authPhoneNumber: maskPhone(account.auth_phone_number),
    lastSmsCode: account.last_sms_code || '',
    lastSmsAt: account.last_sms_at || '',
    createdAt: account.createdAt,
    updatedAt: account.updatedAt,
  };
}

function userAccountView(account, actionToken = '') {
  return {
    id: account.id,
    email: account.email,
    status: account.status || (account.openai_rt ? '已验证' : '邮箱已验证'),
    hasMailboxToken: Boolean(account.client_id && account.refresh_token),
    hasOpenAiRt: Boolean(account.openai_rt),
    hasSmsUrl: Boolean(account.auth_phone_sms_url),
    authPhoneNumber: maskPhone(account.auth_phone_number),
    lastSmsCode: account.last_sms_code || '',
    lastSmsAt: account.last_sms_at || '',
    actionToken,
  };
}

function makeActionToken(accountId) {
  const expiresAt = Date.now() + 100 * 365 * 24 * 60 * 60 * 1000;
  const payload = `${accountId}.${expiresAt}`;
  const sig = createHmac('sha256', ACTION_TOKEN_SECRET).update(payload).digest('base64url');
  return `${payload}.${sig}`;
}

function verifyActionToken(accountId, token) {
  const text = String(token || '').trim();
  const parts = text.split('.');
  if (parts.length !== 3) return false;
  const [tokenAccountId, expiresAtText, sig] = parts;
  if (tokenAccountId !== String(accountId || '')) return false;
  const expiresAt = Number(expiresAtText);
  if (!Number.isFinite(expiresAt)) return false;
  const payload = `${tokenAccountId}.${expiresAtText}`;
  const expected = createHmac('sha256', ACTION_TOKEN_SECRET).update(payload).digest('base64url');
  return sig === expected;
}

function parseCookies(req) {
  const header = String(req.headers.cookie || '');
  const cookies = {};
  for (const part of header.split(';')) {
    const index = part.indexOf('=');
    if (index <= 0) continue;
    const key = part.slice(0, index).trim();
    const value = part.slice(index + 1).trim();
    cookies[key] = decodeURIComponent(value);
  }
  return cookies;
}

function makeAdminSessionToken() {
  const expiresAt = Date.now() + ADMIN_SESSION_TTL_MS;
  const payload = `${expiresAt}.${randomBytes(12).toString('base64url')}`;
  const sig = createHmac('sha256', ACTION_TOKEN_SECRET).update(payload).digest('base64url');
  return `${payload}.${sig}`;
}

function verifyAdminSessionToken(token) {
  const parts = String(token || '').split('.');
  if (parts.length !== 3) return false;
  const [expiresAtText, nonce, sig] = parts;
  const expiresAt = Number(expiresAtText);
  if (!Number.isFinite(expiresAt) || expiresAt < Date.now() || !nonce) return false;
  const payload = `${expiresAtText}.${nonce}`;
  const expected = createHmac('sha256', ACTION_TOKEN_SECRET).update(payload).digest('base64url');
  return sig === expected;
}

function hasValidAdminAuth(req) {
  if (!ADMIN_KEY) return false;
  const key = String(req.headers['x-admin-key'] || req.query.admin_key || req.body?.adminKey || '').trim();
  if (key && key === ADMIN_KEY) return true;
  const token = parseCookies(req)[ADMIN_COOKIE_NAME];
  return verifyAdminSessionToken(token);
}

function setAdminCookie(res) {
  const token = makeAdminSessionToken();
  res.setHeader('Set-Cookie', `${ADMIN_COOKIE_NAME}=${encodeURIComponent(token)}; Max-Age=${Math.floor(ADMIN_SESSION_TTL_MS / 1000)}; Path=/; HttpOnly; SameSite=Lax`);
}

function clearAdminCookie(res) {
  res.setHeader('Set-Cookie', `${ADMIN_COOKIE_NAME}=; Max-Age=0; Path=/; HttpOnly; SameSite=Lax`);
}

function handleAdminPage(req, res) {
  if (!ADMIN_KEY) {
    res.status(503).send('服务端未配置 ADMIN_KEY，管理员功能已禁用');
    return;
  }
  const key = String(req.query.admin_key || '').trim();
  if (key && key === ADMIN_KEY) {
    setAdminCookie(res);
    res.redirect('/admin.html');
    return;
  }
  if (!hasValidAdminAuth(req)) {
    res.status(401).sendFile(path.join(__dirname, 'public', 'admin-login.html'));
    return;
  }
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
}

function requireAdmin(req, res, next) {
  if (!ADMIN_KEY) {
    res.status(503).json({ ok: false, error: '服务端未配置 ADMIN_KEY，管理员功能已禁用' });
    return;
  }
  if (hasValidAdminAuth(req)) return next();
  res.status(401).json({ ok: false, error: '管理员密钥错误' });
}

function requireUserAction(req, res, next) {
  if (hasValidAdminAuth(req)) return next();
  const token = String(req.headers['x-action-token'] || req.body?.actionToken || req.query.action_token || '').trim();
  if (verifyActionToken(req.params.id, token)) return next();
  res.status(403).json({ ok: false, error: '账号未通过购买校验，请重新导入校验' });
}

async function initDatabase() {
  await fs.mkdir(DATA_DIR, { recursive: true });
  try {
    const raw = await fs.readFile(DB_FILE, 'utf8');
    const parsed = JSON.parse(raw);
    const accounts = Array.isArray(parsed.accounts) ? parsed.accounts : [];
    dbState = {
      version: Number(parsed.version || 1),
      updatedAt: String(parsed.updatedAt || parsed.updated_at || ''),
      accounts: accounts.map(normalizeDbAccount).filter(account => account.emailKey),
    };
  } catch (error) {
    if (error?.code !== 'ENOENT') throw error;
    dbState = { version: 1, updatedAt: nowIso(), accounts: [] };
    await saveDatabase();
  }
}

async function ensureDatabase() {
  await dbReady;
}

async function saveDatabase() {
  dbState.updatedAt = nowIso();
  const tmpFile = `${DB_FILE}.tmp`;
  await fs.writeFile(tmpFile, JSON.stringify(dbState, null, 2) + '\n', 'utf8');
  await fs.rename(tmpFile, DB_FILE);
}

async function withDatabaseWrite(fn) {
  await ensureDatabase();
  const task = dbWriteQueue.then(async () => {
    const result = await fn();
    await saveDatabase();
    return result;
  });
  dbWriteQueue = task.catch(() => {});
  return task;
}

function findAccountByEmail(email) {
  const key = normalizeEmail(stripExportNamePrefix(email));
  return dbState.accounts.find(account => account.emailKey === key) || null;
}

function findAccountById(id) {
  return dbState.accounts.find(account => account.id === String(id || '').trim()) || null;
}

function requireMailboxAccount(account) {
  if (!account?.email || !account.client_id || !account.refresh_token) {
    throw new Error('该邮箱缺少 client_id 或 refresh_token，不能拉取邮件');
  }
  return {
    id: account.id || '',
    email: account.email,
    password: account.password || '',
    client_id: account.client_id,
    refresh_token: account.refresh_token,
    auth_phone_number: account.auth_phone_number || '',
    auth_phone_sms_url: account.auth_phone_sms_url || '',
  };
}

// ------------------------- OpenAI OAuth JSON 获取 -------------------------
const AUTH_BASE_URL = 'https://auth.openai.com';
const AUTH_AUTHORIZE_CONTINUE_URL = `${AUTH_BASE_URL}/api/accounts/authorize/continue`;
const AUTH_EMAIL_OTP_SEND_URL = `${AUTH_BASE_URL}/api/accounts/email-otp/send`;
const AUTH_EMAIL_OTP_VALIDATE_URL = `${AUTH_BASE_URL}/api/accounts/email-otp/validate`;
const AUTH_WORKSPACE_SELECT_URL = `${AUTH_BASE_URL}/api/accounts/workspace/select`;
const AUTH_PHONE_SEND_URL = `${AUTH_BASE_URL}/api/accounts/add-phone/send`;
const AUTH_PHONE_OTP_SEND_URL = `${AUTH_BASE_URL}/api/accounts/phone-otp/send`;
const AUTH_PHONE_OTP_VALIDATE_URL = `${AUTH_BASE_URL}/api/accounts/phone-otp/validate`;
const AUTH_OAUTH_TOKEN_URLS = [
  `${AUTH_BASE_URL}/api/oauth/oauth2/token`,
  `${AUTH_BASE_URL}/oauth/token`,
];
const DEFAULT_REDIRECT_URI = 'http://localhost:1455/auth/callback';
const DEFAULT_CLIENT_ID = 'app_EMoamEEZ73f0CkXaXp7hrann';
const DEFAULT_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36';
const DEFAULT_DEVICE_PROFILE = {
  userAgent: DEFAULT_USER_AGENT,
  acceptLanguage: 'zh-CN,zh;q=0.9,en;q=0.8',
  locale: 'zh-CN',
  languages: ['zh-CN', 'zh'],
  timezoneId: 'Asia/Shanghai',
  viewportWidth: 1365,
  viewportHeight: 768,
  screenWidth: 1366,
  screenHeight: 768,
  outerWidth: 1376,
  outerHeight: 860,
  deviceScaleFactor: 1,
  hardwareConcurrency: 8,
  deviceMemory: 8,
  jsHeapSizeLimit: 4294967296,
  platform: 'Win32',
  vendor: 'Google Inc.',
  maxTouchPoints: 0,
  hasTouch: false,
  isMobile: false,
  colorDepth: 24,
  pixelDepth: 24,
};
const DEFAULT_CLIENT_HINTS = {
  secChUa: '"Google Chrome";v="146", "Chromium";v="146", "Not.A/Brand";v="24"',
  secChUaFullVersionList: '"Google Chrome";v="146.0.0.0", "Chromium";v="146.0.0.0", "Not.A/Brand";v="24.0.0.0"',
  secChUaMobile: '?0',
  secChUaPlatform: '"Windows"',
  secChUaPlatformVersion: '"15.0.0"',
  secChViewportWidth: '"1365"',
};
const EMAIL_OTP_VALIDATE_MAX_ATTEMPTS = 2;
const EMAIL_OTP_RETRY_DELAY_MS = 2000;
const PHONE_OTP_WAIT_TIMEOUT_MS = 180000;
const PHONE_OTP_POLL_INTERVAL_MS = 5000;
const JSON_LOGIN_TIMEOUT_MS = 180000;
const SUB2API_DEFAULT_EXPIRES_IN = 864000;

function normalizeExportFormat(value) {
  return String(value || '').trim() === 'CLIProxyAPI' ? 'CLIProxyAPI' : 'sub2api';
}

function sanitizeFileSegment(value) {
  return String(value || '').replace(/[<>:"/\\|?*\x00-\x1F]/g, '_');
}

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

function randomUrlSafeString(length) {
  return randomBytes(length > 0 ? length : 32).toString('base64url');
}

function pkceCodeChallenge(codeVerifier) {
  return createHash('sha256').update(codeVerifier).digest('base64url');
}

function decodeJwtPayload(token) {
  const parts = String(token || '').split('.');
  if (parts.length < 2) return {};
  try {
    const normalized = parts[1].replace(/-/g, '+').replace(/_/g, '/');
    const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, '=');
    const parsed = JSON.parse(Buffer.from(padded, 'base64').toString('utf8'));
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch {
    return {};
  }
}

function getNestedRecord(payload, key) {
  const value = payload?.[key];
  return value && typeof value === 'object' && !Array.isArray(value) ? value : {};
}

function firstNonEmpty(...values) {
  for (const value of values) {
    if (value == null) continue;
    const normalized = String(value).trim();
    if (normalized) return normalized;
  }
  return '';
}

function buildBrowserHeaders(init = {}) {
  return {
    'user-agent': DEFAULT_USER_AGENT,
    'accept-language': DEFAULT_DEVICE_PROFILE.acceptLanguage,
    'sec-ch-ua': DEFAULT_CLIENT_HINTS.secChUa,
    'sec-ch-ua-full-version-list': DEFAULT_CLIENT_HINTS.secChUaFullVersionList,
    'sec-ch-ua-mobile': DEFAULT_CLIENT_HINTS.secChUaMobile,
    'sec-ch-ua-platform': DEFAULT_CLIENT_HINTS.secChUaPlatform,
    'sec-ch-ua-platform-version': DEFAULT_CLIENT_HINTS.secChUaPlatformVersion,
    'sec-ch-viewport-width': DEFAULT_CLIENT_HINTS.secChViewportWidth,
    ...init,
  };
}

function normalizeAuthContinueUrl(value) {
  const text = String(value || '').trim();
  if (!text) return '';
  return text.startsWith('http') ? text : new URL(text, AUTH_BASE_URL).toString();
}

function parseExpiredTime(value) {
  const text = String(value || '').trim();
  if (!text) return 0;
  const normalized = text.endsWith('Z') ? text : `${text}Z`;
  const timestamp = Date.parse(normalized);
  return Number.isFinite(timestamp) ? Math.floor(timestamp / 1000) : 0;
}

function resolveOrganizationId(idClaims, accessClaims) {
  const idAuth = getNestedRecord(idClaims, 'https://api.openai.com/auth');
  const accessAuth = getNestedRecord(accessClaims, 'https://api.openai.com/auth');
  const organizations = [idAuth.organizations, accessAuth.organizations].find(Array.isArray);
  if (!Array.isArray(organizations) || !organizations.length) return '';
  const first = organizations[0];
  return first && typeof first === 'object' && !Array.isArray(first) ? firstNonEmpty(first.id) : '';
}

function buildSub2ApiAccount(record) {
  const accessClaims = decodeJwtPayload(record.access_token);
  const idClaims = decodeJwtPayload(record.id_token);
  const accessAuth = getNestedRecord(accessClaims, 'https://api.openai.com/auth');
  const idAuth = getNestedRecord(idClaims, 'https://api.openai.com/auth');
  const accessProfile = getNestedRecord(accessClaims, 'https://api.openai.com/profile');
  const expiresAt = parseExpiredTime(record.expired) || Number(accessClaims.exp || 0);
  const issuedAt = Number(accessClaims.iat || 0);
  const expiresIn = expiresAt && issuedAt ? Math.max(expiresAt - issuedAt, 0) : SUB2API_DEFAULT_EXPIRES_IN;
  const email = firstNonEmpty(record.email, accessProfile.email, idClaims.email, accessClaims.email);
  const accountId = firstNonEmpty(record.account_id, accessAuth.chatgpt_account_id, idAuth.chatgpt_account_id);
  const planType = firstNonEmpty(record.plan_type, accessAuth.chatgpt_plan_type, idAuth.chatgpt_plan_type, 'free');

  return {
    name: email || `openai-${Date.now()}`,
    platform: 'openai',
    type: 'oauth',
    credentials: {
      access_token: String(record.access_token || ''),
      chatgpt_account_id: accountId,
      chatgpt_user_id: firstNonEmpty(accessAuth.chatgpt_user_id, accessAuth.user_id, accessClaims.sub),
      expires_at: expiresAt,
      expires_in: expiresIn,
      organization_id: resolveOrganizationId(idClaims, accessClaims),
      plan_type: planType,
      refresh_token: String(record.refresh_token || ''),
    },
    extra: { email },
    concurrency: Number(process.env.SUB2API_CONCURRENCY || 10),
    priority: Number(process.env.SUB2API_PRIORITY || 1),
    rate_multiplier: 1,
    auto_pause_on_expired: true,
  };
}

function buildSub2ApiExport(records, exportedAt = new Date().toISOString().replace(/\.\d{3}Z$/, 'Z')) {
  return {
    exported_at: exportedAt,
    proxies: [],
    accounts: records.map(buildSub2ApiAccount),
  };
}

function buildSub2ApiJson(record) {
  return buildSub2ApiExport([record]);
}

const CRC32_TABLE = (() => {
  const table = new Uint32Array(256);
  for (let i = 0; i < 256; i += 1) {
    let crc = i;
    for (let j = 0; j < 8; j += 1) {
      crc = (crc & 1) ? (0xEDB88320 ^ (crc >>> 1)) : (crc >>> 1);
    }
    table[i] = crc >>> 0;
  }
  return table;
})();

function crc32(buffer) {
  let crc = 0xFFFFFFFF;
  for (const byte of buffer) crc = CRC32_TABLE[(crc ^ byte) & 0xFF] ^ (crc >>> 8);
  return (crc ^ 0xFFFFFFFF) >>> 0;
}

function dosDateTime(date = new Date()) {
  const year = Math.max(1980, date.getFullYear());
  return {
    time: (date.getHours() << 11) | (date.getMinutes() << 5) | Math.floor(date.getSeconds() / 2),
    date: ((year - 1980) << 9) | ((date.getMonth() + 1) << 5) | date.getDate(),
  };
}

function makeZip(files) {
  const localParts = [];
  const centralParts = [];
  const stamp = dosDateTime();
  let offset = 0;
  for (const file of files) {
    const nameBuffer = Buffer.from(file.name, 'utf8');
    const dataBuffer = Buffer.isBuffer(file.data) ? file.data : Buffer.from(String(file.data || ''), 'utf8');
    const crc = crc32(dataBuffer);
    const localHeader = Buffer.alloc(30);
    localHeader.writeUInt32LE(0x04034b50, 0);
    localHeader.writeUInt16LE(20, 4);
    localHeader.writeUInt16LE(0x0800, 6);
    localHeader.writeUInt16LE(0, 8);
    localHeader.writeUInt16LE(stamp.time, 10);
    localHeader.writeUInt16LE(stamp.date, 12);
    localHeader.writeUInt32LE(crc, 14);
    localHeader.writeUInt32LE(dataBuffer.length, 18);
    localHeader.writeUInt32LE(dataBuffer.length, 22);
    localHeader.writeUInt16LE(nameBuffer.length, 26);
    localHeader.writeUInt16LE(0, 28);
    localParts.push(localHeader, nameBuffer, dataBuffer);

    const centralHeader = Buffer.alloc(46);
    centralHeader.writeUInt32LE(0x02014b50, 0);
    centralHeader.writeUInt16LE(20, 4);
    centralHeader.writeUInt16LE(20, 6);
    centralHeader.writeUInt16LE(0x0800, 8);
    centralHeader.writeUInt16LE(0, 10);
    centralHeader.writeUInt16LE(stamp.time, 12);
    centralHeader.writeUInt16LE(stamp.date, 14);
    centralHeader.writeUInt32LE(crc, 16);
    centralHeader.writeUInt32LE(dataBuffer.length, 20);
    centralHeader.writeUInt32LE(dataBuffer.length, 24);
    centralHeader.writeUInt16LE(nameBuffer.length, 28);
    centralHeader.writeUInt16LE(0, 30);
    centralHeader.writeUInt16LE(0, 32);
    centralHeader.writeUInt16LE(0, 34);
    centralHeader.writeUInt16LE(0, 36);
    centralHeader.writeUInt32LE(0, 38);
    centralHeader.writeUInt32LE(offset, 42);
    centralParts.push(centralHeader, nameBuffer);
    offset += localHeader.length + nameBuffer.length + dataBuffer.length;
  }

  const centralSize = centralParts.reduce((sum, part) => sum + part.length, 0);
  const eocd = Buffer.alloc(22);
  eocd.writeUInt32LE(0x06054b50, 0);
  eocd.writeUInt16LE(0, 4);
  eocd.writeUInt16LE(0, 6);
  eocd.writeUInt16LE(files.length, 8);
  eocd.writeUInt16LE(files.length, 10);
  eocd.writeUInt32LE(centralSize, 12);
  eocd.writeUInt32LE(offset, 16);
  eocd.writeUInt16LE(0, 20);
  return Buffer.concat([...localParts, ...centralParts, eocd]);
}

async function buildSub2ApiZipForAccounts(accounts) {
  const records = [];
  const files = [];
  const errors = [];
  const exportedAt = new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');

  for (const account of accounts) {
    try {
      if (!account.openai_rt) throw new Error('该邮箱尚未导入 OpenAI rttoken');
      const logs = [];
      const record = await resolveOpenAIRecordForExport(account, logs);
      if (record.refresh_token && record.refresh_token !== account.openai_rt) {
        await withDatabaseWrite(async () => {
          const latest = findAccountById(account.id);
          if (!latest) return;
          latest.openai_rt = record.refresh_token;
          latest.status = 'RT已刷新';
          latest.updatedAt = nowIso();
        });
        account.openai_rt = record.refresh_token;
      }
      records.push(record);
      const email = firstNonEmpty(record.email, account.email);
      files.push({
        name: `individual/${sanitizeFileSegment(email || account.email)}.json`,
        data: JSON.stringify(buildSub2ApiExport([record], exportedAt), null, 2) + '\n',
      });
    } catch (error) {
      errors.push({ email: account.email, error: error instanceof Error ? error.message : String(error) });
    }
  }

  if (!records.length) throw new Error(errors.map(item => `${item.email}: ${item.error}`).join('；') || '没有可导出的 sub2api 账号');

  files.unshift({
    name: 'sub2api-account-all.json',
    data: JSON.stringify(buildSub2ApiExport(records, exportedAt), null, 2) + '\n',
  });
  files.push({
    name: '取件结果.txt',
    data: [
      '取货格式：Sub2API',
      `成功取件：${records.length}`,
      `失败取件：${errors.length}`,
      `转换账号：${records.length}`,
      ...errors.map(item => `失败：${item.email} ${item.error}`),
      '',
    ].join('\n'),
  });

  return { zip: makeZip(files), success: records.length, failed: errors.length };
}

function buildCLIProxyApiJson(record) {
  const accessClaims = decodeJwtPayload(record.access_token);
  const idClaims = decodeJwtPayload(record.id_token);
  const accessAuth = getNestedRecord(accessClaims, 'https://api.openai.com/auth');
  const idAuth = getNestedRecord(idClaims, 'https://api.openai.com/auth');
  const accessProfile = getNestedRecord(accessClaims, 'https://api.openai.com/profile');
  const accountId = firstNonEmpty(record.account_id, accessAuth.chatgpt_account_id, idAuth.chatgpt_account_id);
  const email = firstNonEmpty(record.email, accessProfile.email, idClaims.email, accessClaims.email);
  const planType = firstNonEmpty(record.plan_type, accessAuth.chatgpt_plan_type, idAuth.chatgpt_plan_type);

  return {
    type: firstNonEmpty(record.type, 'codex'),
    access_token: String(record.access_token || ''),
    account_id: accountId,
    chatgpt_account_id: accountId,
    email,
    name: firstNonEmpty(record.name, email),
    plan_type: planType,
    chatgpt_plan_type: planType,
    id_token: String(record.id_token || ''),
    refresh_token: String(record.refresh_token || ''),
    last_refresh: String(record.last_refresh || ''),
    expired: String(record.expired || ''),
  };
}

function buildExportJson(record, format) {
  return format === 'CLIProxyAPI'
    ? buildCLIProxyApiJson(record)
    : buildSub2ApiJson(record);
}

function performanceNow() {
  return Number(process.hrtime.bigint() / BigInt(1_000_000));
}

function base64Json(value) {
  return Buffer.from(JSON.stringify(value), 'utf8').toString('base64');
}

function randomPick(items) {
  return items[Math.floor(Math.random() * items.length)];
}

function sentinelHashHex(input) {
  let hash = 2166136261;
  for (let i = 0; i < input.length; i += 1) {
    hash ^= input.charCodeAt(i);
    hash = Math.imul(hash, 16777619) >>> 0;
  }
  hash ^= hash >>> 16;
  hash = Math.imul(hash, 2246822507) >>> 0;
  hash ^= hash >>> 13;
  hash = Math.imul(hash, 3266489909) >>> 0;
  hash ^= hash >>> 16;
  return (hash >>> 0).toString(16).padStart(8, '0');
}

function collectSentinelFingerprintData(sid) {
  return [
    DEFAULT_DEVICE_PROFILE.screenWidth + DEFAULT_DEVICE_PROFILE.screenHeight,
    new Date().toString(),
    DEFAULT_DEVICE_PROFILE.jsHeapSizeLimit,
    Math.random(),
    DEFAULT_USER_AGENT,
    'https://sentinel.openai.com/sentinel/20260219f9f6/sdk.js',
    '20260219f9f6',
    DEFAULT_DEVICE_PROFILE.languages[0],
    DEFAULT_DEVICE_PROFILE.languages.join(','),
    Math.random(),
    randomPick([
      `userAgent−${DEFAULT_USER_AGENT}`,
      `language−${DEFAULT_DEVICE_PROFILE.languages[0]}`,
      `hardwareConcurrency−${DEFAULT_DEVICE_PROFILE.hardwareConcurrency}`,
    ]),
    'location',
    randomPick(['window', 'self', 'document', 'navigator', 'location', 'screen', 'history']),
    performanceNow(),
    sid,
    'sv',
    DEFAULT_DEVICE_PROFILE.hardwareConcurrency,
    Date.now(),
    0,
    1,
    1,
    0,
    0,
    0,
    1,
  ];
}

async function generateSentinelAnswer(seed, difficulty) {
  const start = performanceNow();
  const sid = randomUUID();
  const data = collectSentinelFingerprintData(sid);
  for (let attempt = 0; attempt < 500000; attempt += 1) {
    data[3] = attempt;
    data[9] = Math.round(performanceNow() - start);
    const encoded = base64Json(data);
    const digest = sentinelHashHex(seed + encoded);
    if (digest.substring(0, difficulty.length) <= difficulty) {
      return `${encoded}~S`;
    }
    if ((attempt + 1) % 5000 === 0) await Promise.resolve();
  }
  return `wQ8Lk5FbGpA2NcR9dShT6gYjU7VxZ4D${base64Json('max attempts exceeded')}`;
}

async function fetchOpenAISentinelToken(fetcher, deviceID, flow) {
  const requirementSeed = `${Math.random()}`;
  const reqToken = `gAAAAAC${await generateSentinelAnswer(requirementSeed, '0')}`;
  const response = await fetcher('https://sentinel.openai.com/backend-api/sentinel/req', {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      'user-agent': DEFAULT_USER_AGENT,
    },
    body: JSON.stringify({
      p: reqToken,
      id: deviceID,
      flow,
    }),
  });
  if (!response.ok) {
    throw new Error(`请求 sentinel requirements 失败: ${response.status} body=${await response.text()}`);
  }
  const requirements = await response.json();
  if (requirements.turnstile?.dx) {
    throw new Error('当前 OpenAI 登录触发 Turnstile，服务器无浏览器模式暂不能自动通过');
  }
  const proof = requirements.proofofwork?.required && requirements.proofofwork.seed && requirements.proofofwork.difficulty
    ? `gAAAAAB${await generateSentinelAnswer(requirements.proofofwork.seed, requirements.proofofwork.difficulty)}`
    : null;
  return JSON.stringify({
    p: proof,
    t: null,
    c: requirements.token,
    id: deviceID,
    flow,
  });
}

function normalizeOpenAIAuthRecord(email, payload) {
  if (!payload.access_token) throw new Error(`token响应缺少 access_token: ${JSON.stringify(payload)}`);
  if (!payload.refresh_token) throw new Error(`token响应缺少 refresh_token: ${JSON.stringify(payload)}`);
  if (!payload.id_token) throw new Error(`token响应缺少 id_token: ${JSON.stringify(payload)}`);

  const accessClaims = decodeJwtPayload(payload.access_token);
  const idClaims = decodeJwtPayload(payload.id_token);
  const authClaim = getNestedRecord(accessClaims, 'https://api.openai.com/auth');
  const idAuthClaim = getNestedRecord(idClaims, 'https://api.openai.com/auth');
  const accountId = firstNonEmpty(authClaim.chatgpt_account_id, idAuthClaim.chatgpt_account_id);
  const exp = Number(accessClaims.exp || 0);
  if (!accountId) throw new Error(`token中缺少 account_id: ${JSON.stringify(accessClaims)}`);
  if (!exp) throw new Error(`access_token中缺少 exp: ${JSON.stringify(accessClaims)}`);

  return {
    access_token: payload.access_token,
    account_id: accountId,
    disabled: false,
    email: firstNonEmpty(idClaims.email, accessClaims.email, email),
    expired: new Date(exp * 1000).toISOString(),
    id_token: payload.id_token,
    last_refresh: new Date().toISOString(),
    refresh_token: payload.refresh_token,
    type: 'codex',
    websockets: false,
  };
}

function extractOpenAICode(text) {
  const normalized = String(text || '').replace(/\s+/g, ' ');
  const preferred = [
    /(?:OpenAI|ChatGPT|verification|verify|code|验证码|登录码)[^\d]{0,80}(\d{6})/i,
    /\b(\d{6})\b/,
  ];
  for (const re of preferred) {
    const match = normalized.match(re);
    if (match?.[1]) return match[1];
  }
  return null;
}

async function waitForOpenAIEmailCode(account, minTimestamp, logger, timeoutMs = JSON_LOGIN_TIMEOUT_MS) {
  const accessToken = await refreshAccessToken(account.refresh_token, account.client_id, logger);
  const client = new ImapFlow({
    host: 'outlook.office365.com',
    port: 993,
    secure: true,
    auth: {
      user: account.email,
      accessToken,
    },
    logger: false,
  });
  const seen = new Set();
  const folders = ['INBOX', 'Junk', 'Junk Email'];
  const startedAt = Date.now();

  try {
    await client.connect();
    logger('已连接邮箱 IMAP，等待 OpenAI 验证码...');
    while (Date.now() - startedAt < timeoutMs) {
      for (const folder of folders) {
        let opened = false;
        try {
          opened = await client.mailboxOpen(folder).then(() => true).catch(() => false);
          if (!opened) continue;
          const status = client.mailbox;
          if (!status?.exists) continue;
          const start = Math.max(1, status.exists - 25 + 1);
          for await (const msg of client.fetch(`${start}:*`, { uid: true, envelope: true, source: true })) {
            const key = `${folder}:${msg.uid}`;
            if (seen.has(key)) continue;
            seen.add(key);

            const dateValue = (msg.envelope && msg.envelope.date) || new Date();
            const mailTime = new Date(dateValue).getTime();
            if (Number.isFinite(mailTime) && mailTime < minTimestamp - 5000) continue;

            let parsed;
            try { parsed = await simpleParser(msg.source); } catch { parsed = {}; }
            const subject = (msg.envelope && msg.envelope.subject) || parsed.subject || '';
            const from = (msg.envelope && msg.envelope.from && msg.envelope.from[0])
              ? `${msg.envelope.from[0].name || ''} <${msg.envelope.from[0].address || ''}>`
              : (parsed.from && parsed.from.text) || '';
            const text = parsed.text || (parsed.html ? String(parsed.html).replace(/<[^>]+>/g, ' ') : '');
            const haystack = `${subject}\n${from}\n${text}`;
            const isOpenAI = /openai|chatgpt/i.test(haystack);
            const code = isOpenAI ? extractOpenAICode(haystack) : null;
            if (code) {
              logger(`收到 OpenAI 验证码: ${code}`);
              return code;
            }
          }
        } catch (error) {
          logger(`拉取 ${folder} 失败: ${error.message}`, 'warn');
        }
      }
      await sleep(5000);
    }
    throw new Error('等待 OpenAI 邮箱验证码超时');
  } finally {
    try { await client.logout(); } catch {}
  }
}

class OpenAIJsonAuthFlow {
  constructor(account, sse) {
    this.account = account;
    this.sse = sse;
    this.jar = new CookieJar();
    this.fetch = makeFetchCookie(fetch, this.jar);
    this.state = '';
    this.codeVerifier = '';
    this.deviceID = '';
    this.emailOtpRequestedAtMs = 0;
  }

  log(msg, level = 'info') {
    this.sse.send('log', { time: new Date().toISOString(), level, msg });
  }

  async readCookie(url, key) {
    const cookies = await this.jar.getCookies(url);
    return cookies.find(cookie => cookie.key === key)?.value || '';
  }

  prepareLoginUrl(prompt = 'login') {
    this.state = randomUrlSafeString(24);
    this.codeVerifier = randomUrlSafeString(64);
    const query = new URLSearchParams({
      client_id: DEFAULT_CLIENT_ID,
      response_type: 'code',
      redirect_uri: DEFAULT_REDIRECT_URI,
      scope: 'openid email profile offline_access',
      state: this.state,
      code_challenge: pkceCodeChallenge(this.codeVerifier),
      code_challenge_method: 'S256',
      prompt,
      id_token_add_organizations: 'true',
      codex_cli_simplified_flow: 'true',
      login_hint: this.account.email,
    });
    return `${AUTH_BASE_URL}/oauth/authorize?${query.toString()}`;
  }

  async formatErrorResponse(response) {
    const body = await response.text();
    try {
      const payload = JSON.parse(body);
      const code = payload?.error?.code || payload?.error;
      if (code) return `${response.status} code=${code}`;
    } catch {}
    return `${response.status} body=${body}`;
  }

  async fetchSentinelToken(flow) {
    return fetchOpenAISentinelToken(this.fetch, this.deviceID, flow);
  }

  async authorizeContinue() {
    const sentinelToken = await this.fetchSentinelToken('authorize_continue');
    const response = await this.fetch(AUTH_AUTHORIZE_CONTINUE_URL, {
      method: 'POST',
      headers: buildBrowserHeaders({
        'content-type': 'application/json',
        'openai-sentinel-token': sentinelToken,
      }),
      body: JSON.stringify({
        username: {
          kind: 'email',
          value: this.account.email,
        },
      }),
    });
    if (!response.ok) throw new Error(`AuthorizeContinue请求失败: ${await this.formatErrorResponse(response)}`);
    const payload = await response.json();
    return normalizeAuthContinueUrl(payload.continue_url);
  }

  async sendEmailOtp() {
    const response = await this.fetch(AUTH_EMAIL_OTP_SEND_URL, {
      method: 'GET',
      headers: buildBrowserHeaders({
        accept: 'application/json',
        referer: `${AUTH_BASE_URL}/log-in`,
      }),
    });
    if (!response.ok) throw new Error(`EmailOtpSend请求失败: ${await this.formatErrorResponse(response)}`);
    this.emailOtpRequestedAtMs = Date.now();
    const payload = await response.json();
    return normalizeAuthContinueUrl(payload.continue_url);
  }

  async emailOtpValidate() {
    let lastErrorMessage = '';
    for (let attempt = 1; attempt <= EMAIL_OTP_VALIDATE_MAX_ATTEMPTS; attempt += 1) {
      const code = await waitForOpenAIEmailCode(
        this.account,
        this.emailOtpRequestedAtMs || Date.now() - 10000,
        (msg, level = 'info') => this.log(msg, level),
      );
      const response = await this.fetch(AUTH_EMAIL_OTP_VALIDATE_URL, {
        method: 'POST',
        headers: buildBrowserHeaders({
          accept: 'application/json',
          'content-type': 'application/json',
          origin: AUTH_BASE_URL,
          referer: `${AUTH_BASE_URL}/email-verification`,
        }),
        body: JSON.stringify({ code }),
      });
      if (response.ok) {
        const payload = await response.json();
        return normalizeAuthContinueUrl(payload.continue_url);
      }
      lastErrorMessage = await this.formatErrorResponse(response);
      if (!lastErrorMessage.includes('wrong_email_otp_code') || attempt >= EMAIL_OTP_VALIDATE_MAX_ATTEMPTS) {
        throw new Error(`EmailOtpValidate请求失败: ${lastErrorMessage}`);
      }
      this.log('验证码疑似过期或取错，重新发码后重试', 'warn');
      await this.sendEmailOtp();
      await sleep(EMAIL_OTP_RETRY_DELAY_MS);
    }
    throw new Error(`EmailOtpValidate请求失败: ${lastErrorMessage || 'unknown'}`);
  }

  async resolveWorkspaceID() {
    const cookie = await this.readCookie(AUTH_BASE_URL, 'oai-client-auth-session');
    if (!cookie) throw new Error('未找到 oai-client-auth-session cookie，无法提取 workspace');
    const encodedPayload = cookie.split('.')[0];
    const payload = JSON.parse(Buffer.from(encodedPayload.replace(/-/g, '+').replace(/_/g, '/').padEnd(Math.ceil(encodedPayload.length / 4) * 4, '='), 'base64').toString('utf8'));
    const workspaceID = payload.workspaces?.find(w => w.kind === 'personal')?.id || payload.workspaces?.[0]?.id;
    if (!workspaceID) throw new Error(`当前会话未发现 workspace: ${JSON.stringify(payload)}`);
    return workspaceID;
  }

  async selectWorkspace(consentURL) {
    await this.fetch(consentURL, {
      method: 'GET',
      headers: buildBrowserHeaders({
        accept: 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        referer: `${AUTH_BASE_URL}/email-verification`,
      }),
    });
    const workspaceID = await this.resolveWorkspaceID();
    const response = await this.fetch(AUTH_WORKSPACE_SELECT_URL, {
      method: 'POST',
      headers: buildBrowserHeaders({
        accept: 'application/json',
        'content-type': 'application/json',
        origin: AUTH_BASE_URL,
        referer: consentURL,
      }),
      body: JSON.stringify({ workspace_id: workspaceID }),
    });
    if (!response.ok) throw new Error(`WorkspaceSelect请求失败: ${await this.formatErrorResponse(response)}`);
    const payload = await response.json();
    return normalizeAuthContinueUrl(payload.continue_url);
  }

  async sendPhoneOtp(phoneNumber) {
    const response = await this.fetch(AUTH_PHONE_SEND_URL, {
      method: 'POST',
      headers: buildBrowserHeaders({
        accept: 'application/json',
        'content-type': 'application/json',
        origin: AUTH_BASE_URL,
        referer: `${AUTH_BASE_URL}/add-phone`,
      }),
      body: JSON.stringify({ phone_number: phoneNumber }),
    });
    if (!response.ok) throw new Error(`SendPhoneOtp请求失败: ${await this.formatErrorResponse(response)}`);
    const payload = await response.json();
    return normalizeAuthContinueUrl(payload.continue_url);
  }

  async sendExistingPhoneOtp() {
    const response = await this.fetch(AUTH_PHONE_OTP_SEND_URL, {
      method: 'POST',
      headers: buildBrowserHeaders({
        accept: 'application/json',
        'content-type': 'application/json',
        origin: AUTH_BASE_URL,
        referer: `${AUTH_BASE_URL}/phone-otp/select-channel`,
      }),
      body: JSON.stringify({ channel: 'sms' }),
    });
    if (!response.ok) throw new Error(`PhoneOtpSend请求失败: ${await this.formatErrorResponse(response)}`);
    const payload = await response.json();
    return normalizeAuthContinueUrl(payload.continue_url || `${AUTH_BASE_URL}/phone-verification`);
  }

  async validatePhoneOtp(code) {
    const response = await this.fetch(AUTH_PHONE_OTP_VALIDATE_URL, {
      method: 'POST',
      headers: buildBrowserHeaders({
        accept: 'application/json',
        'content-type': 'application/json',
        origin: AUTH_BASE_URL,
        referer: `${AUTH_BASE_URL}/phone-verification`,
      }),
      body: JSON.stringify({ code }),
    });
    if (!response.ok) throw new Error(`PhoneOtpValidate请求失败: ${await this.formatErrorResponse(response)}`);
    const payload = await response.json();
    return normalizeAuthContinueUrl(payload.continue_url);
  }

  async handleAddPhone() {
    const phoneNumber = String(this.account.auth_phone_number || '').trim();
    if (!phoneNumber) throw new Error('触发 add-phone，但该账号没有保存授权手机号');
    this.log(`提交已保存手机号: ${maskPhone(phoneNumber)}`);
    await this.sendPhoneOtp(phoneNumber);
    return this.handlePhoneVerification();
  }

  async handlePhoneVerification() {
    this.log('遇到手机验证，使用已保存短信链接自动接码');
    const code = await waitForPhoneCode(this.account, (msg, level = 'info') => this.log(msg, level));
    this.log('提交手机号短信验证码');
    return this.validatePhoneOtp(code);
  }

  async handlePhoneOtpSelectChannel() {
    this.log('遇到手机验证码通道选择，自动选择短信接收');
    try {
      await this.sendExistingPhoneOtp();
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      this.log(`自动选择短信通道失败，继续尝试读取已发送验证码: ${message}`, 'warn');
    }
    return this.handlePhoneVerification();
  }

  extractAuthResult(callbackURL) {
    const url = new URL(callbackURL);
    const code = url.searchParams.get('code') || '';
    const state = url.searchParams.get('state') || '';
    if (!code) throw new Error(`callback 中缺少 code: ${callbackURL}`);
    if (!state) throw new Error(`callback 中缺少 state: ${callbackURL}`);
    if (this.state && state !== this.state) throw new Error(`callback state 不匹配: expected=${this.state} actual=${state}`);
    return { callbackURL, code, state };
  }

  async followOAuthRedirects(startURL) {
    let currentURL = startURL;
    for (let hop = 0; hop < 10; hop += 1) {
      if (currentURL.startsWith(`${AUTH_BASE_URL}/add-phone`)) {
        currentURL = await this.handleAddPhone();
        continue;
      }
      if (currentURL.startsWith(`${AUTH_BASE_URL}/phone-otp/select-channel`)) {
        currentURL = await this.handlePhoneOtpSelectChannel();
        continue;
      }
      if (currentURL.startsWith(`${AUTH_BASE_URL}/phone-verification`)) {
        currentURL = await this.handlePhoneVerification();
        continue;
      }
      if (currentURL.startsWith(DEFAULT_REDIRECT_URI)) return this.extractAuthResult(currentURL);
      const response = await this.fetch(currentURL, {
        method: 'GET',
        redirect: 'manual',
        headers: buildBrowserHeaders({
          accept: 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }),
      });
      const location = response.headers.get('location');
      if (location) {
        const nextURL = new URL(location, currentURL).toString();
        if (nextURL.startsWith(`${AUTH_BASE_URL}/add-phone`)) {
          currentURL = await this.handleAddPhone();
          continue;
        }
        if (nextURL.startsWith(`${AUTH_BASE_URL}/phone-otp/select-channel`)) {
          currentURL = await this.handlePhoneOtpSelectChannel();
          continue;
        }
        if (nextURL.startsWith(`${AUTH_BASE_URL}/phone-verification`)) {
          currentURL = await this.handlePhoneVerification();
          continue;
        }
        if (nextURL.startsWith(DEFAULT_REDIRECT_URI)) return this.extractAuthResult(nextURL);
        currentURL = nextURL;
        continue;
      }
      if (response.url.startsWith(`${AUTH_BASE_URL}/add-phone`)) {
        currentURL = await this.handleAddPhone();
        continue;
      }
      if (response.url.startsWith(`${AUTH_BASE_URL}/phone-otp/select-channel`)) {
        currentURL = await this.handlePhoneOtpSelectChannel();
        continue;
      }
      if (response.url.startsWith(`${AUTH_BASE_URL}/phone-verification`)) {
        currentURL = await this.handlePhoneVerification();
        continue;
      }
      if (response.url.startsWith(DEFAULT_REDIRECT_URI)) return this.extractAuthResult(response.url);
      throw new Error(`OAuth跳转未到达callback: status=${response.status} url=${response.url}`);
    }
    throw new Error(`OAuth跳转次数过多，最后停在: ${currentURL}`);
  }

  async exchangeCodeForToken(code) {
    let lastError = '';
    for (const tokenURL of AUTH_OAUTH_TOKEN_URLS) {
      const body = new URLSearchParams({
        grant_type: 'authorization_code',
        client_id: DEFAULT_CLIENT_ID,
        code,
        redirect_uri: DEFAULT_REDIRECT_URI,
        code_verifier: this.codeVerifier,
      });
      const response = await this.fetch(tokenURL, {
        method: 'POST',
        headers: buildBrowserHeaders({
          accept: 'application/json',
          'content-type': 'application/x-www-form-urlencoded',
          'sec-fetch-dest': 'empty',
          'sec-fetch-mode': 'cors',
          'sec-fetch-site': 'same-site',
        }),
        body,
      });
      if (!response.ok) {
        lastError = `endpoint=${tokenURL} ${await this.formatErrorResponse(response)}`;
        continue;
      }
      const payload = await response.json();
      return normalizeOpenAIAuthRecord(this.account.email, payload);
    }
    throw new Error(`Code换Token失败: ${lastError}`);
  }

  async run() {
    this.log(`开始 OpenAI 邮箱验证码授权: ${this.account.email}`);
    const oauthUrl = this.prepareLoginUrl('login');
    const oauthResp = await this.fetch(oauthUrl, {
      redirect: 'follow',
      headers: buildBrowserHeaders({
        'accept-encoding': 'gzip, deflate, br',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'none',
      }),
    });
    if (!oauthResp.ok) throw new Error(`OauthUrl请求失败: ${oauthResp.status}`);

    if (oauthResp.url.startsWith(DEFAULT_REDIRECT_URI)) {
      const result = this.extractAuthResult(oauthResp.url);
      return this.exchangeCodeForToken(result.code);
    }
    const allowedStartUrls = new Set([
      `${AUTH_BASE_URL}/log-in`,
      `${AUTH_BASE_URL}/email-verification`,
      `${AUTH_BASE_URL}/sign-in-with-chatgpt/codex/consent`,
      `${AUTH_BASE_URL}/add-phone`,
      `${AUTH_BASE_URL}/phone-otp/select-channel`,
      `${AUTH_BASE_URL}/phone-verification`,
    ]);
    if (!allowedStartUrls.has(oauthResp.url) && !oauthResp.url.startsWith(`${AUTH_BASE_URL}/add-phone`) && !oauthResp.url.startsWith(`${AUTH_BASE_URL}/phone-otp/select-channel`) && !oauthResp.url.startsWith(`${AUTH_BASE_URL}/phone-verification`)) {
      throw new Error(`OauthUrl重定向到错误的URL: ${oauthResp.url}`);
    }

    this.deviceID = await this.readCookie('https://openai.com', 'oai-did');
    if (!this.deviceID) throw new Error('OauthUrl未返回 oai-did cookie');

    let continueURL = oauthResp.url;
    if (continueURL === `${AUTH_BASE_URL}/email-verification`) {
      this.emailOtpRequestedAtMs = Date.now() - 10000;
    }
    if (continueURL === `${AUTH_BASE_URL}/log-in`) {
      this.log('提交登录邮箱');
      continueURL = await this.authorizeContinue();
    }
    if (continueURL === `${AUTH_BASE_URL}/log-in/password`) {
      this.log('该账号要求密码登录，当前功能只支持邮箱验证码登录', 'error');
      throw new Error('该账号进入密码登录页，无法无密码获取 RT');
    }
    if (continueURL === AUTH_EMAIL_OTP_SEND_URL) {
      this.log('发送邮箱验证码');
      continueURL = await this.sendEmailOtp();
    }
    if (continueURL === `${AUTH_BASE_URL}/email-verification`) {
      this.log('等待并提交邮箱验证码');
      continueURL = await this.emailOtpValidate();
    }
    if (continueURL.startsWith(`${AUTH_BASE_URL}/add-phone`)) {
      continueURL = await this.handleAddPhone();
    }
    if (continueURL.startsWith(`${AUTH_BASE_URL}/phone-otp/select-channel`)) {
      continueURL = await this.handlePhoneOtpSelectChannel();
    }
    if (continueURL.startsWith(`${AUTH_BASE_URL}/phone-verification`)) {
      continueURL = await this.handlePhoneVerification();
    }
    if (continueURL === `${AUTH_BASE_URL}/sign-in-with-chatgpt/codex/consent`) {
      this.log('选择默认工作区');
      continueURL = await this.selectWorkspace(continueURL);
    }

    if (continueURL.startsWith(`${AUTH_BASE_URL}/add-phone`)) {
      continueURL = await this.handleAddPhone();
    }
    if (continueURL.startsWith(`${AUTH_BASE_URL}/phone-otp/select-channel`)) {
      continueURL = await this.handlePhoneOtpSelectChannel();
    }
    if (continueURL.startsWith(`${AUTH_BASE_URL}/phone-verification`)) {
      continueURL = await this.handlePhoneVerification();
    }
    if (continueURL === `${AUTH_BASE_URL}/sign-in-with-chatgpt/codex/consent`) {
      this.log('选择默认工作区');
      continueURL = await this.selectWorkspace(continueURL);
    }

    this.log('交换授权 code 获取 refresh_token');
    this.log(`继续 OAuth 跳转: ${continueURL}`);
    const result = await this.followOAuthRedirects(continueURL);
    return this.exchangeCodeForToken(result.code);
  }
}

// ------------------------- OAuth -------------------------
// 参考 codex-console：依次尝试 LIVE / CONSUMERS / COMMON 三种端点
const IMAP_SCOPE = 'https://outlook.office.com/IMAP.AccessAsUser.All offline_access';
const TOKEN_ENDPOINTS = [
  // v1.0 端点（用 resource 而非 scope），常见于早期发的 refresh_token
  { name: 'V1-COMMON',          url: 'https://login.microsoftonline.com/common/oauth2/token',             scope: '', resource: 'https://outlook.office.com/' },
  { name: 'V1-CONSUMERS',       url: 'https://login.microsoftonline.com/consumers/oauth2/token',          scope: '', resource: 'https://outlook.office.com/' },
  // v2.0 端点
  { name: 'LIVE',               url: 'https://login.live.com/oauth20_token.srf',                          scope: '' },
  { name: 'LIVE+scope',         url: 'https://login.live.com/oauth20_token.srf',                          scope: IMAP_SCOPE },
  { name: 'CONSUMERS',          url: 'https://login.microsoftonline.com/consumers/oauth2/v2.0/token',     scope: IMAP_SCOPE },
  { name: 'CONSUMERS-noscope',  url: 'https://login.microsoftonline.com/consumers/oauth2/v2.0/token',     scope: '' },
  { name: 'COMMON',             url: 'https://login.microsoftonline.com/common/oauth2/v2.0/token',        scope: IMAP_SCOPE },
  { name: 'COMMON-noscope',     url: 'https://login.microsoftonline.com/common/oauth2/v2.0/token',        scope: '' },
  { name: 'ORGANIZATIONS',      url: 'https://login.microsoftonline.com/organizations/oauth2/v2.0/token', scope: IMAP_SCOPE },
];

async function refreshAccessToken(refreshToken, clientId, logger) {
  const errors = [];
  for (const ep of TOKEN_ENDPOINTS) {
    const params = {
      client_id: clientId,
      grant_type: 'refresh_token',
      refresh_token: refreshToken,
    };
    if (ep.scope) params.scope = ep.scope;
    if (ep.resource) params.resource = ep.resource;
    try {
      const resp = await fetch(ep.url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
          'Accept': 'application/json',
        },
        body: new URLSearchParams(params).toString(),
      });
      const text = await resp.text();
      let data; try { data = JSON.parse(text); } catch { data = {}; }
      if (resp.ok && data.access_token) {
        logger?.(`Token 端点 ${ep.name} 成功`);
        return data.access_token;
      }
      const msg = data.error_description || data.error || `HTTP ${resp.status}`;
      errors.push(`${ep.name}: ${msg}`);
      logger?.(`Token 端点 ${ep.name} 失败: ${msg}`, 'warn');
    } catch (e) {
      errors.push(`${ep.name}: ${e.message}`);
      logger?.(`Token 端点 ${ep.name} 异常: ${e.message}`, 'warn');
    }
  }
  throw new Error('所有 Token 端点均失败 -> ' + errors.join(' | '));
}

function parseAccount(line) {
  const parts = String(line || '').trim().split('----');
  if (parts.length < 4) {
    throw new Error('账户格式错误，应为 email----password----client_id----refresh_token');
  }
  const [rawEmail, password, client_id, refresh_token, ...extraParts] = parts;
  const email = stripExportNamePrefix(rawEmail);
  if (!email || !refresh_token || !client_id) {
    throw new Error('email / refresh_token / client_id 不能为空');
  }
  const extra = parseAccountExtraParts(extraParts);
  return {
    email: email.trim(),
    password,
    refresh_token: refresh_token.trim(),
    client_id: client_id.trim(),
    raw: [email.trim(), password || '', client_id.trim(), refresh_token.trim()].join('----'),
    ...extra,
  };
}

function parseAccountExtraParts(parts) {
  const result = {};
  for (const part of parts || []) {
    const text = String(part || '').trim();
    if (!text) continue;
    const eq = text.indexOf('=');
    if (eq <= 0) continue;
    const key = text.slice(0, eq).trim();
    const value = text.slice(eq + 1).trim();
    if (key === 'rt_token' || key === 'openai_rt') result.openai_rt = value;
    if (key === 'auth_phone') result.auth_phone_number = value;
    if (key === 'auth_phone_sms_url' || key === 'sms_url') result.auth_phone_sms_url = value;
  }
  return result;
}

function parseManagementImportLine(line) {
  const text = String(line || '').trim();
  if (!text) throw new Error('空行');
  const parts = text.split('----').map(part => part.trim());
  const email = stripExportNamePrefix(parts[0]);
  if (!email || !email.includes('@')) throw new Error('缺少有效邮箱');

  if (parts.length >= 4) {
    const account = parseAccount(text);
    return {
      email: account.email,
      password: account.password || '',
      client_id: account.client_id,
      refresh_token: account.refresh_token,
      raw: account.raw,
      openai_rt: account.openai_rt || '',
      auth_phone_number: account.auth_phone_number || '',
      auth_phone_sms_url: account.auth_phone_sms_url || '',
      mode: 'mailbox',
    };
  }

  if (parts.length >= 2) {
    const rtToken = parts[1].replace(/^rt_token=/, '').trim();
    if (!rtToken) throw new Error('rttoken 不能为空');
    return { email, openai_rt: rtToken, mode: 'rt' };
  }

  throw new Error('格式错误，应为 email----rttoken 或 email----password----client_id----refresh_token');
}

function parseUserImportLine(line) {
  const text = String(line || '').trim();
  if (!text) throw new Error('空行');
  const parts = text.split('----').map(part => part.trim());
  const email = stripExportNamePrefix(parts[0]);
  if (!email || !email.includes('@')) throw new Error('缺少有效邮箱');
  return { email };
}

function mergeImportedAccount(existing, imported) {
  const now = nowIso();
  if (existing) {
    existing.email = imported.email || existing.email;
    existing.emailKey = normalizeEmail(existing.email);
    if ('password' in imported) existing.password = imported.password || '';
    if (imported.client_id) existing.client_id = imported.client_id;
    if (imported.refresh_token) existing.refresh_token = imported.refresh_token;
    if (imported.raw) existing.raw = imported.raw;
    if (imported.openai_rt) existing.openai_rt = imported.openai_rt;
    if (imported.auth_phone_number) existing.auth_phone_number = imported.auth_phone_number;
    if (imported.auth_phone_sms_url) existing.auth_phone_sms_url = imported.auth_phone_sms_url;
    existing.status = imported.openai_rt ? '已导入RT' : '已更新邮箱';
    existing.updatedAt = now;
    return existing;
  }
  return normalizeDbAccount({
    email: imported.email,
    password: imported.password || '',
    client_id: imported.client_id || '',
    refresh_token: imported.refresh_token || '',
    raw: imported.raw || '',
    openai_rt: imported.openai_rt || '',
    auth_phone_number: imported.auth_phone_number || '',
    auth_phone_sms_url: imported.auth_phone_sms_url || '',
    status: imported.openai_rt ? '已导入RT' : '邮箱已导入',
    createdAt: now,
    updatedAt: now,
  });
}

function buildOriginalImportLine(account) {
  const extras = [];
  if (account.openai_rt) extras.push(`rt_token=${account.openai_rt}`);
  if (account.auth_phone_number) extras.push(`auth_phone=${account.auth_phone_number}`);
  if (account.auth_phone_sms_url) extras.push(`auth_phone_sms_url=${account.auth_phone_sms_url}`);

  const raw = String(account.raw || '').trim();
  if (raw) return [raw, ...extras].join('----');
  if (account.openai_rt) return [account.email, account.openai_rt].join('----');
  return [account.email, account.password || '', account.client_id || '', account.refresh_token || '', ...extras].join('----');
}

function extractPhoneCode(text) {
  const normalized = String(text || '').replace(/\s+/g, ' ');
  const patterns = [
    /OpenAI[^\d]{0,80}(\d{6})/i,
    /验证代码[^\d]{0,20}(\d{6})/,
    /验证码[^\d]{0,20}(\d{6})/,
    /\b(\d{6})\b/,
  ];
  for (const pattern of patterns) {
    const match = normalized.match(pattern);
    if (match?.[1]) return match[1];
  }
  return '';
}

async function fetchSmsPayload(smsUrl) {
  const url = String(smsUrl || '').trim();
  if (!/^https?:\/\//i.test(url)) throw new Error('该邮箱没有有效短信链接');
  const response = await fetch(url, { cache: 'no-store' });
  const text = await response.text();
  const code = extractPhoneCode(text);
  return {
    ok: response.ok,
    status: response.status,
    code,
    preview: text.slice(0, 1200),
  };
}

async function waitForPhoneCode(account, logger, timeoutMs = PHONE_OTP_WAIT_TIMEOUT_MS) {
  const smsUrl = String(account?.auth_phone_sms_url || '').trim();
  if (!smsUrl) throw new Error('该邮箱没有保存授权手机号短信链接');
  const phoneNumber = String(account?.auth_phone_number || '').trim();
  const started = Date.now();
  let lastPreview = '';
  while (Date.now() - started < timeoutMs) {
    try {
      const payload = await fetchSmsPayload(smsUrl);
      lastPreview = String(payload.preview || '').slice(0, 300);
      if (payload.code) {
        logger?.(`读取到手机号验证码: ${payload.code}${phoneNumber ? ` (${maskPhone(phoneNumber)})` : ''}`);
        if (account.id) {
          await withDatabaseWrite(async () => {
            const latest = findAccountById(account.id);
            if (!latest) return;
            latest.last_sms_code = payload.code;
            latest.last_sms_at = nowIso();
            latest.updatedAt = nowIso();
          });
        }
        return payload.code;
      }
      logger?.(`手机号短信暂未识别到验证码: HTTP ${payload.status}`, 'warn');
    } catch (error) {
      lastPreview = error instanceof Error ? error.message : String(error);
      logger?.(`读取手机号短信失败: ${lastPreview}`, 'warn');
    }
    await sleep(PHONE_OTP_POLL_INTERVAL_MS);
  }
  throw new Error(`手机短信验证码获取超时，导出失败${phoneNumber ? ` (${maskPhone(phoneNumber)})` : ''}，最后返回: ${lastPreview}`);
}

async function refreshOpenAIRecordFromRt(account, logger) {
  const rt = String(account?.openai_rt || '').trim();
  if (!rt) throw new Error('该邮箱尚未导入 OpenAI rttoken');
  let lastError = '';
  for (const tokenURL of AUTH_OAUTH_TOKEN_URLS) {
    const response = await fetch(tokenURL, {
      method: 'POST',
      headers: buildBrowserHeaders({
        accept: 'application/json',
        'content-type': 'application/x-www-form-urlencoded',
      }),
      body: new URLSearchParams({
        grant_type: 'refresh_token',
        client_id: DEFAULT_CLIENT_ID,
        refresh_token: rt,
      }),
    });
    const text = await response.text();
    let payload;
    try { payload = JSON.parse(text); } catch { payload = {}; }
    if (response.ok && payload.access_token) {
      logger?.(`OpenAI RT 刷新成功: ${tokenURL}`);
      return normalizeOpenAIRecordFromRefreshPayload(account.email, payload, rt);
    }
    lastError = `endpoint=${tokenURL} HTTP ${response.status} ${text.slice(0, 300)}`;
    logger?.(`OpenAI RT 刷新失败: ${lastError}`, 'warn');
  }
  throw new Error(`OpenAI RT 刷新 access_token 失败: ${lastError}`);
}

async function resolveOpenAIRecordForExport(account, logs) {
  const logger = (msg, level = 'info') => logs.push({ time: nowIso(), level, msg });
  try {
    return await refreshOpenAIRecordFromRt(account, logger);
  } catch (error) {
    const refreshError = error instanceof Error ? error.message : String(error);
    logger(`OpenAI RT 刷新失败，尝试通过邮箱验证码重新登录获取 RT: ${refreshError}`, 'warn');

    let mailboxAccount;
    try {
      mailboxAccount = requireMailboxAccount(account);
    } catch (mailboxError) {
      const message = mailboxError instanceof Error ? mailboxError.message : String(mailboxError);
      throw new Error(`${refreshError}；无法重新登录获取 RT: ${message}`);
    }

    const sse = {
      send(event, data) {
        if (event !== 'log') return;
        logs.push({
          time: data?.time || nowIso(),
          level: data?.level || 'info',
          msg: data?.msg || data?.error || '',
        });
      },
    };

    try {
      const record = await new OpenAIJsonAuthFlow(mailboxAccount, sse).run();
      logger('重新登录获取 OpenAI RT 成功');
      return record;
    } catch (loginError) {
      const message = loginError instanceof Error ? loginError.message : String(loginError);
      throw new Error(`${refreshError}；重新登录获取 RT 失败: ${message}`);
    }
  }
}

function normalizeOpenAIRecordFromRefreshPayload(email, payload, fallbackRt) {
  const accessToken = String(payload.access_token || '');
  if (!accessToken) throw new Error('刷新 RT 后缺少 access_token');
  const accessClaims = decodeJwtPayload(accessToken);
  const accessAuth = getNestedRecord(accessClaims, 'https://api.openai.com/auth');
  const accountId = firstNonEmpty(accessAuth.chatgpt_account_id, accessAuth.account_id);
  const exp = Number(accessClaims.exp || 0);
  const refreshToken = String(payload.refresh_token || fallbackRt || '');
  if (!accountId) throw new Error(`access_token 中缺少 account_id: ${JSON.stringify(accessClaims)}`);
  return {
    access_token: accessToken,
    account_id: accountId,
    email,
    expired: exp ? new Date(exp * 1000).toISOString() : '',
    id_token: String(payload.id_token || ''),
    last_refresh: nowIso(),
    plan_type: firstNonEmpty(accessAuth.chatgpt_plan_type),
    refresh_token: refreshToken,
    type: 'codex',
  };
}

// ------------------------- 验证码提取 -------------------------
const CODE_PATTERNS = [
  /(?:verification|security|access|one[- ]?time|login|sign[- ]?in|confirm|verify|otp|code)[^\d]{0,40}(\d{4,8})/i,
  /(?:验证码|校验码|动态码|登录码)[^\d]{0,20}(\d{4,8})/,
  /\b(\d{6})\b/,
  /\b(\d{4,8})\b/,
];

function extractCode(text) {
  if (!text) return null;
  const t = String(text).replace(/\s+/g, ' ');
  for (const re of CODE_PATTERNS) {
    const m = t.match(re);
    if (m && m[1]) return m[1];
  }
  return null;
}

// ------------------------- IMAP 会话管理 -------------------------
class MailSession {
  constructor(account, sse) {
    this.account = account;
    this.sse = sse;
    this.client = null;
    this.stopped = false;
    this.seenMailKeys = new Set();
  }

  log(msg, level = 'info') {
    this.sse.send('log', { time: new Date().toISOString(), level, msg });
  }

  async connect() {
    const accessToken = await refreshAccessToken(
      this.account.refresh_token,
      this.account.client_id,
      (msg, level = 'info') => this.log(msg, level),
    );
    this.log('已获取 access_token，准备登录 IMAP...');

    this.client = new ImapFlow({
      host: 'outlook.office365.com',
      port: 993,
      secure: true,
      auth: {
        user: this.account.email,
        accessToken,
      },
      logger: false,
    });

    this.client.on('error', (err) => {
      this.log('IMAP 错误: ' + err.message, 'error');
    });

    await this.client.connect();
    this.log(`已连接 ${this.account.email}`);
    this.sse.send('status', { connected: true, email: this.account.email });
  }

  async fetchRecent(folder = 'INBOX', limit = 15) {
    const lock = await this.client.getMailboxLock(folder);
    try {
      const status = this.client.mailbox;
      if (!status || !status.exists) return;
      const start = Math.max(1, status.exists - limit + 1);
      const range = `${start}:*`;
      for await (const msg of this.client.fetch(range, { uid: true, envelope: true, source: true, flags: true })) {
        const mailKey = `${folder}:${msg.uid}`;
        if (this.seenMailKeys.has(mailKey)) continue;
        this.seenMailKeys.add(mailKey);
        let parsed;
        try { parsed = await simpleParser(msg.source); } catch { parsed = {}; }
        const subject = (msg.envelope && msg.envelope.subject) || parsed.subject || '';
        const from = (msg.envelope && msg.envelope.from && msg.envelope.from[0])
          ? `${msg.envelope.from[0].name || ''} <${msg.envelope.from[0].address || ''}>`
          : (parsed.from && parsed.from.text) || '';
        const date = (msg.envelope && msg.envelope.date) || parsed.date || new Date();
        const text = parsed.text || (parsed.html ? String(parsed.html).replace(/<[^>]+>/g, ' ') : '');
        const code = extractCode(subject + ' \n ' + text);

        const item = {
          id: mailKey,
          uid: msg.uid,
          folder,
          from,
          subject,
          date,
          preview: text.slice(0, 500),
          body: text,
          code,
        };
        this.sse.send('mail', item);
        if (code) {
          this.sse.send('code', { code, subject, from, date });
        }
      }
    } finally {
      lock.release();
    }
  }

  async run() {
    try {
      await this.connect();
      // 首次拉取常用文件夹
      const folders = ['INBOX', 'Junk', 'Junk Email'];
      while (!this.stopped) {
        for (const f of folders) {
          if (this.stopped) break;
          try {
            const exists = await this.client.mailboxOpen(f).then(() => true).catch(() => false);
            if (exists) {
              await this.fetchRecent(f, 15);
            }
          } catch (e) {
            this.log(`拉取 ${f} 失败: ${e.message}`, 'warn');
          }
        }
        // 简易轮询：每 5s
        await new Promise(r => setTimeout(r, 5000));
      }
    } catch (e) {
      this.log('会话异常: ' + e.message, 'error');
      this.sse.send('status', { connected: false, error: e.message });
    } finally {
      try { await this.client?.logout(); } catch {}
    }
  }

  stop() {
    this.stopped = true;
    try { this.client?.close(); } catch {}
  }
}

// ------------------------- SSE 通道 -------------------------
class SSEChannel {
  constructor(res) {
    this.res = res;
    this.alive = true;
    res.on('close', () => { this.alive = false; });
  }
  send(event, data) {
    if (!this.alive) return;
    try {
      this.res.write(`event: ${event}\n`);
      this.res.write(`data: ${JSON.stringify(data)}\n\n`);
    } catch {}
  }
}

// ------------------------- 管理 API -------------------------
app.get('/api/accounts', requireAdmin, async (_req, res) => {
  try {
    await ensureDatabase();
    const accounts = [...dbState.accounts]
      .sort((a, b) => String(b.updatedAt || '').localeCompare(String(a.updatedAt || '')))
      .map(publicAccountView);
    res.json({ ok: true, accounts, updatedAt: dbState.updatedAt });
  } catch (error) {
    res.status(500).json({ ok: false, error: error instanceof Error ? error.message : String(error) });
  }
});

app.get('/api/admin/session', requireAdmin, (_req, res) => {
  res.json({ ok: true, protected: Boolean(ADMIN_KEY) });
});

app.post('/api/admin/login', (req, res) => {
  if (!ADMIN_KEY) {
    res.status(503).json({ ok: false, error: '服务端未配置 ADMIN_KEY，管理员功能已禁用' });
    return;
  }
  const key = String(req.body?.adminKey || '').trim();
  if (key !== ADMIN_KEY) {
    res.status(401).json({ ok: false, error: '管理员密钥错误' });
    return;
  }
  setAdminCookie(res);
  res.json({ ok: true });
});

app.post('/api/admin/logout', (_req, res) => {
  clearAdminCookie(res);
  res.json({ ok: true });
});

app.get('/api/accounts/export-original', requireAdmin, async (_req, res) => {
  try {
    await ensureDatabase();
    const lines = [...dbState.accounts]
      .sort((a, b) => String(b.createdAt || b.updatedAt || '').localeCompare(String(a.createdAt || a.updatedAt || '')))
      .map(buildOriginalImportLine)
      .filter(Boolean);
    const text = `${lines.join('\n')}${lines.length ? '\n' : ''}`;
    const fileName = `accounts-original-${new Date().toISOString().slice(0, 10)}.txt`;
    res.set({
      'Content-Type': 'text/plain; charset=utf-8',
      'Content-Disposition': `attachment; filename="${fileName}"`,
      'Cache-Control': 'no-store',
    });
    res.send(text);
  } catch (error) {
    res.status(500).json({ ok: false, error: error instanceof Error ? error.message : String(error) });
  }
});

app.post('/api/accounts/import', requireAdmin, async (req, res) => {
  const text = String(req.body?.text || req.body?.accounts || '').trim();
  if (!text) {
    res.status(400).json({ ok: false, error: '请粘贴要导入的账号，每行一个' });
    return;
  }

  try {
    const result = await withDatabaseWrite(async () => {
      const lines = text.split(/\r?\n/).map(line => line.trim()).filter(Boolean);
      const rows = [];
      const errors = [];
      let created = 0;
      let updated = 0;
      let matched = 0;
      for (const [index, line] of lines.entries()) {
        try {
          const imported = parseManagementImportLine(line);
          const existing = findAccountByEmail(imported.email);
          if (existing) matched += 1;
          const merged = mergeImportedAccount(existing, imported);
          if (existing) {
            updated += 1;
          } else {
            dbState.accounts.push(merged);
            created += 1;
          }
          rows.push({ line: index + 1, email: merged.email, existed: Boolean(existing), mode: imported.mode, id: merged.id });
        } catch (error) {
          errors.push({ line: index + 1, error: error instanceof Error ? error.message : String(error) });
        }
      }
      if (!rows.length) throw new Error(errors.map(item => `第 ${item.line} 行: ${item.error}`).join('；') || '没有可导入账号');
      return {
        rows,
        errors,
        summary: { total: lines.length, imported: rows.length, matched, created, updated, failed: errors.length },
        accounts: dbState.accounts.map(publicAccountView),
      };
    });
    res.json({ ok: true, ...result });
  } catch (error) {
    res.status(400).json({ ok: false, error: error instanceof Error ? error.message : String(error) });
  }
});

app.delete('/api/accounts/:id', requireAdmin, async (req, res) => {
  try {
    const deleted = await withDatabaseWrite(async () => {
      const index = dbState.accounts.findIndex(account => account.id === String(req.params.id || '').trim());
      if (index < 0) throw new Error('账号不存在');
      const [account] = dbState.accounts.splice(index, 1);
      return publicAccountView(account);
    });
    res.json({ ok: true, deleted });
  } catch (error) {
    res.status(404).json({ ok: false, error: error instanceof Error ? error.message : String(error) });
  }
});

app.post('/api/user/import', async (req, res) => {
  const text = String(req.body?.text || '').trim();
  if (!text) {
    res.status(400).json({ ok: false, error: '请粘贴购买账号，每行一个 email----rttoken' });
    return;
  }

  try {
    await ensureDatabase();
    const lines = text.split(/\r?\n/).map(line => line.trim()).filter(Boolean);
    const rows = [];
    const errors = [];
    for (const [index, line] of lines.entries()) {
      try {
        const imported = parseUserImportLine(line);
        const account = findAccountByEmail(imported.email);
        if (!account) {
          rows.push({ line: index + 1, email: imported.email, matched: false, reason: '验证未通过' });
          continue;
        }
        rows.push({
          line: index + 1,
          email: imported.email,
          matched: true,
          account: userAccountView(account, makeActionToken(account.id)),
        });
      } catch (error) {
        errors.push({ line: index + 1, error: error instanceof Error ? error.message : String(error) });
      }
    }
    res.json({
      ok: true,
      rows,
      errors,
      summary: {
        total: lines.length,
        matched: rows.filter(row => row.matched).length,
        unmatched: rows.filter(row => !row.matched).length,
        failed: errors.length,
      },
    });
  } catch (error) {
    res.status(400).json({ ok: false, error: error instanceof Error ? error.message : String(error) });
  }
});

app.post('/api/accounts/:id/mail', requireUserAction, async (req, res) => {
  try {
    await ensureDatabase();
    const stored = findAccountById(req.params.id);
    if (!stored) throw new Error('邮箱不存在');
    const account = requireMailboxAccount(stored);

    res.set({
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
      'X-Accel-Buffering': 'no',
    });
    res.flushHeaders?.();

    const sse = new SSEChannel(res);
    sse.send('log', { msg: '连接已建立，正在启动单次邮件拉取...' });
    const session = new MailSession(account, sse);
    const hb = setInterval(() => {
      try { res.write(': ping\n\n'); } catch {}
    }, 15000);

    res.on('close', () => {
      clearInterval(hb);
      session.stop();
    });

    session.run();
  } catch (error) {
    if (!res.headersSent) {
      res.status(400).json({ ok: false, error: error instanceof Error ? error.message : String(error) });
    }
  }
});

app.post('/api/accounts/:id/sms', requireUserAction, async (req, res) => {
  try {
    let payload;
    const updated = await withDatabaseWrite(async () => {
      const account = findAccountById(req.params.id);
      if (!account) throw new Error('邮箱不存在');
      const smsUrl = String(req.body?.smsUrl || account.auth_phone_sms_url || '').trim();
      if (!smsUrl) throw new Error('该邮箱没有绑定的授权手机号短信链接');
      payload = await fetchSmsPayload(smsUrl);
      account.auth_phone_sms_url = smsUrl;
      account.last_sms_code = payload.code || account.last_sms_code || '';
      account.last_sms_at = nowIso();
      account.status = payload.code ? '短信已拉取' : '短信无验证码';
      account.updatedAt = nowIso();
      return publicAccountView(account);
    });
    res.json({ ok: true, ...payload, account: updated });
  } catch (error) {
    res.status(400).json({ ok: false, error: error instanceof Error ? error.message : String(error) });
  }
});

app.post('/api/accounts/:id/export-json', requireUserAction, async (req, res) => {
  const exportFormat = normalizeExportFormat(req.body?.format);
  try {
    await ensureDatabase();
    const account = findAccountById(req.params.id);
    if (!account) throw new Error('邮箱不存在');
    if (!account.openai_rt) throw new Error('该邮箱尚未导入 OpenAI rttoken');
    const logs = [];
    const record = await resolveOpenAIRecordForExport(account, logs);
    if (record.refresh_token && record.refresh_token !== account.openai_rt) {
      await withDatabaseWrite(async () => {
        const latest = findAccountById(req.params.id);
        if (!latest) return;
        latest.openai_rt = record.refresh_token;
        latest.status = 'RT已刷新';
        latest.updatedAt = nowIso();
      });
      logs.push({ time: nowIso(), level: 'info', msg: 'OpenAI RT 已同步更新到数据库' });
    }
    const json = buildExportJson(record, exportFormat);
    const fileName = `${new Date().toISOString().slice(0, 10)}-${sanitizeFileSegment(account.email)}.${exportFormat}.json`;
    res.json({ ok: true, email: account.email, format: exportFormat, fileName, json, logs });
  } catch (error) {
    res.status(400).json({ ok: false, error: error instanceof Error ? error.message : String(error) });
  }
});

app.post('/api/accounts/export-sub2api-zip', requireAdmin, async (req, res) => {
  try {
    await ensureDatabase();
    const ids = Array.isArray(req.body?.ids) ? req.body.ids.map(id => String(id || '').trim()).filter(Boolean) : [];
    if (!ids.length) throw new Error('请先选择要导出的账号');

    const selected = ids.map(id => findAccountById(id)).filter(Boolean);
    if (!selected.length) throw new Error('未找到可导出的账号');
    const { zip } = await buildSub2ApiZipForAccounts(selected);
    const fileName = `sub2api-export-${new Date().toISOString().slice(0, 10)}.zip`;
    res.set({
      'Content-Type': 'application/zip',
      'Content-Disposition': `attachment; filename="${fileName}"`,
      'Cache-Control': 'no-store',
    });
    res.send(zip);
  } catch (error) {
    res.status(400).json({ ok: false, error: error instanceof Error ? error.message : String(error) });
  }
});

app.post('/api/user/export-sub2api-zip', async (req, res) => {
  try {
    await ensureDatabase();
    const items = Array.isArray(req.body?.accounts) ? req.body.accounts : [];
    if (!items.length) throw new Error('请先选择要导出的账号');

    const selected = [];
    for (const item of items) {
      const id = String(item?.id || '').trim();
      const token = String(item?.actionToken || '').trim();
      if (!id || !verifyActionToken(id, token)) continue;
      const account = findAccountById(id);
      if (account) selected.push(account);
    }
    if (!selected.length) throw new Error('没有通过校验的可导出账号，请重新导入校验');

    const { zip } = await buildSub2ApiZipForAccounts(selected);
    const fileName = `sub2api-export-${new Date().toISOString().slice(0, 10)}.zip`;
    res.set({
      'Content-Type': 'application/zip',
      'Content-Disposition': `attachment; filename="${fileName}"`,
      'Cache-Control': 'no-store',
    });
    res.send(zip);
  } catch (error) {
    res.status(400).json({ ok: false, error: error instanceof Error ? error.message : String(error) });
  }
});

app.post('/api/stream', async (req, res) => {
  let account;
  try {
    account = parseAccount(req.body?.account);
  } catch (e) {
    res.status(400).json({ ok: false, error: e.message });
    return;
  }

  res.set({
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive',
    'X-Accel-Buffering': 'no',
  });
  res.flushHeaders?.();

  const sse = new SSEChannel(res);
  sse.send('log', { msg: '连接已建立，正在启动接码会话...' });

  const session = new MailSession(account, sse);

  // 心跳
  const hb = setInterval(() => {
    try { res.write(': ping\n\n'); } catch {}
  }, 15000);

  res.on('close', () => {
    clearInterval(hb);
    session.stop();
  });

  session.run();
});

app.post('/api/openai-json', async (req, res) => {
  let account;
  const exportFormat = normalizeExportFormat(req.body?.format);
  try {
    account = parseAccount(req.body?.account);
  } catch (e) {
    res.status(400).json({ ok: false, error: e.message });
    return;
  }

  res.set({
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive',
    'X-Accel-Buffering': 'no',
  });
  res.flushHeaders?.();

  const sse = new SSEChannel(res);
  const hb = setInterval(() => {
    try { res.write(': ping\n\n'); } catch {}
  }, 15000);
  res.on('close', () => clearInterval(hb));

  try {
    const flow = new OpenAIJsonAuthFlow(account, sse);
    const record = await flow.run();
    const json = buildExportJson(record, exportFormat);
    const fileName = `${new Date().toISOString().slice(0, 10)}-${sanitizeFileSegment(account.email)}.${exportFormat}.json`;
    sse.send('result', {
      ok: true,
      email: account.email,
      format: exportFormat,
      fileName,
      json,
    });
    sse.send('log', { time: new Date().toISOString(), level: 'info', msg: `${exportFormat} JSON 已生成，可点击下载` });
  } catch (error) {
    sse.send('error', { ok: false, error: error instanceof Error ? error.message : String(error) });
  } finally {
    clearInterval(hb);
    try { res.end(); } catch {}
  }
});

app.listen(PORT, () => {
  console.log(`Hotmail 接码服务已启动: http://localhost:${PORT}`);
});
