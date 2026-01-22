"""
主流媒体来源映射配置
v4.9.0: 支持 URL 域名到媒体名称的映射

用途：
- 数据入库时解析 URL 域名
- source 字段 -> 媒体英文名称简称
- layer_name 字段 -> 媒体中文全称
"""

from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass
class MediaSource:
    """媒体来源信息"""

    domain: str  # 域名
    name_en: str  # 英文名称/简称
    name_zh: str  # 中文名称/全称
    region: str  # 地区
    category: str  # 类别: news, financial, tech, official, government


# 主流媒体映射字典 (domain -> MediaSource)
MEDIA_SOURCE_MAPPING: dict[str, MediaSource] = {
    # ========== 美国 ==========
    "cnn.com": MediaSource("cnn.com", "CNN", "美国有线电视新闻网", "北美", "news"),
    "nytimes.com": MediaSource("nytimes.com", "The New York Times", "纽约时报", "北美", "news"),
    "washingtonpost.com": MediaSource("washingtonpost.com", "The Washington Post", "华盛顿邮报", "北美", "news"),
    "latimes.com": MediaSource("latimes.com", "Los Angeles Times", "洛杉矶时报", "北美", "news"),
    "usatoday.com": MediaSource("usatoday.com", "USA Today", "今日美国", "北美", "news"),
    "wsj.com": MediaSource("wsj.com", "The Wall Street Journal", "华尔街日报", "北美", "financial"),
    "bloomberg.com": MediaSource("bloomberg.com", "Bloomberg", "彭博社", "北美", "financial"),
    "reuters.com": MediaSource("reuters.com", "Reuters", "路透社", "北美", "news"),
    "apnews.com": MediaSource("apnews.com", "Associated Press", "美联社", "北美", "news"),
    "nbcnews.com": MediaSource("nbcnews.com", "NBC News", "美国全国广播公司新闻", "北美", "news"),
    "cbsnews.com": MediaSource("cbsnews.com", "CBS News", "哥伦比亚广播公司新闻", "北美", "news"),
    "abcnews.go.com": MediaSource("abcnews.go.com", "ABC News", "美国广播公司新闻", "北美", "news"),
    "foxnews.com": MediaSource("foxnews.com", "Fox News", "福克斯新闻", "北美", "news"),
    "npr.org": MediaSource("npr.org", "NPR", "美国国家公共电台", "北美", "news"),
    "politico.com": MediaSource("politico.com", "Politico", "政客", "北美", "news"),
    "thehill.com": MediaSource("thehill.com", "The Hill", "国会山报", "北美", "news"),
    "axios.com": MediaSource("axios.com", "Axios", "Axios新闻", "北美", "news"),
    "vox.com": MediaSource("vox.com", "Vox", "Vox媒体", "北美", "news"),
    "huffpost.com": MediaSource("huffpost.com", "HuffPost", "赫芬顿邮报", "北美", "news"),
    "voanews.com": MediaSource("voanews.com", "Voice of America", "美国之音", "北美", "news"),
    # ========== 英国 ==========
    "bbc.com": MediaSource("bbc.com", "BBC News", "英国广播公司新闻", "欧洲", "news"),
    "bbc.co.uk": MediaSource("bbc.co.uk", "BBC News", "英国广播公司新闻", "欧洲", "news"),
    "theguardian.com": MediaSource("theguardian.com", "The Guardian", "卫报", "欧洲", "news"),
    "ft.com": MediaSource("ft.com", "Financial Times", "金融时报", "欧洲", "financial"),
    "telegraph.co.uk": MediaSource("telegraph.co.uk", "The Telegraph", "每日电讯报", "欧洲", "news"),
    "independent.co.uk": MediaSource("independent.co.uk", "The Independent", "独立报", "欧洲", "news"),
    "dailymail.co.uk": MediaSource("dailymail.co.uk", "Daily Mail", "每日邮报", "欧洲", "news"),
    "thetimes.co.uk": MediaSource("thetimes.co.uk", "The Times", "泰晤士报", "欧洲", "news"),
    "sky.com": MediaSource("sky.com", "Sky News", "天空新闻", "欧洲", "news"),
    # ========== 欧洲其他 ==========
    "lemonde.fr": MediaSource("lemonde.fr", "Le Monde", "世界报", "欧洲", "news"),
    "lefigaro.fr": MediaSource("lefigaro.fr", "Le Figaro", "费加罗报", "欧洲", "news"),
    "spiegel.de": MediaSource("spiegel.de", "Der Spiegel", "明镜周刊", "欧洲", "news"),
    "dw.com": MediaSource("dw.com", "Deutsche Welle", "德国之声", "欧洲", "news"),
    "faz.net": MediaSource("faz.net", "Frankfurter Allgemeine", "法兰克福汇报", "欧洲", "news"),
    "elpais.com": MediaSource("elpais.com", "El País", "国家报", "欧洲", "news"),
    "elmundo.es": MediaSource("elmundo.es", "El Mundo", "世界报(西班牙)", "欧洲", "news"),
    "repubblica.it": MediaSource("repubblica.it", "La Repubblica", "共和报", "欧洲", "news"),
    "corriere.it": MediaSource("corriere.it", "Corriere della Sera", "晚邮报", "欧洲", "news"),
    "nrc.nl": MediaSource("nrc.nl", "NRC Handelsblad", "荷兰商报", "欧洲", "news"),
    "rferl.org": MediaSource("rferl.org", "Radio Free Europe", "自由欧洲电台", "欧洲", "news"),
    # ========== 加拿大 ==========
    "cbc.ca": MediaSource("cbc.ca", "CBC News", "加拿大广播公司新闻", "北美", "news"),
    "globalnews.ca": MediaSource("globalnews.ca", "Global News", "环球新闻(加拿大)", "北美", "news"),
    "theglobeandmail.com": MediaSource("theglobeandmail.com", "The Globe and Mail", "环球邮报", "北美", "news"),
    "nationalpost.com": MediaSource("nationalpost.com", "National Post", "国家邮报", "北美", "news"),
    # ========== 澳大利亚/新西兰 ==========
    "abc.net.au": MediaSource("abc.net.au", "ABC News Australia", "澳大利亚广播公司新闻", "大洋洲", "news"),
    "sbs.com.au": MediaSource("sbs.com.au", "SBS News", "SBS新闻", "大洋洲", "news"),
    "smh.com.au": MediaSource("smh.com.au", "Sydney Morning Herald", "悉尼先驱晨报", "大洋洲", "news"),
    "theaustralian.com.au": MediaSource("theaustralian.com.au", "The Australian", "澳大利亚人报", "大洋洲", "news"),
    "nzherald.co.nz": MediaSource("nzherald.co.nz", "NZ Herald", "新西兰先驱报", "大洋洲", "news"),
    # ========== 日本 ==========
    "nhk.or.jp": MediaSource("nhk.or.jp", "NHK World", "日本放送协会世界新闻", "东亚", "news"),
    "asahi.com": MediaSource("asahi.com", "Asahi Shimbun", "朝日新闻", "东亚", "news"),
    "mainichi.jp": MediaSource("mainichi.jp", "Mainichi Shimbun", "每日新闻", "东亚", "news"),
    "yomiuri.co.jp": MediaSource("yomiuri.co.jp", "Yomiuri Shimbun", "读卖新闻", "东亚", "news"),
    "japantimes.co.jp": MediaSource("japantimes.co.jp", "The Japan Times", "日本时报", "东亚", "news"),
    "nikkei.com": MediaSource("nikkei.com", "Nikkei", "日本经济新闻", "东亚", "financial"),
    # ========== 韩国 ==========
    "koreaherald.com": MediaSource("koreaherald.com", "The Korea Herald", "韩国先驱报", "东亚", "news"),
    "koreatimes.co.kr": MediaSource("koreatimes.co.kr", "The Korea Times", "韩国时报", "东亚", "news"),
    "en.yna.co.kr": MediaSource("en.yna.co.kr", "Yonhap News", "韩联社", "东亚", "news"),
    "chosun.com": MediaSource("chosun.com", "Chosun Ilbo", "朝鲜日报", "东亚", "news"),
    # ========== 中国/港澳台 ==========
    "scmp.com": MediaSource("scmp.com", "South China Morning Post", "南华早报", "东亚", "news"),
    "chinadaily.com.cn": MediaSource("chinadaily.com.cn", "China Daily", "中国日报", "东亚", "news"),
    "globaltimes.cn": MediaSource("globaltimes.cn", "Global Times", "环球时报", "东亚", "news"),
    "xinhuanet.com": MediaSource("xinhuanet.com", "Xinhua", "新华社", "东亚", "news"),
    "cgtn.com": MediaSource("cgtn.com", "CGTN", "中国国际电视台", "东亚", "news"),
    "thestandnews.com": MediaSource("thestandnews.com", "The Stand News", "立场新闻", "东亚", "news"),
    "hk01.com": MediaSource("hk01.com", "HK01", "香港01", "东亚", "news"),
    "rthk.hk": MediaSource("rthk.hk", "RTHK", "香港电台", "东亚", "news"),
    "taipeitimes.com": MediaSource("taipeitimes.com", "Taipei Times", "台北时报", "东亚", "news"),
    # ========== 东南亚 ==========
    "straitstimes.com": MediaSource("straitstimes.com", "The Straits Times", "海峡时报", "东南亚", "news"),
    "channelnewsasia.com": MediaSource("channelnewsasia.com", "CNA", "亚洲新闻台", "东南亚", "news"),
    "bangkokpost.com": MediaSource("bangkokpost.com", "Bangkok Post", "曼谷邮报", "东南亚", "news"),
    "thejakartapost.com": MediaSource("thejakartapost.com", "The Jakarta Post", "雅加达邮报", "东南亚", "news"),
    "philstar.com": MediaSource("philstar.com", "Philstar", "菲律宾星报", "东南亚", "news"),
    "vietnamnews.vn": MediaSource("vietnamnews.vn", "Vietnam News", "越南新闻", "东南亚", "news"),
    # ========== 南亚 ==========
    "timesofindia.indiatimes.com": MediaSource(
        "timesofindia.indiatimes.com", "Times of India", "印度时报", "南亚", "news"
    ),
    "thehindu.com": MediaSource("thehindu.com", "The Hindu", "印度教徒报", "南亚", "news"),
    "hindustantimes.com": MediaSource("hindustantimes.com", "Hindustan Times", "印度斯坦时报", "南亚", "news"),
    "ndtv.com": MediaSource("ndtv.com", "NDTV", "新德里电视台", "南亚", "news"),
    "indianexpress.com": MediaSource("indianexpress.com", "Indian Express", "印度快报", "南亚", "news"),
    "dawn.com": MediaSource("dawn.com", "Dawn", "黎明报", "南亚", "news"),
    # ========== 中东 ==========
    "aljazeera.com": MediaSource("aljazeera.com", "Al Jazeera", "半岛电视台", "中东", "news"),
    "arabnews.com": MediaSource("arabnews.com", "Arab News", "阿拉伯新闻", "中东", "news"),
    "haaretz.com": MediaSource("haaretz.com", "Haaretz", "国土报", "中东", "news"),
    "timesofisrael.com": MediaSource("timesofisrael.com", "Times of Israel", "以色列时报", "中东", "news"),
    "jpost.com": MediaSource("jpost.com", "Jerusalem Post", "耶路撒冷邮报", "中东", "news"),
    "middleeasteye.net": MediaSource("middleeasteye.net", "Middle East Eye", "中东之眼", "中东", "news"),
    "thenationalnews.com": MediaSource("thenationalnews.com", "The National", "国民报(阿联酋)", "中东", "news"),
    # ========== 非洲 ==========
    "allafrica.com": MediaSource("allafrica.com", "AllAfrica", "全非洲", "非洲", "news"),
    "news24.com": MediaSource("news24.com", "News24", "新闻24", "非洲", "news"),
    "dailymaverick.co.za": MediaSource("dailymaverick.co.za", "Daily Maverick", "每日特立独行者", "非洲", "news"),
    # ========== 俄罗斯 ==========
    "rt.com": MediaSource("rt.com", "RT", "今日俄罗斯", "俄罗斯", "news"),
    "tass.com": MediaSource("tass.com", "TASS", "塔斯社", "俄罗斯", "news"),
    "themoscowtimes.com": MediaSource("themoscowtimes.com", "The Moscow Times", "莫斯科时报", "俄罗斯", "news"),
    # ========== 国际组织/通讯社 ==========
    "news.un.org": MediaSource("news.un.org", "UN News", "联合国新闻", "国际", "official"),
    "who.int": MediaSource("who.int", "WHO", "世界卫生组织", "国际", "official"),
    "imf.org": MediaSource("imf.org", "IMF", "国际货币基金组织", "国际", "official"),
    "worldbank.org": MediaSource("worldbank.org", "World Bank", "世界银行", "国际", "official"),
    "nato.int": MediaSource("nato.int", "NATO", "北大西洋公约组织", "国际", "official"),
    "europa.eu": MediaSource("europa.eu", "European Union", "欧盟", "国际", "official"),
    # ========== 财经类 ==========
    "economist.com": MediaSource("economist.com", "The Economist", "经济学人", "欧洲", "financial"),
    "forbes.com": MediaSource("forbes.com", "Forbes", "福布斯", "北美", "financial"),
    "barrons.com": MediaSource("barrons.com", "Barron's", "巴伦周刊", "北美", "financial"),
    "fortune.com": MediaSource("fortune.com", "Fortune", "财富", "北美", "financial"),
    "marketwatch.com": MediaSource("marketwatch.com", "MarketWatch", "市场观察", "北美", "financial"),
    "cnbc.com": MediaSource("cnbc.com", "CNBC", "消费者新闻与商业频道", "北美", "financial"),
    "businessinsider.com": MediaSource("businessinsider.com", "Business Insider", "商业内幕", "北美", "financial"),
    "seekingalpha.com": MediaSource("seekingalpha.com", "Seeking Alpha", "寻找阿尔法", "北美", "financial"),
    # ========== 科技类 ==========
    "techcrunch.com": MediaSource("techcrunch.com", "TechCrunch", "科技敲门砖", "北美", "tech"),
    "wired.com": MediaSource("wired.com", "Wired", "连线", "北美", "tech"),
    "theverge.com": MediaSource("theverge.com", "The Verge", "边缘", "北美", "tech"),
    "arstechnica.com": MediaSource("arstechnica.com", "Ars Technica", "技艺", "北美", "tech"),
    "engadget.com": MediaSource("engadget.com", "Engadget", "瘾科技", "北美", "tech"),
    "zdnet.com": MediaSource("zdnet.com", "ZDNet", "ZDNet科技", "北美", "tech"),
    "cnet.com": MediaSource("cnet.com", "CNET", "CNET科技", "北美", "tech"),
    "thenextweb.com": MediaSource("thenextweb.com", "The Next Web", "下一网", "欧洲", "tech"),
    "venturebeat.com": MediaSource("venturebeat.com", "VentureBeat", "创业节拍", "北美", "tech"),
    "techradar.com": MediaSource("techradar.com", "TechRadar", "科技雷达", "欧洲", "tech"),
    # ========== 政府官网 ==========
    "whitehouse.gov": MediaSource("whitehouse.gov", "White House", "美国白宫", "北美", "government"),
    "state.gov": MediaSource("state.gov", "U.S. State Dept", "美国国务院", "北美", "government"),
    "defense.gov": MediaSource("defense.gov", "U.S. Defense Dept", "美国国防部", "北美", "government"),
    "gov.uk": MediaSource("gov.uk", "UK Government", "英国政府", "欧洲", "government"),
    "fmprc.gov.cn": MediaSource("fmprc.gov.cn", "MFA China", "中国外交部", "东亚", "government"),
    "mofa.go.jp": MediaSource("mofa.go.jp", "MOFA Japan", "日本外务省", "东亚", "government"),
}


