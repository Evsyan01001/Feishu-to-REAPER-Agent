---
name: "audio-workstation-control"
description: "控制REAPER音频工作站执行各类操作，包括轨道管理、播放录音、剪辑导出、效果器调整等。Invoke when user asks for REAPER operations, audio track control, playback/recording commands, or any audio workstation manipulation."
---

# 音频工作站控制技能 (Audio Workstation Control)

## 功能说明
该技能实现了与REAPER数字音频工作站的双向通信能力，支持通过自然语言指令控制REAPER执行各种音频创作操作。

## 核心能力
1. **轨道管理**：创建、删除、重命名、静音、独奏轨道
2. **传输控制**：播放、暂停、停止、录音、快进、快退、定位时间轴
3. **剪辑操作**：分割、合并、移动、删除音频片段
4. **效果器控制**：添加、调整、旁路各种音频效果器
5. **参数调整**：调节音量、声像、增益、EQ、压缩等参数
6. **导出功能**：导出音频文件到指定格式和路径

## 使用方式
当用户发送以下类型的指令时自动调用此技能：
- 包含"REAPER"、"轨道"、"播放"、"录音"、"剪辑"、"导出"、"效果器"等关键词
- 任何需要操作音频工作站的自然语言指令

## 技术实现
- 基于三层解耦架构：Agent层 → Python Bridge层 → Lua Gateway层
- 内置780个REAPER API白名单，安全校验机制防止非法操作
- 强制撤销点保护，所有操作支持Ctrl+Z回退
- 超时机制避免REAPER无响应

## 调用示例
用户指令："在REAPER中创建一个新的音频轨道"
自动生成的工具调用：
```json
{
  "name": "execute_reaper_lua",
  "parameters": {
    "lua_script": "reaper.Undo_BeginBlock()\nlocal track = reaper.InsertTrackAtIndex(reaper.CountTracks(0), true)\nreaper.GetSetMediaTrackInfo_String(track, 'P_NAME', '新建音频轨道', true)\nreaper.Undo_EndBlock('创建新音频轨道', -1)",
    "used_apis": ["reaper.Undo_BeginBlock", "reaper.CountTracks", "reaper.InsertTrackAtIndex", "reaper.GetSetMediaTrackInfo_String", "reaper.Undo_EndBlock"]
  }
}
```
