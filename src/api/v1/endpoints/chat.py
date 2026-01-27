"""
Chat API 端点

提供智能搜索和对话管理功能，集成 NL Search 和远程 AI 服务。

**功能**:
- POST /chat/sync: 主搜索接口（支持同步/异步模式）
- 任务管理: 创建、查询、删除后台任务
- 对话管理: 会话创建、消息历史、置顶等
- 搜索历史: 历史记录查询和统计

**v4.0.0 更新**:
- 集成 LangGraph 搜索引擎
- 通过 SearchEngineAdapter 支持多种搜索后端
- 环境变量 SEARCH_ENGINE=langgraph 启用 LangGraph
- 自动回退机制（LangGraph 失败时回退到 NL Search）

**v3.0.0 更新**:
- 统一任务化模型，支持 wait=true/false 模式
- 移除冗余的 SSE 流式接口和简化接口

**v2.7.0 更新**:
- 添加 Token 认证，强制从 Token 获取用户身份
- 添加用户隔离逻辑（admin 查看所有，普通用户只能查看自己的）
- 新增 info_items 和 is_pinned 字段支持
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union
import json
import logging
import httpx
from datetime import datetime
from pathlib import Path

from src.services.nl_search.nl_search_service import nl_search_service
from src.services.nl_search.search_history_service import search_history_service
from src.services.search_engine_adapter import search_engine_adapter
from src.infrastructure.database.connection import get_mongodb_database
from src.infrastructure.database.chat_conversation_repository import (
    chat_conversation_repository
)
from src.infrastructure.database.chat_task_repository import chat_task_repository
from src.services.chat_task_service import chat_task_service
from src.services.chat_search_service import get_chat_search_service, ChatSearchService
from src.core.domain.entities.chat_search_elements import ChatSearchElements
from src.core.domain.entities.auth.user import User
from src.api.dependencies.auth import get_current_active_user
from bson import ObjectId
import os

logger = logging.getLogger(__name__)

# AI服务配置 (支持环境变量覆盖)
REMOTE_AI_SERVICE_URL = os.getenv("LAYER_AI_SERVICE_URL", "http://localhost:8035/chat")
REMOTE_AI_SERVICE_TIMEOUT = 300.0  # 5分钟 - LangGraph 5层搜索需要更长时间

router = APIRouter()


# ==================== 工具函数 ====================

async def populate_info_items(info_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """填充 info_items 的完整数据 (v2.9.0)

    从原表查询完整信息，根据 source 字段路由到不同的集合:
    - "用户上传" → file_uploads 集合
    - 其他 → news_results 集合

    Args:
        info_items: 只包含 mongo_id + source 的引用列表

    Returns:
        填充了 title, score, preview 等完整信息的列表
    """
    if not info_items:
        return []

    db = await get_mongodb_database()
    populated_items = []

    for item in info_items:
        mongo_id = item.get("mongo_id") or item.get("id")
        source = item.get("source", "")

        if not mongo_id:
            populated_items.append(item)
            continue

        try:
            if source == "用户上传":
                # 从 file_uploads 集合查询
                result = await db["file_uploads"].find_one(
                    {"_id": ObjectId(mongo_id)},
                    {"title": 1, "content": 1, "_id": 0}
                )
                if result:
                    populated_items.append({
                        **item,
                        "title": result.get("title") or item.get("title", ""),
                        "preview": (result.get("content") or "")[:200],
                    })
                else:
                    populated_items.append(item)
            else:
                # 从 news_results 集合查询
                result = await db["news_results"].find_one(
                    {"_id": mongo_id},
                    {"news_results.title_zh": 1, "news_results.summary_zh": 1, "_id": 0}
                )
                if result:
                    nested = result.get("news_results", {})
                    populated_items.append({
                        **item,
                        "title": nested.get("title_zh") or item.get("title", ""),
                        "preview": (nested.get("summary_zh") or "")[:200],
                    })
                else:
                    populated_items.append(item)

        except Exception as e:
            logger.warning(f"填充 info_item 失败 (mongo_id={mongo_id}): {e}")
            populated_items.append(item)

    return populated_items


# ==================== 数据模型 ====================

class HistoryMessage(BaseModel):
    """历史消息模型"""
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str


class ChatRequest(BaseModel):
    """Chat请求模型（兼容前端）

    v1.1.0: 新增 conversation_id 和 history 支持多轮对话
    """
    question: str = Field(
        ...,
        description="用户提问（自然语言）",
        min_length=1,
        max_length=1000,
        examples=["请介绍关于西藏的新闻"]
    )
    user_id: Optional[str] = Field(
        None,
        description="用户ID（可选）"
    )
    search_mode: str = Field(
        default="single",
        description="搜索模式: single=单次搜索, multi=多问题分解",
        pattern="^(single|multi)$"
    )
    conversation_id: Optional[str] = Field(
        None,
        description="对话会话ID（可选，用于多轮对话）"
    )
    history: Optional[List[HistoryMessage]] = Field(
        None,
        description="对话历史（可选，如果提供了conversation_id会自动从服务器获取）"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "question": "请介绍关于西藏的新闻",
                "conversation_id": "248728141926559744",
                "history": [
                    {"role": "user", "content": "你好"},
                    {"role": "assistant", "content": "你好！有什么可以帮助你的？"}
                ]
            }
        }


class CategoryModel(BaseModel):
    """分类信息模型"""
    大类: str
    类别: str
    地域: str


class SourceDetail(BaseModel):
    """来源详情模型（增强版，统一格式）

    v2.7.1: 统一新闻来源和用户上传格式
    - 用户上传数据映射到相同字段结构
    - file_uploads.title → title_zh
    - file_uploads.content → content_zh
    - file_uploads.storage_url → url
    """
    id: str = Field(..., description="UUID")
    mongo_id: str = Field(..., description="MongoDB ID")
    title: str = Field(..., description="标题")
    source: str = Field(..., description="来源：新闻网站名称 或 '用户上传'")
    category: CategoryModel = Field(..., description="分类信息")
    publish_time: str = Field(..., description="发布时间")
    preview: str = Field(..., description="内容预览")
    url: Optional[str] = Field(None, description="完整URL")
    markdown_content: Optional[str] = Field(None, description="完整Markdown内容")
    html_content: Optional[str] = Field(None, description="HTML格式内容")
    content_length: Optional[int] = Field(None, description="内容长度")
    title_zh: Optional[str] = Field(None, description="中文标题")
    summary_zh: Optional[str] = Field(None, description="中文摘要")
    content_zh: Optional[str] = Field(None, description="中文内容/正文")


class ChatSyncResponse(BaseModel):
    """Chat同步响应模型"""
    question: str = Field(..., description="用户问题")
    answer: str = Field(..., description="完整答案")
    sources: List[SourceDetail] = Field(..., description="数据来源列表（含完整内容）")
    sources_count: int = Field(..., description="来源数量")
    answer_length: int = Field(..., description="答案长度")
    status: str = Field(..., description="状态")
    # v4.6.0: task_id 改为存储 LangGraph 工作流ID（用于查询langgraph_search_results）
    # 数据迁移到 news_results 后，Celery任务ID不再需要，统一使用 LangGraph thread_id
    task_id: Optional[str] = Field(None, description="LangGraph工作流ID，用于查询langgraph_search_results")


# ==================== 要素确认相关模型 (v4.20.0) ====================

class ChatSearchElementsModel(BaseModel):
    """搜索要素模型 (v4.20.0)

    用于要素确认流程，封装 LLM 提取的搜索参数。
    """
    keywords: List[str] = Field(..., description="中文关键词列表")
    keywords_en: List[str] = Field(default_factory=list, description="英文关键词列表")
    time_range: Optional[str] = Field(None, description="时间范围 (qdr:d, qdr:w, qdr:m, qdr:y)")
    source_preferences: List[str] = Field(default_factory=list, description="来源偏好 (official, mainstream, regional)")
    languages: List[str] = Field(default_factory=lambda: ["zh", "en"], description="搜索语言列表")
    search_strategy: Dict[str, Any] = Field(default_factory=dict, description="搜索策略配置")
    summary: str = Field(default="", description="事件简要描述")
    event_type: str = Field(default="", description="事件类型")
    llm_reasoning: str = Field(default="", description="LLM 分析理由")
    original_query: str = Field(default="", description="原始查询")


class ConfirmElementsRequest(BaseModel):
    """确认要素请求 (v4.20.0)"""
    confirmed_elements: ChatSearchElementsModel = Field(..., description="用户确认的搜索要素")


class ChatTaskWithElementsResponse(BaseModel):
    """带要素的任务响应 (v4.20.0)

    用于要素确认流程的第一阶段响应。
    """
    task_id: str = Field(..., description="任务ID")
    status: str = Field(..., description="任务状态 (awaiting_confirmation)")
    extracted_elements: Optional[ChatSearchElementsModel] = Field(None, description="LLM 提取的搜索要素")
    message: str = Field(default="", description="提示消息")
    created_at: Optional[str] = Field(None, description="创建时间")


# ==================== v3.0.0: 任务模式相关模型 ====================

class ChatTaskCreatedResponse(BaseModel):
    """任务创建响应（异步模式）"""
    task_id: str = Field(..., description="任务ID")
    status: str = Field(..., description="任务状态")
    message: str = Field(..., description="提示消息")
    created_at: str = Field(..., description="创建时间")


class ChatTaskProgressModel(BaseModel):
    """任务进度模型"""
    current_step: str = Field(..., description="当前步骤")
    message: str = Field(..., description="进度消息")
    percentage: int = Field(..., description="进度百分比")


class ChatTaskDetailResponse(BaseModel):
    """任务详情响应"""
    task_id: str = Field(..., description="任务ID")
    status: str = Field(..., description="任务状态: pending/searching/processing/completed/failed")
    progress: ChatTaskProgressModel = Field(..., description="任务进度")
    question: str = Field(..., description="用户问题")
    result: Optional[Dict[str, Any]] = Field(None, description="任务结果（完成后填充）")
    error: Optional[Dict[str, Any]] = Field(None, description="错误信息（失败时填充）")
    history_id: Optional[str] = Field(None, description="关联的历史记录ID")
    created_at: Optional[str] = Field(None, description="创建时间")
    completed_at: Optional[str] = Field(None, description="完成时间")


class ChatTaskListResponse(BaseModel):
    """任务列表响应"""
    items: List[ChatTaskDetailResponse] = Field(..., description="任务列表")
    total: int = Field(..., description="总数")
    limit: int = Field(..., description="每页数量")
    offset: int = Field(..., description="偏移量")


# ==================== API端点 ====================

# 注意：POST /chat/sync 主搜索接口已迁移至 Chat V2
# 请使用 POST /chat/v2/sync 进行搜索
# Chat V2 提供更先进的层分离架构和要素确认功能

# ==================== 任务管理 API (v3.0.0) ====================
# 注意：以下任务管理接口已迁移至 Chat V2 (api/v1/chat/v2/*)
# 请使用 Chat V2 接口进行搜索任务管理
# - POST /chat/v2/sync - 主搜索接口
# - GET /chat/v2/tasks - 任务列表
# - GET /chat/v2/tasks/{task_id} - 任务详情
# - POST /chat/v2/tasks/{task_id}/confirm - 确认搜索要素

# ==================== 对话历史 API ====================
# v1.1.0 新增：对话会话持久化
# chat_conversation_repository 已在文件顶部导入


class InfoItemModel(BaseModel):
    """信息条目存储模型 (v2.9.0 优化, v4.22.0 扩展)

    只存储引用信息 (mongo_id + source)，查询时从原表填充完整数据。
    优化目的: 减少数据冗余，降低数据库存储压力，保证数据一致性。

    v4.22.0: 添加 markdown_content 和 html_content 字段支持完整内容存储
    """
    id: str = Field(..., description="条目ID (同 mongo_id)")
    mongo_id: str = Field(..., description="MongoDB 数据库 ID")
    source: str = Field(..., description="来源类型 (新闻/用户上传)")
    # 以下字段为可选，用于兼容旧数据和查询时填充
    title: Optional[str] = Field(None, description="标题 (查询时填充)")
    score: Optional[float] = Field(None, description="相关性评分 (查询时填充)")
    preview: Optional[str] = Field(None, description="预览内容 (查询时填充)")
    # v4.22.0: 完整内容字段
    markdown_content: Optional[str] = Field(None, description="Markdown格式内容")
    html_content: Optional[str] = Field(None, description="HTML格式内容")


class ConversationCreateRequest(BaseModel):
    """创建对话会话请求

    v2.7.0: user_id 已移除，后端从 Token 自动获取用户身份
    """
    title: Optional[str] = Field(None, description="会话标题（可选，自动从首条消息生成）")
    is_pinned: Optional[bool] = Field(False, description="是否置顶")


class ConversationCreateResponse(BaseModel):
    """创建对话会话响应"""
    conversation_id: str
    title: str
    created_at: str


class MessageModel(BaseModel):
    """消息模型"""
    id: str
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str
    timestamp: str
    sources: List[Dict[str, Any]] = []
    info_items: List[InfoItemModel] = Field(default_factory=list, description="关联的信息条目")


class ConversationModel(BaseModel):
    """对话会话模型

    v2.7.0: 新增 is_pinned 和 info_items 字段
    """
    id: str = Field(..., alias="_id")
    title: str
    user_id: Optional[str]
    messages: List[MessageModel]
    message_count: int
    last_message_at: str
    created_at: str
    is_pinned: bool = Field(default=False, description="是否置顶")
    info_items: List[InfoItemModel] = Field(default_factory=list, description="对话关联的信息条目")

    class Config:
        populate_by_name = True


class ConversationListItem(BaseModel):
    """对话列表项"""
    id: str = Field(..., alias="_id")
    title: str
    user_id: Optional[str]
    message_count: int
    last_message_at: str
    last_message: Optional[MessageModel]
    created_at: str
    is_pinned: bool = Field(default=False, description="是否置顶")

    class Config:
        populate_by_name = True


class ConversationListResponse(BaseModel):
    """对话列表响应"""
    conversations: List[ConversationListItem]
    total: int
    has_more: bool


class AddMessageRequest(BaseModel):
    """添加消息请求"""
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., min_length=1)
    sources: Optional[List[Dict[str, Any]]] = None
    info_items: Optional[List[InfoItemModel]] = Field(None, description="关联的信息条目")


@router.post(
    "/chat/conversations",
    response_model=ConversationCreateResponse,
    summary="创建对话会话",
    description="创建新的对话会话，返回会话ID。v2.7.0: 需要 Token 认证"
)
async def create_conversation(
    request: ConversationCreateRequest,
    current_user: User = Depends(get_current_active_user)  # v2.7.0: 强制 Token 认证
):
    """创建新对话会话

    v2.7.0: user_id 从 Token 自动获取，不再从请求参数传入
    """
    try:
        # v2.7.0: 从 Token 获取用户 ID
        user_id = str(current_user.id)

        conversation_id = await chat_conversation_repository.create_conversation(
            user_id=user_id,
            title=request.title,
            metadata={"is_pinned": request.is_pinned or False}
        )

        conversation = await chat_conversation_repository.get_by_id(
            conversation_id, include_messages=False
        )

        logger.info(f"创建对话会话成功: conv_id={conversation_id}, user_id={user_id}")

        return ConversationCreateResponse(
            conversation_id=conversation_id,
            title=conversation["title"],
            created_at=conversation["created_at"].isoformat()
        )

    except Exception as e:
        logger.error(f"创建对话会话失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="创建对话会话失败")


@router.get(
    "/chat/conversations",
    response_model=ConversationListResponse,
    summary="获取对话列表",
    description="获取用户的对话会话列表（分页）。v2.7.0: 需要 Token 认证，admin 可查看所有，普通用户只能查看自己的"
)
async def get_conversations(
    current_user: User = Depends(get_current_active_user),  # v2.7.0: 强制 Token 认证
    limit: int = 20,
    offset: int = 0
):
    """获取对话列表

    v2.7.0: 用户隔离
    - admin 角色可查看所有对话
    - 普通用户只能查看自己的对话
    """
    try:
        # v2.7.0: 用户隔离逻辑
        is_admin = "admin" in current_user.roles
        effective_user_id = None if is_admin else str(current_user.id)

        logger.info(f"获取对话列表: user_id={current_user.id}, is_admin={is_admin}, effective_filter={effective_user_id}")

        conversations = await chat_conversation_repository.get_recent_conversations(
            user_id=effective_user_id,
            limit=limit + 1,  # 多取一条判断是否有更多
            offset=offset
        )

        has_more = len(conversations) > limit
        if has_more:
            conversations = conversations[:limit]

        total = await chat_conversation_repository.count_conversations(user_id=effective_user_id)

        # 转换时间格式
        items = []
        for conv in conversations:
            last_msg = conv.get("last_message")
            metadata = conv.get("metadata", {})
            items.append(ConversationListItem(
                _id=conv["_id"],
                title=conv["title"],
                user_id=conv.get("user_id"),
                message_count=conv["message_count"],
                last_message_at=conv["last_message_at"].isoformat() if conv.get("last_message_at") else "",
                last_message=MessageModel(
                    id=last_msg["id"],
                    role=last_msg["role"],
                    content=last_msg["content"],
                    timestamp=last_msg["timestamp"],
                    sources=last_msg.get("sources", []),
                    info_items=last_msg.get("info_items", [])
                ) if last_msg else None,
                created_at=conv["created_at"].isoformat() if conv.get("created_at") else "",
                is_pinned=metadata.get("is_pinned", False)
            ))

        return ConversationListResponse(
            conversations=items,
            total=total,
            has_more=has_more
        )

    except Exception as e:
        logger.error(f"获取对话列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取对话列表失败")


@router.get(
    "/chat/conversations/{conversation_id}",
    summary="获取对话详情",
    description="获取指定对话会话的完整信息和消息历史。v2.7.0: 需要 Token 认证，非 admin 只能访问自己的对话"
)
async def get_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_active_user)  # v2.7.0: 强制 Token 认证
):
    """获取对话详情

    v2.7.0: 用户隔离 - 非 admin 只能访问自己的对话
    """
    try:
        conversation = await chat_conversation_repository.get_by_id(
            conversation_id, include_messages=True
        )

        if not conversation:
            raise HTTPException(status_code=404, detail="对话会话不存在")

        # v2.7.0: 权限检查 - 非 admin 只能访问自己的对话
        is_admin = "admin" in current_user.roles
        conv_owner_id = conversation.get("user_id")
        if not is_admin and str(conv_owner_id) != str(current_user.id):
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "AUTH_005",
                    "message": "权限不足，您只能查看自己的对话"
                }
            )

        # 转换时间格式 + v2.9.0: 填充 info_items 完整数据
        messages = []
        for msg in conversation.get("messages", []):
            # v2.9.0: 填充消息中的 info_items
            msg_info_items = msg.get("info_items", [])
            if msg_info_items:
                msg_info_items = await populate_info_items(msg_info_items)

            messages.append({
                "id": msg["id"],
                "role": msg["role"],
                "content": msg["content"],
                "timestamp": msg["timestamp"],
                "sources": msg.get("sources", []),
                "info_items": msg_info_items
            })

        # v2.9.0: 填充对话级别的 info_items
        conv_info_items = conversation.get("info_items", [])
        if conv_info_items:
            conv_info_items = await populate_info_items(conv_info_items)

        metadata = conversation.get("metadata", {})
        return {
            "id": conversation["_id"],
            "title": conversation["title"],
            "user_id": conversation.get("user_id"),
            "messages": messages,
            "message_count": conversation["message_count"],
            "last_message_at": conversation["last_message_at"].isoformat() if conversation.get("last_message_at") else "",
            "created_at": conversation["created_at"].isoformat() if conversation.get("created_at") else "",
            "is_pinned": metadata.get("is_pinned", False),
            "info_items": conv_info_items
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取对话详情失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取对话详情失败")


@router.post(
    "/chat/conversations/{conversation_id}/messages",
    summary="添加消息",
    description="向对话会话添加新消息。v2.7.0: 需要 Token 认证，非 admin 只能向自己的对话添加消息"
)
async def add_message(
    conversation_id: str,
    request: AddMessageRequest,
    current_user: User = Depends(get_current_active_user)  # v2.7.0: 强制 Token 认证
):
    """添加消息到对话

    v2.7.0: 用户隔离 - 非 admin 只能向自己的对话添加消息
    """
    try:
        # v2.7.0: 先检查对话归属
        conversation = await chat_conversation_repository.get_by_id(
            conversation_id, include_messages=False
        )

        if not conversation:
            raise HTTPException(status_code=404, detail="对话会话不存在")

        # v2.7.0: 权限检查
        is_admin = "admin" in current_user.roles
        conv_owner_id = conversation.get("user_id")
        if not is_admin and str(conv_owner_id) != str(current_user.id):
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "AUTH_005",
                    "message": "权限不足，您只能向自己的对话添加消息"
                }
            )

        # 转换 info_items 为字典格式
        info_items_dict = None
        if request.info_items:
            info_items_dict = [item.model_dump() for item in request.info_items]

        message_id = await chat_conversation_repository.add_message(
            conversation_id=conversation_id,
            role=request.role,
            content=request.content,
            sources=request.sources,
            metadata={"info_items": info_items_dict} if info_items_dict else None
        )

        if not message_id:
            raise HTTPException(status_code=404, detail="对话会话不存在")

        return {
            "message_id": message_id,
            "conversation_id": conversation_id,
            "role": request.role,
            "content": request.content
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"添加消息失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="添加消息失败")


@router.get(
    "/chat/conversations/{conversation_id}/messages",
    summary="获取消息历史",
    description="获取对话会话的消息历史（支持分页）。v2.7.0: 需要 Token 认证，非 admin 只能获取自己的对话消息"
)
async def get_messages(
    conversation_id: str,
    current_user: User = Depends(get_current_active_user),  # v2.7.0: 强制 Token 认证
    limit: Optional[int] = None,
    before: Optional[str] = None
):
    """获取消息历史

    v2.7.0: 用户隔离 - 非 admin 只能获取自己的对话消息
    """
    try:
        # v2.7.0: 先检查对话归属
        conversation = await chat_conversation_repository.get_by_id(
            conversation_id, include_messages=False
        )

        if not conversation:
            raise HTTPException(status_code=404, detail="对话会话不存在")

        # v2.7.0: 权限检查
        is_admin = "admin" in current_user.roles
        conv_owner_id = conversation.get("user_id")
        if not is_admin and str(conv_owner_id) != str(current_user.id):
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "AUTH_005",
                    "message": "权限不足，您只能获取自己的对话消息"
                }
            )

        messages = await chat_conversation_repository.get_messages(
            conversation_id=conversation_id,
            limit=limit,
            before_message_id=before
        )

        if messages is None:
            raise HTTPException(status_code=404, detail="对话会话不存在")

        return {
            "conversation_id": conversation_id,
            "messages": messages,
            "count": len(messages)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取消息历史失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取消息历史失败")


@router.get(
    "/chat/conversations/{conversation_id}/messages/{message_id}",
    summary="获取单条消息详情",
    description="获取单条消息的完整详情，包含填充后的 info_items。v2.10.0 新增"
)
async def get_message_detail(
    conversation_id: str,
    message_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """获取单条消息详情

    v2.10.0 新增 - 用于点击"查看 X 条搜索结果"时获取完整的 info_items

    返回包含:
    - 消息基本信息 (id, role, content, timestamp)
    - sources 来源引用
    - info_items 完整信息条目列表（已填充 title, preview 等字段）

    Args:
        conversation_id: 对话会话ID
        message_id: 消息ID

    Returns:
        消息详情，包含填充后的 info_items
    """
    try:
        # 先检查对话归属
        conversation = await chat_conversation_repository.get_by_id(
            conversation_id, include_messages=False
        )

        if not conversation:
            raise HTTPException(status_code=404, detail="对话会话不存在")

        # 权限检查
        is_admin = "admin" in current_user.roles
        conv_owner_id = conversation.get("user_id")
        if not is_admin and str(conv_owner_id) != str(current_user.id):
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "AUTH_005",
                    "message": "权限不足，您只能获取自己的对话消息"
                }
            )

        # 获取单条消息
        message = await chat_conversation_repository.get_message_by_id(
            conversation_id=conversation_id,
            message_id=message_id
        )

        if not message:
            raise HTTPException(status_code=404, detail="消息不存在")

        # 填充 info_items 完整数据
        msg_info_items = message.get("info_items", [])
        if msg_info_items:
            msg_info_items = await populate_info_items(msg_info_items)

        return {
            "conversation_id": conversation_id,
            "message": {
                "id": message["id"],
                "role": message["role"],
                "content": message["content"],
                "timestamp": message["timestamp"],
                "sources": message.get("sources", []),
                "info_items": msg_info_items,
                "info_items_count": len(msg_info_items)
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取消息详情失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取消息详情失败")


class UpdateConversationRequest(BaseModel):
    """更新对话请求 - v2.7.0 扩展"""
    title: Optional[str] = Field(None, min_length=1, max_length=100, description="会话标题")
    is_pinned: Optional[bool] = Field(None, description="是否置顶")


@router.patch(
    "/chat/conversations/{conversation_id}",
    summary="更新对话",
    description="更新对话会话的标题或置顶状态。v2.7.0: 需要 Token 认证，非 admin 只能更新自己的对话"
)
async def update_conversation(
    conversation_id: str,
    request: UpdateConversationRequest,
    current_user: User = Depends(get_current_active_user)  # v2.7.0: 强制 Token 认证
):
    """更新对话

    v2.7.0: 用户隔离 - 非 admin 只能更新自己的对话
    """
    try:
        # v2.7.0: 先检查对话归属
        conversation = await chat_conversation_repository.get_by_id(
            conversation_id, include_messages=False
        )

        if not conversation:
            raise HTTPException(status_code=404, detail="对话会话不存在")

        # v2.7.0: 权限检查
        is_admin = "admin" in current_user.roles
        conv_owner_id = conversation.get("user_id")
        if not is_admin and str(conv_owner_id) != str(current_user.id):
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "AUTH_005",
                    "message": "权限不足，您只能更新自己的对话"
                }
            )

        # 更新标题
        if request.title:
            await chat_conversation_repository.update_title(
                conversation_id=conversation_id,
                title=request.title
            )

        # 更新置顶状态
        if request.is_pinned is not None:
            await chat_conversation_repository.update_metadata(
                conversation_id=conversation_id,
                metadata={"is_pinned": request.is_pinned},
                merge=True
            )

        return {
            "success": True,
            "title": request.title,
            "is_pinned": request.is_pinned
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新对话失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="更新对话失败")


@router.delete(
    "/chat/conversations/{conversation_id}",
    summary="删除对话",
    description="删除指定的对话会话。v2.7.0: 需要 Token 认证，非 admin 只能删除自己的对话"
)
async def delete_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_active_user)  # v2.7.0: 强制 Token 认证
):
    """删除对话会话

    v2.7.0: 用户隔离 - 非 admin 只能删除自己的对话
    """
    try:
        # v2.7.0: 先检查对话归属
        conversation = await chat_conversation_repository.get_by_id(
            conversation_id, include_messages=False
        )

        if not conversation:
            raise HTTPException(status_code=404, detail="对话会话不存在")

        # v2.7.0: 权限检查
        is_admin = "admin" in current_user.roles
        conv_owner_id = conversation.get("user_id")
        if not is_admin and str(conv_owner_id) != str(current_user.id):
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "AUTH_005",
                    "message": "权限不足，您只能删除自己的对话"
                }
            )

        success = await chat_conversation_repository.delete_conversation(
            conversation_id=conversation_id
        )

        if not success:
            raise HTTPException(status_code=404, detail="对话会话不存在")

        logger.info(f"删除对话会话成功: conv_id={conversation_id}, user_id={current_user.id}")

        return {"success": True, "deleted_id": conversation_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除对话会话失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="删除对话会话失败")


@router.get(
    "/chat/conversations/search",
    summary="搜索对话",
    description="按关键词搜索对话会话。v2.7.0: 需要 Token 认证，admin 可搜索所有，普通用户只能搜索自己的"
)
async def search_conversations(
    q: str,
    current_user: User = Depends(get_current_active_user),  # v2.7.0: 强制 Token 认证
    limit: int = 20
):
    """搜索对话

    v2.7.0: 用户隔离
    - admin 角色可搜索所有对话
    - 普通用户只能搜索自己的对话
    """
    try:
        # v2.7.0: 用户隔离逻辑
        is_admin = "admin" in current_user.roles
        effective_user_id = None if is_admin else str(current_user.id)

        logger.info(f"搜索对话: user_id={current_user.id}, is_admin={is_admin}, query='{q[:20]}...'")

        conversations = await chat_conversation_repository.search_conversations(
            query=q,
            user_id=effective_user_id,
            limit=limit
        )

        items = []
        for conv in conversations:
            last_msg = conv.get("last_message")
            metadata = conv.get("metadata", {})
            items.append({
                "id": conv["_id"],
                "title": conv["title"],
                "user_id": conv.get("user_id"),
                "message_count": conv["message_count"],
                "last_message_at": conv["last_message_at"].isoformat() if conv.get("last_message_at") else "",
                "last_message": {
                    "id": last_msg["id"],
                    "role": last_msg["role"],
                    "content": last_msg["content"],
                    "timestamp": last_msg["timestamp"],
                    "sources": last_msg.get("sources", []),
                    "info_items": last_msg.get("info_items", [])
                } if last_msg else None,
                "created_at": conv["created_at"].isoformat() if conv.get("created_at") else "",
                "is_pinned": metadata.get("is_pinned", False)
            })

        return {
            "query": q,
            "results": items,
            "count": len(items)
        }

    except Exception as e:
        logger.error(f"搜索对话失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="搜索对话失败")


# ==================== 搜索历史 API (v2.8.0) ====================

class SearchHistoryResultModel(BaseModel):
    """搜索结果项模型"""
    mongo_id: str
    source: str
    title: str
    score: float
    category: Optional[Dict[str, str]] = None
    publish_time: Optional[str] = None
    preview: Optional[str] = None


class SearchHistoryItemModel(BaseModel):
    """搜索历史记录模型"""
    id: str = Field(..., alias="_id")
    user_id: int
    query: str
    answer: Optional[str] = None
    results: Optional[List[SearchHistoryResultModel]] = None
    results_count: int = 0
    conversation_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None

    class Config:
        populate_by_name = True


class SearchHistoryListResponse(BaseModel):
    """搜索历史列表响应"""
    items: List[SearchHistoryItemModel]
    total: int
    limit: int
    offset: int


class SearchHistoryStatsResponse(BaseModel):
    """搜索统计响应"""
    total_searches: int
    total_results: int
    avg_results_per_search: float


@router.get(
    "/chat/search-history",
    summary="获取搜索历史列表",
    description="获取当前用户的搜索历史记录（分页）。v2.8.0 新增"
)
async def get_search_history(
    current_user: User = Depends(get_current_active_user),
    limit: int = 20,
    offset: int = 0,
    source_filter: Optional[str] = None
):
    """获取用户搜索历史列表

    Args:
        limit: 返回数量限制
        offset: 偏移量
        source_filter: 按来源类型筛选 (可选)
    """
    try:
        result = await search_history_service.get_user_history(
            user_id=current_user.id,
            limit=limit,
            offset=offset,
            source_filter=source_filter
        )

        # 转换日期格式
        items = []
        for item in result["items"]:
            items.append({
                "_id": item["_id"],
                "user_id": item["user_id"],
                "query": item["query"],
                "answer": item.get("answer"),
                "results_count": item.get("results_count", 0),
                "conversation_id": item.get("conversation_id"),
                "metadata": item.get("metadata"),
                "created_at": item["created_at"].isoformat() if item.get("created_at") else None
            })

        return SearchHistoryListResponse(
            items=items,
            total=result["total"],
            limit=result["limit"],
            offset=result["offset"]
        )

    except Exception as e:
        logger.error(f"获取搜索历史失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取搜索历史失败")


@router.get(
    "/chat/search-history/{history_id}",
    summary="获取搜索历史详情",
    description="获取指定搜索历史的完整详情"
)
async def get_search_history_detail(
    history_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """获取搜索历史详情"""
    try:
        history = await search_history_service.get_history_detail(
            history_id=history_id,
            user_id=current_user.id
        )

        if not history:
            raise HTTPException(status_code=404, detail="历史记录不存在")

        return {
            "_id": history["_id"],
            "user_id": history["user_id"],
            "query": history["query"],
            "answer": history.get("answer"),
            "results": history.get("results", []),
            "results_count": history.get("results_count", 0),
            "conversation_id": history.get("conversation_id"),
            "metadata": history.get("metadata"),
            "created_at": history["created_at"].isoformat() if history.get("created_at") else None,
            "updated_at": history["updated_at"].isoformat() if history.get("updated_at") else None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取搜索历史详情失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取搜索历史详情失败")


@router.get(
    "/chat/search-history/by-result/{mongo_id}",
    summary="按结果ID查询历史",
    description="查询引用了特定搜索结果的历史记录"
)
async def find_history_by_result(
    mongo_id: str,
    current_user: User = Depends(get_current_active_user),
    limit: int = 20
):
    """查询包含特定 mongo_id 的历史记录"""
    try:
        histories = await search_history_service.find_by_result_id(
            mongo_id=mongo_id,
            user_id=current_user.id,
            limit=limit
        )

        items = []
        for h in histories:
            items.append({
                "_id": h["_id"],
                "query": h["query"],
                "results_count": h.get("results_count", 0),
                "created_at": h["created_at"].isoformat() if h.get("created_at") else None
            })

        return {"items": items, "count": len(items)}

    except Exception as e:
        logger.error(f"按结果ID查询历史失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="查询失败")


@router.get(
    "/chat/search-history/by-source/{source}",
    summary="按来源类型查询历史",
    description="查询包含特定来源类型的历史记录"
)
async def find_history_by_source(
    source: str,
    current_user: User = Depends(get_current_active_user),
    limit: int = 20,
    offset: int = 0
):
    """按来源类型查询历史记录"""
    try:
        histories = await search_history_service.find_by_source_type(
            source=source,
            user_id=current_user.id,
            limit=limit,
            offset=offset
        )

        items = []
        for h in histories:
            items.append({
                "_id": h["_id"],
                "query": h["query"],
                "results_count": h.get("results_count", 0),
                "created_at": h["created_at"].isoformat() if h.get("created_at") else None
            })

        return {"items": items, "count": len(items)}

    except Exception as e:
        logger.error(f"按来源类型查询历史失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="查询失败")


@router.get(
    "/chat/search-history/stats",
    response_model=SearchHistoryStatsResponse,
    summary="获取搜索统计",
    description="获取用户的搜索行为统计"
)
async def get_search_stats(
    current_user: User = Depends(get_current_active_user)
):
    """获取用户搜索统计"""
    try:
        stats = await search_history_service.get_user_statistics(current_user.id)
        return SearchHistoryStatsResponse(**stats)

    except Exception as e:
        logger.error(f"获取搜索统计失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取统计失败")


@router.delete(
    "/chat/search-history/{history_id}",
    summary="删除搜索历史",
    description="删除指定的搜索历史记录"
)
async def delete_search_history(
    history_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """删除搜索历史记录"""
    try:
        success = await search_history_service.delete_history(
            history_id=history_id,
            user_id=current_user.id
        )

        if not success:
            raise HTTPException(status_code=404, detail="历史记录不存在或无权删除")

        return {"message": "删除成功", "history_id": history_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除搜索历史失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="删除失败")
