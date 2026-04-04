import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon

# 导入我们自己写的模块
from config import get_resource_path
from ui.mainwindow import MainWindow

def main():
    # 1. 初始化 PyQt6 应用程序实例
    app = QApplication(sys.argv)
    
    # 2. 设置全局的应用程序图标
    # 这里使用了 get_resource_path，确保无论是在开发环境还是打包成 exe 后，都能精准找到图标！
    # ⚠️ 提示：请确保你的项目根目录下，真实存在一张名为 icon.ico 的图片
    icon_path = get_resource_path('icon.ico')
    app.setWindowIcon(QIcon(icon_path))
    
    # 3. 实例化并展示我们精心打造的主窗口
    window = MainWindow()
    window.show()
    
    # 4. 进入事件主循环，监听用户的点击和操作，直到程序关闭
    sys.exit(app.exec())

if __name__ == "__main__":
    main()