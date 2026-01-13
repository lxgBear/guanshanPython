"""来源发现节点

使用 Claude 动态发现当事方的官方信息来源。
"""

import json
import logging
from typing import Dict, Any, List, Optional

from anthropic import Anthropic

from ..state import SearchState, DiscoveredSource
from ..config import LangGraphSearchConfig

logger = logging.getLogger(__name__)


# Claude 来源发现提示词
SOURCE_DISCOVERY_PROMPT = """你是一个国际新闻来源专家。请为以下当事方识别可靠的信息来源。

当事方: {parties}
事件背景: {context}

请以 JSON 格式返回每个当事方的信息来源，格式如下:

{{
    "sources": [
        {{
            "party_name": "当事方名称",
            "party_type": "country|organization|person",
            "party_code": "ISO国家代码或组织简称",
            "primary_language": "主要语言代码(en/zh/ja/ko/ru/fr/de/es/ar)",
            "official_gov": ["官方政府网站域名"],
            "official_agency": ["官方通讯社域名"],
            "local_mainstream": ["当地主流媒体域名"],
            "confidence": 0.0-1.0
        }}
    ]
}}

注意事项:
1. 官方来源 (official_gov): 政府部门、外交部、国防部等官方网站
2. 官方通讯社 (official_agency): 国家通讯社、官方新闻机构
3. 当地主流媒体 (local_mainstream): 该国/地区的权威媒体
4. confidence: 来源可靠度评分

常见来源参考:
- 美国: whitehouse.gov, state.gov, apnews.com, reuters.com, nytimes.com
- 中国: gov.cn, xinhuanet.com, chinadaily.com.cn
- 日本: kantei.go.jp, mofa.go.jp, nhk.or.jp, japantimes.co.jp
- 韩国: korea.kr, yonhapnews.co.kr, koreaherald.com
- 俄罗斯: kremlin.ru, mid.ru, tass.com, rt.com
- 欧盟: europa.eu, europarl.europa.eu

请只返回 JSON，不要添加任何其他文字。"""


