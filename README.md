# Feishu Agent - 智能工具感知助手

一个集成飞书机器人、RAG知识库、DeepSeek API、MCP工具调用的企业级智能代理系统，专为游戏音频设计领域优化，提供专业、安全、多轮对话的AI助手服务，支持通过自然语言控制REAPER等外部工具。

![系统架构](docs/architecture.png)

## ✨ 核心特性

### 🤖 多平台支持
- **飞书集成**：完整的飞书机器人Webhook接口，支持签名验证、消息去重
- **CLI模式**：本地命令行交互，方便开发和测试
- **Web服务**：Flask RESTful API，支持健康检查和状态监控

### 🧠 智能知识库（RAG）
- **专业领域优化**：内置游戏音频设计术语表和参数库
- **智能检索**：基于向量相似度搜索，支持置信度过滤
- **内容清洗**：自动去除冗余信息，提取核心内容
- **多格式支持**：TXT、MD、PDF、JSON文档自动解析

### 🔒 企业级安全
- **P0安全模块**：飞书Webhook签名验证，防重放攻击
- **消息去重**：Redis优先，内存回退，防止重复处理
- **会话隔离**：多用户会话管理，数据安全隔离

### 💬 智能对话
- **多轮对话**：基于上下文的连续对话，支持历史追溯
- **会话管理**：自动超时清理，滚动窗口限制
- **指令控制**：支持`/reset`、`/新对话`等管理指令

### 🛠️ 工具调用能力
- **MCP协议支持**：通过Model Context Protocol连接外部工具（如REAPER音频工作站）
- **智能工具检测**：基于自然语言自动检测用户意图，推荐合适工具
- **提示词工程**：通过精心设计的提示词解决DeepSeek不支持function calling的限制
- **工具注册表**：集中管理可用工具，支持动态发现和注册
- **同步/异步执行**：支持同步HTTP调用和异步MCP工具执行

### ⚙️ 生产就绪
- **降级策略**：Redis不可用时自动切换到内存模式，工具不可用时优雅降级
- **健康检查**：完善的监控接口和状态统计，包括工具可用性检查
- **配置驱动**：环境变量配置，无需修改代码

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                    用户交互层                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │   飞书App    │  │   CLI终端   │  │  HTTP API    │         │
│  └─────────────┘  └─────────────┘  └─────────────┘          │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    应用服务层                                 │
│  ┌─────────────────────────────────────────────────────┐    │
│  │           ToolAwareFeishuAgent (增强版)              │    │
│  │  • 消息路由        • 会话管理      • 指令解析           │    │
│  │  • 工具意图检测    • 提示词工程    • 结果整合            │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    工具协调层                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │ 工具注册表    │  │ 工具协调器   │  │  MCP客户端   │          │
│  │ • 工具发现    │  │ • 意图解析  │   │ • MCP连接   │          │
│  │ • 元数据管理  │  │ • 执行调度   │  │ • 工具调用   │          │
│  └─────────────┘  └─────────────┘  └─────────────┘          │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    智能处理层                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │ RAG引擎      │  │ DeepSeekAPI │  │ 对话管理器   │          │
│  │ • 知识检索   │  │ • AI对话     │  │ • 历史管理   │          │
│  │ • 向量搜索   │  │ • 模型调用    │  │ • 超时控制   │          │
│  └─────────────┘  └─────────────┘  └─────────────┘          │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    数据存储层                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │ ChromaDB    │  │   Redis     │  │ 本地文件系统  │          │
│  │ • 向量索引    │  │ • 会话缓存   │  │ • 知识文档   │          │
│  │ • 语义搜索    │  │ • 消息去重   │  │ • 配置文件   │          │
│  └─────────────┘  └─────────────┘  └─────────────┘          │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 快速开始

### 环境要求

- Python 3.8+
- Redis 5.0+ (可选，用于分布式会话和消息去重)
- 至少2GB可用内存

### 安装步骤

