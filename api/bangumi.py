import requests, urllib.parse, datetime, json, os, hashlib
import queue, time
import concurrent.futures 
from bs4 import BeautifulSoup
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QImage, QPixmap
from config import APP_CONFIG, CACHE_DIR, IMG_CACHE_DIR

class ApiConfig:
    API_BASE = 'https://api.bgm.tv'
    WEB_BASE = 'https://bgm.tv'
    CHII_BASE = 'https://chii.in'
    USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

bgm_session = requests.Session()
bgm_session.headers.update({'User-Agent': ApiConfig.USER_AGENT})
IMAGE_CACHE = {}

class BangumiAPI:
    def search(self, keyword, type_=2):
        try:
            res = bgm_session.get(f"{ApiConfig.API_BASE}/search/subject/{urllib.parse.quote(keyword)}?type={type_}", timeout=10)
            if res.status_code == 200:
                return res.json().get('list', [])
            return None
        except Exception as e: 
            print(f"[BangumiAPI] Search Error: {e}")
            return None
        
    def get_calendar(self):
        try:
            res = bgm_session.get(f"{ApiConfig.API_BASE}/calendar", timeout=8)
            if res.status_code == 200:
                return res.json()
            return []
        except Exception as e: 
            print(f"[BangumiAPI] Calendar Error: {e}")
            return []

class BangumiAuthAPI:
    def __init__(self):
        self.username = APP_CONFIG.get('bgm_username', '')
        self.token = APP_CONFIG.get('bgm_token', '')
        self.headers = {'Authorization': f'Bearer {self.token}' if self.token else ''}
        
    def get_my_collection(self, status_type=3, subject_type=2):
        if not self.username or not self.token: return None, "未配置账号"
        try:
            res = bgm_session.get(f"{ApiConfig.API_BASE}/v0/users/{self.username}/collections?subject_type={subject_type}&type={status_type}&limit=100", headers=self.headers, timeout=10)
            if res.status_code == 200:
                return res.json().get('data', []), ""
            return None, f"同步失败(状态码:{res.status_code})"
        except Exception as e: 
            print(f"[BangumiAuth] Get Collection Error: {e}")
            return None, "网络异常"
        
    # ✨ 核心修复：根据 subject_type 严格分流调用的 API 接口
    def update_progress(self, sid, ep_status=None, vol_status=None, subject_type=2):
        if not self.token: return False, "未配置账号 Token"
        try:
            if subject_type == 2:
                # 📺 番剧 (Anime) 必须调用专门的 watched_eps 老接口
                url = f"{ApiConfig.API_BASE}/subject/{sid}/update/watched_eps"
                res = bgm_session.post(url, headers=self.headers, data={'watched_eps': str(ep_status)}, timeout=5)
                if res.status_code in [200, 202, 204]: 
                    return True, "番剧进度已成功同步！"
                else:
                    return False, f"API 拒绝更新番剧进度 (状态码: {res.status_code})"
            else:
                # 📚 书籍 (Book) 使用 v0 集合修改接口，支持卷话双轨
                url = f"{ApiConfig.API_BASE}/v0/users/-/collections/{sid}"
                payload = {}
                if ep_status is not None: payload['ep_status'] = int(ep_status)
                if vol_status is not None: payload['vol_status'] = int(vol_status)
                
                res = bgm_session.patch(url, headers=self.headers, json=payload, timeout=5)
                if res.status_code in [200, 202, 204]: 
                    return True, "书籍进度已成功同步！"
                else:
                    try: err_msg = res.json().get('message', res.text)
                    except: err_msg = res.text
                    return False, f"API 拒绝更新书籍进度 (状态码: {res.status_code})\n详情: {err_msg}"
        except Exception as e: 
            print(f"[BangumiAuth] Update Progress Error: {e}")
            return False, f"网络错误: {e}"

    # ✨ 核心修复：全量同步时也避免给番剧传非法参数
    def update_collection_status(self, subject_id, status_type, ep_status=0, vol_status=None, rating=0, comment="", subject_type=2):
        if not self.token: return False, "未配置账号 Token"
        try:
            url = f"{ApiConfig.API_BASE}/v0/users/-/collections/{subject_id}"
            payload = {
                "type": status_type, 
            }
            # 只有书籍可以在 collection 接口直接附带更新进度
            if subject_type == 1:
                payload["ep_status"] = int(ep_status)
                if vol_status is not None: 
                    payload["vol_status"] = int(vol_status)
                    
            if rating > 0: payload["rate"] = rating
            if comment: payload["comment"] = comment
            
            res = bgm_session.post(url, headers=self.headers, json=payload, timeout=5)
            
            if res.status_code not in [200, 202, 204]: 
                return False, f"同步状态失败，状态码: {res.status_code}"
                
            # 对于番剧，状态保存完后，必须额外调用专属接口更新其集数
            if subject_type == 2 and ep_status > 0:
                prog_url = f"{ApiConfig.API_BASE}/subject/{subject_id}/update/watched_eps"
                bgm_session.post(prog_url, headers=self.headers, data={'watched_eps': str(ep_status)}, timeout=5)
                
            return True, "状态已成功同步至云端！"
        except Exception as e: 
            print(f"[BangumiAuth] Update Status Error: {e}")
            return False, f"网络错误: {e}"

