# staging-monitor #1028 测试修复

构建：[Jenkins #1028](http://100.105.114.178:8080/job/staging-monitor/1028/)。
被测版本：`da5eb543bf17aa0c772eebbf0961e4dc2daac0e8`。
2026-09-11 通过 `/health` 确认复测环境版本一致。源码取自 Jenkins 对应提交；UI 选择器通过有头 Playwright 的实际 DOM 快照核对。

## 修复内容

| 问题 | 修复 |
|---|---|
| 创建智能体未出现在列表 | 新表单要求选择模型；用例补上模型选择，并严格等待创建弹窗关闭，不再忽略提交未成功 |
| 9 条智能体配置操作报 `NoneType.locator` | 弹窗记住上次标签页；读取名称验证目标 Agent 前先切回「身份与指令」 |
| 4 条组织成员操作失败 | 搜索结果实际是包含姓名的按钮；改为等待匹配候选并点击，不再依赖不存在的 `role=option` 或 Enter 选择 |
| 后续用例重复处理浏览器弹窗 | 特殊字符及 XSS 用例使用具名监听函数，并在 `finally` 移除，防止共享页面事件残留 |
| ACP 缺少 `max_sessions` | 与当前服务 schema 对齐：字段已移除；继续严格校验 ID、名称、状态和时间戳 |
| 实例 API 契约不一致 | 校验 `instanceUid/environmentId/name/status/createdAt`；跨组织活动查询严格断言 403；不存在实例的删除严格断言 404/NOT_FOUND；清理使用持久实例 UID |
| 3 条沙箱错误映射单元测试失败 | 校验当前公开错误文案，同时保留状态码及错误码断言 |
| ACP 超时恢复单元测试随机失败 | 显式注入首次连接超时，避免用 1ms 墙钟预算测试恢复分支，继续断言只重启、不重建 |
| 2 条 ProdView 单元测试失败 | 去掉与必填 agentId 契约矛盾的空值成功场景；验证输入约束、环境创建及持久实例返回；修正 mock 导出并清理注入依赖 |
| 知识资源启停仅显示笼统 400 | 保留失败，显示服务返回的原始错误正文；成功时严格验证 enabled，仅在切换成功后恢复状态 |

退出登录与技能公开切换在复测中通过，未添加重试或忽略网络错误以使其通过。工作流版本测试在修复事件监听残留后通过；原构建的超时仍可能受到其他时序因素影响。

## 未解决的环境故障

知识资源启停仍返回：

```json
{"success":false,"error":{"code":"TOGGLE_FAILED","message":"getaddrinfo ETIMEOUT ragflow"}}
```

创建临时知识库也返回 HTTP 502 / `KNOWLEDGE_PROVIDER_ERROR`，错误同为 `getaddrinfo ETIMEOUT ragflow`。
应用无法解析 RAGFlow 服务名。需要检查被测应用所在服务器的容器网络、RAGFlow 服务及其地址配置；本次没有更改应用部署配置，也没有用 skip 或放宽断言掩盖故障。

## 验证记录

- 对应版本的完整 Bun 单元测试在独立容器执行：**3421 通过，0 失败**（194 个文件）。
- ACP 和实例 API：11 条用例均已在修复后通过。
- UI 使用有头 Chromium 复测：按每条用例的最后一次结果汇总，**19 条通过**，包括原构建涉及的 17 条 UI 用例及 2 条事件监听相关聊天用例。最后一批配置回归为 13/13 通过。
- 知识资源启停复测：确认上述 DNS 故障，保留失败。

单元测试日志：`_temp/staging1028/units-second.log`。
API 日志：`_temp/staging1028/api.log`、`api-final.log`。
UI 日志：`_temp/staging1028/ui-first.log`、`ui-second.log`、`ui-events.log`。

以上为独立验证结果，不代表新的 Jenkins staging 全量构建结果。
