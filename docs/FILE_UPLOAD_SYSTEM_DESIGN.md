# 文件上传系统设计文档

## 📋 概述

完整的企业级文件上传系统，支持单文件/多文件上传、云存储集成、文件类型和大小限制。

**版本**: v1.0.0
**创建日期**: 2025-10-24
**状态**: 设计中

---

## 🎯 功能需求

### 核心功能
- ✅ 单文件上传
- ✅ 多文件批量上传
- ✅ 文件类型限制（白名单机制）
- ✅ 文件大小限制（可配置）
- ✅ 云存储集成（阿里云 OSS、腾讯云 COS、AWS S3）

### 高级功能
- ✅ 上传进度追踪
- ✅ 断点续传支持
- ✅ 病毒扫描集成
- ✅ 图片自动压缩
- ✅ CDN 加速支持
- ✅ 访问控制（公开/私有）
- ✅ 临时签名 URL
- ✅ 文件过期管理

---

## 🏗️ 系统架构

### 领域层 (Domain Layer)

#### FileUpload 实体
```python
@dataclass
class FileUpload:
    # 基础信息
    file_id: str
    original_filename: str
    stored_filename: str
    display_name: Optional[str]

    # 文件属性
    file_size: int
    mime_type: str
    file_extension: str
    category: FileCategory

    # 存储信息
    storage_provider: StorageProvider
    storage_bucket: Optional[str]
    storage_path: str
    storage_url: Optional[str]
    cdn_url: Optional[str]

    # 状态管理
    status: UploadStatus  # PENDING, UPLOADING, PROCESSING, COMPLETED, FAILED, DELETED
    upload_progress: int

    # 安全检查
    virus_scan_status: Optional[str]
    content_hash: Optional[str]

    # 关联信息
    uploaded_by: str
    related_entity_type: Optional[str]
    related_entity_id: Optional[str]

    # 访问控制
    is_public: bool
    access_token: Optional[str]
    expires_at: Optional[datetime]
```

#### 状态枚举

**UploadStatus**:
- `PENDING`: 待上传
- `UPLOADING`: 上传中
- `PROCESSING`: 处理中（病毒扫描、格式转换）
- `COMPLETED`: 完成
- `FAILED`: 失败
- `DELETED`: 已删除

**StorageProvider**:
- `LOCAL`: 本地存储
- `ALIYUN_OSS`: 阿里云 OSS
- `TENCENT_COS`: 腾讯云 COS
- `AWS_S3`: AWS S3
- `QINIU`: 七牛云

**FileCategory**:
- `DOCUMENT`: 文档（PDF, Word, Excel）
- `IMAGE`: 图片
- `VIDEO`: 视频
- `AUDIO`: 音频
- `ARCHIVE`: 压缩包
- `DATA`: 数据文件（CSV, JSON）
- `OTHER`: 其他

### 基础设施层 (Infrastructure Layer)

#### 存储服务接口
```python
class StorageProvider(ABC):
    async def upload_file(file_content, destination_path, content_type) -> (path, url)
    async def download_file(file_path) -> bytes
    async def delete_file(file_path) -> bool
    async def file_exists(file_path) -> bool
    async def get_file_url(file_path, expires_in) -> str
    async def get_file_size(file_path) -> int
```

#### 存储提供商实现

**LocalStorageService** (本地存储 - 开发测试用)
- 文件系统存储
- 本地路径管理
- 开发环境使用

**AliyunOSSService** (阿里云 OSS)
- OSS SDK 集成
- 分片上传支持
- CDN 加速
- 签名 URL 生成

**TencentCOSService** (腾讯云 COS)
- COS SDK 集成
- 多地域支持
- CDN 集成

**AWSS3Service** (AWS S3)
- S3 SDK 集成
- 跨区域复制
- CloudFront 集成

#### 数据仓储

**FileUploadRepository**
```python
class FileUploadRepository:
    async def create(file_upload) -> FileUpload
    async def get_by_id(file_id) -> Optional[FileUpload]
    async def update(file_upload) -> bool
    async def delete(file_id) -> bool
    async def list_by_user(user_id, page, page_size) -> (List[FileUpload], int)
    async def list_by_entity(entity_type, entity_id) -> List[FileUpload]
    async def list_by_status(status, page, page_size) -> (List[FileUpload], int)
    async def batch_delete(file_ids) -> int
```

### 应用层 (Application Layer)

#### FileUploadService
```python
class FileUploadService:
    # 文件上传
    async def upload_single_file(file, config, uploaded_by) -> FileUpload
    async def upload_multiple_files(files, config, uploaded_by) -> FileUploadBatch

    # 文件管理
    async def get_file(file_id) -> FileUpload
    async def delete_file(file_id, user_id) -> bool
    async def batch_delete_files(file_ids, user_id) -> int

    # 访问控制
    async def generate_access_url(file_id, expires_in) -> str
    async def verify_access_token(file_id, token) -> bool

    # 文件验证
    async def validate_file(file, config) -> (bool, Optional[str])
    async def scan_virus(file_path) -> (bool, Optional[str])
```

