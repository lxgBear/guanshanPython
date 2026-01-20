"""
输出格式化处理器

将结果格式化为不同的输出格式
"""

from ..models.schemas import CrawlOutput


def format_as_markdown(output: CrawlOutput) -> str:
    """
    格式化为Markdown

    Args:
        output: 爬取输出对象

    Returns:
        Markdown格式的字符串
    """
    lines: list[str] = []

    # 标题
    lines.append(f"# {output.query}")
    lines.append("")

    # 摘要
    if output.summary:
        lines.append("## 摘要")
        lines.append("")
        lines.append(output.summary)
        lines.append("")

    # 元信息
    lines.append("## 搜索信息")
    lines.append("")
    lines.append(f"- **找到结果**: {output.total_found} 条")
    lines.append(f"- **使用关键词**: {', '.join(output.keywords_used)}")
    lines.append(f"- **执行时间**: {output.execution_time:.2f}秒")
    lines.append("")

    # 搜索结果
    lines.append("## 搜索结果")
    lines.append("")

    for i, result in enumerate(output.results, 1):
        lines.append(f"### {i}. {result.title}")
        lines.append("")
        lines.append(f"- **URL**: {result.url}")
        lines.append(f"- **来源**: {result.source}")
        if result.description:
            lines.append(f"- **描述**: {result.description}")
        lines.append("")

    # 深度抓取内容
    if output.scraped_contents:
        lines.append("## 详细内容")
        lines.append("")

        for content in output.scraped_contents:
            lines.append(f"### {content.title}")
            lines.append("")
            lines.append(f"**URL**: {content.url}")
            lines.append("")
            if content.markdown:
                lines.append(content.markdown[:2000])
                if len(content.markdown) > 2000:
                    lines.append("...")
                    lines.append("*(内容已截断)*")
            lines.append("")

    return "\n".join(lines)


def format_as_json(output: CrawlOutput) -> str:
    """
    格式化为JSON

    Args:
        output: 爬取输出对象

    Returns:
        JSON格式的字符串
    """
    return output.model_dump_json(indent=2, ensure_ascii=False)


def format_as_structured(output: CrawlOutput) -> str:
    """
    格式化为结构化文本

    Args:
        output: 爬取输出对象

    Returns:
        结构化文本
    """
    lines: list[str] = []

    lines.append(f"查询: {output.query}")
    lines.append(f"关键词: {', '.join(output.keywords_used)}")
    lines.append(f"结果数: {output.total_found}")
    lines.append(f"耗时: {output.execution_time:.2f}s")
    lines.append("")

    if output.summary:
        lines.append("--- 摘要 ---")
        lines.append(output.summary)
        lines.append("")

    lines.append("--- 结果 ---")
    for i, result in enumerate(output.results, 1):
        lines.append(f"{i}. {result.title}")
        lines.append(f"   URL: {result.url}")
        if result.description:
            lines.append(f"   {result.description}")
        lines.append("")

    return "\n".join(lines)


def format_results(
    output: CrawlOutput,
    format_type: str = "markdown",
) -> str:
    """
    根据类型格式化结果

    Args:
        output: 爬取输出对象
        format_type: 格式类型 (markdown, json, structured)

    Returns:
        格式化后的字符串
    """
    if format_type == "json":
        return format_as_json(output)
    elif format_type == "structured":
        return format_as_structured(output)
    else:
        return format_as_markdown(output)
