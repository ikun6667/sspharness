# LangGraph Harness — 设计文档

## 一句话定位

**Coding agent 的运行时，本质是一张可中断、可续跑的循环状态图。LangGraph 比裸 `while True` 更自然地表达这个性质。**

---

## 1. 为什么不是"裸循环就够了"

learn-claude-code 用 `while True` + hooks 挂满了 26 个机制，证明了 harness 的组成。但其中三类需求在裸循环里实现起来很别扭：

| 需求 | 裸循环的痛点 | LangGraph 的原语 |
|------|-------------|-----------------|
| 权限确认 (HITL) | 需要在循环体内手写状态机，跨进程恢复几乎不可能 | `interrupt()` + checkpointer，暂停/恢复是框架白给的 |
| 会话续跑 | 必须自己序列化消息历史 + 反序列化 | checkpointer 持久化整个 state，重启后 `ainvoke` 自动续上 |
| 子 agent 隔离 | 要么共享消息列表（污染），要么自己管理子进程 | subgraph 天然隔离上下文，父图只看到最终结果 |

其余机制（工具循环、消息追加）裸循环和 LangGraph 差别不大，但上面三块足以证明"用图来表达更自然"。

## 2. 架构：插件化

借鉴 deepseek-harness 的"一切皆插件"思想，但用 Python 方式实现：

```
Plugin 协议
├── tools()      → 贡献工具定义
├── nodes()      → 贡献图节点
├── edges()      → 贡献路由边
├── hooks()      → 贡献生命周期拦截器
└── extra_channels() → 贡献额外的 state 通道

PluginRegistry
├── register(plugin)
├── resolve() → PluginManifest  ← 合并所有插件的贡献，检测冲突
└── list_plugins()

GraphBuilder
├── 读取 PluginManifest
├── 构建 StateGraph（核心 agent 循环 + 插件节点）
├── 挂载 hooks 到对应节点
└── compile(checkpointer=...)
```

**扩展方式**：加一个新能力 = 写一个 Plugin 实现类 → register → 完事。不碰核心代码。

## 3. 四个内置插件

| 插件 | 贡献 | 面试角度 |
|------|------|---------|
| **ToolsPlugin** | read_file / write_file / list_files / bash 四个工具 | "最小但完整的 coding agent 工具集" |
| **PermissionsPlugin** | PRE_TOOL_CALL hook → interrupt() 暂停 | "框架真增量 #1：HITL 是裸循环最痛的部分" |
| **MemoryPlugin** | POST_LLM_CALL hook → 消息压缩 | "state channel 改写 vs 手工 splice 列表" |
| **SubagentPlugin** | spawn_subagent 工具 → 内部编译子图 | "框架真增量 #3：subgraph 天然隔离上下文" |

## 4. 主循环状态图

```
         ┌──────────┐
    ┌───→│  agent   │──────┐
    │    │ (LLM调用) │      │
    │    └──────────┘      │
    │                      ▼
    │              ┌──────────────┐
    │              │ should_continue│
    │              └──────┬───────┘
    │                     │
    │         ┌───────────┼───────────┐
    │         ▼                       ▼
    │    [有 tool_calls]         [无 tool_calls]
    │         │                       │
    │         ▼                       ▼
    │    ┌──────────┐              ┌─────┐
    └────│  tools   │              │ END │
         │ (执行工具) │              └─────┘
         └──────────┘
```

- **agent 节点**：调用 LLM，触发 PRE/POST_LLM_CALL hooks（权限检查、消息压缩）
- **tools 节点**：执行工具，触发 PRE/POST_TOOL_CALL hooks
- **should_continue**：条件边，检查最后一条消息是否有 tool_calls

## 5. 面试护城河：什么是框架给的，什么是你设计的

| 组件 | 框架白给 | 你设计的 |
|------|---------|---------|
| 工具循环 | ToolNode + should_continue 条件边 | 无 |
| 消息追加 | add_messages reducer | 无 |
| 会话持久化 | MemorySaver / SqliteSaver checkpointer | 选择哪种 checkpointer、thread_id 策略 |
| 权限 HITL | interrupt() 原语 | **权限策略（哪些工具需要确认）、策略配置接口** |
| 消息压缩 | 无（需自己做） | **压缩算法、阈值策略、改写 state 的方式** |
| 子 agent | subgraph 机制 | **子 agent 的系统提示、隔离边界、结果回传格式** |
| 插件系统 | 无（需自己做） | **Plugin 协议设计、Registry 冲突检测、GraphBuilder 装配逻辑** |

## 6. 简历叙事线

```
实习项目：RAG 检索优化 + Multi-Agent（LangGraph）
    ↓ 同一框架族，深入理解 agent 运行时
本项目：Agent Harness / 工具编排（LangGraph + 插件架构）
    ↓ 从"用框架"到"设计框架"
目标岗位：AI 编程工具方向
```

## 7. 目录结构

```
langgraph-harness/
├── pyproject.toml
├── src/harness/
│   ├── core/
│   │   ├── state.py          # AgentState 定义 + reducer
│   │   ├── plugin.py         # Plugin 协议 + ToolSpec/HookSpec
│   │   ├── registry.py       # PluginRegistry + PluginManifest
│   │   └── graph.py          # GraphBuilder — 编译插件为可运行图
│   ├── plugins/
│   │   ├── tools.py          # 内置工具（read/write/list/bash）
│   │   ├── permissions.py    # HITL 权限（interrupt）
│   │   ├── memory.py         # 上下文压缩
│   │   └── subagent.py       # 子 agent（subgraph）
│   └── llm/
│       ├── base.py           # BaseLLM 协议
│       └── anthropic_client.py
├── examples/
│   ├── basic_agent.py        # 无权限的基础 agent
│   └── hitl_agent.py         # 带 HITL 权限的 agent
├── tests/
│   ├── test_registry.py
│   ├── test_state.py
│   └── test_graph.py
└── docs/
    └── design.md             # 本文件
```

## 8. 下一步扩展点（设计好了但没实现）

- **持久化 checkpointer**：换 SqliteSaver / PostgresSaver，实现真正的跨进程续跑
- **更多工具**：edit_file（diff-based）、grep、glob
- **DeepSeek/OpenAI 后端**：实现 BaseLLM 协议即可
- **插件市场**：第三方插件通过 pip install + register 接入
- **trajectory 日志**：参考 deepseek-harness 的 append-only session log