def extract_domain_from_url(url: str) -> str:
    """从 URL 中提取主域名

    Args:
        url: 完整 URL

    Returns:
        主域名（小写，去除 www. 前缀）
    """
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        # 移除 www. 前缀
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return ""


def get_media_source(url: str) -> MediaSource | None:
    """根据 URL 获取媒体来源信息

    Args:
        url: 完整 URL

    Returns:
        MediaSource 对象，如果未找到则返回 None
    """
    domain = extract_domain_from_url(url)
    if not domain:
        return None

    # 精确匹配
    if domain in MEDIA_SOURCE_MAPPING:
        return MEDIA_SOURCE_MAPPING[domain]

    # 子域名匹配 (如 news.bbc.com -> bbc.com, chinese.aljazeera.net -> aljazeera.com)
    for key in MEDIA_SOURCE_MAPPING:
        if domain.endswith("." + key) or domain == key:
            return MEDIA_SOURCE_MAPPING[key]

    return None


def get_source_name_zh(url: str) -> str:
    """获取媒体中文名称

    Args:
        url: 完整 URL

    Returns:
        媒体中文名称，未找到则返回域名
    """
    media = get_media_source(url)
    if media:
        return media.name_zh
    return extract_domain_from_url(url) or "未知来源"


def get_source_name_en(url: str) -> str:
    """获取媒体英文名称

    Args:
        url: 完整 URL

    Returns:
        媒体英文名称，未找到则返回域名
    """
    media = get_media_source(url)
    if media:
        return media.name_en
    return extract_domain_from_url(url) or "Unknown"


def get_source_region(url: str) -> str:
    """获取媒体地区

    Args:
        url: 完整 URL

    Returns:
        地区名称，未找到则返回空字符串
    """
    media = get_media_source(url)
    if media:
        return media.region
    return ""


def get_source_category(url: str) -> str:
    """获取媒体类别

    Args:
        url: 完整 URL

    Returns:
        类别名称 (news/financial/tech/official/government)，未找到则返回 "web"
    """
    media = get_media_source(url)
    if media:
        return media.category
    return "web"
