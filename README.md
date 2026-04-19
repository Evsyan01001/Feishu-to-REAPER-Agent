# Feishu Agent - 智能音频助手

一个集成飞书机器人、RAG知识库、DeepSeek API的企业级智能代理系统，专为游戏音频设计领域优化。提供专业、安全、多轮对话的AI助手服务，支持通过自然语言直接控制REAPER音频工作站，采用文件系统通信+Lua脚本的轻量级集成方案。


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

### 🛠️ REAPER 控制能力
- **直接音频工作站控制**：通过文件系统与REAPER通信，无需复杂协议
- **智能指令解析**：自然语言指令自动解析为REAPER Action ID
- **Lua脚本桥接**：`listen.lua` 在REAPER端常驻，监听指令文件并执行
- **支持操作类型**：播放控制、增益调整、降噪处理、声像调节、导出渲染等
- **降级策略**：解析失败时提供简化处理和操作建议

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
│  │              FeishuAgent (主控制器)                   │    │
│  │  • 消息路由        • 会话管理      • 指令分发           │    │
│  │  • REAPER指令处理  • RAG检索      • AI对话            │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    REAPER控制层                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │ 指令解析器    │  │ Action映射器 │  │ 文件通信器   │          │
│  │ • 意图识别    │  │ • ID匹配    │  │ • 指令投递   │          │
│  │ • 参数提取    │  │ • 关键词搜索  │  │ • 跨平台支持 │          │
│  └─────────────┘  └─────────────┘  └─────────────┘          │
│                              │                               │
│                    ┌─────────────┐                          │
│                    │ listen.lua   │  ← REAPER端常驻脚本       │
│                    │ • 指令执行   │                          │
│                    │ • Action调用 │                          │
│                    └─────────────┘                          │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    智能处理层                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │ RAG引擎      │  │ DeepSeekAPI │  │ 对话管理器   │          │
│  │ • 知识检索   │  │ • AI对话     │  │ • 历史管理   │          │
│  │ • 向量搜索   │  │ • 流式输出    │  │ • 超时控制   │          │
│  └─────────────┘  └─────────────┘  └─────────────┘          │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    数据存储层                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │ ChromaDB    │  │   Redis     │  │ 本地文件系统  │          │
│  │ • 向量索引    │  │ • 会话缓存   │  │ • 知识文档   │          │
│  │ • 语义搜索    │  │ • 消息去重   │  │ • 指令文件   │          │
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
   cp .env
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
# REAPER 控制器配置
# ====================
ENABLE_REAPER_CONTROLLER=true  # 是否启用REAPER控制器
# 通信文件路径（可选，默认自动适配平台）
# Windows: C:\Users\Public\reaper_cmd.txt
# macOS/Linux: /tmp/reaper_cmd.txt
# REAPER_CMD_FILE=
```

### 知识库准备

1. **准备知识文档**
   - 将文档放入 `data/` 目录，支持格式：`.txt`, `.md`, `.pdf`, `.json`
   - 系统会自动构建向量数据库

2. **专业领域文件（可选）**
   - `audio_glossary.json` - 音频术语表
   - `audio_parameters.json` - 音频参数库
   - 放置在 `data/` 目录中

### REAPER 集成准备

1. **复制 Lua 脚本到 REAPER**
   - 将 `code/listen.lua` 复制到 REAPER 的脚本目录
   - REAPER → Actions → Show Action List → Script → 加载 `listen.lua`

2. **启动 REAPER 监听**
   - 在 REAPER 中运行一次 `listen.lua`
   - 脚本会在 REAPER 控制台输出启动信息
   - 之后 REAPER 会常驻监听 `reaper_cmd.txt` 文件

3. **验证连接**
   - 运行 `python main.py` 后，输入 "播放" 指令
   - 如果 REAPER 开始播放，说明集成成功

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

#### 2. REAPER 控制模式（启用REAPER集成）
```bash
# 启用REAPER控制器
export ENABLE_REAPER_CONTROLLER=true

# 运行主程序
python main.py
```

交互示例（REAPER控制）：
```
=======================================================
Feishu Agent 命令行模式（多轮对话已启用）
重置指令：/reset / /新对话 / /清除记忆 / 重置对话
REAPER控制器：已启用
=======================================================

