"""允许通过 python -m chaoxing_sign 运行"""
import sys
import os

# 将上级目录加到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import main
main()