#### FileValidationService
```python
class FileValidationService:
    # 基础验证
    def validate_file_type(filename, allowed_types) -> bool
    def validate_file_size(size, max_size) -> bool
    def validate_mime_type(mime_type, allowed_mimes) -> bool

    # 内容验证
    async def validate_file_content(file_content, mime_type) -> bool
    async def scan_malware(file_path) -> (bool, Optional[str])

    # 图片处理
    async def compress_image(image_path, quality) -> str
    async def generate_thumbnail(image_path, size) -> str
```

### API 层 (API Layer)

#### 端点设计

**POST /api/v1/files/upload**
- 单文件上传
- 支持表单数据和 JSON
- 返回文件信息和访问 URL

**POST /api/v1/files/upload/batch**
- 多文件批量上传
- 支持进度追踪
- 返回批次信息

**GET /api/v1/files/{file_id}**
- 获取文件信息
- 权限验证

**GET /api/v1/files/{file_id}/download**
- 下载文件
- 支持断点续传
- 生成临时签名 URL

**DELETE /api/v1/files/{file_id}**
- 删除文件（软删除）
- 权限验证

**GET /api/v1/files**
- 列表查询
- 支持筛选（状态、类型、用户）
- 分页支持

**POST /api/v1/files/{file_id}/access-url**
- 生成临时访问 URL
- 可配置过期时间

---

## 📊 数据库设计

### file_uploads 集合

```javascript
{
  "_id": ObjectId,
  "file_id": "uuid",
  "original_filename": "document.pdf",
  "stored_filename": "20251024_abc123_document.pdf",
  "display_name": "项目文档.pdf",

  "file_size": 1024000,
  "mime_type": "application/pdf",
  "file_extension": ".pdf",
  "category": "document",

  "storage_provider": "aliyun_oss",
  "storage_bucket": "my-bucket",
  "storage_path": "uploads/2025/10/20251024_abc123_document.pdf",
  "storage_url": "https://my-bucket.oss-cn-hangzhou.aliyuncs.com/...",
  "cdn_url": "https://cdn.example.com/...",

  "status": "completed",
  "upload_progress": 100,

  "virus_scan_status": "clean",
  "content_hash": "sha256:abc123...",

  "metadata": {
    "width": 1920,
    "height": 1080,
    "duration": null
  },

  "uploaded_by": "user123",
  "related_entity_type": "search_task",
  "related_entity_id": "task456",

  "is_public": false,
  "access_token": "token_xyz",
  "expires_at": ISODate("2025-11-24T00:00:00Z"),

  "created_at": ISODate("2025-10-24T10:00:00Z"),
  "updated_at": ISODate("2025-10-24T10:05:00Z"),
  "deleted_at": null,

  "is_test_data": false
}
```

### 索引设计

```javascript
// 主键索引
db.file_uploads.createIndex({"file_id": 1}, {unique: true})

// 查询索引
db.file_uploads.createIndex({"uploaded_by": 1, "created_at": -1})
db.file_uploads.createIndex({"status": 1})
db.file_uploads.createIndex({"category": 1})

// 关联索引
db.file_uploads.createIndex({
  "related_entity_type": 1,
  "related_entity_id": 1
})

// 过期清理索引
db.file_uploads.createIndex({
  "expires_at": 1,
  "status": 1
}, {
  partialFilterExpression: {"expires_at": {$exists: true}}
})

// 软删除索引
db.file_uploads.createIndex({
  "deleted_at": 1
}, {
  partialFilterExpression: {"deleted_at": {$ne: null}}
})
```

---

## 🔐 安全设计

### 文件验证

**1. 类型验证**
- MIME type 白名单
- 文件扩展名验证
- Magic number 检查（文件头检测）

**2. 大小限制**
- 单文件最大 10MB（可配置）
- 批量上传总大小限制
- 用户配额管理

**3. 内容安全**
- 病毒扫描（ClamAV 集成）
- 恶意代码检测
- 图片 EXIF 数据清理

### 访问控制

**1. 公开文件**
- 直接 CDN URL 访问
- 无需认证

**2. 私有文件**
- 临时签名 URL（STS）
- 访问令牌验证
- IP 白名单（可选）

**3. 权限验证**
- 用户身份验证
- 文件所有权验证
- 角色权限检查

---

## ⚡ 性能优化

### 上传优化

**1. 分片上传**
- 大文件（>5MB）自动分片
- 并行上传分片
- 断点续传支持

**2. 直传优化**
- 客户端直传云存储
- 服务端签名授权
- 减少服务器带宽压力

**3. CDN 加速**
- 静态文件 CDN 分发
- 边缘节点缓存
- 就近访问优化

### 存储优化

**1. 智能分层**
- 热数据：标准存储
- 温数据：低频存储
- 冷数据：归档存储

**2. 压缩处理**
- 图片自动压缩（质量 85%）
- 生成缩略图
- WebP 格式转换

