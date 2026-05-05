"""
飞书机器人Webhook服务
实现：接收飞书事件回调、签名验证、消息处理、回复消息
"""
import os
import json
import hmac
import hashlib
import base64
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import uvicorn
import requests
from dotenv import load_dotenv
from main.feishu_agent import FeishuAgent
import time
import logging

load_dotenv()

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Feishu Agent Webhook")
agent = FeishuAgent()

# 飞书配置
FEISHU_APP_ID = os.getenv("FEISHU_APP_ID")
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET")
FEISHU_ENCRYPT_KEY = os.getenv("FEISHU_ENCRYPT_KEY")
FEISHU_VERIFICATION_TOKEN = os.getenv("FEISHU_VERIFICATION_TOKEN")

# 飞书API端点
FEISHU_BASE_URL = "https://open.feishu.cn"

# 缓存tenant_access_token
_tenant_token = {
    "token": None,
    "expire_time": 0
}

def get_tenant_access_token() -> str:
    """获取tenant_access_token，带缓存"""
    global _tenant_token
    now = int(time.time())
    
    # 如果token还有效（提前5分钟过期）
    if _tenant_token["token"] and _tenant_token["expire_time"] > now + 300:
        return _tenant_token["token"]
    
    try:
        url = f"{FEISHU_BASE_URL}/open-apis/auth/v3/tenant_access_token/internal"
        headers = {"Content-Type": "application/json"}
        data = {
            "app_id": FEISHU_APP_ID,
            "app_secret": FEISHU_APP_SECRET
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=10)
        response.raise_for_status()
        result = response.json()
        
        if result.get("code") != 0:
            logger.error(f"获取tenant_access_token失败: {result}")
            return ""
        
        _tenant_token["token"] = result["tenant_access_token"]
        _tenant_token["expire_time"] = now + result["expire"]
        logger.info("tenant_access_token更新成功")
        return _tenant_token["token"]
        
    except Exception as e:
        logger.error(f"获取tenant_access_token异常: {e}")
        return ""

def verify_signature(timestamp: str, nonce: str, body: bytes, signature: str) -> bool:
    """验证飞书请求签名"""
    if not FEISHU_ENCRYPT_KEY:
        return True
    
    try:
        key = FEISHU_ENCRYPT_KEY.encode("utf-8")
        msg = (timestamp + nonce).encode("utf-8") + body
        hmac_result = hmac.new(key, msg, hashlib.sha256).digest()
        calculated_signature = base64.b64encode(hmac_result).decode("utf-8")
        return hmac.compare_digest(calculated_signature, signature)
    except Exception as e:
        logger.error(f"签名验证异常: {e}")
        return False

def decrypt_data(encrypted_data: str) -> dict:
    """解密飞书加密数据"""
    if not FEISHU_ENCRYPT_KEY:
        return {}
    
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.backends import default_backend
        
        key = FEISHU_ENCRYPT_KEY.encode("utf-8")
        key = hashlib.sha256(key).digest()
        
        encrypted = base64.b64decode(encrypted_data)
        iv = encrypted[:16]
        ciphertext = encrypted[16:]
        
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        padded_data = decryptor.update(ciphertext) + decryptor.finalize()
        
        # 移除PKCS7填充
        pad_length = padded_data[-1]
        data = padded_data[:-pad_length].decode("utf-8")
        return json.loads(data)
        
    except Exception as e:
        logger.error(f"解密失败: {e}")
        return {}

def send_feishu_message(open_id: str, content: str, msg_type: str = "text") -> bool:
    """发送消息到飞书"""
    try:
        token = get_tenant_access_token()
        if not token:
            return False
        
        url = f"{FEISHU_BASE_URL}/open-apis/im/v1/messages"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        data = {
            "receive_id": open_id,
            "msg_type": msg_type,
            "content": json.dumps({"text": content}, ensure_ascii=False)
        }
        
        params = {"receive_id_type": "open_id"}
        response = requests.post(url, headers=headers, json=data, params=params, timeout=10)
        response.raise_for_status()
        result = response.json()
        
        if result.get("code") != 0:
            logger.error(f"发送消息失败: {result}")
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"发送消息异常: {e}")
        return False

