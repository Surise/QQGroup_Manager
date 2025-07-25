import os
import sys
import subprocess
from pathlib import Path

def install_pyinstaller():
    """安装PyInstaller"""
    try:
        import PyInstaller
    except ImportError:
        print("正在安装PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "PyInstaller"])

def build_exe():
    """使用PyInstaller打包成exe"""
    # 确保在src目录下
    src_path = os.path.dirname(os.path.abspath(__file__))
    os.chdir(src_path)
    
    # 安装PyInstaller（如果尚未安装）
    install_pyinstaller()
    
    # PyInstaller命令
    cmd = [
        "pyinstaller",
        "--name=天鱼群管系统",
        "--windowed",  # GUI应用，无控制台窗口
        "--add-data=templates;templates",
        "--add-data=static;static",
        "--add-data=keywords.json;.",
        "--add-data=welcome_config.json;.",
        "--hidden-import=PyQt5.sip",
        "--hidden-import=queue",
        "--hidden-import=concurrent.futures",
        "--hidden-import=concurrent.futures.thread",
        "--hidden-import=concurrent.futures.process",
        "--hidden-import=xml.etree.ElementTree",
        "--hidden-import=xml.etree.ElementPath",
        "--icon=NONE",
        "main.py"
    ]
    
    print("正在打包成exe文件...")
    print("命令:", " ".join(cmd))
    
    try:
        subprocess.check_call(cmd)
        print("打包完成！exe文件位于dist目录中。")
    except subprocess.CalledProcessError as e:
        print(f"打包失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    build_exe()