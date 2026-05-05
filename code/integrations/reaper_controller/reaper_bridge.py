import json
import os
import time


class ReaperBridge:
    """REAPER控制桥梁，负责与REAPER端的Lua网关通信"""
    
    def __init__(self, db_path=None, shared_dir=None):
        """
        初始化 REAPER 控制桥梁
        :param db_path: API 知识库 json 路径 (用于拦截校验)，默认使用项目内的data/reaper_api_db.json
        :param shared_dir: 存放通信文件的绝对路径目录，默认使用项目内的shared_dir
        """
        # 默认路径配置
        if db_path is None:
            db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "reaper_api_db.json")
        
        if shared_dir is None:
            shared_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "shared_dir")
        
        self.shared_dir = shared_dir
        self.task_file = os.path.join(shared_dir, "agent_task.lua")
        self.result_file = os.path.join(shared_dir, "agent_result.txt")
        
        # 确保共享目录存在
        os.makedirs(shared_dir, exist_ok=True)
        
        # 加载API白名单
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"找不到知识库文件: {db_path}")
        with open(db_path, 'r', encoding='utf-8') as f:
            self.api_db = json.load(f)
            self.valid_api_names = {api["name"] for api in self.api_db}

    def _validate_command(self, lua_code, required_apis):
        """风险拦截与指令校验"""
        # 危险关键词拦截
        dangerous_keywords = ["os.execute", "os.remove", "io.popen", "io.open", "os.rename", "os.mkdir", "os.rmdir"]
        for kw in dangerous_keywords:
            if kw in lua_code:
                return False, f"❌ 权限拦截：禁止调用危险系统函数 '{kw}'"
        
        # API白名单校验
        for api in required_apis:
            api_name = api.replace("reaper.", "")
            if api_name not in self.valid_api_names and api_name not in ["Undo_BeginBlock", "Undo_EndBlock", "UpdateArrange"]:
                return False, f"❌ 校验失败：调用了未授权或不存在的 API '{api_name}'"
        
        # 撤销点保护校验
        if "reaper.Undo_BeginBlock" not in lua_code:
            return False, "❌ 校验失败：未包含撤销点保护 (Undo_BeginBlock)"
        
        if "reaper.Undo_EndBlock" not in lua_code:
            return False, "❌ 校验失败：未包含撤销点结束 (Undo_EndBlock)"
        
        return True, "✅ 校验通过"

    def execute_lua(self, lua_code, required_apis):
        """
        发送指令并获取执行结果
        :param lua_code: 大模型生成的纯Lua可执行代码
        :param required_apis: 声明该脚本中实际调用的REAPER API名称数组
        :return: 包含成功或失败详情的字符串
        """
        # 执行安全校验
        is_valid, val_msg = self._validate_command(lua_code, required_apis)
        if not is_valid:
            return val_msg
        
        # 清理遗留文件
        if os.path.exists(self.result_file):
            os.remove(self.result_file)
        if os.path.exists(self.task_file):
            os.remove(self.task_file)

        # 写入任务文件
        with open(self.task_file, "w", encoding="utf-8") as f:
            f.write(lua_code)
        
        # 等待执行结果
        timeout = 15
        start_time = time.time()
        
        while not os.path.exists(self.result_file):
            if time.time() - start_time > timeout:
                if os.path.exists(self.task_file):
                    os.remove(self.task_file)
                return "❌ 执行超时：REAPER 底层网关无响应。"
            time.sleep(0.1)
        
        # 读取并返回结果
        with open(self.result_file, "r", encoding="utf-8") as f:
            raw_result = f.read()
        os.remove(self.result_file)
        
        return f"✅ 底层执行成功" if "✅" in raw_result else f"⚠️ 底层抛出异常：{raw_result}"