class CalendarWorker(QThread):
    data_fetched = pyqtSignal(list, str)
    def run(self):
        today_str = datetime.datetime.today().strftime("%Y%m%d")
        cache_file = os.path.join(CACHE_DIR, f"calendar_{today_str}.json")
        data = []
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f: data = json.load(f)
            except: pass
            
        if not data:
            data = BangumiAPI().get_calendar()
            if data:
                try:
                    with open(cache_file, 'w', encoding='utf-8') as f: json.dump(data, f)
                except: pass

        today_idx = datetime.datetime.today().weekday()
        days = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        items = next((day.get('items', []) for day in data if day.get('weekday', {}).get('id') == today_idx + 1), [])
        self.data_fetched.emit(items, days[today_idx])

class YearTopWorker(QThread):
    data_fetched = pyqtSignal(list)
    def _extract(self, url):
        results = []
        try:
            r = bgm_session.get(url, timeout=10)
            if r.status_code != 200: return results
            r.encoding = 'utf-8'
            soup = BeautifulSoup(r.text, 'html.parser')
            ul = soup.find('ul', id='browserItemList')
            if not ul: return results
            for item in ul.find_all('li', class_='item')[:8]:
                a_tag = item.find('a', class_='l')
                if not a_tag: continue
                sid = a_tag['href'].split('/')[-1]
                name = a_tag.text.strip()
                score_tag = item.find('small', class_='fade')
                score = score_tag.text.strip() if score_tag else "暂无"
                img_tag = item.find('img')
                img_url = ""
                if img_tag and img_tag.has_attr('src'):
                    img_url = img_tag['src'].replace('/s/', '/l/')
                    if img_url.startswith('//'): img_url = "https:" + img_url
                results.append({'id': int(sid) if sid.isdigit() else sid, 'name': name, 'rating': {'score': score}, 'images': {'large': img_url}})
        except Exception as e:
            print(f"[YearTopWorker] Extract Error: {e}")
        return results

    def run(self):
        year = datetime.datetime.today().year
        today_str = datetime.datetime.today().strftime("%Y%m%d")
        cache_file = os.path.join(CACHE_DIR, f"yeartop_{today_str}.json")
        results = []
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f: results = json.load(f)
            except: pass
            
        if not results:
            results = self._extract(f"{ApiConfig.WEB_BASE}/anime/browser/airtime/{year}?sort=rank")
            if not results: results = self._extract(f"{ApiConfig.WEB_BASE}/anime/browser?sort=rank")
            if results:
                try:
                    with open(cache_file, 'w', encoding='utf-8') as f: json.dump(results, f)
                except: pass
        self.data_fetched.emit(results)

class MyCollectionWorker(QThread):
    data_fetched = pyqtSignal(list, str) 
    def __init__(self, status_type=3, subject_type=2): 
        super().__init__()
        self.status_type = status_type
        self.subject_type = subject_type
        
    def run(self):
        data, err = BangumiAuthAPI().get_my_collection(self.status_type, self.subject_type)
        self.data_fetched.emit(data or [], err)

