// ChatGPT Session Helper - Background Service Worker

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'createPayUrl') {
    handleCreatePayUrl(request.accessToken)
      .then(result => sendResponse(result))
      .catch(error => sendResponse({ error: error.message }));
    return true;
  }
  if (request.action === 'fetchSmsLink') {
    handleFetchSmsLink(request.url)
      .then(result => sendResponse(result))
      .catch(error => sendResponse({ ok: false, error: error.message }));
    return true;
  }
});

async function handleFetchSmsLink(url) {
  const smsUrl = String(url || '').trim();
  if (!/^https?:\/\//i.test(smsUrl)) throw new Error('取码链接格式错误');
  const resp = await fetch(smsUrl, { cache: 'no-store' });
  const text = await resp.text();
  if (!resp.ok) throw new Error(`取码链接请求失败: HTTP ${resp.status}`);
  return { ok: true, text };
}

async function handleCreatePayUrl(accessToken) {
  const CHECKOUT_ENDPOINT = 'https://chatgpt.com/backend-api/payments/checkout';

  const payload = {
    plan_name: 'chatgptplusplan',
    billing_details: {
      country: 'DE',
      currency: 'EUR',
    },
    cancel_url: 'https://chatgpt.com/#pricing',
    promo_campaign: {
      promo_campaign_id: 'plus-1-month-free',
      is_coupon_from_query_param: false,
    },
    checkout_ui_mode: 'hosted',
  };

  const resp = await fetch(CHECKOUT_ENDPOINT, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${accessToken}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  const data = await resp.json().catch(() => ({}));
  const checkoutUrl = data.url || data.checkout_url || data.redirect_url;

  if (!resp.ok || !checkoutUrl) {
    console.error('[Background Error] checkout creation failed', { status: resp.status, data });
    throw new Error(`生成支付链接失败: HTTP ${resp.status}`);
  }

  await chrome.tabs.create({ url: checkoutUrl });
  return { success: true, payUrl: checkoutUrl };
}
