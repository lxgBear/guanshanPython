"""多语言配置模块

统一管理所有支持的语言及其对应的媒体域名映射。

支持的语言 (25种):
- 东亚: zh(中文), ja(日语), ko(韩语)
- 欧洲: en(英语), fr(法语), de(德语), es(西班牙语), it(意大利语), pt(葡萄牙语), nl(荷兰语), ru(俄语)
- 东欧: uk(乌克兰语), pl(波兰语)
- 中欧/北欧/南欧: cs(捷克语), sv(瑞典语), el(希腊语)
- 中东: ar(阿拉伯语), tr(土耳其语), he(希伯来语)
- 南亚: hi(印地语), ur(乌尔都��), bn(孟加拉语)
- 东南亚: vi(越南语), th(泰语), id(印尼语), ms(马来语), tl(菲律宾语)

覆盖约75%全球人口
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class LanguageConfig:
    """单语言配置

    Attributes:
        code: ISO 639-1 语言代码 (如 "en", "zh")
        name: 语言中文名称 (如 "英语", "中文")
        name_native: 语言本地名称 (如 "English", "中文")
        name_english: 语言英文名称 (如 "English", "Chinese")
        regions: 主要使用该语言的国家/地区列表
        media_domains: 主流新闻媒体域名列表
        country_codes: ISO 3166 国家代码列表
        direction: 文字方向 ("ltr" 或 "rtl")
    """
    code: str                              # ISO 639-1 代码
    name: str                              # 中文名称
    name_native: str                       # 本地名称
    name_english: str                      # 英文名称
    regions: List[str] = field(default_factory=list)     # 主要使用地区
    media_domains: List[str] = field(default_factory=list)  # 主流媒体域名
    country_codes: List[str] = field(default_factory=list)  # 国家代码
    direction: str = "ltr"                 # 文字方向


# ============================================================================
# 语言配置注册表
# ============================================================================

LANGUAGE_REGISTRY: Dict[str, LanguageConfig] = {
    # ===== 东亚语言 =====
    "zh": LanguageConfig(
        code="zh",
        name="中文",
        name_native="中文",
        name_english="Chinese",
        regions=["中国", "台湾", "香港", "澳门", "新加坡"],
        media_domains=[
            # 中国大陆
            "xinhuanet.com", "people.com.cn", "cctv.com", "cnr.cn",
            "thepaper.cn", "caixin.com", "ifeng.com", "sina.com.cn",
            "sohu.com", "qq.com", "163.com", "gtimg.cn",
            # 台湾
            "udn.com", "ltn.com.tw", "chinatimes.com", "tvbs.com.tw",
            # 香港
            "hk01.com", "scmp.com", "thestandard.com.hk",
            # 国际中文
            "bbc.com/zhongwen", "cn.nytimes.com", "rfi.fr/cn",
        ],
        country_codes=["CN", "TW", "HK", "MO", "SG"],
    ),

    "ja": LanguageConfig(
        code="ja",
        name="日语",
        name_native="日本語",
        name_english="Japanese",
        regions=["日本"],
        media_domains=[
            "nhk.or.jp", "asahi.com", "yomiuri.co.jp", "mainichi.jp",
            "nikkei.com", "sankei.com", "tokyo-np.co.jp", "hokkaido-np.co.jp",
        ],
        country_codes=["JP"],
    ),

    "ko": LanguageConfig(
        code="ko",
        name="韩语",
        name_native="한국어",
        name_english="Korean",
        regions=["韩国", "朝鲜"],
        media_domains=[
            "khan.co.kr", "chosun.com", "donga.com", "joins.com",
            "hani.co.kr", "kmib.co.kr", "munhwa.com", "sedaily.com",
        ],
        country_codes=["KR", "KP"],
    ),

    # ===== 英语 =====
    "en": LanguageConfig(
        code="en",
        name="英语",
        name_native="English",
        name_english="English",
        regions=["美国", "英国", "加拿大", "澳大利亚", "新西兰", "爱尔兰", "南非"],
        media_domains=[
            # 国际通讯社
            "reuters.com", "apnews.com", "afp.com",
            # 北美
            "bbc.com", "cnn.com", "nytimes.com", "washingtonpost.com",
            "wsj.com", "nbcnews.com", "abcnews.go.com", "usatoday.com",
            "latimes.com", "chicagotribune.com", "bloomberg.com", "politico.com",
            "axios.com", "theguardian.com", "ft.com",
            # 欧洲
            "france24.com", "dw.com", "rferl.org", "rfi.fr",
            # 国际
            "aljazeera.com", "time.com", "newsweek.com", "theatlantic.com",
        ],
        country_codes=["US", "GB", "CA", "AU", "NZ", "IE", "ZA"],
    ),

    # ===== 欧洲语言 =====
    "fr": LanguageConfig(
        code="fr",
        name="法语",
        name_native="Français",
        name_english="French",
        regions=["法国", "加拿大魁北克", "比利时", "瑞士", "摩纳哥"],
        media_domains=[
            "lemonde.fr", "lefigaro.fr", "liberation.fr", "francetvinfo.fr",
            "rfi.fr", "france24.com", "leparisien.fr", "lepoint.fr",
            "l'express.fr", "latribune.fr", "courrierinternational.com",
        ],
        country_codes=["FR", "CA", "BE", "CH", "MC"],
    ),

    "de": LanguageConfig(
        code="de",
        name="德语",
        name_native="Deutsch",
        name_english="German",
        regions=["德国", "奥地利", "瑞士", "列支敦士登", "卢森堡"],
        media_domains=[
            "spiegel.de", "zeit.de", "faz.net", "sueddeutsche.de",
            "bild.de", "tagesspiegel.de", "dw.com", "orf.at",
            "nzz.ch", "bazonline.ch", "handelsblatt.com",
        ],
        country_codes=["DE", "AT", "CH", "LI", "LU"],
    ),

    "es": LanguageConfig(
        code="es",
        name="西班牙语",
        name_native="Español",
        name_english="Spanish",
        regions=["西班牙", "墨西哥", "阿根廷", "哥伦比亚", "秘鲁", "委内瑞拉", "智利"],
        media_domains=[
            # 西班牙
            "elpais.com", "elmundo.es", "abc.es", "lavanguardia.com",
            "elconfidencial.com", "eldiario.es", "marca.com", "as.com",
            # 拉丁美洲
            "reforma.com", "milenio.com", "clarin.com", "lanacion.com.ar",
            "elcomercio.com", "eltiempo.com",
        ],
        country_codes=["ES", "MX", "AR", "CO", "PE", "VE", "CL"],
    ),

    "it": LanguageConfig(
        code="it",
        name="意大利语",
        name_native="Italiano",
        name_english="Italian",
        regions=["意大利", "瑞士", "圣马力诺", "梵蒂冈"],
        media_domains=[
            "repubblica.it", "corriere.it", "lastampa.it", "ilsole24ore.com",
            "ilmessaggero.it", "leggo.it", "fanpage.it", "adnkronos.com",
            "ansa.it", "rainews.it",
        ],
        country_codes=["IT", "CH", "SM", "VA"],
    ),

    "pt": LanguageConfig(
        code="pt",
        name="葡萄牙语",
        name_native="Português",
        name_english="Portuguese",
        regions=["葡萄牙", "巴西", "安哥拉", "莫桑比克"],
        media_domains=[
            # 葡萄牙
            "publico.pt", "expresso.pt", "observador.pt", "dn.pt",
            "jornaldenegocios.pt", "sapo.pt", "rtp.pt",
            # 巴西
            "globo.com", "folha.uol.com.br", "estadao.com.br",
            "uol.com.br", "terra.com.br", "abril.com.br",
        ],
        country_codes=["PT", "BR", "AO", "MZ"],
    ),

    "nl": LanguageConfig(
        code="nl",
        name="荷兰语",
        name_native="Nederlands",
        name_english="Dutch",
        regions=["荷兰", "比利时", "苏里南"],
        media_domains=[
            "nos.nl", "nrc.nl", "volkskrant.nl", "ad.nl",
            "telegraaf.nl", "fd.nl", "trouw.nl", "parool.nl",
            "demorgen.be", "standaard.be",
        ],
        country_codes=["NL", "BE", "SR"],
    ),

    "ru": LanguageConfig(
        code="ru",
        name="俄语",
        name_native="Русский",
        name_english="Russian",
        regions=["俄罗斯", "白俄罗斯", "哈萨克斯坦", "吉尔吉斯斯坦"],
        media_domains=[
            "tass.ru", "ria.ru", "rbc.ru", "kremlin.ru",
            " Kommersant.ru", "gazeta.ru", "iz.ru", "rt.com",
        ],
        country_codes=["RU", "BY", "KZ", "KG"],
    ),

    # ===== 中东语言 =====
    "ar": LanguageConfig(
        code="ar",
        name="阿拉伯语",
        name_native="العربية",
        name_english="Arabic",
        regions=["沙特", "阿联酋", "埃及", "卡塔尔", "科威特", "约旦", "黎巴嫩"],
        media_domains=[
            "aljazeera.com", "arabic.cnn.com", "bbc.com/arabic",
            "alarabiya.net", "asharq.com", "reuters.com/arabic",
            "middleeasteye.net", "skynewsarabia.com",
        ],
        country_codes=["SA", "AE", "EG", "QA", "KW", "JO", "LB"],
        direction="rtl",
    ),

    "tr": LanguageConfig(
        code="tr",
        name="土耳其语",
        name_native="Türkçe",
        name_english="Turkish",
        regions=["土耳其", "塞浦路斯"],
        media_domains=[
            "hurriyet.com.tr", "milliyet.com.tr", "sabah.com.tr",
            "cumhuriyet.com.tr", "yenisafak.com", "sozcu.com.tr",
            "dunya.com", "aa.com.tr", "trthaber.com",
        ],
        country_codes=["TR", "CY"],
    ),

    # ===== 南亚语言 =====
    "hi": LanguageConfig(
        code="hi",
        name="印地语",
        name_native="हिन्दी",
        name_english="Hindi",
        regions=["印度", "尼泊尔"],
        media_domains=[
            "ndtv.com", "timesofindia.indiatimes.com", "hindustantimes.com",
            "indiatoday.in", "indianexpress.com", "bbc.com/hindi",
            "jagran.com", "dainikbhaskar.com", "aajtak.in",
        ],
        country_codes=["IN", "NP"],
    ),

    "ur": LanguageConfig(
        code="ur",
        name="乌尔都语",
        name_native="اردو",
        name_english="Urdu",
        regions=["巴基斯坦", "印度"],
        media_domains=[
            "dawn.com", "tribune.com.pk", "thenews.com.pk",
            "geo.tv", "arynews.tv", "express.com.pk",
            "jang.com.pk", "bbc.com/urdu",
        ],
        country_codes=["PK", "IN"],
        direction="rtl",
    ),

    # ===== 东南亚语言 =====
    "vi": LanguageConfig(
        code="vi",
        name="越南语",
        name_native="Tiếng Việt",
        name_english="Vietnamese",
        regions=["越南"],
        media_domains=[
            "vnexpress.net", "thanhnien.vn", "tuoitre.vn",
            "vietnamnews.vn", "vnn.vn", "baomoi.com",
            "dantri.com.vn", "vtv.vn", "laodong.com.vn",
        ],
        country_codes=["VN"],
    ),

    "th": LanguageConfig(
        code="th",
        name="泰语",
        name_native="ภาษาไทย",
        name_english="Thai",
        regions=["泰国"],
        media_domains=[
            "bangkokpost.com", "thaipbsworld.com", "nationthailand.com",
            "khaosodenglish.com", "thaipbs.or.th", "manager.co.th",
            "thairath.co.th", "khaosod.co.th", "posttoday.com",
        ],
        country_codes=["TH"],
    ),

    "id": LanguageConfig(
        code="id",
        name="印尼语",
        name_native="Bahasa Indonesia",
        name_english="Indonesian",
        regions=["印度尼西亚"],
        media_domains=[
            "kompas.com", "detik.com", "tempo.co",
            " Republika.co.id", "jakpost.com", "liputan6.com",
            "suara.com", "tribunnews.com", "cnnindonesia.com",
        ],
        country_codes=["ID"],
    ),

    "ms": LanguageConfig(
        code="ms",
        name="马来语",
        name_native="Bahasa Melayu",
        name_english="Malay",
        regions=["马来西亚", "文莱", "新加坡"],
        media_domains=[
            "thestar.com.my", "nst.com.my", "malaymail.com",
            "bharian.com.my", "utusan.com.my", "bernama.com",
            "channelnewsasia.com", "straitstimes.com.sg",
        ],
        country_codes=["MY", "BN", "SG"],
    ),

    # ===== Phase 2 扩展语言 =====
    # 南���
    "bn": LanguageConfig(
        code="bn",
        name="孟加拉语",
        name_native="বাংলা",
        name_english="Bengali",
        regions=["孟加拉国", "印度"],
        media_domains=[
            "thedailystar.net", "dhakatribune.com", "bdnews24.com",
            "prothomalo.com", "kalerkantho.com", "bd-pratidin.com",
            "jugantor.com", "kalbela.com", "anandabazar.com",
            "ebela.in", "bartamanpatrika.com",
        ],
        country_codes=["BD", "IN"],
    ),

    # 中东
    "he": LanguageConfig(
        code="he",
        name="希伯来语",
        name_native="עברית",
        name_english="Hebrew",
        regions=["以色列"],
        media_domains=[
            "haaretz.co.il", "ynetnews.com", "timesofisrael.com",
            "israelhayom.co.il", "walla.co.il", "mako.co.il",
            "channel12.co.il", "n12.co.il", "israelnationalnews.com",
        ],
        country_codes=["IL"],
        direction="rtl",
    ),

    # 东欧
    "uk": LanguageConfig(
        code="uk",
        name="乌克兰语",
        name_native="Українська",
        name_english="Ukrainian",
        regions=["乌克兰"],
        media_domains=[
            "pravda.com.ua", "kyivpost.com", "ukrinform.net",
            "rbk.ua", "gordonua.com", "env.time.com.ua",
            "zn.ua", "umoloda.kyiv.ua", "ukraineworld.org",
        ],
        country_codes=["UA"],
    ),

    "pl": LanguageConfig(
        code="pl",
        name="波兰语",
        name_native="Polski",
        name_english="Polish",
        regions=["波兰"],
        media_domains=[
            "wyborcza.pl", "rp.pl", "gazeta.pl",
            "tvn24.pl", "polsatnews.pl", "onet.pl",
            "wp.pl", "interia.pl", "se.pl", "money.pl",
        ],
        country_codes=["PL"],
    ),

    # 东南亚
    "tl": LanguageConfig(
        code="tl",
        name="菲律宾语",
        name_native="Filipino",
        name_english="Filipino",
        regions=["菲律宾"],
        media_domains=[
            "inquirer.net", "philstar.com", "manilastandard.net",
            "rappler.com", "gmanetwork.com", "abs-cbn.com",
            "philippinedailyinquirer.net", "mb.com.ph", "pna.gov.ph",
        ],
        country_codes=["PH"],
    ),

    # 中欧/北欧/南欧
    "cs": LanguageConfig(
        code="cs",
        name="捷克语",
        name_native="Čeština",
        name_english="Czech",
        regions=["捷克"],
        media_domains=[
            "idnes.cz", "novinky.cz", "ihned.cz",
            "irozhlas.cz", "denik.cz", "aktualne.cz",
            "echo24.cz", "seznamzpravy.cz", "ctk.cz",
        ],
        country_codes=["CZ"],
    ),

    "sv": LanguageConfig(
        code="sv",
        name="瑞典语",
        name_native="Svenska",
        name_english="Swedish",
        regions=["瑞典", "芬兰"],
        media_domains=[
            "dn.se", "svd.se", "aftonbladet.se",
            "expressen.se", "svt.se", "di.se",
            "nyheteridag.se", "aftonbladet.se", " Omni.se",
        ],
        country_codes=["SE", "FI"],
    ),

    "el": LanguageConfig(
        code="el",
        name="希腊语",
        name_native="Ελληνικά",
        name_english="Greek",
        regions=["希腊", "塞浦路斯"],
        media_domains=[
            "kathimerini.gr", "ethnos.gr", "tovima.gr",
            "news247.gr", "protothema.gr", "capital.gr",
            "efsyn.gr", "in.gr", "cnn.gr",
        ],
        country_codes=["GR", "CY"],
    ),
}


# ============================================================================
# 国家/地区到语言的映射
# ============================================================================

COUNTRY_TO_LANGUAGES: Dict[str, List[str]] = {
    # 东亚
    "中国": ["zh"], "台湾": ["zh"], "香港": ["zh"], "澳门": ["zh"],
    "日本": ["ja"], "韩国": ["ko"], "朝鲜": ["ko"],
    # 欧洲
    "美国": ["en"], "英国": ["en"], "加拿大": ["en", "fr"],
    "澳大利亚": ["en"], "新西兰": ["en"], "爱尔兰": ["en"],
    "法国": ["fr"], "德国": ["de"], "意大利": ["it"],
    "西班牙": ["es"], "葡萄牙": ["pt"], "荷兰": ["nl"],
    "比利时": ["nl", "fr"], "瑞士": ["de", "fr", "it"],
    "俄罗斯": ["ru"], "乌克兰": ["uk"], "波兰": ["pl"],
    "捷克": ["cs"], "瑞典": ["sv"], "希腊": ["el"],
    # 中东
    "沙特": ["ar"], "阿联酋": ["ar"], "埃及": ["ar"],
    "土耳其": ["tr"], "以色列": ["he"],
    # 南亚
    "印度": ["hi", "en"], "巴基斯坦": ["ur"], "孟加拉": ["bn"],
    # 东南亚
    "越南": ["vi"], "泰国": ["th"], "印尼": ["id"],
    "马来西亚": ["ms", "en"], "新加坡": ["en", "zh", "ms"],
    "菲律宾": ["en", "tl"],
    # 其他
    "芬兰": ["sv", "fi"], "塞浦路斯": ["el", "en"],
}


# ============================================================================
# 辅助函数
# ============================================================================

def get_language_config(code: str) -> Optional[LanguageConfig]:
    """获取语言配置

    Args:
        code: ISO 639-1 语言代码

    Returns:
        LanguageConfig 或 None
    """
    return LANGUAGE_REGISTRY.get(code)


def get_media_domains(code: str) -> List[str]:
    """获取语言对应的主流媒体域名

    Args:
        code: ISO 639-1 语言代码

    Returns:
        域名列表
    """
    config = get_language_config(code)
    return config.media_domains if config else []


def get_languages_by_region(region: str) -> List[str]:
    """根据地区获取语言代码

    Args:
        region: 地区名称（中文）

    Returns:
        语言代码列表
    """
    return COUNTRY_TO_LANGUAGES.get(region, [])


def get_all_supported_languages() -> List[str]:
    """获取所有支持的语言代码

    Returns:
        语言代码列表
    """
    return list(LANGUAGE_REGISTRY.keys())


def get_language_name(code: str, locale: str = "zh") -> str:
    """获取语言名称

    Args:
        code: ISO 639-1 语言代码
        locale: 返回名称的语言 ("zh" 中文, "en" 英文, "native" 本地)

    Returns:
        语言名称
    """
    config = get_language_config(code)
    if not config:
        return code

    if locale == "zh":
        return config.name
    elif locale == "en":
        return config.name_english
    elif locale == "native":
        return config.name_native
    return config.name


def is_rtl_language(code: str) -> bool:
    """判断是否为从右到左的语言

    Args:
        code: ISO 639-1 语言代码

    Returns:
        是否为 RTL 语言
    """
    config = get_language_config(code)
    return config.direction == "rtl" if config else False


def get_primary_languages() -> List[str]:
    """获取主要语言（使用最广泛）的列表

    Returns:
        主要语言代码列表
    """
    return ["zh", "en", "es", "hi", "ar", "pt", "ru", "ja", "de", "fr"]


def get_european_languages() -> List[str]:
    """获取欧洲语言列表

    Returns:
        欧洲语言代码列表
    """
    return ["en", "fr", "de", "es", "it", "pt", "nl", "ru", "uk", "pl", "cs", "sv", "el"]


def get_asian_languages() -> List[str]:
    """获取亚洲语言列表

    Returns:
        亚洲语言代码列表
    """
    return ["zh", "ja", "ko", "hi", "ur", "bn", "vi", "th", "id", "ms", "tl", "ar", "tr", "he"]


def get_south_asian_languages() -> List[str]:
    """获取南亚语言列表

    Returns:
        南亚语言代码列表
    """
    return ["hi", "ur", "bn"]


def get_eastern_european_languages() -> List[str]:
    """获取东欧语言列表

    Returns:
        东欧语言代码列表
    """
    return ["ru", "uk", "pl"]


def get_central_european_languages() -> List[str]:
    """获取中欧语言列表

    Returns:
        中欧语言代码列表
    """
    return ["de", "cs", "pl"]


def get_nordic_languages() -> List[str]:
    """获取北欧语言列表

    Returns:
        北欧语言代码列表
    """
    return ["sv", "fi", "da", "no"]


def get_baltic_languages() -> List[str]:
    """获取波罗的海语言列表

    Returns:
        波罗的海语言代码列表
    """
    return ["et", "lv", "lt"]


def get_rtl_languages() -> List[str]:
    """获取从右到左(RTL)的语言列表

    Returns:
        RTL语言代码列表
    """
    return ["ar", "he", "ur", "fa"]


# ============================================================================
# 智能语言检测
# ============================================================================

# Unicode 范围映射到语言代码
UNICODE_RANGES = {
    # 中日韩统一表意文字
    "zh": [
        (0x4E00, 0x9FFF),    # CJK Unified Ideographs
        (0x3400, 0x4DBF),    # CJK Unified Ideographs Extension A
        (0x20000, 0x2A6DF),  # CJK Unified Ideographs Extension B
        (0x2A700, 0x2B73F),  # CJK Unified Ideographs Extension C
        (0x2B740, 0x2B81F),  # CJK Unified Ideographs Extension D
    ],
    # 日语特有字符
    "ja": [
        (0x3040, 0x309F),    # Hiragana
        (0x30A0, 0x30FF),    # Katakana
        (0x31F0, 0x31FF),    # Katakana Phonetic Extensions
    ],
    # 韩语
    "ko": [
        (0xAC00, 0xD7AF),    # Hangul Syllables
        (0x1100, 0x11FF),    # Hangul Jamo
        (0x3130, 0x318F),    # Hangul Compatibility Jamo
    ],
    # 阿拉伯语
    "ar": [
        (0x0600, 0x06FF),    # Arabic
        (0x0750, 0x077F),    # Arabic Supplement
        (0x08A0, 0x08FF),    # Arabic Extended-A
    ],
    # 希伯来语
    "he": [
        (0x0590, 0x05FF),    # Hebrew
    ],
    # 泰语
    "th": [
        (0x0E00, 0x0E7F),    # Thai
    ],
    # 越南语（使用拉丁字母+声调符号）
    "vi": [
        (0x1EA0, 0x1EF9),    # Vietnamese specific Latin Extended Additional
    ],
    # 俄语（西里尔字母）
    "ru": [
        (0x0400, 0x04FF),    # Cyrillic
        (0x0500, 0x052F),    # Cyrillic Supplement
    ],
    # 希腊语
    "el": [
        (0x0370, 0x03FF),    # Greek and Coptic
    ],
    # 印地语（天城文）
    "hi": [
        (0x0900, 0x097F),    # Devanagari
    ],
    # 孟加拉语
    "bn": [
        (0x0980, 0x09FF),    # Bengali
    ],
    # 土耳其语特有字符
    "tr": [
        # 土耳其语主要使用拉丁字母，但有特殊字符 ğ, ı, İ, ş, ç, ö, ü
        # 这些在 Latin Extended 中，需要特殊处理
    ],
}

# 越南语特有字符列表（带声调的越南语字母）
VIETNAMESE_CHARS = set("àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ"
                       "ÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴĐ")

# 土耳其语特有字符
TURKISH_CHARS = set("ğĞıİşŞçÇöÖüÜ")


def _char_in_range(char: str, ranges: list) -> bool:
    """检查字符是否在指定的 Unicode 范围内"""
    code_point = ord(char)
    for start, end in ranges:
        if start <= code_point <= end:
            return True
    return False


def detect_query_language(query: str) -> List[str]:
    """智能检测查询文本的语言

    基于 Unicode 字符范围分析查询文本，返回检测到的语言列表。
    如果无法确定语言，返回 ["en", "zh"] 作为双语搜索默认值。

    Args:
        query: 用户查询文本

    Returns:
        检测到的语言代码列表，如 ["zh"], ["en"], ["zh", "en"]
    """
    if not query or not query.strip():
        return ["en", "zh"]

    # 统计各语言字符数量
    lang_scores: Dict[str, int] = {}
    latin_count = 0
    total_chars = 0

    for char in query:
        if char.isspace() or char in '.,!?;:\'"-()[]{}0123456789':
            continue

        total_chars += 1

        # 检查越南语特有字符
        if char in VIETNAMESE_CHARS:
            lang_scores["vi"] = lang_scores.get("vi", 0) + 5  # 高权重
            continue

        # 检查土耳其语特有字符
        if char in TURKISH_CHARS:
            lang_scores["tr"] = lang_scores.get("tr", 0) + 5
            continue

        # 检查各语言的 Unicode 范围
        matched = False
        for lang_code, ranges in UNICODE_RANGES.items():
            if ranges and _char_in_range(char, ranges):
                lang_scores[lang_code] = lang_scores.get(lang_code, 0) + 1
                matched = True
                break

        # 拉丁字母
        if not matched and char.isalpha():
            latin_count += 1

    if total_chars == 0:
        return ["en", "zh"]

    # 分析结果
    detected_languages = []

    # 检查非拉丁语言
    for lang_code, score in sorted(lang_scores.items(), key=lambda x: -x[1]):
        if score >= 2 or (total_chars <= 10 and score >= 1):
            # 西里尔字母：区分俄语、乌克兰语
            if lang_code == "ru":
                detected_languages.append("ru")
            # 天城文：可能是印地语或其他印度语言
            elif lang_code == "hi":
                detected_languages.append("hi")
            else:
                detected_languages.append(lang_code)

    # 如果主要是拉丁字母
    if latin_count > total_chars * 0.5 and "vi" not in detected_languages and "tr" not in detected_languages:
        # 纯拉丁字母，假设为英语
        if not detected_languages:
            detected_languages.append("en")
        elif "en" not in detected_languages:
            # 混合语言情况（如中英混合）
            detected_languages.append("en")

    # 处理日语与中文共用汉字的情况
    if "zh" in detected_languages and "ja" in detected_languages:
        # 如果有日语假名，优先日语
        if lang_scores.get("ja", 0) > 0:
            detected_languages.remove("zh")
        else:
            detected_languages.remove("ja")

    # 无法检测时的默认值：中英双语
    if not detected_languages:
        return ["en", "zh"]

    return detected_languages


def get_default_languages_for_query(query: str) -> List[str]:
    """根据查询内容获取默认搜索语言

    这是对外暴露的主要接口，用于替代硬编码的 ["zh"] 默认值。

    Args:
        query: 用户查询文本

    Returns:
        建议的搜索语言列表
    """
    detected = detect_query_language(query)

    # 确保返回的语言在支持列表中
    supported = get_all_supported_languages()
    return [lang for lang in detected if lang in supported] or ["en", "zh"]
