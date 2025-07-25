import sys
import os

# 添加src目录到Python路径
sys.path.insert(0, os.path.dirname(__file__))

if __name__ == "__main__":
    # 导入并运行主程序
    try:
        from main import main
        main()
    except ImportError as e:
        print(f"导入错误: {e}")
        print("请确保已安装所有依赖项:")
        print("pip install -r requirements.txt")