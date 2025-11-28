# 文件上传模块破损导入修复

**日期**: 2025-11-28
**问题类型**: Import Error
**严重级别**: 中 (潜在启动失败风险)
**状态**: ✅ 已修复

---

## 问题描述

### 发现过程
在分析项目文件上传功能时,发现 `src/infrastructure/storage/__init__.py` 中存在破损的导入语句:

```python
# ❌ 这些文件不存在,导致导入失败
from src.infrastructure.storage.local_storage import LocalStorageService
from src.infrastructure.storage.aliyun_oss import AliyunOSSService
```

### 影响范围
- **当前影响**: 如果其他模块尝试导入 `src.infrastructure.storage`,会导致 `ModuleNotFoundError`
- **潜在风险**: 系统启动失败
- **实际情况**: 经验证,目前没有生产代码导入这些类,仅文档引用

### 根本原因
文件上传功能处于**未完成状态**:
- ✅ 领域模型已完成 (`src/core/domain/entities/file_upload.py`)
- ✅ 抽象接口已定义 (`src/infrastructure/storage/base_storage.py`)
- ❌ 具体实现缺失 (`local_storage.py`, `aliyun_oss.py` 等文件不存在)
- ❌ API端点未实现

---

## 修复方案

### 实施步骤

**Step 1: 注释破损导入**
```python
# TODO: 实现具体存储提供商
# from src.infrastructure.storage.local_storage import LocalStorageService
# from src.infrastructure.storage.aliyun_oss import AliyunOSSService
```

**Step 2: 更新导出列表**
```python
__all__ = [
    "StorageProvider",  # ✅ 只导出已存在的抽象基类
    # "LocalStorageService",  # 待实现
    # "AliyunOSSService"      # 待实现
]
```

**Step 3: 添加说明文档**
```python
"""
注意: 具体存储实现尚未完成，暂时只导出抽象基类
"""
```

### 修复效果
- ✅ 消除导入错误风险
- ✅ 保留 TODO 标记,明确待实现项
- ✅ 系统可以正常启动和运行
- ✅ 不影响现有功能 (nl-search, chat, crawl, archive)

---

## 验证结果

### 引用扫描
```bash
# 搜索所有对 LocalStorageService 和 AliyunOSSService 的引用
$ grep -r "LocalStorageService|AliyunOSSService" --include="*.py"
```

**结果**:
- ✅ 无生产代码引用
- ℹ️ 仅设计文档 `docs/FILE_UPLOAD_SYSTEM_DESIGN.md` 中提及

### 模块导入测试
```python
# 现在可以安全导入此模块
from src.infrastructure.storage import StorageProvider  # ✅ 成功
```

---

## 后续工作 (可选)

如需实现完整的文件上传功能,需要按以下顺序进行:

### Phase 1: 本地存储实现 (最小可用)
```
1. 创建 src/infrastructure/storage/local_storage.py
2. 实现 LocalStorageService 类继承 StorageProvider
3. 配置本地存储路径 (.env: LOCAL_STORAGE_PATH)
4. 单元测试
```

### Phase 2: API端点实现
```
1. 创建 src/api/v1/endpoints/upload.py
2. POST   /api/v1/upload - 文件上传
3. GET    /api/v1/files/{file_id} - 文件下载
4. DELETE /api/v1/files/{file_id} - 文件删除
5. GET    /api/v1/files - 文件列表
6. 添加路由到 src/api/v1/router.py
```

### Phase 3: 云存储支持 (可选)
```
1. 实现 AliyunOSSService (阿里云)
2. 实现 TencentCOSService (腾讯云)
3. 配置 API 密钥和区域设置
```

---

## 相关文件

**已修改**:
- `src/infrastructure/storage/__init__.py` - 注释破损导入

**相关文档**:
- `docs/FILE_UPLOAD_SYSTEM_DESIGN.md` - 文件上传系统设计文档

**相关代码** (未修改):
- `src/core/domain/entities/file_upload.py` - 领域模型 (完整)
- `src/infrastructure/storage/base_storage.py` - 抽象接口 (完整)

---

## 总结

**问题**: 文件上传模块存在破损导入,引用不存在的实现类
**原因**: 功能未完成,只有设计和接口,缺少具体实现
**修复**: 注释导入,添加 TODO 标记,防止启动失败
**影响**: 无 (当前没有代码使用文件上传功能)
**建议**: 如需此功能,按阶段实现;否则保持当前状态即可

**修复人**: Claude Code
**Git Commit**: 待提交
