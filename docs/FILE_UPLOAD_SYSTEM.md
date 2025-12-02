# 文件上传系统文档

## 概述

关山智能系统的文件上传功能支持 PDF 和 DOCX 文档的上传、内容提取和标签管理。系统采用"先提取后存储"的优化策略，确保只有有效文档被持久化存储。

## 核心特性

### 1. 智能内容提取 (Extract-Before-Store)

**优化策略**: 在将文件写入磁盘前，先在内存中提取文档内容并验证有效性。

**优势**:
- ✅ 避免存储无效/损坏的文件，节省磁盘空间
- ✅ 提前发现问题文件，快速返回错误反馈
- ✅ 减少不必要的磁盘 I/O 操作
- ✅ 确保存储的文档都是可解析的

**工作流程**:
```
1. 接收文件上传 → 读取到内存 (BytesIO)
2. 提取文档内容 (PDF/DOCX)
   ├─ 成功 → 继续存储
   └─ 失败 → 返回 HTTP 400 错误
3. 计算文件哈希 (SHA256)
4. 存储到本地文件系统
5. 保存元数据到 MongoDB
```

### 2. 文档内容提取

**支持格式**:
- **PDF**: 使用 PyMuPDF (fitz) 提取
- **DOCX**: 使用 python-docx 提取

**提取内容**:
- 全文内容
- 页数/段落数
- 元数据 (作者、标题等)
- 图片检测
- 表格内容 (DOCX)
- 字数统计

**性能优化**:
- 内存操作，无临时文件
- 异步处理，使用线程池避免阻塞
- 详细的错误处理和日志

### 3. 文件标签管理

**功能**: 用户可以在上传文件时定义标签，便于后续组织和检索。

**标签规则**:
- 格式: 逗号分隔字符串 (例如: `重要,合同,2024`)
- 最多 10 个标签
- 每个标签最长 20 字符
- 自动去重和去除空白
- 自动过滤空标签

**使用示例**:
```bash
curl -X POST "http://localhost:8000/api/v1/upload?tags=重要,合同,2024" \
  -F "file=@document.pdf"
```

## API 端点

### 1. 上传文件

**端点**: `POST /api/v1/upload`

**请求参数**:
- `file` (required): 上传的文件 (multipart/form-data)
- `user_id` (optional): 用户ID
- `category` (optional): 文件分类
- `tags` (optional): 文件标签 (逗号分隔)

**支持格式**: PDF (`.pdf`), DOCX (`.docx`)

**最大文件大小**: 100MB (可在 `.env` 中配置)

**请求示例**:
```bash
# 基本上传
curl -X POST "http://localhost:8000/api/v1/upload" \
  -F "file=@report.pdf"

# 带标签和用户ID
curl -X POST "http://localhost:8000/api/v1/upload?user_id=user_001&tags=季度报告,2024,重要" \
  -F "file=@Q1_report.pdf"

# 带分类
curl -X POST "http://localhost:8000/api/v1/upload?category=contract&tags=法律,合同" \
  -F "file=@contract.docx"
```

**成功响应** (HTTP 200):
```json
{
  "success": true,
  "message": "文件上传成功",
  "file_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "filename": "report.pdf",
  "file_size": 1048576,
  "file_size_formatted": "1.00 MB",
  "content_hash": "sha256:abc123...",
  "access_url": "http://localhost:8000/api/v1/files/a1b2c3d4...",
  "tags": ["季度报告", "2024", "重要"],
  "extracted_content": {
    "total_pages": 10,
    "word_count": 5000,
    "has_images": true
  },
  "created_at": "2024-12-02T10:00:00Z"
}
```

**错误响应**:

- **HTTP 400**: 文件格式不支持
```json
{
  "detail": "不支持的文件格式。仅支持 PDF 和 DOCX"
}
```

- **HTTP 400**: 文件内容提取失败
```json
{
  "detail": "文件内容提取失败，无法上传: PDF 格式损坏"
}
```

- **HTTP 413**: 文件过大
```json
{
  "detail": "文件大小超过限制 (最大 100MB)"
}
```

### 2. 下载文件

**端点**: `GET /api/v1/files/{file_id}`

**路径参数**:
- `file_id` (required): 文件ID

**请求示例**:
```bash
curl -O "http://localhost:8000/api/v1/files/a1b2c3d4-e5f6-7890-abcd-ef1234567890"
```

**成功响应**: 返回文件二进制流，自动设置正确的 Content-Type

**错误响应**:
- **HTTP 404**: 文件不存在

### 3. 删除文件

**端点**: `DELETE /api/v1/files/{file_id}`

**路径参数**:
- `file_id` (required): 文件ID

**请求示例**:
```bash
curl -X DELETE "http://localhost:8000/api/v1/files/a1b2c3d4-e5f6-7890-abcd-ef1234567890"
```

