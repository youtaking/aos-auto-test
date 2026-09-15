# 应用缺陷：未匹配路由返回空响应（部分为 200 空 body）

| 项 | 值 |
|---|---|
| 环境 | staging `http://100.105.9.16:38879` |
| 部署版本 | `da5eb543bf17aa0c772eebbf0961e4dc2daac0e8`（`/health` 返回的 `commitId` 与 Jenkins [staging-monitor #1099](http://100.105.114.178:8080/job/staging-monitor/1099/) 一致） |
| 发现时间 | 2026-09-14 |
| 发现来源 | #1099 接口用例失败：3 条 control API 用例报 `RuntimeError: Web API error: UNKNOWN - | Full response: {}` |
| 严重程度 | 中——不影响已注册接口的功能，但会吞掉所有"接口不存在 / 方法不对"的错误信息 |

## 现象

未注册路径（或已注册路径的方法不匹配）返回**空 body**，其中一部分状态码还是 **200**：

| 请求 | 实际返回 | 期望 |
|---|---|---|
| `GET /__nope__` | **200**，空 body，无 `Content-Type` | 404 + JSON 错误体 |
| `GET /web/__nope__` | **200**，空 body | 404 + JSON 错误体 |
| `POST /web/__nope__` | **200**，空 body | 404 + JSON 错误体 |
| `GET /api/__nope__` | **200**，空 body | 404 + JSON 错误体 |
| `GET /api/auth/sign-in/email`（该路由只接受 POST） | 404，空 body | 404 + `{"error":{"type":"NOT_FOUND",...}}` |
| `GET /web/config/providers?name=<id>`（已注册路由，未登录） | 401 + `{"error":{"type":"unauthorized","message":"Not authenticated"}}` | 正常（对照组：错误响应链路本身可用） |
| `GET /web/config/providers`（已注册路由，已登录） | 200 + 正常 JSON | 正常 |

响应头带应用自身的 CORS 头与 `x-request-id`（由 `injectRequestId` 注入），可确认响应由应用产生，不是前置网关改写。

## 复现

无需登录：

```bash
curl -i http://100.105.9.16:38879/__nope__
curl -i http://100.105.9.16:38879/web/__nope__
curl -i -X POST http://100.105.9.16:38879/web/__nope__
curl -i http://100.105.9.16:38879/api/auth/sign-in/email   # 方法不对
curl -i http://100.105.9.16:38879/web/config/providers?name=nonexistent  # 对照组：未登录应为 401 + JSON
```

Python 版本见本文件末尾的探针脚本。

## 影响

1. **错误信息丢失**：客户端无法区分"接口不存在/方法不对"与"成功但无内容"。本次 3 条 control API 用例之所以只报出零信息量的 `Full response: {}`，直接原因就是这里返回了空 body。
2. **静默失败**：状态码 200 + 空 body 会被通用客户端（本项目的 `base_client._parse_response`）当成"无内容的成功响应"，拼错 URL、路由被下线、方法写错这三类问题都不会被立刻发现。
3. **契约不可依赖**：既然路由不存在也返回 200，任何基于状态码做重试/告警的逻辑都会失效。

## 相关代码（`da5eb543`）

- `src/plugins/error-handler.ts:86-97`：NOT_FOUND 分支本应返回 `404` + `{error:{type:"NOT_FOUND", message}}`
- `src/plugins/error-handler.ts:81-83`：非法 UUID 同样返回 `404` + JSON
- `src/plugins/static.ts:64-79`：SPA fallback 的全局 `onError`，其中 `:67` 对非 `/ctrl/*` 路径直接 `return`（不接管），`:79` 命中时把状态码重置为 200 并返回 `index.html`
- `src/index.ts:180,184`：`ctrlStaticPlugin` 注册在 `errorPlugin` 之前（注释说明这是为了让 SPA fallback 先执行）

## 成因方向（待应用侧确认）

实测与 `error-handler.ts` 的意图不一致：NOT_FOUND 既没有返回设计中的 JSON 错误体，部分还变成了 200。可能的方向：

- `ctrlStaticPlugin` 的全局 `onError` 对非 `/ctrl/*` 路径 `return` 后，错误没有继续交给 `errorPlugin` 输出 JSON；
- 或 `@elysiajs/static` 的 `indexHTML` 机制先把 `set.status` 改写成了 200（`static.ts:51-53` 的注释提到了这个行为），导致 200 空 body。

建议应用侧确认 Elysia `onError` 链在"未匹配路由"场景下的实际走向，并让未匹配路由稳定返回 `404` + JSON 错误体。

## 关联发现：下线路由未删干净（同为应用侧）

`src/routes/web/control.ts` 定义了 `POST /web/sessions/:id/events|control|interrupt`（`:108,:140,:172`），但 `src/routes/web/index.ts` 的 `.use(...)` 链里没有 `webControl`——`0ea07115` 移除了 `import webControl` 与 `.use(webControl)`，文件却保留下来成了死代码。

它不是功能缺陷（前端调用方也已在同一次提交中删除，聊天改走 RCS relay），但会误导使用者（本次#1099 的用例就是照着它写的）。建议一并删除该文件。

## 测试侧处理

- 3 条 control API 正向用例（`tests/api_suites/test_control_api.py` 的 `test_send_session_event` / `test_send_session_control` / `test_interrupt_session`）已于 2026-09-15 删除：接口已下线，断言的是废弃契约，不再作为回归对象。
- 同批从平台用例集 `api_all_cases`（id 19）移除对应条目（case id 2017/2018/2019），否则 CI 会继续下发已不存在的 pytest node id，导致收集阶段报错。已确认 `/api/ci/staging-resolve-tests` 由 723 条降为 720 条且不再包含这三条。
- 该文件保留 2 条负向用例（"不存在的会话必须报错"），不依赖正向契约。
- 若本条缺陷修复（未匹配路由返回 404 + JSON），`base_client._parse_response` 将不再把空响应静默解析成 `{}`，客户端侧的报错信息会恢复正常。
## 附录：探针脚本

```python
import httpx

BASE = "http://100.105.9.16:38879"
c = httpx.Client(base_url=BASE, verify=False, timeout=30)

for method, path in [
    ("GET", "/__nope__"),
    ("GET", "/web/__nope__"),
    ("POST", "/web/__nope__"),
    ("GET", "/api/__nope__"),
    ("GET", "/api/auth/sign-in/email"),
    ("GET", "/web/config/providers?name=nonexistent"),
]:
    r = c.request(method, path)
    print(f"{method:5} {r.status_code}  ct={r.headers.get('content-type')!r}  len={len(r.content)}  {path}")
    print(f"      body={r.text[:120]!r}")
```

对照说明：前 5 条应为 404 + JSON，实际为空 body（前 4 条还是 200）；最后 1 条是已注册路由，未登录返回 401 + JSON——说明鉴权失败的响应链路是正常的，只有"路由未匹配"这一条链路丢响应，可用于排除"环境整体不可用"和"错误处理完全失效"两种可能。
