"""
LLM 提供者

支持多种LLM提供者: OpenAI, Anthropic, Ollama, 自定义Claude API
"""

from functools import lru_cache

from langchain_core.language_models import BaseChatModel

from ..config.settings import get_settings


def get_openai_llm(
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    temperature: float | None = None,
) -> BaseChatModel:
    """获取OpenAI LLM实例"""
    from langchain_openai import ChatOpenAI

    settings = get_settings()

    # 构建参数
    kwargs = {
        "model": model or settings.llm_model,
        "api_key": api_key or settings.llm_api_key,
        "temperature": temperature if temperature is not None else settings.llm_temperature,
    }

    # 如果有 base_url，添加到参数中（支持第三方 API 代理）
    actual_base_url = base_url or settings.llm_base_url
    if actual_base_url:
        kwargs["base_url"] = actual_base_url

    return ChatOpenAI(**kwargs)


def get_anthropic_llm(
    model: str | None = None,
    api_key: str | None = None,
    temperature: float | None = None,
) -> BaseChatModel:
    """获取Anthropic LLM实例"""
    from langchain_anthropic import ChatAnthropic

    settings = get_settings()

    return ChatAnthropic(
        model=model or settings.llm_model,
        api_key=api_key or settings.llm_api_key,
        temperature=temperature if temperature is not None else settings.llm_temperature,
    )


def get_ollama_llm(
    model: str | None = None,
    base_url: str | None = None,
    temperature: float | None = None,
) -> BaseChatModel:
    """获取Ollama LLM实例"""
    try:
        from langchain_ollama import ChatOllama
    except ImportError as e:
        raise ImportError(
            "langchain-ollama is required for Ollama support. "
            "Install it with: uv add langchain-ollama"
        ) from e

    settings = get_settings()

    return ChatOllama(
        model=model or settings.llm_model,
        base_url=base_url or settings.llm_base_url or "http://localhost:11434",
        temperature=temperature if temperature is not None else settings.llm_temperature,
    )


def get_custom_claude_llm(
    base_url: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    temperature: float | None = None,
) -> BaseChatModel:
    """获取自定义Claude API LLM实例

    用于连接第三方 Claude API 代理服务

    Args:
        base_url: API基础URL (默认: https://api.codeable.icu)
        api_key: API密钥
        model: 模型名称 (默认: claude-opus-4-5-20251101)
        temperature: 温度参数

    Returns:
        ChatAnthropic LLM实例
    """
    from langchain_anthropic import ChatAnthropic

    settings = get_settings()

    # 使用自定义配置或默认值
    resolved_base_url = base_url or settings.custom_claude_base_url
    resolved_api_key = api_key or settings.custom_claude_api_key
    resolved_model = model or settings.custom_claude_model
    resolved_temperature = temperature if temperature is not None else settings.llm_temperature

    # 确保有API密钥
    if not resolved_api_key:
        raise ValueError(
            "自定义Claude API密钥未配置。"
            "请设置环境变量 GS_CRAWL_CUSTOM_CLAUDE_API_KEY 或传入 api_key 参数"
        )

    # 如果 base_url 已包含路径后缀 (如 /claude 或 /v1)，则不再添加
    if resolved_base_url.rstrip('/').endswith(('/claude', '/v1')):
        final_base_url = resolved_base_url
    else:
        final_base_url = resolved_base_url

    return ChatAnthropic(
        model=resolved_model,
        api_key=resolved_api_key,
        base_url=final_base_url,
        temperature=resolved_temperature,
        default_headers={"anthropic-version": "2023-06-01"},
    )


@lru_cache
def get_llm(
    provider: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    temperature: float | None = None,
) -> BaseChatModel:
    """
    获取LLM实例

    Args:
        provider: LLM提供者 (openai, anthropic, ollama, custom_claude)
        model: 模型名称
        api_key: API密钥
        temperature: 温度参数

    Returns:
        LLM实例
    """
    settings = get_settings()
    provider = provider or settings.llm_provider

    if provider == "openai":
        return get_openai_llm(model=model, api_key=api_key, temperature=temperature)
    elif provider == "anthropic":
        return get_anthropic_llm(model=model, api_key=api_key, temperature=temperature)
    elif provider == "ollama":
        return get_ollama_llm(model=model, temperature=temperature)
    elif provider == "custom_claude":
        return get_custom_claude_llm(api_key=api_key, model=model, temperature=temperature)
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")
