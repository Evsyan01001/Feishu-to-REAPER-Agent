"""
Feishu Agent 主入口
兼容原有使用方式，默认启动CLI模式
"""
import sys
import os

# 将当前目录加入Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cli.main import main

if __name__ == "__main__":
    main()
