import os
from PyQt6.QtWidgets import (QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QWidget, QDialog)
from PyQt6.QtGui import QPainter, QPen, QColor, QPixmap, QPainterPath
from PyQt6.QtCore import Qt, pyqtSignal, QRect
from PyQt6.QtWidgets import QGraphicsDropShadowEffect, QApplication
from config import APP_CONFIG

class IconButton(QPushButton):
    def __init__(self, parent, btn_type):
        super().__init__(parent); self.btn_type = btn_type; self.setFixedSize(45, 38); self.setCursor(Qt.CursorShape.PointingHandCursor)
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.underMouse():
            if self.btn_type == "close": painter.setBrush(QColor("#E81123"))
            else:
                c = QColor(0, 0, 0, 20) if APP_CONFIG.get('theme') == 'light' else QColor(255, 255, 255, 30)
                painter.setBrush(c)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(self.rect().adjusted(6, 6, -6, -6), 4, 4)

        color = QColor("#4B5563") if APP_CONFIG.get('theme') == 'light' else QColor("#CCCCCC")
        if self.underMouse() and self.btn_type == "close": color = QColor("white")
        pen = QPen(color, 1.2); painter.setPen(pen)
        cx, cy = self.width() // 2, self.height() // 2; s = 5
        if self.btn_type == "min": painter.drawLine(cx - s, cy, cx + s, cy)
        elif self.btn_type == "max": painter.drawRect(cx - s, cy - s, s * 2, s * 2)
        elif self.btn_type == "close":
            painter.drawLine(cx - s, cy - s, cx + s, cy + s); painter.drawLine(cx + s, cy - s, cx - s, cy + s)

class CustomTitleBar(QFrame):
    def __init__(self, parent, title, show_max=True):
        super().__init__(parent); self.parent_window = parent; self.setFixedHeight(38); self.setObjectName("TitleBar")
        layout = QHBoxLayout(self); layout.setContentsMargins(15, 0, 0, 0); layout.setSpacing(0)
        self.icon_lbl = QLabel(); self.icon_lbl.setPixmap(QApplication.windowIcon().pixmap(16, 16)); self.icon_lbl.setContentsMargins(0, 0, 8, 0)
        self.title_label = QLabel(title); self.title_label.setObjectName("TitleLabel")
        self.min_btn = IconButton(self, "min"); self.max_btn = IconButton(self, "max"); self.close_btn = IconButton(self, "close")
        
        self.min_btn.clicked.connect(self.parent_window.showMinimized)
        if show_max: self.max_btn.clicked.connect(self.toggle_max)
        else: self.max_btn.hide()
        self.close_btn.clicked.connect(self.parent_window.close)
        
        layout.addWidget(self.icon_lbl); layout.addWidget(self.title_label); layout.addStretch()
        layout.addWidget(self.min_btn); layout.addWidget(self.max_btn); layout.addWidget(self.close_btn)
        self.start_pos = None

    def toggle_max(self):
        if self.parent_window.isMaximized():
            self.parent_window.showNormal()
            if hasattr(self.parent_window, 'main_frame'): self.parent_window.main_frame.setStyleSheet("")
        else:
            self.parent_window.showMaximized()
            if hasattr(self.parent_window, 'main_frame'): self.parent_window.main_frame.setStyleSheet("QFrame#MainFrame { border-radius: 0px; border: none; }")
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton: self.start_pos = event.globalPosition().toPoint()
    def mouseMoveEvent(self, event):
        if self.start_pos is not None:
            delta = event.globalPosition().toPoint() - self.start_pos
            self.parent_window.move(self.parent_window.pos() + delta); self.start_pos = event.globalPosition().toPoint()
    def mouseReleaseEvent(self, event): self.start_pos = None
    def mouseDoubleClickEvent(self, event):
        if self.max_btn.isVisible(): self.toggle_max()

def setup_frameless_dialog(dialog, title, width, height):
    dialog.setObjectName("FramelessDialog") 
    dialog.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
    dialog.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    dialog.setFixedSize(width, height)
    main_frame = QFrame(); main_frame.setObjectName("DialogFrame")
    base_lay = QVBoxLayout(dialog); base_lay.setContentsMargins(0, 0, 0, 0); base_lay.addWidget(main_frame)
    layout = QVBoxLayout(main_frame); layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(CustomTitleBar(dialog, title, show_max=False))
    content_widget = QWidget(); content_lay = QVBoxLayout(content_widget); content_lay.setContentsMargins(20, 15, 20, 20)
    layout.addWidget(content_widget)
    return content_lay

