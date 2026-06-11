import os, subprocess, re, requests, urllib.parse
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
                             QPushButton, QLabel, QScrollArea, QGridLayout, QSizeGrip,
                             QSystemTrayIcon, QMenu, QApplication, QFileDialog, QMessageBox, QComboBox, QDialog, QCheckBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal 
from PyQt6.QtGui import QAction, QPixmap

from config import APP_CONFIG, save_config
from ui.theme import apply_global_theme
from api.bangumi import CalendarWorker, YearTopWorker, GlobalImageFetcher, BangumiAPI
from api.scraper import SearchWorker, SUPPORTED_SITES
from ui.components import CustomTitleBar, AnimeCard, setup_frameless_dialog, BackgroundFrame, CustomMessageBox
from ui.dialogs import CloseConfirmDialog, SettingsDialog, MyCollectionDialog, DetailDialog, EpisodeDialog, AliasSelectDialog

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(1000, 750)
        self.api = BangumiAPI()
        self.threads = []
        
        self.image_fetcher = GlobalImageFetcher()
        self.image_fetcher.image_loaded.connect(self.apply_image_to_card)
        self.image_fetcher.start()
        self.url_to_cards = {}  
        
        self.main_frame = BackgroundFrame() 
        self.setCentralWidget(self.main_frame)
        
        main_lay = QVBoxLayout(self.main_frame)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(0)
        
        self.title_bar = CustomTitleBar(self, "智能追番助手 Pro", show_max=True)
        main_lay.addWidget(self.title_bar)
        
        self.content_widget = QWidget()
        self.content_widget.setObjectName("ContentWidget")
        self.main_lay = QVBoxLayout(self.content_widget)
        self.main_lay.setContentsMargins(20, 15, 20, 20)
        main_lay.addWidget(self.content_widget)
        
        self.grip = QSizeGrip(self.main_frame)
        self.grip.setFixedSize(15, 15)
        
        toolbar = QHBoxLayout()
        # ✨ 修改：加入搜索分类下拉框
        self.type_combo = QComboBox()
        self.type_combo.addItems(["📺 搜番剧", "📚 搜书籍"])
        self.type_combo.setFixedWidth(100)
        
        self.input = QLineEdit()
        self.input.setPlaceholderText("输入关键字，例如：葬送的芙莉莲")
        self.btn = QPushButton("🔍 搜索")
        self.btn.setFixedWidth(100)
        self.btn.clicked.connect(self.run_search)
        self.input.returnPressed.connect(self.run_search)
        
        my_btn = QPushButton("📚 我的收藏")
        my_btn.setObjectName("RedBtn")
        my_btn.clicked.connect(self.open_my)
        
        qbt_btn = QPushButton("🚀 qBit")
        qbt_btn.setObjectName("GreenBtn")
        qbt_btn.clicked.connect(self.launch_qbt)
        
        set_btn = QPushButton("⚙️ 设置")
        set_btn.setObjectName("GrayBtn")
        set_btn.clicked.connect(self.open_set)
        
        toolbar.addWidget(self.type_combo)
        toolbar.addWidget(self.input)
        toolbar.addWidget(self.btn)
        toolbar.addWidget(my_btn)
        toolbar.addWidget(qbt_btn)
        toolbar.addWidget(set_btn)
        self.main_lay.addLayout(toolbar)
        
        self.scroll = QScrollArea()
        self.scroll.setStyleSheet("border: none; background-color: transparent;")
        
        self.container = QWidget()
        self.container_lay = QVBoxLayout(self.container)
        self.container_lay.setContentsMargins(0, 0, 0, 0)
        
        self.home_widget = QWidget()
        self.home_lay = QVBoxLayout(self.home_widget)
        self.home_lay.setContentsMargins(0, 0, 0, 0)
        
        self.today_lbl = QLabel("📺 加载中...")
        self.today_lbl.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.today_grid = QGridLayout()
        self.home_lay.addWidget(self.today_lbl)
        self.home_lay.addLayout(self.today_grid)
        
        self.top_lbl = QLabel("🏆 本年度高分榜")
        self.top_lbl.setStyleSheet("font-size: 18px; font-weight: bold; margin-top: 25px;")
        self.top_grid = QGridLayout()
        self.home_lay.addWidget(self.top_lbl)
        self.home_lay.addLayout(self.top_grid)
        
        self.container_lay.addWidget(self.home_widget)
        
        self.search_widget = QWidget()
        self.search_lay = QVBoxLayout(self.search_widget)
        self.search_lay.setContentsMargins(0, 0, 0, 0)
        
        self.search_lbl = QLabel("🔍 搜索结果")
        self.search_lbl.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.search_grid = QGridLayout()
        
        self.search_lay.addWidget(self.search_lbl)
        self.search_lay.addLayout(self.search_grid)
        self.search_widget.hide() 
        
        self.container_lay.addWidget(self.search_widget)
        self.container_lay.addStretch()
        
        self.scroll.setWidget(self.container)
        self.scroll.setWidgetResizable(True)
        self.main_lay.addWidget(self.scroll)
        
        apply_global_theme()
        self.load_home()
        self.setup_tray()

    def request_image(self, url, card):
        if url not in self.url_to_cards:
            self.url_to_cards[url] = []
        self.url_to_cards[url].append(card)
        self.image_fetcher.fetch(url)

    def apply_image_to_card(self, url, qimg):
        if url in self.url_to_cards:
            for card in self.url_to_cards[url]:
                try: card.img.setPixmap(QPixmap.fromImage(qimg))
                except: pass
            del self.url_to_cards[url]

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.grip.move(self.width() - 15, self.height() - 15)

    def setup_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QApplication.windowIcon())
        tray_menu = QMenu()
        show_action = QAction("显示主窗口", self)
        show_action.triggered.connect(self.showNormal)
        quit_action = QAction("完全退出", self)
        quit_action.triggered.connect(self.safe_quit)
        tray_menu.addAction(show_action)
        tray_menu.addSeparator()
        tray_menu.addAction(quit_action)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.tray_clicked)
        self.tray_icon.show()

    def tray_clicked(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick: 
            self.showNormal()
            self.activateWindow()

    def stop_all_threads(self):
        if hasattr(self, 'image_fetcher'):
            self.image_fetcher.stop()
            self.image_fetcher.wait()
            
        for worker in self.threads[:]:
            if worker.isRunning():
                worker.terminate()
                worker.wait()
            self.cleanup_thread(worker)

    def safe_quit(self):
        self.stop_all_threads()
        QApplication.instance().quit()

    def closeEvent(self, event):
        action = APP_CONFIG.get('close_action', 0)
        if action == 1:
            event.ignore()
            self.hide()
            self.tray_icon.showMessage("智能追番助手", "已最小化至系统托盘后台运行", QSystemTrayIcon.MessageIcon.Information, 2000)
            return
        elif action == 2:
            event.accept()
            self.safe_quit()
            return
            
        dialog = CloseConfirmDialog(self)
        result = dialog.exec()
        if result == 1:
            if dialog.remember:
                APP_CONFIG['close_action'] = 1
                save_config(APP_CONFIG)
            event.ignore()
            self.hide()
            self.tray_icon.showMessage("智能追番助手", "已最小化至系统托盘后台运行", QSystemTrayIcon.MessageIcon.Information, 2000)
        elif result == 2:
            if dialog.remember:
                APP_CONFIG['close_action'] = 2
                save_config(APP_CONFIG)
            event.accept()
            self.safe_quit()
        else:
            event.ignore()

    def launch_qbt(self):
        p = APP_CONFIG.get('qbt_path', '')
        if p and os.path.exists(p): 
            subprocess.Popen([p])
        else: 
            CustomMessageBox.show(self, "提示", "请先在设置中配置 qBittorrent 客户端路径", "warning")
            
    def open_my(self): 
        MyCollectionDialog(self).exec()
        
    def open_set(self): 
        SettingsDialog(self).exec()
        
    def clear_grid(self, grid):
        for i in reversed(range(grid.count())):
            w = grid.itemAt(i).widget()
            if w: w.setParent(None)

    def cleanup_thread(self, worker):
        if worker in self.threads:
            self.threads.remove(worker)
        worker.deleteLater()

    def load_home(self): 
        self.w = CalendarWorker()
        self.threads.append(self.w)
        self.w.data_fetched.connect(self.render_home)
        self.w.finished.connect(lambda: self.cleanup_thread(self.w))
        self.w.start()
        
        self.top_w = YearTopWorker()
        self.threads.append(self.top_w)
        self.top_w.data_fetched.connect(self.render_top)
        self.top_w.finished.connect(lambda: self.cleanup_thread(self.top_w))
        self.top_w.start()
        
    def render_home(self, items, day):
        self.today_lbl.setText(f"📺 {day} · 今日新番放送")
        self.clear_grid(self.today_grid)
        for i, item in enumerate(items):
            c = AnimeCard(item['id'], item.get('name_cn') or item['name'])
            c.clicked.connect(lambda sid, name: self.handle_click(sid, name, False))
            self.today_grid.addWidget(c, i // 4, i % 4)
            if item.get('images', {}).get('large'):
                self.request_image(item['images']['large'], c)

    def render_top(self, items):
        if not items:
            self.top_lbl.setText("🏆 高分榜 (暂无数据)")
        self.clear_grid(self.top_grid)
        for i, item in enumerate(items):
            score = item.get('rating', {}).get('score', 0)
            name = f"⭐{score} {item.get('name_cn') or item['name']}"
            c = AnimeCard(item['id'], name)
            c.clicked.connect(lambda sid, name: self.handle_click(sid, name, False))
            self.top_grid.addWidget(c, i // 4, i % 4)
            if item.get('images', {}).get('large'):
                self.request_image(item['images']['large'], c)
                
    def run_search(self):
        kw = self.input.text().strip()
        if not kw: 
            self.search_widget.hide()
            self.home_widget.show()
            return
            
        self.home_widget.hide()
        self.search_widget.show()
        self.search_lbl.setText(f"🔍 '{kw}' 的搜索结果...")
        self.btn.setEnabled(False)
        self.clear_grid(self.search_grid)
        
        # ✨ 修改：区分类型搜索
        search_type = 1 if self.type_combo.currentIndex() == 1 else 2
        self.search_w = SearchWorkerThread(self.api, kw, search_type)
        self.threads.append(self.search_w)
        self.search_w.search_done.connect(self.render_search)
        self.search_w.finished.connect(lambda: self.cleanup_thread(self.search_w))
        self.search_w.start()

    def render_search(self, res):
        if res:
            for i, item in enumerate(res):
                c = AnimeCard(item['id'], item.get('name_cn') or item['name'])
                c.clicked.connect(self.handle_search_click)
                self.search_grid.addWidget(c, i // 4, i % 4)
                if item.get('images', {}).get('common'):
                    self.request_image(item['images']['common'], c)
        self.btn.setEnabled(True)

    # ✨ 修改：加入对是否是书籍的判断
    def handle_search_click(self, sid, name):
        is_book = self.type_combo.currentIndex() == 1
        self.handle_click(sid, name, is_book)

    def handle_click(self, sid, name, is_book=False):
        clean_name = name.split(" ", 1)[1] if name.startswith("⭐") else name
        if DetailDialog(sid, clean_name, is_book, self).exec() == QDialog.DialogCode.Accepted: 
            self.show_config(clean_name, sid)
            
    def show_config(self, name, sid=None):
        conf = QDialog(self)
        lay = setup_frameless_dialog(conf, "聚合搜刮配置", 520, 600) 
        
        clean_name = re.sub(r'(第[一二三四五六七八九十\d]+季|Season\s*\d+|Part\s*\d+|第.*部分)', '', name, flags=re.IGNORECASE).strip()
        season_match = re.search(r'(第[一二三四五六七八九十\d]+季|Season\s*\d+|S\d+)', name, flags=re.IGNORECASE)
        filter_str = ""
        if season_match:
            s = season_match.group(1)
            if "第二季" in s or "S2" in s.upper(): filter_str = "S02, 第二季, 2nd"
            elif "第三季" in s or "S3" in s.upper(): filter_str = "S03, 第三季, 3rd"
            elif "第四季" in s or "S4" in s.upper(): filter_str = "S04, 第四季, 4th"
            else: filter_str = s
            
        lbl1 = QLabel("<b>1. 站点搜索词</b> (PT站推荐用英文/罗马音)：")
        lbl1.setWordWrap(True)
        lay.addWidget(lbl1)
        
        kw_lay = QHBoxLayout()
        kw_in = QLineEdit(clean_name)
        kw_lay.addWidget(kw_in)
        
        trans_btn = QPushButton("🏷️ 提取原名/别名")
        trans_btn.setObjectName("OrangeBtn")
        trans_btn.setToolTip("从Bangumi精确抓取所有外文别名！")
        kw_lay.addWidget(trans_btn)
        lay.addLayout(kw_lay)
        
        def do_translate():
            if not sid:
                CustomMessageBox.show(conf, "提示", "抱歉，直接搜索暂无法提取别名，请从首页卡片点击进入。", "warning")
                return
                
            trans_btn.setEnabled(False)
            trans_btn.setText("⏳ 获取中...")
            self.trans_worker = AliasFetcherThread(sid)
            self.threads.append(self.trans_worker)
            
            def on_done(aliases):
                trans_btn.setEnabled(True)
                trans_btn.setText("🏷️ 提取原名/别名")
                if aliases:
                    if len(aliases) == 1:
                        kw_in.setText(aliases[0])
                    else:
                        dlg = AliasSelectDialog(aliases, conf)
                        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.selected_alias:
                            kw_in.setText(dlg.selected_alias)
                else: 
                    CustomMessageBox.show(conf, "提示", "获取失败，可能由于网络原因或该番剧没有登记外文名。", "warning")
                    
            self.trans_worker.alias_fetched.connect(on_done)
            self.trans_worker.finished.connect(lambda: self.cleanup_thread(self.trans_worker))
            self.trans_worker.start()
            
        trans_btn.clicked.connect(do_translate)
        
        lay.addWidget(QLabel("<b>2. 结果必须包含词</b>："))
        incl_in = QLineEdit(filter_str)
        lay.addWidget(incl_in)

        lay.addWidget(QLabel("<b>3. 选择搜刮源</b>："))
        site_grid = QGridLayout()
        self.site_chips = []
        site_names = [s_name for s_name, cfg in SUPPORTED_SITES.items() if cfg["enabled"]]
        site_names.extend(s.get('name', '') for s in APP_CONFIG.get('custom_rss', []))
        all_sites = list(dict.fromkeys(s for s in site_names if s))
        
        for i, s_name in enumerate(all_sites):
            btn = QPushButton()
            btn.setCheckable(True)
            btn.setChecked(True)
            btn.setProperty("site_name", s_name)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            
            def update_style(checked, b=btn, n=s_name):
                if checked:
                    b.setText(f"✅ {n}")
                    b.setStyleSheet("""
                        QPushButton { background-color: #3B82F6; color: white; border: none; border-radius: 6px; padding: 8px; font-weight: bold; }
                        QPushButton:hover { background-color: #2563EB; }
                    """)
                else:
                    b.setText(f"❌ {n}")
                    b.setStyleSheet("""
                        QPushButton { background-color: transparent; color: #888888; border: 1px solid #888888; border-radius: 6px; padding: 8px; }
                        QPushButton:hover { background-color: rgba(136, 136, 136, 0.1); }
                    """)
                    
            btn.toggled.connect(update_style)
            update_style(True)
            self.site_chips.append(btn)
            site_grid.addWidget(btn, i // 2, i % 2)
            
        lay.addLayout(site_grid)
        
        h_lay = QHBoxLayout()
        qual = QLineEdit("1080"); excl = QLineEdit()
        h_lay.addLayout(self._create_v_box("画质:", qual))
        h_lay.addLayout(self._create_v_box("排除:", excl))
        lay.addLayout(h_lay)
        
        go = QPushButton("🚀 开始智能搜刮")
        go.setFixedHeight(42); go.setObjectName("BlueBtn")
        lay.addWidget(go)
        
        go.clicked.connect(lambda: self.scrap(kw_in.text().strip(), [b.property("site_name") for b in self.site_chips if b.isChecked()], qual.text(), excl.text(), incl_in.text(), conf, go))
        conf.exec()

    def _create_v_box(self, label, widget):
        v = QVBoxLayout(); v.addWidget(QLabel(f"<b>{label}</b>")); v.addWidget(widget); return v
        
    def scrap(self, name, sites, q, e, incl, diag, btn):
        if not sites: CustomMessageBox.show(diag, "提示", "请选择搜索源！", "warning"); return
        
        total_sites = len(sites)
        btn.setEnabled(False)
        btn.setText(f"⏳ 搜刮中 (0/{total_sites})...")
        
        self.sw = SearchWorker(name, sites, q, e, incl)
        self.threads.append(self.sw) 
        
        def on_prog(c, t, s):
            btn.setText(f"⏳ 搜刮中 ({c}/{t})...")
            
        self.sw.search_progress.connect(on_prog)
        self.sw.search_done.connect(lambda stat, msg, res, errs: self.show_eps(stat, msg, res, errs, diag))
        self.sw.finished.connect(lambda: self.cleanup_thread(self.sw))
        self.sw.start()
        
    def show_eps(self, stat, msg, res, errors, diag):
        diag.accept()
        
        if errors:
            err_text = "\n".join(errors)
            if not res:
                CustomMessageBox.show(self, "搜刮失败", f"很遗憾，未找到可用资源。\n各站反馈如下：\n\n{err_text}", "error")
                return
        
        if stat == "success": EpisodeDialog(self.sw.name, res, self).exec()
        else: CustomMessageBox.show(self, "提示", msg, "warning")

# ✨ 修改：加入了 type_
class SearchWorkerThread(QThread):
    search_done = pyqtSignal(list)
    def __init__(self, api, kw, type_=2): super().__init__(); self.api = api; self.kw = kw; self.type_ = type_
    def run(self): self.search_done.emit(self.api.search(self.kw, self.type_) or [])

class AliasFetcherThread(QThread):
    alias_fetched = pyqtSignal(list) 
    
    def __init__(self, sid): 
        super().__init__()
        self.sid = sid
        
    def run(self):
        if not self.sid:
            self.alias_fetched.emit([])
            return
            
        try:
            from api.bangumi import ApiConfig, bgm_session
            r = bgm_session.get(ApiConfig.api_url(f"/v0/subjects/{self.sid}"), timeout=5)
            if r.status_code == 200:
                data = r.json()
                aliases = []
                
                if data.get('name'): aliases.append(data.get('name'))
                for box in data.get('infobox', []):
                    if box.get('key') in ['别名', '英文名', '日文名']:
                        val = box.get('value')
                        if isinstance(val, list):
                            for v in val:
                                if isinstance(v, dict) and 'v' in v:
                                    aliases.append(v.get('v'))
                        elif isinstance(val, str):
                            aliases.append(val)
                            
                if not aliases and data.get('name_cn'):
                    aliases.append(data.get('name_cn'))

                unique_aliases = list(dict.fromkeys(aliases))
                self.alias_fetched.emit(unique_aliases)
            else:
                self.alias_fetched.emit([])
        except Exception as e:
            print(f"提取别名失败: {e}")
            self.alias_fetched.emit([])
