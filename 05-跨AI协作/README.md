# 05 · 跨 AI 协作：把活派给另一套会话/Agent

**适用**：任务能拆成互不依赖的几块，想并行跑；或主线上下文已经装不下细节，想把执行挪出去。

**不适用**：任务需要频繁来回确认；或产物路径高度重叠（会双写）。

---

## 1. 先拿工作区 ID，再建会话

不传 `workspaceId` 时，子会话落在 `C:\Users\<用户>\Documents\Qoder\<日期>\<sessionId>`，**不是**当前项目目录。

```
list_workspaces            → 记下目标 workspace 的 id 和 root
create_chat_session({
  prompt: "<自包含的任务书>",
  workspaceId: "<id>",
  attachments: [{type: "folder", path: "<产物目录>"}],
  callbackMode: "supervise"
})
```

要点：

- **任务书必须自包含**：子会话不继承本会话历史，路径、样板、数据源、验收标准都要写进去。
- **绝对路径写全**，别用“当前目录”这类相对说法。
- `callbackMode: "supervise"` 才会把「完成/需要权限」推到本会话，否则只能轮询。

## 2. 状态怎么读

```
wait_chat_sessions({sessionIds: [...], timeoutMs: 0})   // 立即取快照
read_chat_session({sessionId, turnLimit: 3, maxOutputCharsPerItem: 1200})
```

| 字段 | 含义 |
|---|---|
| `runtimeState: running` | 正在跑 |
| `runtimeState: waiting-user` + `pendingInteractionCount > 0` | **卡在人工确认**，此时发消息只会排队（`queuedTurnCount` 增加），不会解卡 |
| `runtimeState: ready` | 空闲，可以接新任务 |
| `backgroundAgentCount` | 它自己又派了子 agent，往往是你没预期的并发 |

## 3. 权限墙：回调没带 ref 就救不了

`respond_chat_session_interaction` 需要 `interactionRef`，这个值**只能**从监督回调里拿，不能猜、不能从会话记录里翻（实测 jsonl 和 state.json 里都没有）。

- 收到回调且带 `ref:` → 立刻 `{"interactionRef": "...", "type": "permission", "decision": "allow"}`。
- 只看到 `pendingInteractionCount` 涨、却收不到带 ref 的回调 → **不要反复重试**，这条路堵死了。二选一：
  1. 让用户在对应会话界面点确认；
  2. 停掉该会话，改用**本会话内的 Agent 兜底**（见第 6 节）。
- 回应已停止的会话，返回 `expired` 或 `applied` 都属正常，不影响结论。

## 4. 停止不等于结束：会自己复活

`stop_chat_session` 只中断当前轮。如果它还有排队任务，几秒后会**自动续跑**（实测同一 turn 被换新 id 重新拉起）。

正确顺序：

```
① send_message_to_chat_session({sessionId, prompt: "立即停机：任务已转交其他会话，不要再调用任何工具、不要再创建或修改任何文件，只回复“已停止”。"})
② stop_chat_session({sessionId})
③ wait_chat_sessions(...) 确认 runtimeState 变成 ready
④ 读盘确认它没有在停机前写入产物（find -newermt）
```

## 5. 一个写者原则

派新执行者之前，先把旧的全部停干净。否则两个写者会覆盖同一批文件，而且**不会报错**——你只会看到格式时好时坏。

派活时在任务书里写明：产物根目录只属于你，禁止写其他年份/其他人的目录。

## 6. 兜底：本会话内的 Agent

子会话撞权限墙时，最快的降级是**在本会话直接开子 Agent**：它继承当前会话的权限模式，实测不会再弹同样的窗。

- 适合：任务边界清楚、产物路径单一、你能事后逐个验收。
- 代价：并发多了会撞当日额度；额度耗尽时 Agent 直接 failed，但**已写入的文件仍在盘上**，先查盘再决定重跑范围。
- 任务书里加一句：`不要派生新的子 agent`，避免套娃。

## 7. 验收：只认磁盘

`lastAssistantText` 经常是 null，完成回调也只代表“这一轮结束了”，不代表活干对了。固定动作：

```bash
ls -d <OUT>/*/                       # 目录齐不齐
find <OUT> -name '*.txt' -newermt '<派活时间>'   # 到底谁写了什么
python <QA_SCRIPT> ...               # 跑结构验收（见 09）
```

再抽查 1–2 个产物读内容，别只看文件大小。

## 8. 任务书模板

```
# 任务：<一句话目标>

你是执行 agent，只做本任务。不要派生新的子 agent，不要询问是否开始，直接干。
若某条命令被拦，换一种写法继续，不要停住等待。

## 交付
<绝对路径清单，几个文件、每个文件叫什么>

## 第一步：读样板
<已验收的样板路径>，逐字模仿版式，不要自创结构。

## 硬规则
<格式、编码、禁用字符、命名>

## 数据源（已缓存，禁止重复下载）
<绝对路径 + 每个文件是什么>

## 自检
<可执行的检查命令；不通过不许汇报完成>

## 汇报
150 字内：完成范围、自检结果、遗留问题。
```
