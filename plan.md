# 方案：为Feishu Agent添加MCP工具支持以控制REAPER并集成飞书表格

## 上下文
当前Feishu Agent项目已实现：
1. 飞书机器人Webhook接口（含P0安全验证）
2. RAG知识库引擎（音频专业知识）
3. 多轮对话管理系统
4. DeepSeek API集成

项目目标：构建音频创作领域垂直AI助手，打通飞书交互与REAPER数字音频工作站的远程控制能力。

**新增需求**：让agent支持MCP（Model Context Protocol），实现：
- 作为MCP客户端控制REAPER项目
- 结合飞书表格完成REAPER的项目管理
- 支持类似Claude Code中的技能调用模式

## 现有基础
1. **REAPER Action ID映射**：已有完整映射表（`data/backup/reaper_actions.md`），包含5大类29个Action ID
2. **项目规划**：B板块负责"REAPER MCP和Skills实现"（文档中有定义但代码未实现）
3. **飞书集成**：已有基础机器人API，但无表格集成
4. **架构**：同步HTTP架构，使用requests库

## 技术约束
1. **DeepSeek不支持function calling**：需通过提示词工程实现工具调用
2. **同步架构**：现有系统是同步的，MCP可能需要异步处理
3. **生产环境要求**：需要错误处理、降级策略、监控

## 架构设计

### 整体架构
```
用户 → 飞书/CLI → FeishuAgent → ToolOrchestrator → [MCPClient, FeishuSheetClient] → REAPER/飞书表格
                              ↘ RAGEngine → 知识库回答
```

### 新增组件
1. **ReaperMCPClient**：REAPER MCP客户端，通过MCP协议调用Action ID
2. **FeishuSheetClient**：飞书表格客户端，管理项目状态和任务
3. **ToolRegistry**：工具注册表，管理可用工具及其元数据
4. **PromptEngine**：提示词引擎，处理DeepSeek不支持function calling的替代方案
5. **ToolCallHandler**：处理同步/异步调用转换

### 工具分类
1. **REAPER控制工具**（基于MCP）：
   - 播放控制：播放、暂停、停止
   - 录音控制：开始录音、停止录音
   - 轨道管理：新建轨道、删除轨道、静音/独奏
   - 剪辑编辑：剪切、复制、粘贴、拆分
   - 工程管理：新建/打开/保存工程、导出音频

2. **飞书表格工具**（基于飞书API）：
   - 项目管理：创建项目、更新状态、添加任务
   - 任务跟踪：分配任务、更新进度、标记完成
   - 团队协作：添加成员、设置权限、通知提醒

3. **音频专业工具**（基于RAG）：
   - 知识查询：音频术语、效果器使用、混音技巧
   - 参数建议：EQ设置、压缩参数、混响配置

## 具体实现方案

### 1. MCP客户端实现 (`reaper_mcp_client.py`)

```python
class ReaperMCPClient:
    """REAPER MCP客户端"""
    
    def __init__(self, host="localhost", port=8000):
        self.host = host
        self.port = port
        self.session = None
        
    async def connect(self):
        """连接REAPER MCP服务器"""
        # 支持多种连接方式：WebSocket、HTTP、OSC
        # REAPER可能通过ReaScript或插件暴露MCP接口
        
    async def execute_action(self, action_id: int, params: dict = None) -> dict:
        """执行REAPER Action ID"""
        # 调用MCP工具的call_tool方法
        # 返回执行结果状态
        
    async def get_project_info(self) -> dict:
        """获取当前工程信息"""
        
    async def list_available_actions(self) -> list:
        """列出所有可用的Action ID"""
```

### 2. 飞书表格客户端 (`feishu_sheet_client.py`)

```python
class FeishuSheetClient:
    """飞书表格客户端"""
    
    def __init__(self, app_id, app_secret):
        self.app_id = app_id
        self.app_secret = app_secret
        self.access_token = None
        
    def get_access_token(self) -> str:
        """获取飞书访问令牌"""
        
    def create_project_sheet(self, project_name: str) -> str:
        """创建项目管理表格"""
        # 返回表格token
        
    def add_project_task(self, sheet_token: str, task_data: dict) -> str:
        """添加项目任务"""
        
    def update_task_status(self, sheet_token: str, task_id: str, status: str) -> bool:
        """更新任务状态"""
        
    def get_project_report(self, sheet_token: str) -> dict:
        """生成项目报告"""
```

### 3. 工具注册表 (`tool_registry.py`)

