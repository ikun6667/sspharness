# LangGraph Harness

基于 LangGraph 的编码 Agent 框架，参考 learn-claude-code 的 26 种机制和 DeepSeek Harness 的插件架构。

## 特性

- **插件化架构**：工具、权限、记忆、MCP 等均为可插拔插件
- **LangGraph 状态图**：利用 interrupt、checkpointer、subgraph 实现复杂工作流
- **多层上下文压缩**：参考 learn-claude-code s08，实现智能上下文管理
- **记忆系统**：选择性回忆、记忆提取与整合（s09）
- **任务系统**：独立工作空间，支持并发任务执行
- **实时交互**：流式响应、实时计时器、任务停止控制
- **MCP 集成**：连接外部 MCP 服务器扩展工具能力

## 技术栈

- **后端**：FastAPI + LangGraph + LangChain
- **前端**：React + Vite + Tailwind CSS
- **LLM**：OpenAI 兼容接口（支持 GLM-5.2、Claude 等）

## 快速开始

### 1. 安装依赖

```bash
# 后端
pip install -e ".[dev]"

# 前端
cd web
npm install
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env` 并填入 API 密钥：

```bash
LLM_BASE_URL=https://llm.polixir.site/v1
LLM_API_KEY=your-api-key-here
LLM_MODEL=glm-5.2
```

### 3. 启动服务

```bash
# 后端（端口 8000）
python -m uvicorn server.main:app --host 0.0.0.0 --port 8000

# 前端（端口 3000）
cd web
npm run dev
```

访问 http://localhost:3000

## 项目结构

```
langgraph-harness/
├── server/              # FastAPI 后端
│   └── main.py         # API 端点
├── src/harness/        # 核心框架
│   ├── core/           # 状态图、插件注册表
│   ├── plugins/        # 内置插件
│   └── llm/            # LLM 抽象层
├── web/                # React 前端
│   └── src/
│       ├── components/ # UI 组件
│       └── api.js      # API 调用
└── workspaces/         # 任务工作空间（运行时生成）
```

## 核心概念

### 插件系统

所有功能通过插件实现：
- `ToolsPlugin`：文件操作、Shell 命令
- `PermissionsPlugin`：权限控制
- `MemoryPlugin`：上下文压缩
- `MemoryStorePlugin`：长期记忆
- `MCPPlugin`：MCP 服务器连接

### 任务系统

每个任务拥有：
- 独立工作空间目录
- 独立对话历史
- 独立工具事件日志
- 支持并发执行

### 上下文管理

多层压缩策略：
1. `tool_result_budget`：工具结果预算控制
2. `snip_compact`：截断过长内容
3. `micro_compact`：微压缩
4. `compact_history`：历史压缩
5. `reactive_compact`：响应式压缩

## 版本

v1.0.0 - 初始版本

## 许可证

MIT