请输入问题（输入 'quit' 退出）：
> 播放当前工程
✅ 指令已执行
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
│   ├── main.py                 # 主程序入口（FeishuAgent）
│   ├── rag_engine.py           # RAG知识检索引擎
│   ├── conversation.py         # 多轮对话管理器
│   ├── listen.lua              # REAPER端Lua脚本（需复制到REAPER脚本目录）
│   │
│   ├── reaper_controller/      # REAPER控制器模块
│   │   ├── __init__.py
│   │   ├── reaper_controller.py   # REAPER控制器主类
│   │   ├── reaper_intent.py       # REAPER意图定义
│   │   ├── action_mapper.py       # Action ID映射器
│   │   ├── instruction_parser.py # 指令解析器
│   │   └── file_communicator.py   # 文件通信器
│   │
│   └── __pycache__/
│
├── data/                   # 知识库文档
│   ├── audio_glossary.json    # 音频术语表
│   ├── audio_parameters.json   # 音频参数库
│   ├── audio_post_production.md   # 音频后期制作指南
│   ├── game_sound_design.md   # 游戏音效设计指南
│   ├── sound_effects_library.md   # 音效库文档
│   ├── openclaw_rules.md      # OpenClaw规则
│   ├── project_context.md     # 项目上下文
│   ├── reaper_actions.md      # REAPER Action ID映射表
│   ├── scenarios.md           # 场景描述
│   └── fallback_knowledge.json # 兜底知识库
│
├── instructions.md         # 系统提示词配置（游戏音频设计师人设）
├── vector_db/              # ChromaDB向量数据库（自动生成）
├── logs/                   # 日志目录（按日期分割）
├── test/                   # 测试文件目录
├── env_rag/                # Python虚拟环境（开发使用）
├── .env                    # 环境配置文件
├── .env.example            # 环境配置示例
├── .gitignore             # Git忽略配置
├── requirements.txt        # Python依赖包
└── README.md              # 项目文档
```

## 🔧 核心模块详解

### 1. FeishuAgent (main.py)
系统的核心协调器，负责：
- 消息路由和处理流程
- 飞书API集成（获取token、回复消息）
- 调用RAG引擎和AI模型
- 管理用户会话生命周期
- REAPER指令分发和处理

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

### 4. PromptManager (main.py)
系统提示词管理器：
- **热更新支持**：运行时动态加载 `instructions.md`
- **快速启动**：默认基础提示词，启动无延迟
- **指令刷新**：通过 `/update_prompt` 命令触发刷新
- **游戏音频设计师人设**：专业的AAA级游戏音频总监角色设定

### 5. ReaperController (reaper_controller/)
REAPER音频工作站控制器，整合指令解析、Action映射和文件通信：

#### 5.1 ReaperInstructionParser (instruction_parser.py)
- **意图识别**：判断用户输入是否为REAPER指令
- **自定义操作解析**：GAIN、DENOISE、EXPORT、PAN、EQ等
- **参数提取**：正则表达式提取数值参数
- **关键词匹配**：支持中英文关键词识别

#### 5.2 ActionMapper (action_mapper.py)
- **Action ID映射**：将自然语言映射到REAPER Action ID
- **关键词索引**：基于 `reaper_actions.md` 构建搜索索引
- **分类管理**：按功能域组织Action（播放控制、轨道操作等）
- **搜索建议**：未匹配时提供相关Action建议

#### 5.3 FileCommunicator (file_communicator.py)
- **跨平台支持**：自动适配Windows/macOS/Linux路径
- **指令投递**：写入 `reaper_cmd.txt` 通信文件
- **阅后即焚**：防止指令重复执行
- **状态反馈**：报告文件访问状态

#### 5.4 listen.lua (REAPER端脚本)
- **常驻监听**：通过 `defer` 实现非阻塞后台轮询
- **指令解析**：解析 `ACTION|xxx`、`GAIN|xx` 等协议格式
- **Action执行**：调用 `reaper.Main_OnCommand()` 执行标准Action
- **自定义操作**：内置增益、降噪、导出等复杂操作处理

### 6. 系统提示词 (instructions.md)
游戏音频设计师专用人设配置：
- **攻击性专业**：对平庸声音零容忍
- **反击式诊断**：先分析问题本质，再给解决方案
- **强制数值**：回答必须包含具体插件名和数值
- **REAPER原生**：优先使用ReaEQ/ReaComp/ReaVerb等原生插件

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

#### 5. REAPER 指令无响应
**原因**：通信文件路径不正确或REAPER脚本未运行
**解决方案**：
- 检查 `listen.lua` 是否已在 REAPER 中加载并运行
- 验证通信文件是否存在（Windows: `C:\Users\Public\reaper_cmd.txt`, macOS/Linux: `/tmp/reaper_cmd.txt`）
- 确认 `ENABLE_REAPER_CONTROLLER=true` 已设置
- 检查 REAPER 控制台是否有错误信息

#### 6. REAPER Action 执行失败
**原因**：Action ID 不正确或 REAPER 版本不兼容
**解决方案**：
- 查看 `data/reaper_actions.md` 确认正确的 Action ID
- 检查 REAPER 版本是否支持该 Action
- 尝试在 REAPER 手动执行该 Action 验证是否有效
- 使用 "播放"、"暂停" 等基础指令测试功能完整性

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

### 测试 REAPER 控制器
```bash
# 测试 REAPER 控制器初始化
python -c "
from reaper_controller import ReaperController
rc = ReaperController()
health = rc.check_health()
print('控制器状态:', health['status'])
"

# 测试指令解析
python -c "
from reaper_controller import ReaperInstructionParser
parser = ReaperInstructionParser()
print('播放是REAPER指令:', parser.is_reaper_command('播放音频'))
print('解析结果:', parser.parse('音量调大3分贝'))
"

# 测试 Action 映射
python -c "
from reaper_controller import ActionMapper
mapper = ActionMapper()
result = mapper.find_action_id('播放')
print('播放 Action ID:', result)
"
```

### 调试 REAPER 通信
```python
# 启用详细调试日志
import logging
logging.basicConfig(level=logging.DEBUG)

# 测试完整流程
from main import FeishuAgent
agent = FeishuAgent()
response = agent.process_message('播放', user_id='test')
print('结果:', response)
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
1. 查看 [Issues](https://github.com/Evsyan01001/Feishu-to-REAPER-Agent/issues) 页面
2. 提交新的Issue
3. 或通过邮件联系维护者 (yelvis491@gmail.com)

---


*最后更新：2026年4月19日*