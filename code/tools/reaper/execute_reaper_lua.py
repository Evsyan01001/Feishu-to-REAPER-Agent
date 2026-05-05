"""
REAPER Lua执行工具
用于执行REAPER自动化脚本，控制音频工作站操作
"""
from typing import Dict, Any, Optional, List
from code.tools.base_tool import BaseTool
from code.integrations.reaper_controller.reaper_bridge import ReaperBridge


class ExecuteReaperLuaTool(BaseTool):
    # 工具元信息
    tool_id: str = "execute_reaper_lua"
    name: str = "execute_reaper_lua"
    description: str = "执行 REAPER 自动化脚本。当用户需要对音频轨道进行增删改查、静音、播放等控制时调用此工具。"
    keywords: List[str] = ["reaper", "音频", "轨道", "播放", "录音", "剪辑", "导出", "效果器"]
    parameters: Dict[str, Any] = {
        "lua_script": {
            "type": "string",
            "required": True,
            "description": "大模型生成的纯 Lua 可执行代码。必须使用 reaper. 前缀，且必须包含 Undo_BeginBlock 和 Undo_EndBlock。"
        },
        "used_apis": {
            "type": "array",
            "items": {
                "type": "string"
            },
            "required": True,
            "description": "声明该脚本中实际调用了哪些 REAPER API 的名称。"
        }
    }

    def __init__(self):
        self.bridge = ReaperBridge()

    def parse_intent(self, user_input: str, **context) -> Optional[Dict[str, Any]]:
        """
        解析用户意图，生成对应的Lua脚本和API参数
        """
        user_input_lower = user_input.lower()
        
        # 处理"开始录音"指令
        if "开始录音" in user_input or "录音" in user_input and ("开始" in user_input or "启动" in user_input):
            lua_script = """
reaper.Undo_BeginBlock()
-- 确保至少有一个轨道被启用录音
local track_count = reaper.CountTracks(0)
if track_count == 0 then
    -- 创建新轨道
    local track = reaper.InsertTrackAtIndex(0, true)
    reaper.SetMediaTrackInfo_Value(track, "I_RECARM", 1) -- 启用录音
    reaper.GetSetMediaTrackInfo_String(track, "P_NAME", "录音轨道", true)
else
    -- 尝试找到已启用录音的轨道，没有的话启用第一个轨道
    local rec_armed_found = false
    for i = 0, track_count - 1 do
        local track = reaper.GetTrack(0, i)
        if reaper.GetMediaTrackInfo_Value(track, "I_RECARM") == 1 then
            rec_armed_found = true
            break
        end
    end
    if not rec_armed_found then
        local first_track = reaper.GetTrack(0, 0)
        reaper.SetMediaTrackInfo_Value(first_track, "I_RECARM", 1)
    end
end
-- 开始录音
reaper.CSurf_OnRecord()
reaper.Undo_EndBlock("开始录音", -1)
            """
            return {
                "lua_script": lua_script.strip(),
                "used_apis": [
                    "reaper.Undo_BeginBlock",
                    "reaper.CountTracks",
                    "reaper.InsertTrackAtIndex",
                    "reaper.SetMediaTrackInfo_Value",
                    "reaper.GetSetMediaTrackInfo_String",
                    "reaper.GetTrack",
                    "reaper.GetMediaTrackInfo_Value",
                    "reaper.CSurf_OnRecord",
                    "reaper.Undo_EndBlock"
                ]
            }
        
        # 处理"停止录音"或"停止"指令
        if "停止录音" in user_input or "停止" in user_input and ("录音" in user_input or "播放" in user_input):
            lua_script = """
reaper.Undo_BeginBlock()
reaper.CSurf_OnStop()
reaper.Undo_EndBlock("停止录音/播放", -1)
            """
            return {
                "lua_script": lua_script.strip(),
                "used_apis": [
                    "reaper.Undo_BeginBlock",
                    "reaper.CSurf_OnStop",
                    "reaper.Undo_EndBlock"
                ]
            }
        
        # 处理"播放"指令
        if "开始播放" in user_input or ("播放" in user_input and "开始" in user_input):
            lua_script = """
reaper.Undo_BeginBlock()
reaper.CSurf_OnPlay()
reaper.Undo_EndBlock("开始播放", -1)
            """
            return {
                "lua_script": lua_script.strip(),
                "used_apis": [
                    "reaper.Undo_BeginBlock",
                    "reaper.CSurf_OnPlay",
                    "reaper.Undo_EndBlock"
                ]
            }
        
        # 处理"暂停"指令
        if "暂停" in user_input:
            lua_script = """
reaper.Undo_BeginBlock()
reaper.CSurf_OnPause()
reaper.Undo_EndBlock("暂停播放", -1)
            """
            return {
                "lua_script": lua_script.strip(),
                "used_apis": [
                    "reaper.Undo_BeginBlock",
                    "reaper.CSurf_OnPause",
                    "reaper.Undo_EndBlock"
                ]
            }
        
        # 处理"取消所有静音"指令
        if "取消静音" in user_input and ("所有" in user_input or "全部" in user_input) or "所有轨道的静音都取消" in user_input:
            lua_script = """
reaper.Undo_BeginBlock()
local track_count = reaper.CountTracks(0)
for i = 0, track_count - 1 do
    local track = reaper.GetTrack(0, i)
    reaper.SetMediaTrackInfo_Value(track, "B_MUTE", 0) -- 取消静音
end
reaper.UpdateArrange()
reaper.Undo_EndBlock("取消所有轨道静音", -1)
            """
            return {
                "lua_script": lua_script.strip(),
                "used_apis": [
                    "reaper.Undo_BeginBlock",
                    "reaper.CountTracks",
                    "reaper.GetTrack",
                    "reaper.SetMediaTrackInfo_Value",
                    "reaper.UpdateArrange",
                    "reaper.Undo_EndBlock"
                ]
            }
        
        # 处理"创建轨道"指令
        if "创建轨道" in user_input or "新建轨道" in user_input:
            lua_script = """
reaper.Undo_BeginBlock()
local track_count = reaper.CountTracks(0)
local track = reaper.InsertTrackAtIndex(track_count, true)
reaper.GetSetMediaTrackInfo_String(track, "P_NAME", "新建轨道", true)
reaper.Undo_EndBlock("创建新轨道", -1)
            """
            return {
                "lua_script": lua_script.strip(),
                "used_apis": [
                    "reaper.Undo_BeginBlock",
                    "reaper.CountTracks",
                    "reaper.InsertTrackAtIndex",
                    "reaper.GetSetMediaTrackInfo_String",
                    "reaper.Undo_EndBlock"
                ]
            }
        
        # 其他指令暂时返回None，后续由大模型Function Calling处理
        return None

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行REAPER Lua脚本
        """
        lua_script = params.get("lua_script", "")
        used_apis = params.get("used_apis", [])
        
        if not lua_script:
            return {
                "success": False,
                "message": "❌ 参数错误：lua_script 不能为空"
            }
        
        if not used_apis:
            return {
                "success": False,
                "message": "❌ 参数错误：used_apis 不能为空"
            }
        
        try:
            result = self.bridge.execute_lua(lua_script, used_apis)
            return {
                "success": "✅" in result,
                "message": result
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"❌ 执行异常：{str(e)}"
            }
