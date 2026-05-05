"""
REAPER 创建轨道工具
"""
import re
from typing import Dict, Any, Optional
from tools.base_tool import BaseTool

class CreateTrackTool(BaseTool):
    tool_id = "reaper.create_track"
    name = "创建音频轨道"
    description = "在REAPER中创建新的音频/MIDI轨道"
    keywords = ["创建轨道", "新建轨道", "加轨道", "添加音频轨道", "创建MIDI轨道"]
    parameters = {
        "track_name": {"type": "string", "required": False, "description": "轨道名称，默认新建轨道"},
        "track_type": {"type": "string", "required": False, "description": "轨道类型：audio/midi，默认audio"},
        "count": {"type": "integer", "required": False, "description": "创建数量，默认1"}
    }

    def parse_intent(self, user_input: str, **context) -> Optional[Dict[str, Any]]:
        """解析创建轨道的意图和参数"""
        params = {}
        
        # 识别轨道类型
        if "MIDI" in user_input or "midi" in user_input:
            params["track_type"] = "midi"
        else:
            params["track_type"] = "audio"
            
        # 识别轨道数量
        count_match = re.search(r"(\d+)(个|条)轨道", user_input)
        if count_match:
            params["count"] = int(count_match.group(1))
        else:
            params["count"] = 1
            
        # 识别轨道名称（简单匹配，后续可优化为LLM提取）
        name_match = re.search(r"命名为['\"](.*?)['\"]|叫['\"](.*?)['\"]", user_input)
        if name_match:
            params["track_name"] = name_match.group(1) or name_match.group(2)
        else:
            params["track_name"] = f"新建{params['track_type']}轨道"
            
        return params

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行创建轨道操作"""
        track_name = params.get("track_name", "新建轨道")
        track_type = params.get("track_type", "audio")
        count = params.get("count", 1)
        
        # 生成Lua代码
        lua_code = f"""
        local count = {count}
        local track_type = "{track_type}"
        local track_name = "{track_name}"
        
        for i = 1, count do
            local track = reaper.InsertTrackAtIndex(reaper.CountTracks(0), true)
            reaper.GetSetMediaTrackInfo_String(track, "P_NAME", track_name .. (count > 1 and " " .. i or ""), true)
            
            -- 设置轨道类型
            if track_type == "midi" then
                reaper.SetMediaTrackInfo_Value(track, "I_RECARM", 1)
                -- 添加MIDI输入
            end
        end
        
        reaper.UpdateArrange()
        return "成功创建" .. count .. "条" .. track_type .. "轨道"
        """
        
        # 这里实际调用REAPER通信层执行，暂时返回模拟结果
        return {
            "success": True,
            "message": f"✅ 将创建{count}条{track_type}轨道：{track_name}",
            "lua_code": lua_code,
            "params": params
        }