@app.post("/webhook/feishu")
async def feishu_webhook(request: Request):
    """飞书事件回调入口"""
    try:
        # 获取请求头
        timestamp = request.headers.get("X-Lark-Request-Timestamp", "")
        nonce = request.headers.get("X-Lark-Request-Nonce", "")
        signature = request.headers.get("X-Lark-Signature", "")
        body = await request.body()
        
        # 验证签名
        if not verify_signature(timestamp, nonce, body, signature):
            logger.warning("签名验证失败")
            raise HTTPException(status_code=403, detail="签名验证失败")
        
        # 解析请求体
        payload = json.loads(body)
        
        # URL验证挑战
        if payload.get("type") == "url_verification":
            return JSONResponse({
                "challenge": payload.get("challenge", "")
            })
        
        # 事件处理
        event = payload.get("event", {})
        header = payload.get("header", {})
        
        # 验证verification_token
        if FEISHU_VERIFICATION_TOKEN and header.get("token") != FEISHU_VERIFICATION_TOKEN:
            logger.warning("Verification Token不匹配")
            raise HTTPException(status_code=403, detail="Verification Token不匹配")
        
        # 处理消息事件
        if header.get("event_type") == "im.message.receive_v1":
            message = event.get("message", {})
            sender = event.get("sender", {})
            
            # 获取消息内容
            msg_type = message.get("msg_type")
            content = json.loads(message.get("content", "{}"))
            user_open_id = sender.get("sender_id", {}).get("open_id", "")
            
            if not user_open_id or not content:
                logger.warning("无效的消息内容")
                return JSONResponse({"code": 0})
            
            # 只处理文本消息
            if msg_type != "text":
                send_feishu_message(user_open_id, "抱歉，目前只支持文本消息交互哦~")
                return JSONResponse({"code": 0})
            
            user_input = content.get("text", "").strip()
            
            # 处理@机器人的情况，去掉@内容
            mentions = message.get("mentions", [])
            for mention in mentions:
                if mention.get("name") == "_all":
                    user_input = user_input.replace(f"@_all", "").strip()
                else:
                    user_input = user_input.replace(f"@{mention.get('name')}", "").strip()
            
            if not user_input:
                send_feishu_message(user_open_id, "请问有什么可以帮您的？")
                return JSONResponse({"code": 0})
            
            logger.info(f"收到飞书用户消息: user_id={user_open_id}, content={user_input}")
            
            # 调用agent处理消息
            result = agent.process_message(user_input, user_open_id)
            
            # 处理回复
            answer = result.get("answer", "")
            if not answer:
                answer = "处理失败，请稍后再试"
            
            # 处理流式响应
            if hasattr(answer, "__iter__") and not isinstance(answer, (str, bytes)):
                full_answer = []
                for chunk in answer:
                    if chunk:
                        full_answer.append(chunk)
                final_answer = "".join(full_answer)
                
                # 保存会话
                if result.get("session"):
                    session = result["session"]
                    session.add_assistant_message(final_answer)
                    agent.conv_manager.save(session)
                
                answer = final_answer
            
            # 发送回复
            send_feishu_message(user_open_id, answer)
        
        return JSONResponse({"code": 0})
        
    except Exception as e:
        logger.error(f"处理飞书回调异常: {e}")
        return JSONResponse({"code": 1, "msg": "处理失败"}, status_code=500)

@app.get("/health")
async def health_check():
    """健康检查接口"""
    return {"status": "ok", "service": "feishu_agent_webhook"}

if __name__ == "__main__":
    port = int(os.getenv("FEISHU_WEBHOOK_PORT", 8000))
    logger.info(f"飞书Webhook服务启动，端口: {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