# ✨ 史诗级外观升级：完全自研的美化版提示框
class CustomMessageBox(QDialog):
    @staticmethod
    def show(parent, title, text, msg_type="info"):
        dialog = QDialog(parent)
        layout = setup_frameless_dialog(dialog, title, 380, 200)
        h_lay = QHBoxLayout(); h_lay.setContentsMargins(15, 10, 15, 10); h_lay.setSpacing(15)
        
        icon_map = {"info": "💡", "warning": "⚠️", "error": "❌", "success": "✅"}
        icon_lbl = QLabel(icon_map.get(msg_type, "💡")); icon_lbl.setStyleSheet("font-size: 38px;")
        h_lay.addWidget(icon_lbl)
        
        text_lbl = QLabel(text); text_lbl.setWordWrap(True)
        color = "#D4D4D4" if APP_CONFIG.get('theme') == 'dark' else "#333333"
        text_lbl.setStyleSheet(f"font-size: 14px; line-height: 1.5; color: {color};")
        h_lay.addWidget(text_lbl, 1)
        
        layout.addLayout(h_lay); layout.addStretch()
        
        btn = QPushButton("确定")
        btn.setObjectName("BlueBtn" if msg_type in ["info", "success"] else "OrangeBtn")
        btn.setFixedSize(100, 35)
        btn.clicked.connect(dialog.accept)
        
        btn_lay = QHBoxLayout(); btn_lay.addStretch(); btn_lay.addWidget(btn); layout.addLayout(btn_lay)
        dialog.exec()
    
    @staticmethod
    def confirm(parent, title, text):
        dialog = QDialog(parent)
        layout = setup_frameless_dialog(dialog, title, 380, 200)
        h_lay = QHBoxLayout(); h_lay.setContentsMargins(15, 10, 15, 10); h_lay.setSpacing(15)
        
        icon_lbl = QLabel("❓"); icon_lbl.setStyleSheet("font-size: 38px;")
        h_lay.addWidget(icon_lbl)
        
        text_lbl = QLabel(text); text_lbl.setWordWrap(True)
        color = "#D4D4D4" if APP_CONFIG.get('theme') == 'dark' else "#333333"
        text_lbl.setStyleSheet(f"font-size: 14px; line-height: 1.5; color: {color};")
        h_lay.addWidget(text_lbl, 1)
        
        layout.addLayout(h_lay); layout.addStretch()
        
        yes_btn = QPushButton("确定"); yes_btn.setObjectName("BlueBtn"); yes_btn.setFixedSize(90, 35)
        yes_btn.clicked.connect(lambda: dialog.done(1))
        no_btn = QPushButton("取消"); no_btn.setObjectName("GrayBtn"); no_btn.setFixedSize(90, 35)
        no_btn.clicked.connect(lambda: dialog.done(0))
        
        btn_lay = QHBoxLayout(); btn_lay.addStretch(); btn_lay.addWidget(yes_btn); btn_lay.addWidget(no_btn)
        layout.addLayout(btn_lay)
        return dialog.exec() == 1

class AnimeCard(QFrame):
    clicked = pyqtSignal(int, str)
    def __init__(self, sid, name):
        super().__init__(); self.setObjectName("AnimeCard"); self.sid = sid; self.setFixedSize(160, 250); self.setCursor(Qt.CursorShape.PointingHandCursor)
        shadow = QGraphicsDropShadowEffect(self); shadow.setBlurRadius(15); shadow.setColor(QColor(0,0,0, 50)); shadow.setYOffset(4); self.setGraphicsEffect(shadow)
        layout = QVBoxLayout(self); self.img = QLabel("Loading..."); self.img.setFixedSize(140, 180); self.img.setObjectName("CardImg")
        self.title = QLabel(name); self.title.setWordWrap(True); self.title.setAlignment(Qt.AlignmentFlag.AlignCenter); self.title.setObjectName("CardTitle")
        layout.addWidget(self.img); layout.addWidget(self.title)
    def mousePressEvent(self, e): 
        if e.button() == Qt.MouseButton.LeftButton: self.clicked.emit(self.sid, self.title.text())

class BackgroundFrame(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("MainFrame")
        self._original_pixmap = None
        self._cached_pixmap = None
        self._align_ratio = APP_CONFIG.get('bg_align', 50) / 100.0
        self.load_background()

    def load_background(self):
        bg_path = APP_CONFIG.get('bg_image', '')
        if bg_path and os.path.exists(bg_path):
            self._original_pixmap = QPixmap(bg_path)
        else:
            self._original_pixmap = None
        self.update_cache()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_cache()

    def update_cache(self):
        if not self._original_pixmap or self._original_pixmap.isNull() or self.width() <= 0 or self.height() <= 0:
            self._cached_pixmap = None
            self.update()
            return

        scaled = self._original_pixmap.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
        x = int((scaled.width() - self.width()) * self._align_ratio)
        y = int((scaled.height() - self.height()) * self._align_ratio)

        crop_rect = QRect(x, y, self.width(), self.height())
        self._cached_pixmap = scaled.copy(crop_rect)
        self.update()

    def paintEvent(self, event):
        if self._cached_pixmap:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            path = QPainterPath()
            path.addRoundedRect(1, 1, self.width() - 2, self.height() - 2, 9, 9)
            painter.setClipPath(path)
            painter.drawPixmap(0, 0, self._cached_pixmap)
            painter.end()
        super().paintEvent(event)