import os, sys, json, requests
from PyQt6.QtWidgets import QApplication

def get_resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'): return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

USER_HOME = os.path.expanduser("~")
CONFIG_FILE = os.path.join(USER_HOME, ".bangumi_helper_config.json")

CACHE_DIR = os.path.join(USER_HOME, ".bangumi_helper_cache")
IMG_CACHE_DIR = os.path.join(CACHE_DIR, "images")
os.makedirs(IMG_CACHE_DIR, exist_ok=True)

# ✨ 修改：新增 qbt_dl_path 字段
DEFAULT_CONFIG = {
    "qbt_host": "localhost", "qbt_port": 8080, "qbt_user": "admin", "qbt_pass": "adminadmin",
    "qbt_path": "", "qbt_dl_path": "", "monika_cookie": "", "bg_image": "", "bg_align": 50, "bgm_username": "", "bgm_token": "",
    "bangumi_gateway": "https://auth.congutsun.com",
    "theme": "light", "close_action": 0, "custom_rss": []
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f: return {**DEFAULT_CONFIG, **json.load(f)}
        except: pass
    return DEFAULT_CONFIG.copy()

def save_config(config_data):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f: json.dump(config_data, f, indent=4)
    except: pass

APP_CONFIG = load_config()
http_session = requests.Session()

def update_session_headers():
    http_session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'Cookie': APP_CONFIG.get("monika_cookie", "")
    })
update_session_headers()

COMMON_BTN_QSS = """
    QPushButton#BlueBtn { background-color: #3B82F6; color: white; border: none; }
    QPushButton#BlueBtn:hover { background-color: #2563EB; }
    QPushButton#RedBtn { background-color: #D32F2F; color: white; border: none; }
    QPushButton#RedBtn:hover { background-color: #E53935; }
    QPushButton#GreenBtn { background-color: #2E7D32; color: white; border: none; }
    QPushButton#GreenBtn:hover { background-color: #388E3C; }
    QPushButton#OrangeBtn { background-color: #F57C00; color: white; border: none; }
    QPushButton#OrangeBtn:hover { background-color: #FB8C00; }
    QPushButton#GrayBtn { background-color: #616161; color: white; border: none; }
    QPushButton#GrayBtn:hover { background-color: #757575; }
"""

LIGHT_QSS = """
    QWidget { font-family: 'Microsoft YaHei', sans-serif; color: #333333; }
    QMainWindow, QDialog#FramelessDialog { background-color: transparent; }
    QMessageBox { background-color: #FFFFFF; }
    QFrame#MainFrame, QFrame#DialogFrame { background-color: #F3F4F6; border-radius: 10px; border: 1px solid #D1D5DB; }
    QFrame#TitleBar { background-color: #FFFFFF; border-top-left-radius: 10px; border-top-right-radius: 10px; border-bottom: 1px solid #E5E7EB; }
    QLabel#TitleLabel { color: #111827; font-size: 13px; font-weight: bold; border: none; }
    QLineEdit { padding: 4px 10px; min-height: 28px; border: 1px solid #D1D5DB; border-radius: 6px; background: #FFFFFF; color: #111827; font-size: 14px; }
    QLineEdit:focus { border: 1px solid #3B82F6; }
    QComboBox { background-color: #FFFFFF; color: #111827; border: 1px solid #D1D5DB; border-radius: 6px; padding: 4px 10px; min-height: 28px; }
    QComboBox QAbstractItemView { background-color: #FFFFFF; color: #111827; border: 1px solid #D1D5DB; selection-background-color: #EFF6FF; selection-color: #1D4ED8; outline: none; }
    QPushButton { background-color: #3B82F6; color: #FFFFFF; border-radius: 6px; padding: 8px 15px; font-weight: bold; font-size: 13px; border: none; }
    QPushButton:hover { background-color: #2563EB; }
    QFrame#AnimeCard { background-color: #FFFFFF; border-radius: 10px; border: 1px solid #E5E7EB; }
    QFrame#AnimeCard:hover { border: 1px solid #3B82F6; }
    QLabel#CardTitle { font-weight: bold; font-size: 13px; color: #1F2937; }
    QListWidget { border: 1px solid #D1D5DB; border-radius: 8px; background-color: #FFFFFF; outline: none; }
    QListWidget::item { border-bottom: 1px solid #F3F4F6; padding: 5px; color: #333333; }
    QListWidget::item:selected, QListWidget::item:selected:active, QListWidget::item:selected:!active { 
        background-color: #EFF6FF; border: 1px solid #93C5FD; border-radius: 4px; color: #1D4ED8; 
    }
    QTextEdit, QLabel#InfoPanel { background-color: #FFFFFF; color: #374151; border: 1px solid #D1D5DB; border-radius: 6px; padding: 10px; }
    QScrollBar:vertical { border: none; background: transparent; width: 8px; margin: 0px; }
    QScrollBar::handle:vertical { background: #D1D5DB; border-radius: 4px; min-height: 30px; }
    QScrollBar::handle:vertical:hover { background: #9CA3AF; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
    QSlider::groove:horizontal { height: 6px; background: #D1D5DB; border-radius: 3px; }
    QSlider::handle:horizontal { background: #3B82F6; width: 16px; margin: -5px 0; border-radius: 8px; }
""" + COMMON_BTN_QSS

