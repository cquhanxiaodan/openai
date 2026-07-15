# 用户指令记忆

本文件记录了用户的指令、偏好和教导，用于在未来的交互中提供参考。

## 条目

### K12 指纹尺寸覆盖
- Date: 2026-07-04
- Context: K12 空间多 session 提取时，随机指纹生成的视口可能太大（超出观看区域）或太小（底部被截断看不到头像）
- Instructions:
  - 在 `OpenAIRegisterPayLinkWorker.run()` 开头，K12 启用时用 `dataclasses.replace()` 将 `self.fingerprint` 的 viewport/screen 固定为 1400x800，outer 固定为 1420x870
  - 不能用直接属性赋值（可能不生效），必须用 `dataclasses.replace()` 创建新实例
  - 不修改 `_new_browser_context` 和 `_install_fingerprint`，只改指纹实例本身

### K12 多空间页面加载增强
- Date: 2026-07-04
- Context: 多空间模式下手动弹窗前导航到 chatgpt.com，ChatGPT 是 React SPA，需要足够时间等 hydration 完成
- Instructions:
  - `register_page.goto("chatgpt.com")` 后用 `wait_for_selector` 等待侧边栏元素出现（timeout 15000ms），再等 3000ms 稳定
  - `wait_for_selector` 超时则 fallback 等 8000ms
  - 按 Escape 消除引导弹窗
  - 尝试点击侧边栏展开按钮（`button[aria-label="Open sidebar"]` 等选择器）
  - JS 将侧边栏 nav/aside 的 scrollTop 设为 scrollHeight，确保头像在可视区域