class DetailWorker(QThread):
    detail_fetched = pyqtSignal(dict)
    def __init__(self, sid): 
        super().__init__()
        self.sid = sid
        
    def run(self):
        res = {'info': None, 'episodes': {'total': 0, 'aired': 0}, 'user_col': None, 'comments': []}
        try:
            r1 = bgm_session.get(f"{ApiConfig.API_BASE}/v0/subjects/{self.sid}", timeout=8)
            if r1.status_code == 200: res['info'] = r1.json()
            
            r2 = bgm_session.get(f"{ApiConfig.API_BASE}/v0/episodes?subject_id={self.sid}", timeout=5)
            if r2.status_code == 200: 
                d = r2.json()
                res['episodes']['total'] = d.get('total', 0)
                res['episodes']['aired'] = sum(1 for e in d.get('data', []) if e.get('ep') and e.get('airdate'))
                
            auth_api = BangumiAuthAPI()
            if auth_api.token and auth_api.username:
                r3 = bgm_session.get(f"{ApiConfig.API_BASE}/v0/users/{auth_api.username}/collections/{self.sid}", headers=auth_api.headers, timeout=5)
                if r3.status_code == 200: res['user_col'] = r3.json()
                
            r4 = bgm_session.get(f"{ApiConfig.CHII_BASE}/subject/{self.sid}", timeout=5)
            r4.encoding = 'utf-8'
            if r4.status_code == 200:
                soup = BeautifulSoup(r4.text, 'html.parser')
                comments_div = soup.find('div', id='comment_box')
                if comments_div:
                    for item in comments_div.find_all('div', class_='item'):
                        if len(res['comments']) >= 10: break
                        user = item.find('a', class_='l')
                        text = item.find('p')
                        stars = item.find('span', class_='starlight')
                        if user and text:
                            star_num = 0
                            if stars and len(stars.get('class', [])) > 1:
                                s_class = stars['class'][1]
                                if s_class.startswith('stars'): star_num = int(s_class.replace('stars', ''))
                            res['comments'].append({'user': user.text.strip(), 'text': text.text.strip(), 'star': star_num})
        except Exception as e: 
            print(f"[DetailWorker] Fetch Error: {e}")
            
        self.detail_fetched.emit(res)

class CollectionUpdateWorker(QThread):
    update_done = pyqtSignal(bool, str)
    def __init__(self, sid, status_type, rating, comment, ep_status=0, vol_status=None, subject_type=2):
        super().__init__()
        self.sid = sid
        self.status_type = status_type
        self.rating = rating
        self.comment = comment
        self.ep_status = ep_status
        self.vol_status = vol_status
        self.subject_type = subject_type # ✨ 记录类型
        
    def run(self):
        success, msg = BangumiAuthAPI().update_collection_status(
            self.sid, self.status_type, self.ep_status, self.vol_status, self.rating, self.comment, self.subject_type
        )
        self.update_done.emit(success, msg)

class EpProgressWorker(QThread):
    update_done = pyqtSignal(bool, str)
    def __init__(self, sid, ep_status=None, vol_status=None, subject_type=2): 
        super().__init__()
        self.sid = sid
        self.ep_status = ep_status
        self.vol_status = vol_status
        self.subject_type = subject_type # ✨ 记录类型
        
    def run(self):
        success, msg = BangumiAuthAPI().update_progress(self.sid, self.ep_status, self.vol_status, self.subject_type)
        self.update_done.emit(success, msg)

class GlobalImageFetcher(QThread):
    image_loaded = pyqtSignal(str, QImage)
    
    def __init__(self):
        super().__init__()
        self.task_queue = queue.Queue()
        self._is_running = True
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)

    def fetch(self, url):
        self.task_queue.put(url)

    def stop(self):
        self._is_running = False
        self.executor.shutdown(wait=False)

    def run(self):
        while self._is_running:
            try:
                url = self.task_queue.get(timeout=0.1)
            except queue.Empty:
                continue
                
            if not self._is_running: break
            self.executor.submit(self._process_image, url)

    def _process_image(self, url):
        if url in IMAGE_CACHE:
            self.image_loaded.emit(url, IMAGE_CACHE[url])
            return

        url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()
        ext = url.split('.')[-1]
        if len(ext) > 5: ext = "jpg"
        local_path = os.path.join(IMG_CACHE_DIR, f"{url_hash}.{ext}")

        if os.path.exists(local_path):
            img = QImage(local_path)
            if not img.isNull():
                IMAGE_CACHE[url] = img
                self.image_loaded.emit(url, img)
                return

        try:
            r = bgm_session.get(url, timeout=5)
            if r.status_code == 200:
                img = QImage()
                img.loadFromData(r.content)
                scaled_img = img.scaled(140, 180, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                scaled_img.save(local_path)
                IMAGE_CACHE[url] = scaled_img
                self.image_loaded.emit(url, scaled_img)
        except Exception as e:
            print(f"[ImageFetcher] Error loading {url}: {e}")