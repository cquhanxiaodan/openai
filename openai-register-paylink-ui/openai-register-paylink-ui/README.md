# OpenAI 注册 + 支付长链接 UI

独立 Python/Tkinter 工具：导入 Hotmail/Outlook OAuth 邮箱，自动走 OpenAI 邮箱验证码注册，注册成功后提取 ChatGPT Plus 支付长链接，并在 UI 上复制。

## 邮箱格式

```text
email----password----client_id----refresh_token
```

`password` 仅保留原格式，不参与 OpenAI 注册。邮箱收码使用 `client_id + refresh_token` 登录 Outlook IMAP。

## 安装

```bash
cd D:\project\aipro\openai-register-paylink-ui
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium
```

## 启动

```bash
python app.py
```

## 使用

1. 粘贴或从文件导入邮箱。
2. 选择支付模式，默认是 `无卡长链接 US/USD`，对应 go-paypal 的无卡模式。
3. 按需填写代理设置；打开支付链接可单独填写 `支付链接动态代理`。
4. 选中邮箱，点击 `注册选中邮箱并提取长链接`。
5. 如果浏览器出现人机验证，请手动完成，脚本会继续检测后续流程。
6. 成功后在右侧复制长链接，或点击 `浏览器打开` 用临时 Chromium 窗口打开。
7. 邮箱废掉时，选中左侧邮箱后点击 `删除选中邮箱`。
8. 如果支付窗口需要扩展，填写 `支付链接扩展目录`，该目录必须是解压后的 Chrome 扩展目录并包含 `manifest.json`。
9. Plus 邮箱可选中后点击 `设为 Plus`，再点击 `Plus授权获取RT`。遇到 add-phone 时会弹窗输入手机号和短信验证码。
10. 授权成功后状态会标记为 `已绑定手机号`，点击 `导出已授权` 导出 `email----password----client_id----refresh_token----rt_token=xxxxx`。
11. 可在 `手机号池` 批量导入 `+手机号https://短信链接`，授权遇到 add-phone 时会自动发送短信、轮询链接提取验证码并提交；手机号失败后自动标记不可用并切换下一个。
12. PayPal 支付扩展默认加载 `D:\downloads\googledownloads\palpay扩展\palpay`。在 `PayPal 扩展资料` 填写 PP 手机号和卡信息后，打开支付链接会自动写入扩展面板；这里的 PP 手机号和授权接码手机号池互不相关。

## 代理

脚本不会假设所有库都会自动使用系统“全局代理”，因此 UI 里做了显式代理配置。

代理链路：

```text
脚本/浏览器/IMAP -> 本地代理 -> 动态代理 -> 目标站点
```

本地代理示例：

```text
http://127.0.0.1:7890
```

动态代理池每行一个，格式：

```text
username:password@hostname:port
```

也可以带 scheme：

```text
http://username:password@hostname:port
```

说明：

- 每个注册流程会轮询取一个动态代理。
- `支付链接动态代理` 只用于打开右侧长链接，和注册用的动态代理池分开。
- 支付链接窗口如果配置了扩展目录，会用临时浏览器资料启动以支持扩展；窗口关闭后会清理临时资料。
- 本地代理留空时，会直接走动态代理。
- 动态代理留空时，只走本地代理。
- 两者都留空时直连。
- 链式代理当前使用 HTTP CONNECT；如果你的本地代理是 SOCKS，请先在本地代理软件里开放 HTTP 端口。
- 浏览器和邮箱 token 刷新会显式走链式代理。
- Outlook IMAP 收码默认直连，避免部分 HTTP 代理不支持 `outlook.office365.com:993` CONNECT 导致 502。

## 说明

- 只做注册和支付长链接提取，不保存 OpenAI RT 或 sub2api JSON。
- 邮箱列表、代理配置、成功生成的长链接会保存到项目目录的 `state.json`，重启后自动恢复。
- `state.json` 包含邮箱 `refresh_token` 和代理信息，属于敏感文件，不要发给别人。
- 如果 OpenAI 要求手机验证或密码步骤，当前任务会停止并在日志提示。
- 长链接提取逻辑参考 `go-paypal` 的 `content-chatgpt.js`：调用 `chatgpt.com/backend-api/payments/checkout`。