**3. 去重优化**
- 内容哈希计算
- 相同文件引用
- 节省存储空间

---

## 📈 监控和告警

### 关键指标

**上传指标**
- 上传成功率
- 平均上传时间
- 上传失败原因分布

**存储指标**
- 总存储容量使用率
- 文件数量统计
- 存储成本分析

**性能指标**
- API 响应时间
- CDN 命中率
- 下载速度

### 告警规则

- 上传成功率 < 95%
- 存储使用率 > 80%
- API 响应时间 > 3s
- 病毒文件检出

---

## 🚀 实施计划

### Phase 1: 基础功能 (已完成)
- [x] FileUpload 领域实体设计
- [x] StorageProvider 接口定义
- [x] 状态枚举和配置

### Phase 2: 存储服务 (进行中)
- [ ] LocalStorageService 实现
- [ ] AliyunOSSService 实现
- [ ] FileUploadRepository 实现

### Phase 3: 业务服务
- [ ] FileUploadService 实现
- [ ] FileValidationService 实现
- [ ] 病毒扫描集成

### Phase 4: API 开发
- [ ] 上传端点实现
- [ ] 下载端点实现
- [ ] 管理端点实现

### Phase 5: 测试和优化
- [ ] 单元测试
- [ ] 集成测试
- [ ] 性能测试
- [ ] 安全测试

---

## 🔧 配置示例

### 环境变量

```bash
# 存储配置
STORAGE_PROVIDER=aliyun_oss  # local, aliyun_oss, tencent_cos, aws_s3
STORAGE_BUCKET=my-bucket
STORAGE_REGION=cn-hangzhou

# 阿里云 OSS
ALIYUN_OSS_ACCESS_KEY=your-access-key
ALIYUN_OSS_SECRET_KEY=your-secret-key
ALIYUN_OSS_ENDPOINT=oss-cn-hangzhou.aliyuncs.com
ALIYUN_OSS_CDN_DOMAIN=cdn.example.com

# 文件限制
MAX_FILE_SIZE=10485760  # 10MB
MAX_FILES_PER_UPLOAD=10
ALLOWED_FILE_TYPES=pdf,doc,docx,xls,xlsx,csv,json,jpg,jpeg,png,gif

# 安全配置
ENABLE_VIRUS_SCAN=true
AUTO_COMPRESS_IMAGES=true
```

### 应用配置

```python
file_upload_config = FileUploadConfig(
    allowed_mime_types=[
        "application/pdf",
        "image/jpeg",
        "image/png"
    ],
    allowed_extensions=[
        ".pdf", ".jpg", ".jpeg", ".png"
    ],
    max_file_size=10 * 1024 * 1024,  # 10MB
    max_files_per_upload=10,
    enable_virus_scan=True,
    auto_compress_images=True,
    storage_provider=StorageProvider.ALIYUN_OSS,
    storage_bucket="my-bucket",
    storage_prefix="uploads"
)
```

---

## 📚 API 使用示例

### 单文件上传

```python
import requests

url = "http://localhost:8000/api/v1/files/upload"
files = {"file": open("document.pdf", "rb")}
data = {
    "uploaded_by": "user123",
    "related_entity_type": "search_task",
    "related_entity_id": "task456",
    "is_public": False
}

response = requests.post(url, files=files, data=data)
result = response.json()

print(f"File ID: {result['file_id']}")
print(f"Storage URL: {result['storage_url']}")
```

### 多文件上传

```python
import requests

url = "http://localhost:8000/api/v1/files/upload/batch"
files = [
    ("files", open("file1.pdf", "rb")),
    ("files", open("file2.jpg", "rb")),
    ("files", open("file3.docx", "rb"))
]
data = {"uploaded_by": "user123"}

response = requests.post(url, files=files, data=data)
result = response.json()

print(f"Batch ID: {result['batch_id']}")
print(f"Total Files: {result['total_files']}")
print(f"Completed: {result['completed_files']}")
```

### 获取临时访问 URL

```python
import requests

url = f"http://localhost:8000/api/v1/files/{file_id}/access-url"
data = {"expires_in": 3600}  # 1 hour

response = requests.post(url, json=data)
result = response.json()

print(f"Temporary URL: {result['url']}")
print(f"Expires At: {result['expires_at']}")
```

---

## 🎯 下一步操作

1. **完成存储服务实现**
   - LocalStorageService
   - AliyunOSSService
   - TencentCOSService

2. **实现数据仓储层**
   - FileUploadRepository
   - 索引创建脚本

3. **开发业务服务**
   - FileUploadService
   - FileValidationService

4. **创建 API 端点**
   - 上传 API
   - 下载 API
   - 管理 API

5. **测试和文档**
   - 单元测试
   - API 文档
   - 使用指南

---

**文档维护**: 请在功能更新时同步更新本文档
**问题反馈**: 发现问题请提交到项目 issue tracker

🤖 Generated with [Claude Code](https://claude.com/claude-code)
