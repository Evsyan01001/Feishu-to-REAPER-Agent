"""
文件系统通信管理器

处理与listen.lua的文件系统通信，支持跨平台
"""

import os
import sys
import logging
import time
import threading
from typing import Optional, Tuple, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class FileCommunicator:
    """处理与listen.lua的文件系统通信"""

    def __init__(self, file_path: str = None):
        """
        初始化文件通信器

        Args:
            file_path: 通信文件路径，如果为None则使用默认路径
        """
        self.file_path = self._resolve_file_path(file_path)
        self._lock = threading.RLock()  # 文件写入锁
        logger.info(f"初始化文件通信器，路径: {self.file_path}")

    def _resolve_file_path(self, file_path: Optional[str]) -> str:
        """解析文件路径"""
        if file_path:
            # 使用用户指定的路径
            return file_path

        # 从环境变量获取
        env_path = os.getenv("REAPER_CMD_FILE")
        if env_path:
            return env_path

        # 平台特定默认路径
        if sys.platform == "win32":
            # Windows默认路径
            return "C:\\Users\\Public\\reaper_cmd.txt"
        elif sys.platform == "darwin":
            # macOS默认路径
            return "/tmp/reaper_cmd.txt"
        else:
            # Linux和其他Unix系统
            return "/tmp/reaper_cmd.txt"

    def send_command(self, command: str, max_retries: int = 3) -> Tuple[bool, str]:
        """
        发送指令到文件

        Args:
            command: 指令字符串，格式如 "ACTION|40001" 或 "GAIN|3"
            max_retries: 最大重试次数

        Returns:
            Tuple[bool, str]: (成功状态, 错误信息)
        """
        if not command or not isinstance(command, str):
            return False, "无效的指令格式"

        # 验证指令格式
        if not self._validate_command_format(command):
            return False, f"指令格式无效: {command}"

        # 获取文件锁
        with self._lock:
            for attempt in range(max_retries):
                try:
                    # 确保目录存在
                    self._ensure_directory_exists()

                    # 写入文件
                    with open(self.file_path, 'w', encoding='utf-8') as f:
                        f.write(command)
                        f.flush()
                        os.fsync(f.fileno())

                    logger.info(f"成功写入指令到文件: {command}")
                    return True, "指令已发送"

                except PermissionError as e:
                    error_msg = f"权限错误: {e}"
                    logger.error(f"第 {attempt + 1} 次尝试失败: {error_msg}")
                    if attempt < max_retries - 1:
                        time.sleep(0.1 * (attempt + 1))  # 指数退避
                    else:
                        return False, error_msg

                except OSError as e:
                    error_msg = f"系统错误: {e}"
                    logger.error(f"第 {attempt + 1} 次尝试失败: {error_msg}")
                    if attempt < max_retries - 1:
                        time.sleep(0.1 * (attempt + 1))
                    else:
                        return False, error_msg

                except Exception as e:
                    error_msg = f"未知错误: {e}"
                    logger.error(f"第 {attempt + 1} 次尝试失败: {error_msg}")
                    if attempt < max_retries - 1:
                        time.sleep(0.1 * (attempt + 1))
                    else:
                        return False, error_msg

            return False, "达到最大重试次数"

    def _validate_command_format(self, command: str) -> bool:
        """验证指令格式"""
        # 指令格式应为 "类型|参数" 或 "类型"
        parts = command.split('|')
        if len(parts) == 1:
            # 无参数指令，如 "EXPORT"
            return bool(parts[0].strip())
        elif len(parts) == 2:
            # 有参数指令，如 "ACTION|40001" 或 "GAIN|3"
            return bool(parts[0].strip()) and bool(parts[1].strip())
        else:
            return False

    def _ensure_directory_exists(self):
        """确保文件所在目录存在"""
        try:
            path = Path(self.file_path)
            parent_dir = path.parent
            if not parent_dir.exists():
                parent_dir.mkdir(parents=True, exist_ok=True)
                logger.debug(f"创建目录: {parent_dir}")
        except Exception as e:
            logger.error(f"创建目录失败: {e}")
            raise

    def check_file_access(self) -> Tuple[bool, str]:
        """检查文件访问权限"""
        try:
            # 尝试写入测试数据
            test_command = "TEST|1"
            with open(self.file_path, 'w', encoding='utf-8') as f:
                f.write(test_command)
                f.flush()

            # 尝试读取验证
            with open(self.file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content == test_command:
                    return True, "文件访问正常"
                else:
                    return False, f"文件内容不匹配: 期望 '{test_command}'，实际 '{content}'"

        except PermissionError as e:
            return False, f"权限不足: {e}"
        except OSError as e:
            return False, f"系统错误: {e}"
        except Exception as e:
            return False, f"未知错误: {e}"

    def get_file_info(self) -> Dict[str, Any]:
        """获取文件信息"""
        try:
            path = Path(self.file_path)
            exists = path.exists()

            info = {
                "path": str(self.file_path),
                "exists": exists,
                "platform": sys.platform,
                "absolute_path": str(path.absolute())
            }

            if exists:
                info.update({
                    "size": path.stat().st_size,
                    "modified": time.ctime(path.stat().st_mtime),
                    "is_file": path.is_file(),
                    "is_dir": path.is_dir()
                })

            return info

        except Exception as e:
            logger.error(f"获取文件信息失败: {e}")
            return {
                "path": str(self.file_path),
                "error": str(e),
                "platform": sys.platform
            }

    def clear_command(self) -> Tuple[bool, str]:
        """清空指令文件"""
        try:
            with self._lock:
                with open(self.file_path, 'w', encoding='utf-8') as f:
                    f.write('')
                    f.flush()

            logger.info("已清空指令文件")
            return True, "文件已清空"

        except Exception as e:
            error_msg = f"清空文件失败: {e}"
            logger.error(error_msg)
            return False, error_msg