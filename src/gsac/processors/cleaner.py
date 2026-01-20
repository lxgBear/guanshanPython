"""
内容清洗处理器

使用LLM清洗和提取网页内容的核心信息
"""

import re

from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel

from ..llm.prompts import CLEAN_CONTENT_PROMPT
from ..models.schemas import ScrapedContent


class CleanedContent(BaseModel):
    """清洗后的内容结构"""

    title: str
    main_content: str
    key_points: list[str] = []
    metadata: dict = {}


def remove_html_tags(text: str) -> str:
    """
    移除HTML标签

    Args:
        text: 原始文本

    Returns:
        清理后的文本
    """
    # 移除script和style标签及其内容
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)

    # 移除HTML标签
    text = re.sub(r"<[^>]+>", "", text)

    # 清理多余空白
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def normalize_whitespace(text: str) -> str:
    """
    标准化空白字符

    Args:
        text: 原始文本

    Returns:
        标准化后的文本
    """
    # 将多个空格替换为单个空格
    text = re.sub(r"[ \t]+", " ", text)

    # 将多个换行替换为两个换行
    text = re.sub(r"\n{3,}", "\n\n", text)

    # 移除行首行尾空白
    lines = [line.strip() for line in text.split("\n")]
    text = "\n".join(lines)

    return text.strip()


def extract_main_content(text: str, min_length: int = 100) -> str:
    """
    提取主要内容

    移除短段落和噪音内容

    Args:
        text: 原始文本
        min_length: 最小段落长度

    Returns:
        主要内容
    """
    paragraphs = text.split("\n\n")
    main_paragraphs = []

    for para in paragraphs:
        para = para.strip()
        # 跳过太短的段落
        if len(para) < min_length:
            # 但保留标题类内容(以#开头)
            if para.startswith("#"):
                main_paragraphs.append(para)
            continue
        main_paragraphs.append(para)

    return "\n\n".join(main_paragraphs)


def clean_content_basic(content: ScrapedContent) -> ScrapedContent:
    """
    基础内容清洗(不使用LLM)

    Args:
        content: 原始抓取内容

    Returns:
        清洗后的内容
    """
    cleaned_markdown = content.markdown or ""

    # 移除HTML残留
    cleaned_markdown = remove_html_tags(cleaned_markdown)

    # 标准化空白
    cleaned_markdown = normalize_whitespace(cleaned_markdown)

    # 提取主要内容
    cleaned_markdown = extract_main_content(cleaned_markdown)

    return ScrapedContent(
        url=content.url,
        title=content.title,
        markdown=cleaned_markdown,
        html=content.html,
        metadata={**content.metadata, "cleaned": True, "clean_method": "basic"},
    )


async def clean_content_with_llm(
    content: ScrapedContent,
    llm: BaseChatModel,
) -> ScrapedContent:
    """
    使用LLM清洗内容

    Args:
        content: 原始抓取内容
        llm: LLM实例

    Returns:
        清洗后的内容
    """
    if not content.markdown:
        return content

    # 先做基础清洗
    basic_cleaned = clean_content_basic(content)

    # 如果内容太短，不需要LLM处理
    if len(basic_cleaned.markdown or "") < 200:
        return basic_cleaned

    # 使用LLM进一步清洗
    try:
        chain = CLEAN_CONTENT_PROMPT | llm
        result = await chain.ainvoke({"content": basic_cleaned.markdown[:5000]})

        cleaned_text = result.content if hasattr(result, "content") else str(result)

        return ScrapedContent(
            url=content.url,
            title=content.title,
            markdown=cleaned_text,
            html=content.html,
            metadata={**content.metadata, "cleaned": True, "clean_method": "llm"},
        )
    except Exception as e:
        # LLM清洗失败时返回基础清洗结果
        return ScrapedContent(
            url=basic_cleaned.url,
            title=basic_cleaned.title,
            markdown=basic_cleaned.markdown,
            html=basic_cleaned.html,
            metadata={
                **basic_cleaned.metadata,
                "clean_error": str(e),
            },
        )


def clean_contents_batch(
    contents: list[ScrapedContent],
) -> list[ScrapedContent]:
    """
    批量基础清洗内容

    Args:
        contents: 原始内容列表

    Returns:
        清洗后的内容列表
    """
    return [clean_content_basic(content) for content in contents]


async def clean_contents_batch_with_llm(
    contents: list[ScrapedContent],
    llm: BaseChatModel,
) -> list[ScrapedContent]:
    """
    批量使用LLM清洗内容

    Args:
        contents: 原始内容列表
        llm: LLM实例

    Returns:
        清洗后的内容列表
    """
    cleaned = []
    for content in contents:
        cleaned_content = await clean_content_with_llm(content, llm)
        cleaned.append(cleaned_content)
    return cleaned