**成功响应** (HTTP 200):
```json
{
  "success": true,
  "message": "文件删除成功",
  "file_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

### 4. 获取文件列表

**端点**: `GET /api/v1/files`

**查询参数**:
- `user_id` (optional): 按用户ID筛选
- `category` (optional): 按分类筛选
- `limit` (optional): 返回数量 (默认 50, 最大 100)
- `offset` (optional): 偏移量 (默认 0)

**请求示例**:
```bash
# 获取所有文件
curl "http://localhost:8000/api/v1/files"

# 筛选特定用户的文件
curl "http://localhost:8000/api/v1/files?user_id=user_001&limit=20"

# 分页
curl "http://localhost:8000/api/v1/files?limit=50&offset=100"
```

**成功响应** (HTTP 200):
```json
{
  "success": true,
  "total": 150,
  "limit": 50,
  "offset": 0,
  "files": [
    {
      "file_id": "a1b2c3d4...",
      "original_filename": "report.pdf",
      "display_name": "Q1 Report",
      "file_size": 1048576,
      "file_size_formatted": "1.00 MB",
      "mime_type": "application/pdf",
      "category": "document",
      "status": "completed",
      "upload_progress": 100,
      "storage_url": "http://localhost:8000/api/v1/files/a1b2c3d4...",
      "uploaded_by": "user_001",
      "tags": ["季度报告", "2024"],
      "created_at": "2024-12-02T10:00:00Z"
    }
  ]
}
```

## 架构设计

### 系统组件

```
┌─────────────────────────────────────────────────────────┐
│                     API Layer                            │
│  (src/api/v1/endpoints/upload.py)                       │
│  - 文件上传/下载/删除/列表 API                           │
│  - 参数验证和错误处理                                    │
└────────────────┬────────────────────────────────────────┘
                 │
    ┌────────────┴────────────┬────────────────────────┐
    │                         │                        │
┌───▼──────────────┐  ┌──────▼────────────┐  ┌───────▼───────┐
│ DocumentExtractor│  │ LocalStorageService│  │   MongoDB     │
│  Service         │  │                    │  │  Repository   │
│                  │  │                    │  │               │
│ - PDF extraction │  │ - File storage     │  │ - Metadata    │
│ - DOCX extraction│  │ - File retrieval   │  │   persistence │
│ - In-memory ops  │  │ - Path management  │  │ - Queries     │
└──────────────────┘  └────────────────────┘  └───────────────┘
```

### 领域实体

**FileUpload Entity** (`src/core/domain/entities/file_upload.py`):
```python
@dataclass
class FileUpload:
    file_id: str
    original_filename: str
    stored_filename: str
    file_size: int
    mime_type: str
    storage_path: str
    storage_url: str
    content_hash: str
    tags: List[str]  # 标签列表
    metadata: Dict[str, Any]  # 包含提取的文档内容
    status: UploadStatus
    uploaded_by: str
    created_at: datetime
```

### 服务层

**DocumentExtractor** (`src/services/document_extractor.py`):
- 负责文档内容提取
- 支持 PDF 和 DOCX 格式
- 异步处理，避免阻塞
- 返回结构化的提取结果

**LocalStorageService** (`src/services/local_storage_service.py`):
- 本地文件系统存储
- 文件路径管理
- 访问 URL 生成
- 文件删除清理

### 数据持久化

**MongoFileUploadRepository** (`src/infrastructure/database/file_upload_repository.py`):
- 实现 `IBasicRepository` 接口
- MongoDB 文档存储
- 支持按用户、状态筛选
- 分页查询

## 配置

### 环境变量 (`.env`)

```bash
# 本地存储配置
LOCAL_STORAGE_ENABLED=true
LOCAL_STORAGE_BASE_PATH=./data/uploads
LOCAL_STORAGE_BASE_URL=http://localhost:8000/api/v1/files
LOCAL_STORAGE_MAX_FILE_SIZE=104857600  # 100MB

# 允许的文件类型
LOCAL_STORAGE_ALLOWED_EXTENSIONS=.pdf,.docx

# MongoDB 配置
MONGODB_URL=mongodb://user:pass@192.168.0.3:27017/?authSource=admin
MONGODB_DB_NAME=guanshan
```

### 依赖安装

```bash
# 安装文档提取库
pip install PyMuPDF python-docx

# 或从 requirements.txt
pip install -r requirements.txt
```

## 使用示例

### Python 客户端示例

```python
import requests

# 1. 上传文件with标签
files = {'file': open('report.pdf', 'rb')}
params = {
    'user_id': 'user_001',
    'tags': '重要,季度报告,2024Q1'
}

response = requests.post(
    'http://localhost:8000/api/v1/upload',
    files=files,
    params=params
)

result = response.json()
file_id = result['file_id']
print(f"文件上传成功, ID: {file_id}")
print(f"标签: {result['tags']}")
print(f"提取字数: {result['extracted_content']['word_count']}")

# 2. 下载文件
download_response = requests.get(
    f'http://localhost:8000/api/v1/files/{file_id}'
)