DARK_QSS = """
    QWidget { font-family: 'Microsoft YaHei', sans-serif; color: #D4D4D4; }
    QMainWindow, QDialog#FramelessDialog { background-color: transparent; }
    QMessageBox { background-color: #2D2D30; }
    QFrame#MainFrame, QFrame#DialogFrame { background-color: #1E1E1E; border-radius: 10px; border: 1px solid #3F3F46; }
    QFrame#TitleBar { background-color: #2D2D30; border-top-left-radius: 10px; border-top-right-radius: 10px; border-bottom: 1px solid #3F3F46; }
    QLabel#TitleLabel { color: #CCCCCC; font-size: 13px; font-weight: bold; border: none; }
    QLineEdit { padding: 4px 10px; min-height: 28px; border: 1px solid #3C3C3C; border-radius: 6px; background: #252526; color: #D4D4D4; font-size: 14px; }
    QLineEdit:focus { border: 1px solid #007ACC; background: #2D2D2D; }
    QComboBox { background-color: #3C3C3C; color: white; border: 1px solid #555555; border-radius: 6px; padding: 4px 10px; min-height: 28px; }
    QComboBox QAbstractItemView { background-color: #2D2D30; color: #D4D4D4; border: 1px solid #3F3F46; selection-background-color: #007ACC; selection-color: white; outline: none; }
    QPushButton { background-color: #0E639C; color: #FFFFFF; border-radius: 6px; padding: 8px 15px; font-weight: bold; font-size: 13px; border: 1px solid #1177BB; }
    QPushButton:hover { background-color: #1177BB; }
    QFrame#AnimeCard { background-color: #252526; border-radius: 10px; border: 1px solid #333333; }
    QFrame#AnimeCard:hover { border: 1px solid #007ACC; }
    QLabel#CardTitle { font-weight: bold; font-size: 13px; color: #E0E0E0; }
    QListWidget { border: 1px solid #3C3C3C; border-radius: 8px; background-color: #1E1E1E; outline: none; }
    QListWidget::item { border-bottom: 1px solid #2D2D2D; padding: 5px; color: #D4D4D4; }
    QListWidget::item:selected, QListWidget::item:selected:active, QListWidget::item:selected:!active { 
        background-color: #37373D; border: 1px solid #007ACC; border-radius: 4px; color: #60A5FA; 
    }
    QTextEdit, QLabel#InfoPanel { background-color: #1E1E1E; color: #D4D4D4; border: 1px solid #3C3C3C; border-radius: 6px; padding: 10px; }
    QScrollBar:vertical { border: none; background: transparent; width: 8px; margin: 0px; }
    QScrollBar::handle:vertical { background: #555555; border-radius: 4px; min-height: 30px; }
    QScrollBar::handle:vertical:hover { background: #777777; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
    QSlider::groove:horizontal { height: 6px; background: #3C3C3C; border-radius: 3px; }
    QSlider::handle:horizontal { background: #007ACC; width: 16px; margin: -5px 0; border-radius: 8px; }
""" + COMMON_BTN_QSS
