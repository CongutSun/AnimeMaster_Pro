import os
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
                             QLineEdit, QComboBox, QFormLayout, QFileDialog, QMessageBox,
                             QListWidget, QListWidgetItem, QAbstractItemView, QTextEdit, QGridLayout, QWidget, QSlider, QCheckBox)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QRect, QPoint
from PyQt6.QtGui import QColor, QPixmap, QPainter, QPainterPath, QPen
from qbittorrentapi import Client
from config import APP_CONFIG, save_config, update_session_headers, http_session
from ui.theme import apply_global_theme
from api.bangumi import BangumiAuthAPI, MyCollectionWorker, DetailWorker, CollectionUpdateWorker, EpProgressWorker
from ui.components import setup_frameless_dialog, CustomMessageBox

# ✨ 新增：用于展示和选择多个别名的弹窗
class AliasSelectDialog(QDialog):
    def __init__(self, aliases, parent=None):
        super().__init__(parent)
        self.selected_alias = None
        layout = setup_frameless_dialog(self, "请选择一个最精准的别名", 420, 350)

        layout.addWidget(QLabel("💡 Bangumi 上存在以下别名，请点击选中一个最适合 PT 站搜索的英文或罗马音：", styleSheet="color: #888; font-size: 12px;"))
        
        self.list_widget = QListWidget()
        self.list_widget.addItems(aliases)
        layout.addWidget(self.list_widget)

        btn_box = QHBoxLayout()
        ok_btn = QPushButton("确定选中")
        ok_btn.setObjectName("BlueBtn")
        ok_btn.clicked.connect(self.on_ok)
        
        cancel_btn = QPushButton("取消")
        cancel_btn.setObjectName("GrayBtn")
        cancel_btn.clicked.connect(self.reject)

        btn_box.addStretch()
        btn_box.addWidget(ok_btn)
        btn_box.addWidget(cancel_btn)
        layout.addLayout(btn_box)

    def on_ok(self):
        item = self.list_widget.currentItem()
        if item:
            self.selected_alias = item.text()
            self.accept()
        else:
            CustomMessageBox.show(self, "提示", "请先在列表中点击选中一项", "warning")

# 以下均为原内容，保持不变
class ImageCropPreview(QWidget):
    ratio_changed = pyqtSignal(int)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(340, 220); self.setCursor(Qt.CursorShape.PointingHandCursor); self.base_pixmap = None
        self.ratio = APP_CONFIG.get('bg_align', 50) / 100.0
        self.crop_rect = QRect(); self.img_rect = QRect(); self.is_dragging = False; self.drag_offset = QPoint(); self.slack_x = 0; self.slack_y = 0

    def load_image(self, path):
        if not path or not os.path.exists(path):
            self.base_pixmap = None; self.update(); return
        full_pix = QPixmap(path)
        if full_pix.isNull(): return
        self.base_pixmap = full_pix.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self._update_geometry()

    def _update_geometry(self):
        if not self.base_pixmap: return
        bw = self.base_pixmap.width(); bh = self.base_pixmap.height()
        offset_x = (self.width() - bw) // 2; offset_y = (self.height() - bh) // 2
        self.img_rect = QRect(offset_x, offset_y, bw, bh)
        target_ratio = 1000 / 750.0; img_ratio = bw / bh
        if img_ratio > target_ratio: ch = bh; cw = int(ch * target_ratio)
        else: cw = bw; ch = int(cw / target_ratio)
        self.slack_x = bw - cw; self.slack_y = bh - ch
        cx = int(self.slack_x * self.ratio); cy = int(self.slack_y * self.ratio)
        self.crop_rect = QRect(offset_x + cx, offset_y + cy, cw, ch); self.update()

    def paintEvent(self, event):
        painter = QPainter(self); painter.setRenderHint(QPainter.RenderHint.Antialiasing); painter.fillRect(self.rect(), QColor("#1E1E1E"))
        if not self.base_pixmap:
            painter.setPen(QColor("#888888")); painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "未选择背景"); return
        painter.drawPixmap(self.img_rect.topLeft(), self.base_pixmap)
        painter.fillRect(self.img_rect, QColor(0, 0, 0, 160))
        crop_x_img = self.crop_rect.x() - self.img_rect.x(); crop_y_img = self.crop_rect.y() - self.img_rect.y()
        highlight = self.base_pixmap.copy(crop_x_img, crop_y_img, self.crop_rect.width(), self.crop_rect.height())
        painter.drawPixmap(self.crop_rect.topLeft(), highlight)
        pen = QPen(QColor(255, 255, 255, 220), 2, Qt.PenStyle.DashLine); painter.setPen(pen); painter.drawRect(self.crop_rect)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.crop_rect.contains(event.pos()):
            self.is_dragging = True; self.drag_offset = event.pos() - self.crop_rect.topLeft()

    def mouseMoveEvent(self, event):
        if self.is_dragging:
            new_pos = event.pos() - self.drag_offset
            new_x = max(self.img_rect.left(), min(new_pos.x(), self.img_rect.right() - self.crop_rect.width() + 1))
            new_y = max(self.img_rect.top(), min(new_pos.y(), self.img_rect.bottom() - self.crop_rect.height() + 1))
            self.crop_rect.moveTo(new_x, new_y); self.update()
            if self.slack_x > 0: self.ratio = (new_x - self.img_rect.left()) / self.slack_x
            elif self.slack_y > 0: self.ratio = (new_y - self.img_rect.top()) / self.slack_y
            else: self.ratio = 0.5
            self.ratio_changed.emit(int(self.ratio * 100))

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton: self.is_dragging = False

class CloseConfirmDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent); self.remember = False
        layout = setup_frameless_dialog(self, "关闭提示", 380, 230)
        lbl = QLabel("确定要关闭智能追番助手吗？\n\n你可以选择完全退出，或者最小化到系统托盘后台运行。"); lbl.setWordWrap(True); lbl.setStyleSheet("font-size: 14px; line-height: 1.5;")
        layout.addWidget(lbl)
        self.remember_cb = QCheckBox("记住我的选择 (日后可在设置中更改)"); self.remember_cb.setStyleSheet("color: #888; font-size: 13px; margin-top: 10px;"); layout.addWidget(self.remember_cb)
        btn_lay = QHBoxLayout()
        tray_btn = QPushButton("最小化到托盘"); tray_btn.setObjectName("OrangeBtn"); exit_btn = QPushButton("完全退出"); exit_btn.setObjectName("RedBtn")
        cancel_btn = QPushButton("取消"); cancel_btn.setObjectName("GrayBtn")
        tray_btn.clicked.connect(self.on_tray); exit_btn.clicked.connect(self.on_exit); cancel_btn.clicked.connect(self.on_cancel)
        btn_lay.addStretch(); btn_lay.addWidget(tray_btn); btn_lay.addWidget(exit_btn); btn_lay.addWidget(cancel_btn); layout.addLayout(btn_lay)
    def on_tray(self): self.remember = self.remember_cb.isChecked(); self.done(1)
    def on_exit(self): self.remember = self.remember_cb.isChecked(); self.done(2)
    def on_cancel(self): self.done(0)

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = setup_frameless_dialog(self, "智能追番助手 设置", 860, 620)
        main_split = QHBoxLayout()
        self.current_align = APP_CONFIG.get('bg_align', 50)
        
        left_widget = QWidget()
        left_lay = QVBoxLayout(left_widget)
        left_lay.setContentsMargins(0, 0, 15, 0)
        left_lay.addWidget(QLabel("<b>🎨 界面外观</b>"))
        form_left = QFormLayout()
        
        self.close_box = QComboBox()
        self.close_box.addItem("🤔 每次询问我", 0); self.close_box.addItem("📥 最小化到托盘后台", 1); self.close_box.addItem("❌ 直接完全退出", 2)
        idx_c = self.close_box.findData(APP_CONFIG.get('close_action', 0))
        if idx_c >= 0: self.close_box.setCurrentIndex(idx_c)
            
        self.theme_box = QComboBox()
        self.theme_box.addItem("🌞 明亮模式 (Light)", "light"); self.theme_box.addItem("🌙 暗黑模式 (Dark)", "dark")
        idx_t = self.theme_box.findData(APP_CONFIG.get('theme', 'light'))
        if idx_t >= 0: self.theme_box.setCurrentIndex(idx_t)

        self.bg_path_in = QLineEdit(APP_CONFIG.get('bg_image', ''))
        self.bg_path_in.setPlaceholderText("留空则使用纯色...")
        self.bg_path_in.textChanged.connect(self.on_bg_changed)
        
        bg_btn = QPushButton("浏览..."); bg_btn.setObjectName("GrayBtn"); bg_btn.clicked.connect(self.choose_bg)
        bg_layout = QHBoxLayout(); bg_layout.addWidget(self.bg_path_in); bg_layout.addWidget(bg_btn)

        form_left.addRow("关闭行为:", self.close_box); form_left.addRow("主题模式:", self.theme_box); form_left.addRow("自定义背景:", bg_layout)
        left_lay.addLayout(form_left)
        
        left_lay.addWidget(QLabel("拖动虚线框取景 (支持滑鼠拖拽)：", styleSheet="color: #888; font-size: 12px; margin-top: 10px;"))
        self.bg_preview = ImageCropPreview(); self.bg_preview.setStyleSheet("border: 1px solid #444; border-radius: 6px;"); self.bg_preview.ratio_changed.connect(self.on_ratio_dragged)
        left_lay.addWidget(self.bg_preview, alignment=Qt.AlignmentFlag.AlignCenter)
        left_lay.addStretch()
        
        right_widget = QWidget(); right_lay = QVBoxLayout(right_widget); right_lay.setContentsMargins(15, 0, 0, 0)
        right_lay.addWidget(QLabel("<b>🔽 账号与下载器</b>"))
        
        form_right_1 = QFormLayout()
        self.host_in = QLineEdit(APP_CONFIG.get('qbt_host', 'localhost'))
        self.port_in = QLineEdit(str(APP_CONFIG.get('qbt_port', 8080)))
        self.qbt_path_in = QLineEdit(APP_CONFIG.get('qbt_path', ''))
        
        qbt_btn = QPushButton("浏览..."); qbt_btn.setObjectName("GrayBtn"); qbt_btn.clicked.connect(self.choose_qbt)
        qbt_layout = QHBoxLayout(); qbt_layout.addWidget(self.qbt_path_in); qbt_layout.addWidget(qbt_btn)
        
        self.cookie_in = QLineEdit(APP_CONFIG.get('monika_cookie', ''))
        self.cookie_in.setPlaceholderText("填入 MonikaDesign 的 Cookie")
        self.bgm_user_in = QLineEdit(APP_CONFIG.get('bgm_username', ''))
        self.bgm_token_in = QLineEdit(APP_CONFIG.get('bgm_token', ''))
        self.bgm_token_in.setEchoMode(QLineEdit.EchoMode.Password)
        
        form_right_1.addRow("qBit WebUI:", self.host_in); form_right_1.addRow("qBit 端口:", self.port_in); form_right_1.addRow("qBit .exe:", qbt_layout)
        form_right_1.addRow("Monika Cookie:", self.cookie_in); form_right_1.addRow("Bgm 账号:", self.bgm_user_in); form_right_1.addRow("Bgm Token:", self.bgm_token_in)
        right_lay.addLayout(form_right_1)
        
        right_lay.addSpacing(15); right_lay.addWidget(QLabel("<b>📡 自定义资源站 (RSS源)</b>"))
        self.rss_list = QListWidget(); self.rss_list.setFixedHeight(100)
        self.custom_rss_data = APP_CONFIG.get('custom_rss', [])
        for item in self.custom_rss_data: self.rss_list.addItem(f"{item['name']} | {item['url']}")
        right_lay.addWidget(self.rss_list)
        
        inputs_lay = QHBoxLayout()
        self.rss_name_in = QLineEdit(); self.rss_name_in.setPlaceholderText("站点名 (如: DMHY)"); self.rss_name_in.setMinimumWidth(100); self.rss_name_in.setMaximumWidth(130)
        self.rss_url_in = QLineEdit(); self.rss_url_in.setPlaceholderText("URL模板 (必须包含 {keyword})")
        inputs_lay.addWidget(self.rss_name_in); inputs_lay.addWidget(self.rss_url_in); right_lay.addLayout(inputs_lay)
        
        btns_lay = QHBoxLayout()
        add_btn = QPushButton("+ 添加"); add_btn.setObjectName("BlueBtn"); add_btn.setFixedSize(80, 30); add_btn.clicked.connect(self.add_rss)
        del_btn = QPushButton("- 删除选中"); del_btn.setObjectName("RedBtn"); del_btn.setFixedSize(90, 30); del_btn.clicked.connect(self.del_rss)
        btns_lay.addStretch(); btns_lay.addWidget(add_btn); btns_lay.addWidget(del_btn); right_lay.addLayout(btns_lay)
        right_lay.addWidget(QLabel("💡 提示: 动漫花园填 https://share.dmhy.org/topics/rss/rss.xml?keyword={keyword}", styleSheet="color: #888; font-size: 11px;"))
        right_lay.addStretch()
        
        main_split.addWidget(left_widget, 5)
        v_line = QFrame(); v_line.setFrameShape(QFrame.Shape.VLine); v_line.setStyleSheet("color: #555;")
        main_split.addWidget(v_line); main_split.addWidget(right_widget, 6); layout.addLayout(main_split)
        
        btn_box = QHBoxLayout()
        save_btn = QPushButton("💾 保存并应用"); save_btn.setObjectName("GreenBtn"); save_btn.setFixedSize(120, 35); save_btn.clicked.connect(self.save_and_close)
        btn_box.addStretch(); btn_box.addWidget(save_btn); layout.addLayout(btn_box); self.on_bg_changed()

    def add_rss(self):
        name = self.rss_name_in.text().strip(); url = self.rss_url_in.text().strip()
        if not name or not url: CustomMessageBox.show(self, "提示", "名称和链接都不能为空！", "warning"); return
        if "{keyword}" not in url: CustomMessageBox.show(self, "提示", "链接中必须包含 {keyword} 作为搜索关键词的占位符！", "warning"); return
        self.custom_rss_data.append({"name": name, "url": url}); self.rss_list.addItem(f"{name} | {url}"); self.rss_name_in.clear(); self.rss_url_in.clear()
    def del_rss(self):
        row = self.rss_list.currentRow()
        if row >= 0: self.rss_list.takeItem(row); del self.custom_rss_data[row]
    def choose_bg(self):
        f, _ = QFileDialog.getOpenFileName(self, "选择背景", "", "Images (*.png *.jpg *.jpeg)")
        if f: self.bg_path_in.setText(f)
    def on_bg_changed(self): self.bg_preview.load_image(self.bg_path_in.text().strip())
    def on_ratio_dragged(self, val): self.current_align = val
    def choose_qbt(self):
        f, _ = QFileDialog.getOpenFileName(self, "选择 qBit", "", "Executable (*.exe)")
        if f: self.qbt_path_in.setText(f)
    def save_and_close(self):
        global APP_CONFIG
        try:
            APP_CONFIG['close_action'] = self.close_box.currentData(); APP_CONFIG['theme'] = self.theme_box.currentData(); APP_CONFIG['bg_image'] = self.bg_path_in.text().strip()
            APP_CONFIG['bg_align'] = self.current_align; APP_CONFIG['qbt_host'] = self.host_in.text().strip(); APP_CONFIG['qbt_port'] = int(self.port_in.text().strip() or 8080)
            APP_CONFIG['qbt_path'] = self.qbt_path_in.text().strip(); APP_CONFIG['monika_cookie'] = self.cookie_in.text().strip(); APP_CONFIG['bgm_username'] = self.bgm_user_in.text().strip()
            APP_CONFIG['bgm_token'] = self.bgm_token_in.text().strip(); APP_CONFIG['custom_rss'] = self.custom_rss_data
            save_config(APP_CONFIG); update_session_headers(); apply_global_theme()
            if self.parent() and hasattr(self.parent(), 'main_frame'):
                if hasattr(self.parent().main_frame, 'load_background'):
                    self.parent().main_frame._align_ratio = APP_CONFIG['bg_align'] / 100.0; self.parent().main_frame.load_background()
            self.accept()
        except: pass