with open('downloaded_report.pdf', 'wb') as f:
    f.write(download_response.content)

# 3. 获取文件列表
list_response = requests.get(
    'http://localhost:8000/api/v1/files',
    params={'user_id': 'user_001', 'limit': 10}
)

files = list_response.json()['files']
for file in files:
    print(f"{file['original_filename']} - {file['tags']}")
```

### JavaScript 客户端示例

```javascript
// 上传文件with标签
async function uploadFile(file, tags) {
  const formData = new FormData();
  formData.append('file', file);

  const params = new URLSearchParams({
    user_id: 'user_001',
    tags: tags.join(',')  // ['重要', '合同'] → '重要,合同'
  });

  const response = await fetch(
    `http://localhost:8000/api/v1/upload?${params}`,
    {
      method: 'POST',
      body: formData
    }
  );

  const result = await response.json();
  console.log('上传成功:', result.file_id);
  console.log('标签:', result.tags);
  return result;
}

// 使用示例
const fileInput = document.getElementById('fileInput');
const file = fileInput.files[0];
const tags = ['重要', '合同', '2024'];

uploadFile(file, tags);
```

## 测试

### 单元测试

```bash
# 运行文件上传测试
pytest tests/test_file_upload.py -v

# 运行文档提取测试
pytest tests/test_document_extractor.py -v
```

### API 测试

使用 Postman 或 curl 测试 API 端点:

```bash
# 测试上传 (带标签)
curl -X POST "http://localhost:8000/api/v1/upload?tags=测试,demo" \
  -F "file=@test.pdf" \
  -v

# 测试列表
curl "http://localhost:8000/api/v1/files?limit=5" | jq .

# 测试删除
curl -X DELETE "http://localhost:8000/api/v1/files/{file_id}" -v
```

## 故障排除

### 常见问题

**1. MongoDB 连接失败**
```
错误: pymongo.errors.ServerSelectionTimeoutError: 192.168.0.3:27017: No route to host
解决: 检查 MongoDB 服务器网络连接和 NO_PROXY 配置
```

**2. 文件提取失败**
```
错误: DocumentExtractionError: PDF 格式损坏
解决: 确认文件完整性，尝试用其他工具打开验证
```

**3. 文件大小超限**
```
错误: 413 Payload Too Large
解决: 调整 .env 中 LOCAL_STORAGE_MAX_FILE_SIZE 配置
```

**4. 标签未正确解析**
```
问题: 上传时提供了标签但响应中tags为空
检查: 确认tags参数格式为逗号分隔字符串，不是JSON数组
正确: tags=重要,合同,2024
错误: tags=["重要","合同","2024"]
```

### 调试日志

查看服务器日志获取详细信息:

```bash
# 实时查看日志
tail -f server.log

# 筛选上传相关日志
grep "upload\|extract\|标签" server.log

# 筛选错误
grep "ERROR\|error\|❌" server.log
```

## 性能优化

### 当前优化措施

1. **内存提取**: 避免临时文件，直接在内存中处理
2. **异步处理**: 使用 ThreadPoolExecutor 避免阻塞
3. **提前验证**: 先提取后存储，减少无效I/O
4. **哈希计算**: SHA256 内容哈希用于去重

### 未来优化计划

- [ ] 实现文件去重 (基于 content_hash)
- [ ] 添加文件压缩 (GZIP)
- [ ] 支持分片上传 (大文件)
- [ ] 添加 CDN 集成
- [ ] 实现缩略图生成 (PDF首页)
- [ ] 添加全文搜索索引
- [ ] 基于标签的高级检索
- [ ] 标签统计和推荐

## 安全考虑

### 已实现的安全措施

1. **文件类型验证**: 仅允许 PDF 和 DOCX
2. **文件大小限制**: 防止磁盘空间耗尽
3. **内容哈希**: SHA256 完整性校验
4. **路径清理**: 防止路径遍历攻击
5. **错误处理**: 避免敏感信息泄露

### 建议增强

- [ ] 病毒扫描集成 (ClamAV)
- [ ] 访问权限控制 (ACL)
- [ ] 文件加密存储
- [ ] 上传频率限制 (Rate Limiting)
- [ ] 文件内容审查 (敏感信息检测)

## 版本历史

### v1.1.0 (2024-12-02)
- ✨ 新增: 文件标签功能支持
- 🔧 优化: "先提取后存储"工作流
- 📝 文档: 完善 API 文档和使用示例

### v1.0.0 (2024-11-XX)
- 🎉 初始版本
- ✨ 支持 PDF 和 DOCX 上传
- ✨ 文档内容自动提取
- ✨ MongoDB 元数据存储

## 相关文档

- [API 总览](./API_OVERVIEW.md)
- [架构设计](./ARCHITECTURE.md)
- [部署指南](./DEPLOYMENT.md)
- [贡献指南](./CONTRIBUTING.md)

## 许可证

Copyright © 2024 关山智能系统. All rights reserved.