1. **克隆项目**
   ```bash
   git clone https://github.com/Evsyan01001/Feishu-to-REAPER-Agent
   cd Feishu_Agent_Demo
   ```

2. **进入代码目录**
   ```bash
   cd code
   ```

3. **创建虚拟环境**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # 或
   venv\Scripts\activate     # Windows
   ```

4. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

5. **环境配置**
   ```bash
   cp .env.example .env
   # 编辑 .env 文件，填写必要的配置
   ```

### 配置说明

创建 `.env` 文件并配置以下参数：

```env
# ====================
# DeepSeek API 配置
# ====================
# 从 https://platform.deepseek.com/ 获取 API 密钥
DEEPSEEK_API_KEY=sk-your-api-key-here
MODEL_NAME=deepseek-chat  # 或 deepseek-coder

# ====================
# 飞书应用配置（飞书集成需要）
# ====================
# 从 https://open.feishu.cn/ 创建应用获取
FEISHU_APP_ID=your_feishu_app_id
FEISHU_APP_SECRET=your_feishu_app_secret

# ====================
# 服务器配置
# ====================
USE_WEBHOOK=false          # true: Webhook模式, false: CLI模式
HOST=0.0.0.0
PORT=5000

# ====================
# RAG 配置
# ====================
CHUNK_SIZE=500             # 文本分块大小
CHUNK_OVERLAP=50           # 分块重叠大小
SEARCH_RESULTS_COUNT=5     # 检索结果数量

# ====================
# 嵌入模型配置
# ====================
EMBEDDING_MODEL=text-embedding-ada-002

# ====================
# 对话配置
# ====================
CONV_MAX_TURNS=10          # 最大对话轮次
CONV_IDLE_TIMEOUT=1800     # 会话空闲超时（秒）
CONV_MAX_SESSIONS=5000     # 最大会话数

# ====================
# 安全配置
# ====================
DEDUP_TTL=60               # 消息去重TTL（秒）
DEDUP_MAX_MEMORY=2000      # 内存去重最大条目数

# ====================
# Redis 配置（可选）
# ====================
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=0

# ====================
# 工具配置（可选，需要工具功能时启用）
# ====================
USE_TOOLS=false                    # 是否启用工具功能
TOOL_PROMPT_ENHANCEMENT=true      # 是否启用提示词增强
MAX_TOOLS_IN_PROMPT=5             # 提示词中最多包含的工具数
TOOL_RESULT_FORMAT=detailed       # 工具结果格式：simple|detailed
AUTO_EXECUTE_TOOLS=true           # 是否自动执行检测到的工具
TOOL_CONFIRMATION_THRESHOLD=0.6   # 工具确认阈值（0-1）

# ====================
# MCP 配置（需要MCP工具时启用）
# ====================
MCP_SERVER_HOST=localhost         # MCP服务器地址
MCP_SERVER_PORT=8000             # MCP服务器端口
MCP_TRANSPORT=stdio              # 传输协议：stdio|http|websocket
MCP_TOOL_DISCOVERY=true          # 是否自动发现MCP工具
```

### 知识库准备

1. **准备知识文档**
   - 将文档放入 `data/` 目录，支持格式：`.txt`, `.md`, `.pdf`, `.json`
   - 系统会自动构建向量数据库

2. **专业领域文件（可选）**
   - `audio_glossary.json` - 音频术语表
   - `audio_parameters.json` - 音频参数库
   - 放置在 `data/` 目录中

### 运行应用

**注意**：以下命令需要在 `code/` 目录下执行（已完成上述安装步骤）。

#### 1. CLI交互模式（开发测试）
```bash
# 确保 USE_WEBHOOK=false
python main.py
```

交互示例：
```
=======================================================
Feishu Agent 命令行模式（多轮对话已启用）
重置指令：/reset / /新对话 / /清除记忆 / 重置对话
=======================================================

请输入问题（输入 'quit' 退出）：
> 什么是ADSR包络？
```

#### 2. 工具感知模式（启用工具调用）
```bash
# 启用工具功能
export USE_TOOLS=true
# 如果需要MCP连接，配置MCP服务器
export MCP_SERVER_HOST=localhost
export MCP_SERVER_PORT=8000

