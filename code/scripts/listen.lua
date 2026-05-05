-- =====================================================================
-- Feishu Agent <-> REAPER MCP 桥接执行端 (终极防弹版)
-- 支持解析自定义 Skill 指令与 reaper_actions.md 全量 Action ID
-- =====================================================================

-- 与 Python MCP Tool/Skill 约定的本地通信信箱
local file_path = "C:\\Users\\Public\\reaper_cmd.txt"

-- 辅助函数：清除字符串两端可能导致匹配失败的隐形字符（空格、换行等）
local function trim(s)
    return (s:gsub("^%s*(.-)%s*$", "%1"))
end

-- 核心逻辑：解析并执行指令
function ProcessCommand(data)
    -- 1. 拆分指令协议，格式统一为 "动作类型|参数值"
    -- 例如: "ACTION|40001" 或 "GAIN|3" 或 "DENOISE|1"
    local raw_action, raw_value = data:match("([^|]+)|([^|]+)")
    if not raw_action then return end

    local action = trim(raw_action)
    local value = trim(raw_value)

    reaper.ShowConsoleMsg("=> ⚙️ [Feishu Agent] 请求执行: [" .. action .. "] 参数: [" .. value .. "]\n")

    -- =========================================================
    -- 核心模块 A：标准 Action ID 触发 (对接 reaper_actions.md)
    -- =========================================================
    if action == "ACTION" then
        local action_id = tonumber(value)
        if action_id then
            -- 调用 REAPER 内部对应的功能 (如 40001=播放, 1013=录音)
            reaper.Main_OnCommand(action_id, 0)
            reaper.ShowConsoleMsg("=> ✅ 成功！已执行 Action ID: " .. action_id .. "\n")
        else
            reaper.ShowConsoleMsg("=> ❌ 失败：接收到无效的 Action ID 格式\n")
        end

    -- =========================================================
    -- 核心模块 B：自定义复杂音频操作 Skill (增益、降噪等)
    -- =========================================================
    elseif action == "GAIN" then
        local track = reaper.GetSelectedTrack(0, 0)
        if track then
            local db = tonumber(value)
            -- 内部 dB 数学换算
            local vol = math.exp(db * 0.115129254) 
            reaper.SetMediaTrackInfo_Value(track, "D_VOL", vol)
            reaper.ShowConsoleMsg("=> ✅ 成功！选中轨道音量已调整为 " .. db .. " dB\n")
        else
            reaper.ShowConsoleMsg("=> ❌ 失败：未选中任何音频轨道！\n")
        end

    elseif action == "DENOISE" then
        local track = reaper.GetSelectedTrack(0, 0)
        if track then
            -- 强制添加降噪插件 ReaFir 并弹出 UI 界面供用户核对
            local fx_index = reaper.TrackFX_AddByName(track, "ReaFir", false, 1)
            reaper.TrackFX_Show(track, fx_index, 3)
            reaper.ShowConsoleMsg("=> ✅ 成功！已挂载降噪插件并弹出界面\n")
        else
            reaper.ShowConsoleMsg("=> ❌ 失败：未选中任何音频轨道！\n")
        end

    elseif action == "EXPORT" then
        -- 触发 Action ID: 40162 (Render)
        reaper.Main_OnCommand(40162, 0)
        reaper.ShowConsoleMsg("=> ✅ 成功！已唤起导出渲染界面\n")

    else
        reaper.ShowConsoleMsg("=> ❌ 失败：未知的动作类型 [" .. action .. "]\n")
    end
end

-- 轮询监听主循环
function MainLoop()
    local file = io.open(file_path, "r")
    if file then
        local data = file:read("*a")
        file:close()
        
        -- 如果信箱内有 Python Agent 投递的内容
        if data and data ~= "" then
            reaper.ShowConsoleMsg("\n【收到新指令】: " .. data .. "\n")
            
            -- 执行指令
            ProcessCommand(data)
            
            -- 阅后即焚，防止同一指令被重复执行
            local clear_file = io.open(file_path, "w")
            if clear_file then
                clear_file:write("")
                clear_file:close()
            end
        end
    end
    -- 借助 REAPER 内部定时器实现非阻塞后台常驻
    reaper.defer(MainLoop)
end

-- 启动信息
reaper.ShowConsoleMsg("==================================================\n")
reaper.ShowConsoleMsg("🚀 Feishu Agent - REAPER 桥接端已启动并常驻后台\n")
reaper.ShowConsoleMsg("📖 已支持 `reaper_actions.md` 全量 29 个指令\n")
reaper.ShowConsoleMsg("==================================================\n")

MainLoop()