class DetailDialog(QDialog):
    def __init__(self, sid, name, parent=None):
        super().__init__(parent); self.sid = sid; layout = setup_frameless_dialog(self, "番剧详情与评价", 580, 720)
        layout.addWidget(QLabel(f"<h2 style='text-align: center; margin-bottom: 0px;'>{name}</h2>"))
        self.info = QLabel("跨越次元壁请求中..."); self.info.setObjectName("InfoPanel"); self.info.setWordWrap(True); layout.addWidget(self.info)
        self.my_review = QLabel(); self.my_review.setWordWrap(True); self.my_review.hide(); layout.addWidget(self.my_review)
        self.ctrl_frame = QFrame(); self.ctrl_frame.setObjectName("MainFrame"); self.ctrl_frame.setStyleSheet("QFrame#MainFrame { padding: 5px; margin: 5px 0px; }")
        ctrl_lay = QGridLayout(self.ctrl_frame)
        ctrl_lay.addWidget(QLabel("<b>🚀 更新状态:</b>"), 0, 0)
        self.status_box = QComboBox(); self.status_box.addItems(["未收藏", "想看 (Wish)", "看过 (Collect)", "在看 (Do)", "搁置 (On Hold)", "抛弃 (Dropped)"])
        for i, v in enumerate([0, 1, 2, 3, 4, 5]): self.status_box.setItemData(i, v)
        ctrl_lay.addWidget(self.status_box, 0, 1)
        ctrl_lay.addWidget(QLabel("<b>⭐ 打分:</b>"), 0, 2)
        self.rate_box = QComboBox(); self.rate_box.addItem("暂不打分", 0)
        for i in range(10, 0, -1): self.rate_box.addItem(f"{i}分 " + "★"*(i//2) + ("☆" if i%2 else ""), i)
        ctrl_lay.addWidget(self.rate_box, 0, 3)
        self.comment_in = QLineEdit(); self.comment_in.setPlaceholderText("写句简短的吐槽或短评吧..."); ctrl_lay.addWidget(self.comment_in, 1, 0, 1, 3)
        self.save_btn = QPushButton("💾 云端同步"); self.save_btn.setObjectName("OrangeBtn"); self.save_btn.clicked.connect(self.save_collection); ctrl_lay.addWidget(self.save_btn, 1, 3)
        layout.addWidget(self.ctrl_frame)
        self.desc = QTextEdit(); self.desc.setReadOnly(True)
        self.btn = QPushButton("🚀 去搜刮下载"); self.btn.setEnabled(False); self.btn.clicked.connect(self.accept)
        layout.addWidget(self.desc); layout.addWidget(self.btn)
        self.w = DetailWorker(sid); self.w.detail_fetched.connect(self.upd); self.w.start()

    def upd(self, d):
        if d['info']:
            s = d['info'].get('rating', {}).get('score', '暂无'); dt = d['info'].get('date', '未知')
            self.info.setText(f"<b>⭐ 官方评分：</b><font color='#E6A23C'><b>{s}</b></font> &nbsp;&nbsp;|&nbsp;&nbsp; <b>📅 首播：</b>{dt} <br><br><b>📺 全网放送进度：</b>已播 <font color='#3B82F6'><b>{d['episodes']['aired']}</b></font> / {d['episodes']['total']} 集")
            html_desc = f"<p style='line-height:1.5;'>{d['info'].get('summary', '暂无官方剧情介绍...')}</p>"
            if d.get('comments'):
                html_desc += "<hr><h3 style='color:#3B82F6; margin-bottom:5px;'>💬 网友热评</h3>"
                for c in d['comments']:
                    star = c['star']; star_str = f"<font color='#E6A23C'>{'★'*(star//2) + ('☆' if star%2 else '')}</font>" if star > 0 else "未打分"
                    html_desc += f"<b style='font-size:13px;'>{c['user']}</b> &nbsp;{star_str}<br><span>{c['text']}</span><br><br>"
            self.desc.setHtml(html_desc)
        if d.get('user_col'):
            uc = d['user_col']
            idx_s = self.status_box.findData(uc.get('type', 0))
            if idx_s >= 0: self.status_box.setCurrentIndex(idx_s)
            idx_r = self.rate_box.findData(uc.get('rate', 0))
            if idx_r >= 0: self.rate_box.setCurrentIndex(idx_r)
            self.comment_in.setText(uc.get('comment', '') or ''); self.save_btn.setText("🔄 更新同步")
            s_map = {1: "想看", 2: "看过", 3: "在看", 4: "搁置", 5: "抛弃"}; my_status = s_map.get(uc.get('type', 0), "已收藏")
            my_rate = f"{uc.get('rate')} 分" if uc.get('rate') else "未打分"; my_comment = uc.get('comment', '') or "暂无吐槽"
            theme = APP_CONFIG.get('theme', 'light'); bg_c = "#EFF6FF" if theme == 'light' else "#1E3A8A"; text_c = "#1D4ED8" if theme == 'light' else "#BFDBFE"
            self.my_review.setStyleSheet(f"background-color: {bg_c}; color: {text_c}; padding: 10px; border-radius: 6px;")
            self.my_review.setText(f"<b>🙋‍♂️ 我的评价 ({my_status})</b><br>⭐ 评分: {my_rate}<br>💬 吐槽: {my_comment}"); self.my_review.show()
        self.btn.setEnabled(True)

    def save_collection(self):
        s_type = self.status_box.currentData()
        if s_type == 0: CustomMessageBox.show(self, "提示", "请选择收藏状态！", "warning"); return
        self.save_btn.setText("⏳ 同步中..."); self.save_btn.setEnabled(False)
        self.upd_w = CollectionUpdateWorker(self.sid, s_type, self.rate_box.currentData(), self.comment_in.text().strip()); self.upd_w.update_done.connect(self.on_save_done); self.upd_w.start()

    def on_save_done(self, success, msg):
        self.save_btn.setText("💾 云端同步"); self.save_btn.setEnabled(True)
        if success: CustomMessageBox.show(self, "大成功", msg, "success"); self.w = DetailWorker(self.sid); self.w.detail_fetched.connect(self.upd); self.w.start()
        else: CustomMessageBox.show(self, "失败", msg, "error")

class EpisodeDialog(QDialog):
    def __init__(self, name, eps, parent=None):
        super().__init__(parent); layout = setup_frameless_dialog(self, "选集下载", 750, 500)
        self.list = QListWidget(); self.list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        for e in eps:
            item = QListWidgetItem(f"⭐ [全集] {e['title']}" if e.get('is_batch') else e['title']); item.setData(Qt.ItemDataRole.UserRole, e['link'])
            if e.get('is_batch'): item.setForeground(QColor("#E6A23C"))
            self.list.addItem(item)
        layout.addWidget(self.list); btn_box = QHBoxLayout(); down = QPushButton("🚀 下载选中项"); down.clicked.connect(self.do_down)
        all_btn = QPushButton("全选"); all_btn.setObjectName("GrayBtn"); all_btn.clicked.connect(self.list.selectAll)
        btn_box.addWidget(all_btn); btn_box.addStretch(); btn_box.addWidget(down); layout.addLayout(btn_box)
        
    def do_down(self):
        items = self.list.selectedItems()
        if not items: return
        if CustomMessageBox.confirm(self, "确认", f"推送 {len(items)} 个任务？"):
            try:
                qbt = Client(host=APP_CONFIG['qbt_host'], port=APP_CONFIG['qbt_port'], username=APP_CONFIG['qbt_user'], password=APP_CONFIG['qbt_pass']); qbt.auth_log_in(); count = 0
                for i in items:
                    u = i.data(Qt.ItemDataRole.UserRole)
                    if u.startswith('magnet:'): qbt.torrents_add(urls=u)
                    else:
                        r = http_session.get(u, timeout=10)
                        if r.status_code == 200: qbt.torrents_add(torrent_files={'t.torrent': r.content})
                    count += 1
                CustomMessageBox.show(self, "成功", f"✅ 推送 {count} 个任务！", "success"); self.accept()
            except: CustomMessageBox.show(self, "错误", "推送失败，请检查配置", "error")

class MyCollectionDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent); self.parent = parent; self.workers = [] 
        layout = setup_frameless_dialog(self, "我的番剧库", 680, 580); h = QHBoxLayout(); h.addWidget(QLabel("<h3 style='margin:0;'>追番库</h3>")); h.addStretch()
        self.type_combo = QComboBox(); self.type_combo.addItems(["想看 (Wish)", "看过 (Collect)", "在看 (Do)", "搁置 (On Hold)", "抛弃 (Dropped)"])
        self.type_combo.setItemData(0, 1); self.type_combo.setItemData(1, 2); self.type_combo.setItemData(2, 3); self.type_combo.setItemData(3, 4); self.type_combo.setItemData(4, 5); self.type_combo.setCurrentIndex(2)
        self.type_combo.currentIndexChanged.connect(self.load); h.addWidget(self.type_combo)
        ref = QPushButton("🔄 刷新"); ref.setFixedWidth(90); ref.setObjectName("GrayBtn"); ref.clicked.connect(self.load); h.addWidget(ref); layout.addLayout(h)
        layout.addWidget(QLabel("💡 提示: 点击标题可查看详情或去下载。")); self.list = QListWidget(); layout.addWidget(self.list); self.load()
        
    def load(self):
        self.list.clear(); self.list.addItem("⏳ 正在穿越次元壁请求数据..."); status_type = self.type_combo.currentData()
        self.w = MyCollectionWorker(status_type); self.w.data_fetched.connect(self.render); self.w.start()
        
    def render(self, colls, err):
        self.list.clear()
        if err: self.list.addItem(f"❌ {err}"); return
        if not colls: self.list.addItem("这个列表空空如也..."); return
        status_type = self.type_combo.currentData()
        for c in colls:
            s = c.get('subject', {}); name = s.get('name_cn') or s.get('name', '未知'); sid = s.get('id'); cur = c.get('ep_status', 0); tot = s.get('eps', 0)
            w = QWidget(); w.setMinimumHeight(65); l = QHBoxLayout(w); l.setContentsMargins(15, 5, 15, 5)
            t = QLabel(f"<b style='font-size:14px; text-decoration: underline; color:#3B82F6;'>{name}</b>"); t.setCursor(Qt.CursorShape.PointingHandCursor)
            t.mousePressEvent = lambda e, i=sid, n=name: self.down(i, n); p = QLabel(f"进度: {cur} / {tot if tot > 0 else '?'}"); l.addWidget(t); l.addStretch(); l.addWidget(p)
            if status_type == 3:
                btn = QPushButton("看完 +1"); btn.setFixedWidth(80); btn.setObjectName("OrangeBtn"); btn.setProperty("current_ep", cur)
                btn.clicked.connect(lambda ch, i=sid, b=btn, lp=p, total=tot: self.prog(i, b, lp, total)); l.addWidget(btn)
            item = QListWidgetItem(self.list); item.setSizeHint(QSize(0, 65)); self.list.setItemWidget(item, w)
            
    def prog(self, sid, btn, lp, tot):
        cur = btn.property("current_ep"); btn.setEnabled(False); btn.setText("更新中...")
        worker = EpProgressWorker(sid, cur + 1); self.workers.append(worker); worker.update_done.connect(lambda ok, msg, w=worker: self.on_prog_done(ok, msg, btn, lp, cur + 1, tot, w)); worker.start()

    def on_prog_done(self, ok, msg, btn, lp, new_ep, tot, worker):
        if worker in self.workers: self.workers.remove(worker)
        worker.deleteLater()
        if ok: btn.setProperty("current_ep", new_ep); lp.setText(f"进度: {new_ep} / {tot if tot > 0 else '?'}"); btn.setEnabled(True); btn.setText("看完 +1")
        else: btn.setEnabled(True); btn.setText("看完 +1"); CustomMessageBox.show(self, "更新失败", msg, "error")
            
    def down(self, sid, name):
        if DetailDialog(sid, name, self).exec() == QDialog.DialogCode.Accepted: self.parent.show_config(name, sid)