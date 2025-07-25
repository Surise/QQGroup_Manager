import sys
import os
import threading
import time
from PyQt5.QtWidgets import QApplication, QMainWindow, QDesktopWidget, QMessageBox
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl, QTimer
from PyQt5.QtGui import QCloseEvent
from werkzeug.serving import make_server

# 添加src目录到Python路径
sys.path.insert(0, os.path.dirname(__file__))

# 导入Flask应用
from bot import app as flask_app

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.flask_thread = None
        self.server = None
        self.initUI()
        self.start_flask_server()
        
    def initUI(self):
        self.setWindowTitle('天鱼群管系统')
        self.setGeometry(100, 100, 1200, 800)
        self.center()
        
        # 创建Web视图
        self.webView = QWebEngineView()
        self.setCentralWidget(self.webView)
        
        # 页面加载完成后显示窗口
        self.webView.loadFinished.connect(self.onLoadFinished)
        
    def center(self):
        # 窗口居中显示
        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())
        
    def start_flask_server(self):
        # 在单独的线程中启动Flask应用
        self.flask_thread = threading.Thread(target=self.run_flask, daemon=True)
        self.flask_thread.start()
        
        # 等待Flask启动后加载页面
        QTimer.singleShot(2000, self.load_web_page)
        
    def run_flask(self):
        # 使用werkzeug运行Flask应用
        self.server = make_server('127.0.0.1', 8080, flask_app, threaded=True)
        self.server.serve_forever()
        
    def load_web_page(self):
        # 加载Web界面
        self.webView.load(QUrl("http://127.0.0.1:8080"))
        
    def onLoadFinished(self, success):
        if success:
            self.show()
        
    def closeEvent(self, event: QCloseEvent):
        # 关闭窗口时的处理
        reply = QMessageBox.question(self, '确认', '确定要退出天鱼群管系统吗？',
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            # 关闭Flask服务器
            try:
                if self.server:
                    self.server.shutdown()
            except Exception as e:
                print(f"关闭服务器时出错: {e}")
            
            # 等待线程结束
            if self.flask_thread and self.flask_thread.is_alive():
                self.flask_thread.join(timeout=3)
            
            event.accept()
        else:
            event.ignore()

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("天鱼群管系统")
    
    # 创建并显示主窗口
    window = MainWindow()
    
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()