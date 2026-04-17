# Feishu Agent - 智能知识库助手

一个集成飞书机器人、RAG知识库、DeepSeek API的企业级智能代理系统，专为游戏音频设计领域优化，提供专业、安全、多轮对话的AI助手服务。

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

### ⚙️ 生产就绪
- **降级策略**：Redis不可用时自动切换到内存模式
- **健康检查**：完善的监控接口和状态统计
- **配置驱动**：环境变量配置，无需修改代码

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                    用户交互层                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │   飞书App    │  │   CLI终端   │  │  HTTP API    │        │
│  └─────────────┘  └─────────────┘  └─────────────┘        │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    应用服务层                                 │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                  FeishuAgent                        │    │
│  │  • 消息路由        • 会话管理      • 指令解析          │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    智能处理层                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │ RAG引擎     │  │ DeepSeekAPI │  │ 对话管理器   │        │
│  │ • 知识检索  │  │ • AI对话    │  │ • 历史管理   │        │
│  │ • 向量搜索  │  │ • 模型调用  │  │ • 超时控制   │        │
│  └─────────────┘  └─────────────┘  └─────────────┘        │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    数据存储层                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │ ChromaDB    │  │   Redis     │  │ 本地文件系统 │        │
│  │ • 向量索引  │  │ • 会话缓存  │  │ • 知识文档   │        │
│  │ • 语义搜索  │  │ • 消息去重  │  │ • 配置文件   │        │
│  └─────────────┘  └─────────────┘  └─────────────┘        │
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
   git clone <repository-url>
   cd Feishu_Agent_Demo
   ```

2. **创建虚拟环境**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # 或
   venv\Scripts\activate     # Windows
   ```

3. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

4. **环境配置**
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

#### 2. Webhook服务模式（生产部署）
```bash
# 设置 USE_WEBHOOK=true
export USE_WEBHOOK=true
python main.py
```

服务启动后：
- Webhook地址：`http://你的域名或IP:5000/webhook/feishu`
- 健康检查：`http://localhost:5000/health`

#### 3. 飞书机器人配置
1. 在[飞书开放平台](https://open.feishu.cn/)创建应用
2. 启用机器人能力
3. 配置事件订阅：
   - 请求地址：`https://你的域名/webhook/feishu`
   - 订阅事件：`接收消息v2.0`
4. 发布应用并添加到群组

## 📁 项目结构

```
Feishu_Agent_Demo/
├── main.py                 # 主程序入口，集成所有组件
├── rag_engine.py           # RAG知识检索引擎
├── conversation.py         # 多轮对话管理器
├── security.py             # P0安全模块（签名验证、消息去重）
├── requirements.txt        # Python依赖包
├── .env                    # 环境配置文件（从.env.example复制）
├── .gitignore             # Git忽略配置
│
├── data/                   # 知识库文档
│   ├── audio_glossary.json    # 音频术语表
│   ├── audio_parameters.json  # 音频参数库
│   ├── *.txt/.md/.pdf      # 知识文档
│   └── ...
│
├── vector_db/              # ChromaDB向量数据库（自动生成）
├── Log/                    # 日志目录
├── Test/                   # 测试文件
└── docs/                   # 文档目录
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

### 日志查看
日志文件位于`Log/`目录，按日期分割：
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

*最后更新：2024年4月*