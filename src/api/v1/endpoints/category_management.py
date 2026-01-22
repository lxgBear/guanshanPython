"""
分类体系管理 API
v4.9.0: 支持分类选项的增删改查

提供档案分类体系的管理接口：
- 大类 (primary): 如 "经济", "政治", "军事" 等
- 中类 (secondary): 如 "金融政策", "贸易协定" 等
- 小类/地域 (tertiary): 如 "北美", "欧洲", "东亚" 等
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Any
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.infrastructure.database.connection import get_mongodb_database
from src.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/categories", tags=["📂 分类体系管理"])

# ============================================================================
# 数据模型
# ============================================================================


class CategorySystem(BaseModel):
    """单个大类的完整结构"""

    primary: str = Field(description="大类名称")
    secondary_options: list[str] = Field(default_factory=list, description="中类选项列表")
    tertiary_options: list[str] = Field(default_factory=list, description="小类/地域选项列表")


class CreateCategoryRequest(BaseModel):
    """创建大类请求"""

    primary: str = Field(description="大类名称", min_length=1, max_length=50)
    secondary_options: list[str] = Field(default_factory=list, description="中类选项列表")
    tertiary_options: list[str] = Field(default_factory=list, description="小类/地域选项列表")


class UpdateCategoryRequest(BaseModel):
    """更新分类请求"""

    secondary_options: list[str] | None = Field(default=None, description="中类选项列表（替换）")
    tertiary_options: list[str] | None = Field(default=None, description="小类/地域选项列表（替换）")


class AddOptionRequest(BaseModel):
    """添加选项请求"""

    option: str = Field(description="选项名称", min_length=1, max_length=100)


class CategoryResponse(BaseModel):
    """分类响应"""

    success: bool
    message: str
    data: Any = None


# ============================================================================
# 数据库操作辅助函数
# ============================================================================

COLLECTION_NAME = "category_system"

# 默认分类体系 (当数据库为空时使用)
DEFAULT_CATEGORY_SYSTEM: dict[str, CategorySystem] = {
    "经济": CategorySystem(
        primary="经济",
        secondary_options=["金融政策", "贸易协定", "能源市场", "产业发展", "经济制裁"],
        tertiary_options=["北美", "欧洲", "东亚", "东南亚", "中东", "非洲", "南美", "大洋洲"],
    ),
    "政治": CategorySystem(
        primary="政治",
        secondary_options=["外交关系", "国内政治", "选举", "政策变化", "政府声明"],
        tertiary_options=["北美", "欧洲", "东亚", "东南亚", "中东", "非洲", "南美", "大洋洲"],
    ),
    "军事": CategorySystem(
        primary="军事",
        secondary_options=["军事演习", "武器装备", "军事冲突", "防务合作", "军事部署"],
        tertiary_options=["北美", "欧洲", "东亚", "东南亚", "中东", "非洲", "南美", "大洋洲"],
    ),
    "科技": CategorySystem(
        primary="科技",
        secondary_options=["人工智能", "半导体", "航天", "网络安全", "生物技术"],
        tertiary_options=["北美", "欧洲", "东亚", "东南亚", "中东", "非洲", "南美", "大洋洲"],
    ),
    "社会": CategorySystem(
        primary="社会",
        secondary_options=["公共卫生", "教育", "环境", "人权", "移民"],
        tertiary_options=["北美", "欧洲", "东亚", "东南亚", "中东", "非洲", "南美", "大洋洲"],
    ),
}


async def get_collection(db: AsyncIOMotorDatabase):
    """获取分类集合"""
    return db[COLLECTION_NAME]


async def ensure_default_categories(db: AsyncIOMotorDatabase):
    """确保默认分类存在"""
    collection = await get_collection(db)
    count = await collection.count_documents({})
    if count == 0:
        # 插入默认分类
        for category in DEFAULT_CATEGORY_SYSTEM.values():
            await collection.insert_one(category.model_dump())
        logger.info(f"已初始化 {len(DEFAULT_CATEGORY_SYSTEM)} 个默认分类")


# ============================================================================
# API 端点
# ============================================================================


@router.get("/", summary="获取完整分类体系")
async def get_category_system(
    db: AsyncIOMotorDatabase = Depends(get_mongodb_database),
) -> dict[str, CategorySystem]:
    """
    获取完整的三级分类体系

    Returns:
        dict: 以大类名称为键的分类体系字典
    """
    try:
        await ensure_default_categories(db)
        collection = await get_collection(db)

        cursor = collection.find({})
        categories = await cursor.to_list(length=100)

        result = {}
        for cat in categories:
            primary = cat.get("primary", "")
            if primary:
                result[primary] = CategorySystem(
                    primary=primary,
                    secondary_options=cat.get("secondary_options", []),
                    tertiary_options=cat.get("tertiary_options", []),
                )

        return result
    except Exception as e:
        logger.error(f"获取分类体系失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取分类体系失败: {e!s}")


@router.get("/{primary}", summary="获取单个大类")
async def get_category(
    primary: str,
    db: AsyncIOMotorDatabase = Depends(get_mongodb_database),
) -> CategorySystem:
    """
    获取指定大类的详细信息

    Args:
        primary: 大类名称

    Returns:
        CategorySystem: 分类详情
    """
    try:
        collection = await get_collection(db)
        doc = await collection.find_one({"primary": primary})

        if not doc:
            raise HTTPException(status_code=404, detail=f"大类 '{primary}' 不存在")

        return CategorySystem(
            primary=doc.get("primary", ""),
            secondary_options=doc.get("secondary_options", []),
            tertiary_options=doc.get("tertiary_options", []),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取大类失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取大类失败: {e!s}")


@router.post("/", summary="创建新的大类")
async def create_primary_category(
    request: CreateCategoryRequest,
    db: AsyncIOMotorDatabase = Depends(get_mongodb_database),
) -> CategoryResponse:
    """
    创建新的一级分类（大类）

    Args:
        request: 创建请求

    Returns:
        CategoryResponse: 操作结果
    """
    try:
        collection = await get_collection(db)

        # 检查是否已存在
        existing = await collection.find_one({"primary": request.primary})
        if existing:
            raise HTTPException(status_code=400, detail=f"大类 '{request.primary}' 已存在")

        # 创建新分类
        category = CategorySystem(
            primary=request.primary,
            secondary_options=request.secondary_options,
            tertiary_options=request.tertiary_options,
        )
        await collection.insert_one(category.model_dump())

        logger.info(f"创建大类: {request.primary}")
        return CategoryResponse(
            success=True, message=f"大类 '{request.primary}' 创建成功", data=category.model_dump()
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建大类失败: {e}")
        raise HTTPException(status_code=500, detail=f"创建大类失败: {e!s}")


@router.put("/{primary}", summary="更新分类选项")
async def update_category(
    primary: str,
    request: UpdateCategoryRequest,
    db: AsyncIOMotorDatabase = Depends(get_mongodb_database),
) -> CategoryResponse:
    """
    更新指定大类的中类和小类选项

    Args:
        primary: 大类名称
        request: 更新请求

    Returns:
        CategoryResponse: 操作结果
    """
    try:
        collection = await get_collection(db)

        # 检查是否存在
        existing = await collection.find_one({"primary": primary})
        if not existing:
            raise HTTPException(status_code=404, detail=f"大类 '{primary}' 不存在")

        # 构建更新
        update_fields = {}
        if request.secondary_options is not None:
            update_fields["secondary_options"] = request.secondary_options
        if request.tertiary_options is not None:
            update_fields["tertiary_options"] = request.tertiary_options

        if not update_fields:
            return CategoryResponse(success=True, message="无需更新")

        await collection.update_one({"primary": primary}, {"$set": update_fields})

        logger.info(f"更新大类: {primary}")
        return CategoryResponse(success=True, message=f"大类 '{primary}' 更新成功")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新大类失败: {e}")
        raise HTTPException(status_code=500, detail=f"更新大类失败: {e!s}")


@router.delete("/{primary}", summary="删除大类")
async def delete_primary_category(
    primary: str,
    db: AsyncIOMotorDatabase = Depends(get_mongodb_database),
) -> CategoryResponse:
    """
    删除指定的一级分类

    Args:
        primary: 大类名称

    Returns:
        CategoryResponse: 操作结果
    """
    try:
        collection = await get_collection(db)

        # 检查是否存在
        existing = await collection.find_one({"primary": primary})
        if not existing:
            raise HTTPException(status_code=404, detail=f"大类 '{primary}' 不存在")

        await collection.delete_one({"primary": primary})

        logger.info(f"删除大类: {primary}")
        return CategoryResponse(success=True, message=f"大类 '{primary}' 删除成功")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除大类失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除大类失败: {e!s}")


@router.post("/{primary}/secondary", summary="添加中类选项")
async def add_secondary_option(
    primary: str,
    request: AddOptionRequest,
    db: AsyncIOMotorDatabase = Depends(get_mongodb_database),
) -> CategoryResponse:
    """
    为指定大类添加中类选项

    Args:
        primary: 大类名称
        request: 添加选项请求

    Returns:
        CategoryResponse: 操作结果
    """
    try:
        collection = await get_collection(db)

        # 检查是否存在
        existing = await collection.find_one({"primary": primary})
        if not existing:
            raise HTTPException(status_code=404, detail=f"大类 '{primary}' 不存在")

        # 检查选项是否已存在
        if request.option in existing.get("secondary_options", []):
            raise HTTPException(status_code=400, detail=f"中类选项 '{request.option}' 已存在")

        await collection.update_one(
            {"primary": primary}, {"$addToSet": {"secondary_options": request.option}}
        )

        logger.info(f"为大类 {primary} 添加中类选项: {request.option}")
        return CategoryResponse(success=True, message=f"中类选项 '{request.option}' 添加成功")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"添加中类选项失败: {e}")
        raise HTTPException(status_code=500, detail=f"添加中类选项失败: {e!s}")


@router.delete("/{primary}/secondary/{option}", summary="删除中类选项")
async def delete_secondary_option(
    primary: str,
    option: str,
    db: AsyncIOMotorDatabase = Depends(get_mongodb_database),
) -> CategoryResponse:
    """
    删除指定大类的中类选项

    Args:
        primary: 大类名称
        option: 选项名称

    Returns:
        CategoryResponse: 操作结果
    """
    try:
        collection = await get_collection(db)

        # 检查是否存在
        existing = await collection.find_one({"primary": primary})
        if not existing:
            raise HTTPException(status_code=404, detail=f"大类 '{primary}' 不存在")

        await collection.update_one({"primary": primary}, {"$pull": {"secondary_options": option}})

        logger.info(f"从大类 {primary} 删除中类选项: {option}")
        return CategoryResponse(success=True, message=f"中类选项 '{option}' 删除成功")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除中类选项失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除中类选项失败: {e!s}")


@router.post("/{primary}/tertiary", summary="添加小类选项")
async def add_tertiary_option(
    primary: str,
    request: AddOptionRequest,
    db: AsyncIOMotorDatabase = Depends(get_mongodb_database),
) -> CategoryResponse:
    """
    为指定大类添加小类/地域选项

    Args:
        primary: 大类名称
        request: 添加选项请求

    Returns:
        CategoryResponse: 操作结果
    """
    try:
        collection = await get_collection(db)

        # 检查是否存在
        existing = await collection.find_one({"primary": primary})
        if not existing:
            raise HTTPException(status_code=404, detail=f"大类 '{primary}' 不存在")

        # 检查选项是否已存在
        if request.option in existing.get("tertiary_options", []):
            raise HTTPException(status_code=400, detail=f"小类选项 '{request.option}' 已存在")

        await collection.update_one(
            {"primary": primary}, {"$addToSet": {"tertiary_options": request.option}}
        )

        logger.info(f"为大类 {primary} 添加小类选项: {request.option}")
        return CategoryResponse(success=True, message=f"小类选项 '{request.option}' 添加成功")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"添加小类选项失败: {e}")
        raise HTTPException(status_code=500, detail=f"添加小类选项失败: {e!s}")


@router.delete("/{primary}/tertiary/{option}", summary="删除小类选项")
async def delete_tertiary_option(
    primary: str,
    option: str,
    db: AsyncIOMotorDatabase = Depends(get_mongodb_database),
) -> CategoryResponse:
    """
    删除指定大类的小类/地域选项

    Args:
        primary: 大类名称
        option: 选项名称

    Returns:
        CategoryResponse: 操作结果
    """
    try:
        collection = await get_collection(db)

        # 检查是否存在
        existing = await collection.find_one({"primary": primary})
        if not existing:
            raise HTTPException(status_code=404, detail=f"大类 '{primary}' 不存在")

        await collection.update_one({"primary": primary}, {"$pull": {"tertiary_options": option}})

        logger.info(f"从大类 {primary} 删除小类选项: {option}")
        return CategoryResponse(success=True, message=f"小类选项 '{option}' 删除成功")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除小类选项失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除小类选项失败: {e!s}")


@router.post("/reset", summary="重置为默认分类")
async def reset_to_default(
    db: AsyncIOMotorDatabase = Depends(get_mongodb_database),
) -> CategoryResponse:
    """
    重置分类体系为默认值

    Returns:
        CategoryResponse: 操作结果
    """
    try:
        collection = await get_collection(db)

        # 清空现有分类
        await collection.delete_many({})

        # 插入默认分类
        for category in DEFAULT_CATEGORY_SYSTEM.values():
            await collection.insert_one(category.model_dump())

        logger.info(f"已重置分类体系为默认值，共 {len(DEFAULT_CATEGORY_SYSTEM)} 个大类")
        return CategoryResponse(
            success=True,
            message=f"已重置为默认分类体系，共 {len(DEFAULT_CATEGORY_SYSTEM)} 个大类",
        )
    except Exception as e:
        logger.error(f"重置分类体系失败: {e}")
        raise HTTPException(status_code=500, detail=f"重置分类体系失败: {e!s}")