```python
@dataclass
class Tool:
    name: str
    description: str
    parameters: dict
    handler: callable
    
class ToolRegistry:
    def __init__(self):
        self.tools = {}
        
    def register(self, tool: Tool):
        """注册工具"""
        
    def get_tool(self, name: str) -> Optional[Tool]:
        """获取工具"""
        
    def list_tools(self) -> list:
        """列出所有工具"""
        
    def match_tool(self, query: str) -> Optional[Tool]:
        """根据查询匹配工具"""
```

### 4. 提示词引擎 (`prompt_engine.py`)

```python
class PromptEngine:
    """提示词引擎 - 处理DeepSeek不支持function calling的替代方案"""
    
    def __init__(self, tool_registry):
        self.tool_registry = tool_registry
        
    def build_system_prompt(self, base_prompt: str) -> str:
        """构建包含工具描述的系统提示词"""
        tool_descriptions = self._format_tool_descriptions()
        return f"""{base_prompt}

可用工具：
{tool_descriptions}

工具调用格式：
当需要使用工具时，请输出：
<tool_call>
<tool_name>工具名称</tool_name>
<parameters>
参数1: 值1
参数2: 值2
</parameters>
</tool_call>

注意：
1. 一次只能调用一个工具
2. 工具调用后我会提供执行结果
3. 根据工具结果继续回答用户问题
"""
    
    def parse_tool_call(self, response: str) -> Optional[dict]:
        """从模型响应中解析工具调用"""
        # 解析<tool_call>标记
        # 提取工具名称和参数
        
    def format_tool_result(self, tool_name: str, result: dict) -> str:
        """格式化工具执行结果"""
```

### 5. 工具编排器 (`tool_orchestrator.py`)

```python
class ToolOrchestrator:
    """工具编排器 - 决定何时以及如何调用工具"""
    
    def __init__(self, reaper_client, sheet_client, tool_registry):
        self.reaper_client = reaper_client
        self.sheet_client = sheet_client
        self.tool_registry = tool_registry
        self.prompt_engine = PromptEngine(tool_registry)
        
    async def process_message(self, user_message: str, history: list) -> dict:
        """处理用户消息，可能包含工具调用"""
        
        # 步骤1: 意图识别 - 判断是否需要工具调用
        needs_tool = self._detect_tool_intent(user_message)
        
        if not needs_tool:
            # 直接知识库问答
            return {"type": "knowledge", "response": user_message}
        
        # 步骤2: 构建包含工具描述的提示词
        system_prompt = self.prompt_engine.build_system_prompt(SYSTEM_PROMPT)
        messages = [{"role": "system", "content": system_prompt}] + history
        
        # 步骤3: 调用DeepSeek
        response = await self.deepseek.chat_completion(messages)
        
        # 步骤4: 解析工具调用
        tool_call = self.prompt_engine.parse_tool_call(response)
        
        if tool_call:
            # 步骤5: 执行工具调用
            result = await self._execute_tool(tool_call)
            
            # 步骤6: 将结果加入对话历史，继续生成最终回答
            final_response = await self._generate_final_response(
                history, user_message, tool_call, result
            )
            
            return {
                "type": "tool_call",
                "tool_name": tool_call["name"],
                "result": result,
                "response": final_response
            }
        
        return {"type": "direct", "response": response}
```

### 6. 与现有FeishuAgent集成 (`main.py`修改)

```python
class FeishuAgent:
    def __init__(self):
        # 现有初始化...
        
        # 新增：工具系统初始化
        self.reaper_client = ReaperMCPClient(
            host=os.getenv("REAPER_MCP_HOST", "localhost"),
            port=int(os.getenv("REAPER_MCP_PORT", "8000"))
        )
        
        self.sheet_client = FeishuSheetClient(
            app_id=os.getenv("FEISHU_APP_ID"),
            app_secret=os.getenv("FEISHU_APP_SECRET")
        )
        
        self.tool_registry = ToolRegistry()
        self._register_tools()
        
        self.tool_orchestrator = ToolOrchestrator(
            reaper_client=self.reaper_client,
            sheet_client=self.sheet_client,
            tool_registry=self.tool_registry
        )
    
    def _register_tools(self):
        """注册所有可用工具"""
        # REAPER控制工具
        self.tool_registry.register(Tool(
            name="reaper_play",
            description="控制REAPER播放/暂停",
            parameters={"action": "播放控制类型"},
            handler=self.reaper_client.execute_action
        ))
        
        # 飞书表格工具
        self.tool_registry.register(Tool(
            name="feishu_create_project",
            description="在飞书表格中创建新项目",
            parameters={"project_name": "项目名称", "description": "项目描述"},
            handler=self.sheet_client.create_project_sheet
        ))
        
        # 更多工具...
    
    async def process_message(self, user_message: str, user_id: str):
        """修改现有process_message方法支持工具调用"""
        
        # 现有逻辑：获取会话、RAG检索
        
        # 新增：工具调用处理
        if self._should_use_tools(user_message):
            result = await self.tool_orchestrator.process_message(
                user_message, 
                session.get_messages_for_api()
            )
            
            if result["type"] == "tool_call":
                # 记录工具调用历史
                session.add_tool_call(
                    tool_name=result["tool_name"],
                    result=result["result"]
                )
                self.conv_manager.save(session)
                
            return self._format_tool_response(result)
        
        # 原有逻辑继续...
```

