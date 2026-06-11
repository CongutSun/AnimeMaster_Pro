import requests, re, urllib.parse
import feedparser
from bs4 import BeautifulSoup
from PyQt6.QtCore import QThread, pyqtSignal
from config import APP_CONFIG, http_session
import concurrent.futures 

SUPPORTED_SITES = {
    "MonikaDesign": {"enabled": True},
    "Mikan Project": {"enabled": True},
    "动漫花园": {"enabled": True},
}

RESOURCE_PROXY_HOSTS = {"mikanani.me", "mikanime.tv", "share.dmhy.org"}

class SearchWorker(QThread):
    # ✨ 新增错误数组回调和进度条信号
    search_done = pyqtSignal(str, str, list, list) # status, msg, results, error_logs
    search_progress = pyqtSignal(int, int, str)    # completed, total, current_site_name
    
    def __init__(self, name, sites, qual, excl, incl):
        super().__init__()
        self.name = name
        self.sites = sites
        self.qual = qual
        self.excl = [w.strip().lower() for w in excl.replace('，', ',').split(',') if w.strip()]
        self.incl = [w.strip().lower() for w in incl.replace('，', ',').split(',') if w.strip()]
        self.routes = {
            "MonikaDesign": self._search_monika,
            "Mikan Project": self._search_mikan,
            "动漫花园": self._search_dmhy,
        }

    def _fetch_single_site(self, site, custom_rss_dict):
        # 注意这里我们把 exception 往外抛，为了让主线程记录错误原因
        if site in self.routes:
            return self.routes[site]()
        elif site in custom_rss_dict:
            return self._search_rss(site, custom_rss_dict[site])
        return []

    def run(self):
        all_results = []
        errors = []
        custom_rss_dict = {item['name']: item['url'] for item in APP_CONFIG.get('custom_rss', [])}
        max_workers = len(self.sites) if self.sites else 1
        completed = 0
        total = len(self.sites)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_site = {
                executor.submit(self._fetch_single_site, site, custom_rss_dict): site 
                for site in self.sites
            }
            
            for future in concurrent.futures.as_completed(future_to_site):
                site = future_to_site[future]
                try:
                    res = future.result()
                    if res: 
                        all_results.extend(res)
                    else:
                        errors.append(f"[{site}] 未找到资源 (可能是名称不匹配或被你的包含/排除词拦截)")
                except Exception as e:
                    errors.append(f"[{site}] 搜刮异常: {str(e)}")
                    
                completed += 1
                self.search_progress.emit(completed, total, site) # ✨ 发送进度
                    
        if not all_results: 
            self.search_done.emit("warning", "选定的资源站中未找到符合条件的资源", [], errors)
        else:
            for i in all_results: 
                i['is_batch'] = bool(re.search(r'(01-\d{2}|全集|合集|Batch|Complete|Fin)', i['title'], re.IGNORECASE))
            all_results.sort(key=lambda x: not x['is_batch'])
            self.search_done.emit("success", f"共找到 {len(all_results)} 条聚合资源", all_results, errors)

    def valid(self, t):
        t = t.lower()
        if self.qual and self.qual.lower() not in t: return False
        if any(x in t for x in self.excl): return False
        if self.incl:
            if not any(x in t for x in self.incl): return False
        return True

    def _get_rss_download_link(self, entry):
        for enclosure in entry.get('enclosures', []):
            href = enclosure.get('href') or enclosure.get('url')
            if href:
                return href
        for link in entry.get('links', []):
            href = link.get('href')
            if href and link.get('type') == 'application/x-bittorrent':
                return href
        return entry.get('link', '')

    def _gateway_base(self):
        return APP_CONFIG.get('bangumi_gateway', '').strip().rstrip('/')

    def _normalize_resource_url(self, url):
        if not url or url.startswith('magnet:'):
            return url
        try:
            parsed = urllib.parse.urlsplit(url)
        except Exception:
            return url
        if parsed.hostname and parsed.hostname.lower() in RESOURCE_PROXY_HOSTS and parsed.scheme == 'http':
            parsed = parsed._replace(scheme='https')
            return urllib.parse.urlunsplit(parsed)
        return url

    def _proxy_resource_url(self, url, mode):
        url = self._normalize_resource_url(url)
        if not url or url.startswith('magnet:'):
            return url

        gateway = self._gateway_base()
        if not gateway:
            return url

        try:
            parsed = urllib.parse.urlsplit(url)
            gateway_host = urllib.parse.urlsplit(gateway).hostname
        except Exception:
            return url

        if parsed.hostname == gateway_host and parsed.path.startswith('/proxy/'):
            return url
        if not parsed.hostname or parsed.hostname.lower() not in RESOURCE_PROXY_HOSTS:
            return url
        return f"{gateway}/proxy/{mode}?url={urllib.parse.quote(url, safe='')}"

    def _search_rss(self, site_name, url_template):
        url = url_template.replace("{keyword}", urllib.parse.quote(self.name))
        try:
            r = http_session.get(self._proxy_resource_url(url, 'rss'), timeout=15)
            if r.status_code != 200: raise Exception(f"HTTP网络拒绝，状态码 {r.status_code}")
            f = feedparser.parse(r.text)
        except Exception as e:
            raise Exception(f"网络请求或解析失败 ({e})")
            
        results = []
        for e in f.entries:
            full_text = e.title
            if hasattr(e, 'description'):
                desc_text = BeautifulSoup(e.description, "html.parser").get_text(separator=" ", strip=True)
                full_text += f" {desc_text}"
            
            if self.valid(full_text):
                dl_link = self._get_rss_download_link(e)
                if "passkey=" not in dl_link:
                    passkey_match = re.search(r'passkey=([a-zA-Z0-9]+)', url_template)
                    if passkey_match:
                        connector = "&" if "?" in dl_link else "?"
                        dl_link = f"{dl_link}{connector}passkey={passkey_match.group(1)}"
                dl_link = self._proxy_resource_url(dl_link, 'torrent')
                results.append({"title": f"[{site_name}] {e.title}", "link": dl_link})
                
        if not results and len(f.entries) > 0:
            raise Exception(f"网站找到了 {len(f.entries)} 条数据，但都被你的[画质/排除词/包含词]过滤掉了。")
        return results

    def _search_mikan(self):
        try:
            rss_url = f"https://mikanani.me/RSS/Search?searchstr={urllib.parse.quote(self.name)}"
            r = http_session.get(self._proxy_resource_url(rss_url, 'rss'), timeout=10)
            if r.status_code != 200: raise Exception(f"Mikan拒绝访问，状态码 {r.status_code}")
            f = feedparser.parse(r.text)
            return [{"title": f"[Mikan] {e.title}", "link": self._proxy_resource_url(self._get_rss_download_link(e), 'torrent')} for e in f.entries if self.valid(e.title)]
        except Exception as e: raise Exception(f"Mikan解析失败 ({e})")

    def _search_dmhy(self):
        return self._search_rss("动漫花园", "https://share.dmhy.org/topics/rss/rss.xml?keyword={keyword}")
        
    def _search_monika(self):
        found = []; seen = set(); visited = set()
        def extract_from_soup(soup_obj):
            extracted = []
            rows = soup_obj.find_all('tr') + soup_obj.find_all('div', class_=re.compile(r'(block|single|item|row|flex)', re.I))
            for row in rows:
                row_text = row.get_text(separator=' ', strip=True)
                if not row_text or not self.valid(row_text): continue
                title_a = row.find('a', class_='view-torrent') or row.find('a', href=re.compile(r'/torrent(s)?/\d+'))
                title = title_a.get_text(strip=True) if title_a else ""
                if not title:
                    a_tags = [a.get_text(strip=True) for a in row.find_all('a') if len(a.get_text(strip=True)) > 5]
                    if a_tags: title = max(a_tags, key=len)
                    else: continue
                dl_a = None
                dl_icon = row.find('i', class_=re.compile(r'fa-download'))
                if dl_icon and dl_icon.find_parent('a'): dl_a = dl_icon.find_parent('a')
                if not dl_a: dl_a = row.find('a', href=re.compile(r'(/download/|magnet:\?xt=)', re.I))
                if dl_a and dl_a.has_attr('href'):
                    url = dl_a['href']
                    if not url.startswith('http') and not url.startswith('magnet'): url = 'https://monikadesign.uk' + url
                    if url not in seen:
                        extracted.append({"title": f"[Monika] {title}", "link": url})
                        seen.add(url)
                else:
                    if title_a and title_a.has_attr('href'):
                        d_url = title_a['href']
                        if not d_url.startswith('http'): d_url = 'https://monikadesign.uk' + d_url
                        if d_url in visited: continue
                        visited.add(d_url)
                        try:
                            ir = http_session.get(d_url, timeout=5)
                            isoup = BeautifulSoup(ir.text, 'html.parser')
                            magnet = next((x['href'] for x in isoup.find_all('a', href=True) if x['href'].startswith('magnet:') or '/download/' in x['href']), None)
                            if magnet and magnet not in seen:
                                if not magnet.startswith('http') and not magnet.startswith('magnet'): magnet = 'https://monikadesign.uk' + magnet
                                extracted.append({"title": f"[Monika] {title}", "link": magnet})
                                seen.add(magnet)
                        except: pass
            return extracted
        try:
            search_url = f"https://monikadesign.uk/torrents?name={urllib.parse.quote(self.name)}"
            r = http_session.get(search_url, timeout=10)
            if r.status_code != 200: raise Exception(f"Monika网络拒绝，状态码 {r.status_code}")
            soup = BeautifulSoup(r.text, 'html.parser')
            found.extend(extract_from_soup(soup))
            series_urls = []
            for a in soup.find_all('a', href=re.compile(r'/(series|group|groups|collection|collections|similar)/\w+', re.I)):
                href = a['href']
                if 'download' in href: continue
                if not href.startswith('http'): href = 'https://monikadesign.uk' + href
                if href not in series_urls: series_urls.append(href)
            for s_url in series_urls[:3]:
                if s_url in visited: continue
                visited.add(s_url)
                try:
                    sr = http_session.get(s_url, timeout=10)
                    ssoup = BeautifulSoup(sr.text, 'html.parser')
                    found.extend(extract_from_soup(ssoup))
                except: continue
        except Exception as e: raise Exception(f"Monika爬取失败: {e}")
        return found
