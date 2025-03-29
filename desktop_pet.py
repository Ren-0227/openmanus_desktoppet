import sys
import asyncio
import logging
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLineEdit, QPushButton, QDialog, QLabel, QVBoxLayout
from PyQt6.QtGui import QPainter, QPen, QColor, QBrush
from PyQt6.QtCore import Qt, QTimer, QPoint
from app.agent.manus import Manus  # 确保正确定义或导入 Manus
from app.logger import logger  # 确保正确定义或导入 logger

# 配置日志记录器
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class InputDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Input Prompt")
        self.setGeometry(100, 100, 400, 100)
        
        self.layout = QVBoxLayout()
        self.prompt_input = QLineEdit()
        self.prompt_input.setPlaceholderText("Enter your prompt (or 'exit'/'quit' to quit):")
        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self.accept)
        
        self.layout.addWidget(self.prompt_input)
        self.layout.addWidget(self.send_button)
        self.setLayout(self.layout)

class DesktopPet(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            self.windowFlags() |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.FramelessWindowHint  # 使用正确的无边框窗口标志
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)  # 设置背景透明
        self.setWindowTitle("桌面宠物")
        self.setGeometry(100, 100, 200, 300)
        
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_pet)
        self.timer.start(1000)  # 每秒更新一次

        # 添加宠物移动功能
        self.move_timer = QTimer()
        self.move_timer.timeout.connect(self.move_pet)
        self.move_timer.start(50)  # 每50毫秒移动一次

        self.speed = QPoint(2, 2)  # 宠物移动的速度
        self.direction = 1  # 宠物移动的方向

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 绘制宠物身体（蓝色圆形）
        painter.setPen(QPen(QColor(0, 0, 255), 2))
        painter.setBrush(QBrush(QColor(200, 200, 255)))
        painter.drawEllipse(50, 100, 100, 100)
        
        # 绘制宠物头部（红色圆形）
        painter.setPen(QPen(QColor(255, 0, 0), 2))
        painter.setBrush(QBrush(QColor(255, 200, 200)))
        painter.drawEllipse(75, 50, 50, 50)
        
        # 绘制宠物眼睛（黑色圆形）
        painter.setPen(QPen(QColor(0, 0, 0), 2))
        painter.setBrush(QBrush(QColor(0, 0, 0)))
        painter.drawEllipse(85, 60, 10, 10)
        painter.drawEllipse(115, 60, 10, 10)
        
        # 绘制宠物嘴巴（黑色线条）
        painter.setPen(QPen(QColor(0, 0, 0), 2))
        painter.drawLine(75, 80, 125, 80)

    def update_pet(self):
        self.update()  # 重绘界面

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # 显示输入对话框
            dialog = InputDialog(self)
            if dialog.exec():
                prompt = dialog.prompt_input.text()
                if prompt.lower() in ["exit", "quit"]:
                    logger.info("Goodbye!")
                    QApplication.quit()
                elif not prompt.strip():
                    logger.warning("Skipping empty prompt.")
                else:
                    logger.warning("Processing your request...")
                    # 在这里调用你的 main 函数
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(self.main(prompt))

    async def main(self, prompt):
        # 这里是你的 main 函数逻辑
        agent = Manus()
        await agent.run(prompt)

    def move_pet(self):
        # 获取当前窗口的位置
        current_pos = self.pos()
        
        # 更新位置
        new_pos = current_pos + self.speed
        
        # 检查是否碰到屏幕边缘
        screen = QApplication.primaryScreen()
        screen_geometry = screen.geometry()
        
        if new_pos.x() < 0 or new_pos.x() + self.width() > screen_geometry.width():
            self.speed.setX(-self.speed.x())  # 反转水平方向
        if new_pos.y() < 0 or new_pos.y() + self.height() > screen_geometry.height():
            self.speed.setY(-self.speed.y())  # 反转垂直方向
        
        # 设置新位置
        self.move(new_pos)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # 使用 globalPosition() 替代 globalPos()
            global_position = event.globalPosition().toPoint()
            self.drag_position = global_position - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and hasattr(self, 'drag_position'):
            global_position = event.globalPosition().toPoint()
            self.move(global_position - self.drag_position)
            event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    pet = DesktopPet()
    pet.show()
    sys.exit(app.exec())