## 关键文件修改清单

### 新增文件
1. `/Volumes/T7/Work/Feishu_Agent_Demo/reaper_mcp_client.py` - REAPER MCP客户端
2. `/Volumes/T7/Work/Feishu_Agent_Demo/feishu_sheet_client.py` - 飞书表格客户端
3. `/Volumes/T7/Work/Feishu_Agent_Demo/tool_registry.py` - 工具注册表
4. `/Volumes/T7/Work/Feishu_Agent_Demo/prompt_engine.py` - 提示词引擎
5. `/Volumes/T7/Work/Feishu_Agent_Demo/tool_orchestrator.py` - 工具编排器

### 修改文件
1. `/Volumes/T7/Work/Feishu_Agent_Demo/main.py` - 集成工具系统到FeishuAgent
2. `/Volumes/T7/Work/Feishu_Agent_Demo/requirements.txt` - 添加新依赖
3. `/Volumes/T7/Work/Feishu_Agent_Demo/.env.example` - 添加新配置

### 配置文件
4. `/Volumes/T7/Work/Feishu_Agent_Demo/config/tools.yaml` - 工具配置文件（可选）

## 依赖项更新

### requirements.txt 新增
```txt
# MCP协议支持
mcp>=0.1.0
websockets>=11.0.0

# 异步支持
aiohttp>=3.9.0

# 飞书SDK（可选，增强表格支持）
lark-oapi>=1.0.0

# YAML配置（可选）
pyyaml>=6.0.0
```

## 配置变更

### .env.example 新增
```env
# ====================
# REAPER MCP 配置
# ====================
REAPER_MCP_ENABLED=true
REAPER_MCP_HOST=localhost
REAPER_MCP_PORT=8000
REAPER_MCP_PROTOCOL=ws  # ws, http, osc

# ====================
# 飞书表格配置
# ====================
FEISHU_SHEET_ENABLED=true
FEISHU_DEFAULT_SHEET_TOKEN=  # 默认项目管理表格

# ====================
# 工具系统配置
# ====================
TOOL_CALL_ENABLED=true
MAX_TOOL_CALLS_PER_TURN=2
TOOL_CALL_TIMEOUT=30
TOOL_FALLBACK_ENABLED=true

# ====================
# 项目管理配置
# ====================
PROJECT_SHEET_TEMPLATE=default
TASK_STATUS_FLOW=["待开始", "进行中", "待审核", "已完成"]
```

## 实施步骤

### 第一阶段：基础架构（2-3天）
1. 创建工具抽象层（ToolRegistry, PromptEngine）
2. 实现REAPER MCP客户端基础框架
3. 实现飞书表格客户端基础框架
4. 更新依赖和配置

### 第二阶段：核心功能（3-4天）
1. 实现REAPER Action ID的MCP调用
2. 实现飞书表格的增删改查操作
3. 集成工具系统到FeishuAgent
4. 实现工具调用流程

### 第三阶段：高级功能（2-3天）
1. 项目管理逻辑（项目创建、任务分配、状态跟踪）
2. 工具组合和编排
3. 错误处理和降级策略
4. 性能优化

### 第四阶段：测试部署（1-2天）
1. 单元测试和集成测试
2. 端到端测试（模拟完整工作流）
3. 文档编写
4. 生产环境部署

## 测试方案

### 单元测试
1. `test_reaper_mcp_client.py` - REAPER MCP客户端测试
2. `test_feishu_sheet_client.py` - 飞书表格客户端测试
3. `test_tool_registry.py` - 工具注册表测试
4. `test_prompt_engine.py` - 提示词引擎测试

### 集成测试
1. `test_tool_integration.py` - 工具系统集成测试
2. `test_reaper_control.py` - REAPER控制集成测试
3. `test_project_management.py` - 项目管理集成测试