# 运行工具感知Agent
python tool_agent.py
```

交互示例（工具调用）：
```
=======================================================
Feishu Agent 工具感知模式（工具调用已启用）
可用工具：reaper_play, reaper_stop, reaper_record, ...
重置指令：/reset
=======================================================

请输入指令（输入 'quit' 退出）：
> 播放当前工程
[工具调用] 执行 reaper_play: 开始播放REAPER工程
[结果] 播放已开始，当前位置：00:01:30
```

#### 3. Webhook服务模式（生产部署）
```bash
# 设置 USE_WEBHOOK=true
export USE_WEBHOOK=true
python main.py
```

服务启动后：
- Webhook地址：`http://你的域名或IP:5000/webhook/feishu`
- 健康检查：`http://localhost:5000/health`

#### 4. 飞书机器人配置
1. 在[飞书开放平台](https://open.feishu.cn/)创建应用
2. 启用机器人能力
3. 配置事件订阅：
   - 请求地址：`https://你的域名/webhook/feishu`
   - 订阅事件：`接收消息v2.0`
4. 发布应用并添加到群组

## 📁 项目结构

```
Feishu_Agent_Demo/
├── code/                   # 源代码目录
│   ├── main.py                 # 主程序入口（基础FeishuAgent）
│   ├── tool_agent.py           # 工具感知Agent（增强版，支持工具调用）
│   ├── rag_engine.py           # RAG知识检索引擎
│   ├── conversation.py         # 多轮对话管理器
│   ├── security.py             # P0安全模块（签名验证、消息去重）
│   ├── tool_registry.py        # 工具注册表，管理可用工具
│   ├── tool_orchestrator.py    # 工具协调器，处理工具意图和执行
│   ├── prompt_engine.py        # 提示词引擎，解决DeepSeek无function calling限制
│   ├── mcp_client.py           # MCP客户端，连接外部工具（如REAPER）
│   ├── debug_rag.py            # RAG调试工具
│   ├── .env                    # 环境配置文件（从.env.example复制）
│   └── __pycache__/
│
├── data/                   # 知识库文档
│   ├── backup/                # 备份文件
│   │   ├── openclaw_rules.md      # OpenClaw规则
│   │   ├── project_context.md     # 项目上下文
│   │   ├── reaper_actions.md      # REAPER Action ID映射表
│   │   └── scenarios.md           # 场景描述
│   ├── audio_glossary.json    # 音频术语表
│   ├── audio_parameters.json  # 音频参数库
│   ├── audio_post_production.md   # 音频后期制作指南
│   ├── game_sound_design.md   # 游戏音效设计指南
│   ├── sound_effects_library.md   # 音效库文档
│   └── ...                    # 其他知识文档
│
├── vector_db/              # ChromaDB向量数据库（自动生成）
├── logs/                   # 日志目录（按日期分割）
│   ├── WORK_LOG_2026-04-16.md
│   ├── 2026.04.17-00:18.md
│   └── ...
├── test/                   # 测试文件目录
├── env_rag/                # Python虚拟环境（开发使用）
├── .gitignore             # Git忽略配置
├── requirements.txt        # Python依赖包
├── README.md              # 项目文档
└── plan.md                # 项目计划和架构设计
```

## 🔧 核心模块详解

### 1. FeishuAgent (main.py)
系统的核心协调器，负责：
- 消息路由和处理流程
- 飞书API集成（获取token、回复消息）
- 调用RAG引擎和AI模型
- 管理用户会话生命周期

### 2. RAGEngine (rag_engine.py)
智能知识检索引擎，提供：
- **统一检索接口**：`search()`方法支持多种返回格式
- **专业领域优化**：音频术语表和参数库优先匹配
- **智能过滤**：置信度阈值过滤低质量结果
- **内容优化**：自动清洗和摘要生成

### 3. ConversationManager (conversation.py)
多轮对话上下文管理：
- **用户会话隔离**：每个用户独立对话历史
- **滚动窗口**：保留最近N轮对话（默认10轮）
- **自动清理**：30分钟无活动自动重置会话
- **持久化存储**：Redis优先，内存回退

### 4. 安全模块 (security.py)
企业级安全保障：
- **签名验证**：HMAC-SHA256验证飞书Webhook签名
- **消息去重**：防止重复处理相同消息
- **防重放攻击**：时间戳验证，防止请求重放

### 5. ToolAwareFeishuAgent (tool_agent.py)
工具感知的增强版Agent，在基础FeishuAgent上添加：
- **工具意图检测**：分析用户消息，识别工具使用意图
- **提示词工程**：通过系统提示词注入工具上下文，解决DeepSeek无function calling限制
- **工具结果整合**：将工具执行结果整合到对话上下文
- **错误恢复**：工具调用失败时的优雅降级处理

### 6. ToolRegistry (tool_registry.py)
工具注册和管理中心：
- **工具发现**：动态注册和发现可用工具
- **元数据管理**：维护工具名称、描述、参数模式
- **分类组织**：按功能域分类工具（REAPER控制、飞书表格、音频专业）
- **健康检查**：监控工具可用性状态

### 7. ToolOrchestrator (tool_orchestrator.py)
工具执行协调器：
- **意图解析**：将用户意图映射到具体工具和参数
- **执行调度**：同步/异步工具调用管理
- **结果处理**：标准化工具输出格式
- **并发控制**：管理多个工具的执行顺序和依赖

### 8. PromptEngine (prompt_engine.py)
提示词工程引擎：
- **工具上下文注入**：将可用工具信息嵌入系统提示词
- **结果格式优化**：将工具结果转换为模型友好的格式
- **调用指导生成**：引导模型正确使用可用工具
- **动态提示调整**：基于对话上下文调整提示策略

### 9. MCPClient (mcp_client.py)
Model Context Protocol客户端：
- **MCP连接**：连接外部MCP服务器（如REAPER音频工作站）
- **工具发现**：从MCP服务器获取可用工具列表
- **协议适配**：处理MCP协议细节和消息格式
- **错误处理**：网络连接和协议错误的恢复机制

## 📊 API接口

### Webhook接口
- `POST /webhook/feishu` - 飞书事件回调
  - 支持事件：`url_verification`, `event_callback`
  - 必需Header：`X-Lark-Signature`, `X-Lark-Request-Timestamp`, `X-Lark-Request-Nonce`

### 健康检查
- `GET /health` - 系统健康状态
  ```json
  {
    "status": "healthy",
    "service": "feishu_agent",
    "dedup": {"backend": "memory", "cached": 42},
    "conv": {"backend": "memory", "active_sessions": 5},
    "signature_verification": true
  }
  ```

### RAG引擎接口
通过`RAGEngine`类提供：
- `search(query, k=5, confidence_threshold=0.65, return_format="structured")`
- `check_health()` - 检查知识库状态

## 🚢 部署指南

### Docker部署
```dockerfile
FROM python:3.9-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# 复制项目文件
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 运行应用
CMD ["python", "main.py"]
```

### 生产环境建议
1. **使用Redis**：确保会话持久化和分布式消息去重
2. **配置SSL**：生产环境必须使用HTTPS
3. **设置防火墙**：限制访问IP，只允许飞书服务器
4. **监控日志**：定期检查Log目录下的日志文件
5. **备份知识库**：定期备份`data/`和`vector_db/`目录

## 🔍 故障排除

### 常见问题

#### 1. RAG引擎初始化失败
```
ImportError: 缺少必要依赖
```
**解决方案**：
```bash
pip install langchain chromadb sentence-transformers pypdf
```

#### 2. 飞书签名验证失败
```
[P0] 签名验证失败：签名不匹配
```
**检查**：
- `.env`中的`FEISHU_APP_SECRET`是否正确
- 飞书控制台的事件订阅URL是否配置正确
- 服务器时间是否同步

#### 3. 消息重复回复
**原因**：消息去重未生效
**解决方案**：
- 检查Redis连接（如果使用Redis）
- 调整`DEDUP_TTL`值（默认60秒）

#### 4. 对话上下文丢失
**原因**：会话超时或Redis连接问题
**解决方案**：
- 检查Redis服务状态
- 调整`CONV_IDLE_TIMEOUT`值
- 检查`.env`中的Redis配置

#### 5. 工具调用失败
**原因**：MCP服务器未连接或工具不可用
**解决方案**：
- 检查MCP服务器是否运行：`nc -z localhost 8000`
- 确认`USE_TOOLS=true`环境变量已设置
- 检查MCP客户端日志中的连接错误
- 确认MCP工具已正确注册到工具注册表

#### 6. 工具意图检测不准确
**原因**：提示词工程配置不当或阈值设置过高
**解决方案**：
- 调整`TOOL_CONFIRMATION_THRESHOLD`值（默认0.6）
- 检查`TOOL_PROMPT_ENHANCEMENT`是否启用
- 验证工具描述是否清晰准确
- 检查PromptEngine日志中的意图识别结果

#### 7. MCP连接超时
**原因**：网络问题或MCP服务器未响应
**解决方案**：
- 检查`MCP_SERVER_HOST`和`MCP_SERVER_PORT`配置
- 确认MCP服务器正在运行且可访问
- 调整MCP客户端超时设置（如有）
- 检查防火墙设置，确保端口可访问

### 日志查看
日志文件位于`logs/`目录，按日期分割：
- `feishu_agent_YYYY-MM-DD.log` - 应用日志
- 日志级别：INFO, WARNING, ERROR

## 🧪 测试与开发

### 测试RAG引擎
```bash
python -c "from rag_engine import RAGEngine; rag = RAGEngine(); print(rag.search('什么是ADSR？'))"
```

### 调试模式
```python
# 在代码中添加调试日志
import logging
logging.basicConfig(level=logging.DEBUG)
```

### 单元测试
```bash
pytest test_*.py
```

### 测试工具调用
```bash
# 测试工具注册表
python -c "from tool_registry import get_tool_registry; reg = get_tool_registry(); print('注册工具数量:', len(reg.list_tools()))"

# 测试MCP客户端连接
python -c "from mcp_client import init_mcp_client; client = init_mcp_client(); print('MCP客户端状态:', '已连接' if client.is_connected() else '未连接')"

# 测试工具意图检测
python -c "
from tool_orchestrator import get_tool_orchestrator
orchestrator = get_tool_orchestrator()
intent = orchestrator.detect_tool_intent('播放当前工程')
print('检测到的意图:', intent.tool_name if intent else '无')
"
```

### 调试工具调用
```python
# 启用详细工具调试日志
import logging
logging.basicConfig(level=logging.DEBUG)

# 查看工具调用详细流程
from tool_agent import ToolAwareFeishuAgent
agent = ToolAwareFeishuAgent()
response = agent.process_message("测试工具调用", user_id="test_user")
print(response)
```

## 🔄 更新与维护

### 知识库更新
1. 添加新文档到`data/`目录
2. 删除`vector_db/`目录
3. 重启应用，自动重建向量数据库

### 系统升级
1. 备份当前配置和数据
2. 更新代码：`git pull`
3. 更新依赖：`pip install -r requirements.txt`
4. 重启应用

## 📄 许可证

本项目采用 MIT 许可证。详见 [LICENSE](LICENSE) 文件。

## 🤝 贡献指南

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 📞 支持与反馈

如有问题或建议，请：
1. 查看 [Issues](https://github.com/your-repo/issues) 页面
2. 提交新的Issue
3. 或通过邮件联系维护者

---

**致谢**：感谢DeepSeek提供强大的AI模型支持，以及飞书开放平台的优秀机器人生态。

*最后更新：2026年4月*