class SourceDiscoveryNode:
    """来源发现节点

    使用 Claude 动态发现当事方的官方信息来源:
    - Layer 0: 官方政府网站、官方机构
    - Layer 1: 官方通讯社、当地主流媒体
    """

    def __init__(
        self,
        config: Optional[LangGraphSearchConfig] = None,
        anthropic_client: Optional[Anthropic] = None,
    ):
        """初始化来源发现节点

        Args:
            config: LangGraph 搜索配置
            anthropic_client: Anthropic 客户端（可选）
        """
        self.config = config or LangGraphSearchConfig()
        self.client = anthropic_client or Anthropic()

    def __call__(self, state: SearchState) -> Dict[str, Any]:
        """执行来源发现

        Args:
            state: 当前搜索状态

        Returns:
            状态更新字典
        """
        parties = state.get("parties", [])
        analysis = state.get("analysis", {})
        user_id = state.get("user_id", "")

        if not parties:
            logger.warning(f"[user:{user_id}] No parties to discover sources for, using generic sources")
            # v4.5.2: 当没有识别到当事方时，使用通用权威来源
            return {
                "discovered_sources": self._get_generic_sources(),
            }

        try:
            logger.info(
                f"[user:{user_id}] Discovering sources for {len(parties)} parties"
            )

            # 获取事件背景
            context = analysis.get("summary", state.get("query", ""))

            # 调用 Claude 发现来源
            discovered = self._discover_with_claude(parties, context)

            # 转换为字典格式存储
            discovered_sources = {}
            for source in discovered:
                party_name = source.party_name
                discovered_sources[party_name] = source.to_dict()

            logger.info(
                f"[user:{user_id}] Discovered sources for "
                f"{len(discovered_sources)} parties"
            )

            return {
                "discovered_sources": discovered_sources,
            }

        except Exception as e:
            logger.error(f"[user:{user_id}] Source discovery failed: {e}")
            # 使用预定义来源作为回退
            return {
                "discovered_sources": self._get_fallback_sources(parties),
            }

    def _discover_with_claude(
        self,
        parties: List[str],
        context: str,
    ) -> List[DiscoveredSource]:
        """使用 Claude 发现来源

        Args:
            parties: 当事方列表
            context: 事件背景

        Returns:
            发现的来源列表
        """
        prompt = SOURCE_DISCOVERY_PROMPT.format(
            parties=", ".join(parties),
            context=context,
        )

        response = self.client.messages.create(
            model=self.config.claude_model,
            max_tokens=self.config.claude_max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )

        # 提取响应文本
        response_text = response.content[0].text.strip()

        # 清理 JSON 响应
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            response_text = "\n".join(lines)

        # 解析 JSON
        try:
            data = json.loads(response_text)
        except json.JSONDecodeError:
            import re
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                data = json.loads(json_match.group())
            else:
                raise ValueError("Unable to extract JSON from response")

        # 转换为 DiscoveredSource 对象
        sources = []
        for item in data.get("sources", []):
            source = DiscoveredSource(
                party_name=item.get("party_name", ""),
                party_type=item.get("party_type", "country"),
                party_code=item.get("party_code", ""),
                official_gov=item.get("official_gov", []),
                official_agency=item.get("official_agency", []),
                local_mainstream=item.get("local_mainstream", []),
                primary_language=item.get("primary_language", "en"),
                confidence=item.get("confidence", 0.7),
            )
            sources.append(source)

        return sources

    def _get_fallback_sources(
        self,
        parties: List[str],
    ) -> Dict[str, Dict[str, Any]]:
        """获取预定义的回退来源

        Args:
            parties: 当事方列表

        Returns:
            预定义来源字典
        """
        # 预定义的主要国家来源
        predefined = {
            "美国": DiscoveredSource(
                party_name="美国",
                party_type="country",
                party_code="US",
                official_gov=["whitehouse.gov", "state.gov", "defense.gov"],
                official_agency=["apnews.com", "reuters.com"],
                local_mainstream=["nytimes.com", "washingtonpost.com", "cnn.com"],
                primary_language="en",
                confidence=0.95,
            ),
            "中国": DiscoveredSource(
                party_name="中国",
                party_type="country",
                party_code="CN",
                official_gov=["gov.cn", "fmprc.gov.cn", "mod.gov.cn"],
                official_agency=["xinhuanet.com", "cctv.com"],
                local_mainstream=["chinadaily.com.cn", "globaltimes.cn"],
                primary_language="zh",
                confidence=0.95,
            ),
            "日本": DiscoveredSource(
                party_name="日本",
                party_type="country",
                party_code="JP",
                official_gov=["kantei.go.jp", "mofa.go.jp", "mod.go.jp"],
                official_agency=["nhk.or.jp"],
                local_mainstream=["japantimes.co.jp", "asahi.com", "mainichi.jp"],
                primary_language="ja",
                confidence=0.95,
            ),
            "韩国": DiscoveredSource(
                party_name="韩国",
                party_type="country",
                party_code="KR",
                official_gov=["korea.kr", "mofa.go.kr", "mnd.go.kr"],
                official_agency=["yonhapnews.co.kr", "en.yna.co.kr"],
                local_mainstream=["koreaherald.com", "koreatimes.co.kr"],
                primary_language="ko",
                confidence=0.95,
            ),
            "俄罗斯": DiscoveredSource(
                party_name="俄罗斯",
                party_type="country",
                party_code="RU",
                official_gov=["kremlin.ru", "mid.ru", "mil.ru"],
                official_agency=["tass.com", "ria.ru"],
                local_mainstream=["rt.com", "rbc.ru"],
                primary_language="ru",
                confidence=0.95,
            ),
        }

        fallback_sources = {}
        for party in parties:
            if party in predefined:
                fallback_sources[party] = predefined[party].to_dict()
            else:
                # 创建空来源占位
                fallback_sources[party] = DiscoveredSource(
                    party_name=party,
                    party_type="unknown",
                    party_code="",
                    confidence=0.5,
                ).to_dict()

        return fallback_sources
