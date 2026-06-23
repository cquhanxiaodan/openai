# Hotmail / Outlook 邮箱授权管理台

项目现在分为两个入口：

- 用户端 `/`：用户导入自己购买到的邮箱，本地保存，不共享给其他用户。
- 管理员端 `/admin.html`：管理员上传账号库，后台持久化保存，用来按邮箱校验用户账号是不是从这里购买的。

## 支持导入格式

```text
email----rttoken
email----password----client_id----refresh_token
email----password----client_id----refresh_token----rt_token=rt_xxx----auth_phone=+1xxx----auth_phone_sms_url=https://...
```

- `email----rttoken`：用于把已授权导出的 OpenAI RT 导入到管理台。
- 完整邮箱格式：用于 Outlook IMAP 拉邮件。
- 带 `rt_token/auth_phone/auth_phone_sms_url` 的完整导出行会同时更新 RT 和绑定手机号短信链接。
- 后台按邮箱查重；库里已有就更新，没有就新增。

## 启动

```bash
npm install
set ADMIN_KEY=你的管理员密钥
npm start
```

打开 http://localhost:3000

默认数据库文件：`data/accounts-db.json`。

## Docker 一键部署

```bash
docker compose up -d --build
```

访问：

```text
http://服务器IP:3000
```

`docker-compose.yml` 已挂载 `./data:/app/data`，重建容器后账号数据库仍会保留。

常用命令：

```bash
docker compose logs -f
docker compose restart
docker compose down
```

## 用户端使用

1. 打开 `http://localhost:3000/`。
2. 粘贴购买到的邮箱；支持直接粘贴 `email`，也兼容 `email----rttoken` 或完整导出行。
3. 点击 `校验并保存到本地`。
4. 后台只用邮箱名对比管理员账号库；命中后才显示可用功能。
5. 匹配成功后，用户可自助 `拉取邮件`、`拉取短信`、`导出 JSON`。
6. 用户端账号只保存在当前浏览器 `localStorage`，不同用户、不同浏览器不会共享。

## 管理员端使用

1. 打开 `http://localhost:3000/admin.html`。
2. 在左侧批量粘贴账号或授权导出行。
3. 点击 `导入到数据库`，后台会按邮箱查重并显示命中/新增/更新统计。
4. 管理员能看到账号库全量列表，普通用户看不到。
5. 管理员功能必须配置 `ADMIN_KEY`；未登录时服务端不会返回管理页面和账号库数据。
6. 可以打开 `http://localhost:3000/admin.html` 输入密钥登录，或使用 `http://localhost:3000/admin.html?admin_key=你的密钥` 设置管理员会话。

## API

- `GET /api/accounts`：读取数据库邮箱列表。
- `POST /api/accounts/import`：批量导入，body: `{ "text": "..." }`。
- `DELETE /api/accounts/:id`：管理员删除账号库里的单个邮箱。
- `POST /api/user/import`：用户导入购买账号并按邮箱校验，body: `{ "text": "email" }`。
- `POST /api/accounts/:id/mail`：按数据库账号 ID 拉取邮件，SSE 返回日志和邮件内容。
- `POST /api/accounts/:id/sms`：读取账号绑定的短信链接。
- `POST /api/accounts/:id/export-json`：用已导入 RT 刷新 access token 并导出 JSON。

旧接口仍保留：

- `POST /api/stream`
- `POST /api/openai-json`

## 环境变量

```bash
PORT=3000
DATA_DIR=./data
ACCOUNTS_DB_FILE=./data/accounts-db.json
ADMIN_KEY=必填管理员密钥
ACTION_TOKEN_SECRET=可选用户操作令牌签名密钥
USER_HERO_EYEBROW=Self Service
USER_HERO_TITLE=账号自助取码
USER_HERO_SUBTITLE=把你购买到的邮箱粘贴到这里，数据只保存在当前浏览器本地。
SUB2API_CONCURRENCY=10
SUB2API_PRIORITY=1
```

用户端顶部文案可通过 `USER_HERO_EYEBROW`、`USER_HERO_TITLE`、`USER_HERO_SUBTITLE` 配置，修改 `.env` 后重启服务生效。

## 隐私说明

- 账号、邮箱 `refresh_token`、OpenAI `rt_token` 会保存到服务端数据库文件 `data/accounts-db.json`。
- 该文件是敏感数据，不要提交、转发或放到公开服务器目录。
- 管理员接口必须设置 `ADMIN_KEY`，否则管理员功能不可用。
- 用户导入的数据只保存在用户自己的浏览器本地，不会写入管理员数据库。
- 用户端不会读取管理员账号库列表，只能提交自己的邮箱做匹配校验。
- 邮件正文和短信内容只在对应请求期间返回给浏览器，默认不落盘保存。