### 端到端测试场景
1. **场景1：创建新项目**
   ```
   用户："帮我在REAPER中创建新工程，并在飞书表格中记录"
   → 创建REAPER工程
   → 在飞书表格中创建项目记录
   → 返回项目信息
   ```

2. **场景2：音频处理工作流**
   ```
   用户："录制一段人声，然后添加压缩效果"
   → 开始录音（REAPER工具）
   → 停止录音
   → 应用压缩效果器
   → 更新任务状态（飞书表格）
   ```

3. **场景3：团队协作**
   ```
   用户："把这段混音任务分配给小王，标记为进行中"
   → 更新飞书表格任务分配
   → 发送飞书通知给小王
   → 更新任务状态
   ```

## 生产环境考虑

### 安全性
1. **REAPER操作权限控制**：限制敏感操作（如删除工程）
2. **飞书表格权限**：基于角色控制表格访问
3. **输入验证**：验证所有工具参数，防止注入攻击
4. **访问日志**：记录所有工具调用和用户操作

### 可靠性
1. **连接重试**：MCP连接失败时自动重试
2. **超时处理**：设置合理的操作超时时间
3. **降级策略**：MCP不可用时降级到无工具模式
4. **健康检查**：定期检查REAPER和飞书服务状态

### 可观测性
1. **详细日志**：记录工具调用详情、参数、结果
2. **性能监控**：监控工具调用响应时间和成功率
3. **业务指标**：统计项目创建数、任务完成率等
4. **告警机制**：工具调用失败、超时、错误率高等告警

## 扩展性设计

### 插件化工具系统
支持动态添加新工具类型：
```python
class ToolPlugin:
    def get_tools(self) -> List[Tool]:
        """返回插件提供的工具列表"""
    
    def initialize(self, config: dict):
        """初始化插件"""
    
    def cleanup(self):
        """清理插件资源"""
```

### 配置驱动工具发现
通过配置文件动态加载工具：
```yaml
tools:
  reaper_play:
    class: reaper_mcp_client.ReaperPlayTool
    config:
      action_id: 40001
      timeout: 10
  
  feishu_create_task:
    class: feishu_sheet_client.CreateTaskTool
    config:
      sheet_token: ${FEISHU_DEFAULT_SHEET_TOKEN}
```

### 工具组合和编排
支持定义工具工作流：
```yaml
workflows:
  new_recording_session:
    steps:
      - tool: feishu_create_project
        params:
          project_name: "新录音项目"
      - tool: reaper_new_project
      - tool: reaper_add_track
        params:
          track_name: "人声"
      - tool: feishu_add_task
        params:
          task_name: "录制人声"
          assignee: "当前用户"
```

## 风险与缓解

### 技术风险
1. **REAPER MCP协议不成熟**：REAPER可能没有官方MCP支持
   - 缓解：使用ReaScript API + WebSocket封装为MCP服务器
   
2. **DeepSeek不支持function calling**：
   - 缓解：使用提示词工程和结构化输出解析

3. **异步与现有同步架构冲突**：
   - 缓解：使用asyncio.to_thread或单独线程处理异步调用

### 业务风险
1. **操作安全**：误操作可能损坏工程文件
   - 缓解：实现操作确认、操作回退、工程备份

2. **数据一致性**：REAPER状态与飞书表格可能不同步
   - 缓解：实现状态同步机制、定期一致性检查

## 成功指标
1. **功能完整性**：支持所有29个REAPER Action ID
2. **工具调用成功率**：>95%的工具调用成功
3. **响应时间**：工具调用平均响应时间<3秒
4. **用户体验**：自然语言到工具调用的准确率>90%
5. **系统稳定性**：MTBF > 30天

## 验收标准
1. 用户可以通过自然语言控制REAPER完成音频创作操作
2. 项目管理信息能正确同步到飞书表格
3. 工具调用失败时有明确的错误提示和降级处理
4. 系统在生产环境稳定运行，无明显性能问题
5. 有完整的监控和日志，便于问题排查

---

**关键文件路径**：
- `/Volumes/T7/Work/Feishu_Agent_Demo/main.py` - 主入口，需要集成工具系统
- `/Volumes/T7/Work/Feishu_Agent_Demo/reaper_mcp_client.py` - REAPER MCP核心实现
- `/Volumes/T7/Work/Feishu_Agent_Demo/feishu_sheet_client.py` - 飞书表格集成
- `/Volumes/T7/Work/Feishu_Agent_Demo/tool_orchestrator.py` - 工具编排逻辑
- `/Volumes/T7/Work/Feishu_Agent_Demo/data/backup/reaper_actions.md` - REAPER Action ID映射表