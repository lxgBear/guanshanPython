# 档案创建完整流程文档

**文档版本**: v1.0.0
**创建日期**: 2025-11-22
**目的**: 详细说明从搜索到档案创建的完整用户操作流程和系统处理流程

---

## 流程概览

```
数据准备 → 用户选择 → (可选)批量编辑 → 创建档案 → 档案管理
```

---

## 完整流程图

```
┌─────────────────────────────────────────────────────────────────┐
│  Phase 1: 数据准备 (获取搜索结果)                                 │
└─────────────────────────────────────────────────────────────────┘
         │
         ├─ 方式A: NL Search (外部搜索)
         │     └─ POST /nl-search → 入库到 news_results
         │
         └─ 方式B: RAG 查询 (内部检索)
               └─ POST /nl-search/rag-query → 检索 news_results
         │
         ↓
   前端显示结果列表 (包含 mongo_id)

┌─────────────────────────────────────────────────────────────────┐
│  Phase 2: 用户查看和选择                                          │
└─────────────────────────────────────────────────────────────────┘
         │
         │ 用户浏览结果列表
         ↓
   用户点击查看详情
         │
         ├─ GET /nl-search/rag-content/{mongo_id}
         │     └─ 获取 markdown_content 和 url
         │
         ↓
   前端展示完整内容
         │
         ↓
   用户选择要归档的结果 (勾选checkbox)

┌─────────────────────────────────────────────────────────────────┐
│  Phase 3: 批量编辑 (可选步骤)                                     │
└─────────────────────────────────────────────────────────────────┘
         │
         │ 如果用户想修改标题、摘要等
         ↓
   POST /user-edits/batch
   {
     "updates": [
       {
         "record_id": "mongo_id",
         "fields": {
           "title": "编辑后的标题",
           "summary": "编辑后的摘要"
         }
       }
     ]
   }
         │
         ↓
   保存到 user_edited_results 集合
         │
         ↓
   前端更新显示 (标记为"已编辑")

┌─────────────────────────────────────────────────────────────────┐
│  Phase 4: 创建档案                                                │
└─────────────────────────────────────────────────────────────────┘
         │
         │ 用户点击"创建档案"按钮
         ↓
   前端弹出档案信息表单
         │
         ├─ 档案名称 (必填)
         ├─ 档案描述 (可选)
         ├─ 标签 (可选)
         └─ 选中的结果列表 (mongo_id数组)
         │
         ↓
   POST /nl-search/archives
   {
     "user_id": 1001,
     "archive_name": "西藏相关新闻汇总",
     "description": "2024年西藏相关重要新闻",
     "tags": ["西藏", "人权", "2024"],
     "search_log_id": "248728141926559744",  // 可选
     "items": [
       {
         "news_result_id": "mongo_id_1",
         "user_notes": "重要参考",
         "user_rating": 5
       },
       {
         "news_result_id": "mongo_id_2",
         "user_notes": "需要跟进",
         "user_rating": 4
       }
     ]
   }
         │
         ↓
   ┌──────────────────────────────────────┐
   │  系统处理 (mongo_archive_service)   │
   └──────────────────────────────────────┘
         │
         ├─ 1. 验证输入数据
         │     └─ 检查必填字段、数据格式
         │
         ├─ 2. 为每个item创建快照
         │     ├─ 从 news_results 读取原始数据
         │     │     └─ 提取: title, content, category, published_at, source, media_urls
         │     │
         │     ├─ 🆕 检查 user_edited_results 是否有编辑记录
         │     │     └─ 查询条件: news_result_id + user_id
         │     │
         │     └─ 🆕 合并编辑内容
         │           ├─ 优先级1: API请求中的 edited_title/edited_summary
         │           ├─ 优先级2: user_edited_results 中的编辑
         │           └─ 优先级3: news_results 原始数据
         │
         ├─ 3. 构建档案文档
         │     └─ 生成 MongoDB ObjectId
         │     └─ 组装所有字段和items
         │
         ├─ 4. 保存到 user_archives 集合
         │     └─ 插入完整档案文档
         │
         └─ 5. 返回档案信息
               └─ archive_id, archive_name, items_count, created_at

┌─────────────────────────────────────────────────────────────────┐
│  Phase 5: 档案管理                                                │
└─────────────────────────────────────────────────────────────────┘
         │
         ├─ 查询档案列表
         │     └─ GET /nl-search/archives?user_id=1001&limit=20
         │
         ├─ 查看档案详情
         │     └─ GET /nl-search/archives/{archive_id}
         │           └─ 返回完整档案信息 (包含所有items)
         │
         ├─ 更新档案信息
         │     └─ PUT /nl-search/archives/{archive_id}?user_id=1001
         │           └─ 更新 archive_name, description, tags
         │
         └─ 删除档案
               └─ DELETE /nl-search/archives/{archive_id}?user_id=1001
```

---

## 详细步骤说明

### Phase 1: 数据准备 (获取搜索结果)

#### 方式A: NL Search (外部搜索)

**用途**: 搜索外部网页，获取最新信息

**操作流程**:
1. 用户输入自然语言查询: "请介绍关于西藏的新闻"
2. 前端调用: `POST /nl-search`
3. 系统执行:
   - LLM分析查询意图
   - GPT-5 Search 搜索外部网页
   - 爬取网页内容
   - URL去重 (26个跟踪参数)
   - 内容Hash去重
4. 数据入库:
   - `nl_search_logs`: 存储搜索元数据
   - `news_results`: 存储搜索结果 (Dual-Write)
5. 返回结果列表 (包含 `mongo_id`)

**特点**:
- ✅ 获取**最新**外部信息
- ✅ 自动去重和内容提取
- ⏱️ 较慢 (需要爬取网页)

#### 方式B: RAG 查询 (内部检索)

**用途**: 从已入库数据中检索相关内容

**操作流程**:
1. 用户输入自然语言查询: "请介绍关于西藏的新闻"
2. 前端调用: `POST /nl-search/rag-query`
3. 系统转发到RAG系统 (192.168.0.5:8035)
4. RAG系统:
   - 向量相似度检索
   - 从 `news_results` 查找相关记录
   - 计算相关性评分
5. SSE流式返回结果 (包含 `mongo_id`)

**特点**:
- ✅ **快速** (内部检索)
- ✅ 基于语义相似度
- ❌ 仅限已入库数据

**返回数据结构**:
```json
{
  "type": "sources",
  "data": [
    {
      "id": "uuid",
      "score": 0.126,
      "title": "新闻标题",
      "source": "来源网站",
      "category": {"大类": "安全情报", "类别": "涉藏", "地域": "东亚"},
      "publish_time": "未知时间",
      "mongo_id": "249832360786370562",  // 🔑 关键字段
      "preview": "内容预览..."
    }
  ]
}
```

---

### Phase 2: 用户查看和选择

#### 步骤 2.1: 浏览结果列表

**前端显示**:
```
┌─────────────────────────────────────────┐
│  搜索结果 (20条)                         │
├─────────────────────────────────────────┤
│  □ 本会编辑留学生张雅笛回国探亲遭"文字狱"│
│     来源: chineseyouthstandfortibet...   │
│     分类: 安全情报 > 涉藏 > 东亚         │
│     评分: ⭐⭐⭐⭐⭐ (0.126)              │
│     预览: 计划赴英国伦敦求学的一名...   │
│     [查看详情]                           │
├─────────────────────────────────────────┤
│  □ 藏汉青年交流小记                      │
│     来源: starshiner.substack.com       │
│     分类: 安全情报 > 涉藏 > 北美         │
│     评分: ⭐⭐⭐ (0.0617)                │
│     预览: 2025年3月28日下午...          │
│     [查看详情]                           │
└─────────────────────────────────────────┘
```

#### 步骤 2.2: 查看详情

**用户操作**: 点击 "查看详情" 按钮

**前端调用**:
```typescript
const showDetail = async (mongo_id: string) => {
  const response = await fetch(
    `/api/v1/nl-search/rag-content/${mongo_id}`
  );
  const content = await response.json();

  // 显示详情模态框
  showModal({
    title: content.title,
    source: content.source,
    url: content.url,
    markdown_content: content.markdown_content
  });
};
```

**后端处理**:
```python
# GET /nl-search/rag-content/{mongo_id}
# 从 news_results 查询 (仅查询需要的字段)
result = await db["news_results"].find_one(
    {"_id": mongo_id},
    {"url": 1, "markdown_content": 1, "title": 1, "source": 1}
)
```

**前端展示**:
```
┌─────────────────────────────────────────────┐
│  本会编辑留学生张雅笛回国探亲遭"文字狱"！   │
├─────────────────────────────────────────────┤
│  来源: chineseyouthstandfortibet.substack   │
│  [📄 查看原文]                               │
├─────────────────────────────────────────────┤
│  # 本会编辑留学生张雅笛回国探亲遭"文字狱"！│
│                                             │
│  计划赴英国伦敦求学的一名留学生因支持...   │
│  （完整Markdown内容）                       │
│                                             │
└─────────────────────────────────────────────┘
│  [选择归档] [关闭]                          │
└─────────────────────────────────────────────┘
```

#### 步骤 2.3: 选择要归档的结果

**用户操作**: 勾选checkbox选择要归档的结果

**前端状态管理**:
```typescript
const [selectedItems, setSelectedItems] = useState<string[]>([]);

const toggleSelection = (mongo_id: string) => {
  setSelectedItems(prev =>
    prev.includes(mongo_id)
      ? prev.filter(id => id !== mongo_id)
      : [...prev, mongo_id]
  );
};
```

---

### Phase 3: 批量编辑 (可选)

#### 场景说明

**什么时候需要批量编辑？**
- 用户想修改标题（让它更简洁或更准确）
- 用户想添加自己的摘要
- 用户想调整分类

**批量编辑 vs 档案创建时编辑**:
- **批量编辑**: 提前保存编辑，可以多次修改
- **档案创建时编辑**: 仅在创建档案时提供编辑内容

#### 批量编辑流程

**前端界面**:
```
┌─────────────────────────────────────────────┐
│  批量编辑 (已选择 3 条)                      │
├─────────────────────────────────────────────┤
│  1. 本会编辑留学生张雅笛回国探亲遭"文字狱" │
│     原标题: 本会编辑留学生张雅笛...         │
│     编辑标题: [留学生因支持藏人被捕]        │
│     编辑摘要: [张雅笛原定到英国...] ✏️      │
├─────────────────────────────────────────────┤
│  2. 藏汉青年交流小记                        │
│     原标题: 藏汉青年交流小记                │
│     编辑标题: [北美藏汉青年交流会议]        │
│     编辑摘要: [2025年3月北加州...] ✏️       │
└─────────────────────────────────────────────┘
│  [保存编辑] [取消]                          │
└─────────────────────────────────────────────┘
```

**前端调用**:
```typescript
const batchEdit = async () => {
  const response = await fetch('/api/v1/user-edits/batch', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      updates: [
        {
          record_id: "249832360786370562",  // mongo_id
          fields: {
            title: "留学生因支持藏人被捕",
            summary: "张雅笛原定到英国伦敦大学亚非学院读硕士..."
          }
        },
        {
          record_id: "249832360786370564",
          fields: {
            title: "北美藏汉青年交流会议",
            summary: "2025年3月北加州藏人文化中心举办..."
          }
        }
      ]
    })
  });
};
```

**后端处理**:
```python
# POST /user-edits/batch
# 保存到 user_edited_results 集合
for update in request.updates:
    await db["user_edited_results"].update_one(
        {
            "news_result_id": update.record_id,
            "user_id": current_user_id
        },
        {
            "$set": {
                "edited_title": update.fields.get("title"),
                "edited_summary": update.fields.get("summary"),
                "edited_at": datetime.utcnow()
            }
        },
        upsert=True  # 如果不存在则插入
    )
```

**效果**:
- ✅ 编辑保存到 `user_edited_results`
- ✅ 前端标记为"已编辑"
- ✅ 创建档案时会自动使用编辑内容

---

### Phase 4: 创建档案

#### 步骤 4.1: 填写档案信息

**前端界面**:
```
┌─────────────────────────────────────────────┐
│  创建档案                                    │
├─────────────────────────────────────────────┤
│  档案名称: [西藏相关新闻汇总] *必填         │
│  档案描述: [2024年西藏相关重要新闻报道]     │
│  标签: [西藏] [人权] [2024]                │
├─────────────────────────────────────────────┤
│  已选择 3 条结果:                           │
│  ✓ 留学生因支持藏人被捕 (已编辑)            │
│  ✓ 北美藏汉青年交流会议 (已编辑)            │
│  ✓ 藏人行政中央驻北美办事处活动             │
├─────────────────────────────────────────────┤
│  为每条结果添加备注和评分:                  │
│                                             │
│  1. 留学生因支持藏人被捕                    │
│     备注: [重要参考资料] ✏️                 │
│     评分: ⭐⭐⭐⭐⭐                          │
│                                             │
│  2. 北美藏汉青年交流会议                    │
│     备注: [需要跟进] ✏️                     │
│     评分: ⭐⭐⭐⭐                            │
└─────────────────────────────────────────────┘
│  [创建档案] [取消]                          │
└─────────────────────────────────────────────┘
```

#### 步骤 4.2: 提交创建请求

**前端调用**:
```typescript
const createArchive = async () => {
  const response = await fetch('/api/v1/nl-search/archives', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      user_id: 1001,
      archive_name: "西藏相关新闻汇总",
      description: "2024年西藏相关重要新闻报道",
      tags: ["西藏", "人权", "2024"],
      search_log_id: "248728141926559744",  // 可选，来自NL Search
      items: [
        {
          news_result_id: "249832360786370562",
          user_notes: "重要参考资料",
          user_rating: 5
        },
        {
          news_result_id: "249832360786370564",
          user_notes: "需要跟进",
          user_rating: 4
        },
        {
          news_result_id: "249832360786370565",
          user_rating: 3
        }
      ]
    })
  });

  const archive = await response.json();
  console.log("档案创建成功:", archive.archive_id);
};
```

#### 步骤 4.3: 系统处理流程

**后端处理** (`src/services/nl_search/mongo_archive_service.py:60`):

```python
async def create_archive(
    user_id: int,
    archive_name: str,
    items: List[Dict[str, Any]],
    description: Optional[str] = None,
    tags: Optional[List[str]] = None,
    search_log_id: Optional[int] = None
) -> Dict[str, Any]:
    """创建档案"""

    # 1️⃣ 验证输入
    if not archive_name or not items:
        raise ValueError("档案名称和条目列表不能为空")

    # 2️⃣ 为每个item创建快照并合并编辑
    archive_items = []
    item_counter = 1

    for item in items:
        news_result_id = item["news_result_id"]

        # 2.1 从 news_results 创建快照
        snapshot = await self._create_snapshot(news_result_id)
        if not snapshot:
            logger.warning(f"跳过无效记录: {news_result_id}")
            continue

        # 2.2 🆕 检查 user_edited_results 是否有编辑记录
        edited_record = await self.db["user_edited_results"].find_one({
            "news_result_id": news_result_id,
            "user_id": user_id
        })

        # 2.3 🆕 合并编辑内容 (优先级规则)
        edited_title = (
            item.get("edited_title") or  # 优先级1: API请求中的
            (edited_record.get("edited_title") if edited_record else None) or  # 优先级2: 已保存的
            snapshot.get("title")  # 优先级3: 原始标题
        )

        edited_summary = (
            item.get("edited_summary") or
            (edited_record.get("edited_summary") if edited_record else None) or
            snapshot.get("content", "")[:200]  # 原始内容前200字
        )

        # 2.4 构建档案条目
        archive_item = {
            "id": item_counter,
            "news_result_id": news_result_id,
            "snapshot": snapshot,
            "edited_title": edited_title,
            "edited_summary": edited_summary,
            "user_notes": item.get("user_notes"),
            "user_rating": item.get("user_rating"),
            "created_at": datetime.utcnow()
        }

        archive_items.append(archive_item)
        item_counter += 1

    # 3️⃣ 构建档案文档
    archive_id = ObjectId()
    archive_doc = {
        "_id": archive_id,
        "user_id": user_id,
        "archive_name": archive_name,
        "description": description,
        "tags": tags or [],
        "search_log_id": search_log_id,
        "items": archive_items,
        "items_count": len(archive_items),
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }

    # 4️⃣ 保存到 user_archives 集合
    await self.db["user_archives"].insert_one(archive_doc)

    # 5️⃣ 返回档案信息
    return {
        "archive_id": str(archive_id),
        "archive_name": archive_name,
        "items_count": len(archive_items),
        "created_at": archive_doc["created_at"].isoformat()
    }
```

**关键逻辑说明**:

1. **快照创建** (`_create_snapshot`):
   ```python
   async def _create_snapshot(self, news_result_id: str) -> Optional[Dict]:
       result = await self.db["news_results"].find_one({"_id": news_result_id})
       if not result:
           return None

       return {
           "title": result.get("title"),
           "content": result.get("content"),
           "category": result.get("category"),
           "published_at": result.get("published_at"),
           "source": result.get("source"),
           "media_urls": result.get("media_urls", [])
       }
   ```

2. **编辑内容合并优先级**:
   ```
   1. API请求中的 edited_title/edited_summary (最高优先级)
      ↓ 如果没有
   2. user_edited_results 中保存的编辑 (批量编辑的结果)
      ↓ 如果没有
   3. news_results 中的原始数据 (保底)
   ```

3. **数据存储结构**:
   ```javascript
   // user_archives 集合
   {
     "_id": ObjectId("..."),
     "user_id": 1001,
     "archive_name": "西藏相关新闻汇总",
     "description": "2024年西藏相关重要新闻报道",
     "tags": ["西藏", "人权", "2024"],
     "search_log_id": "248728141926559744",
     "items": [
       {
         "id": 1,
         "news_result_id": "249832360786370562",
         "snapshot": {
           "title": "原始标题",
           "content": "原始内容",
           "category": {...},
           "published_at": ISODate("..."),
           "source": "来源",
           "media_urls": [...]
         },
         "edited_title": "留学生因支持藏人被捕",  // 编辑后的标题
         "edited_summary": "张雅笛原定...",  // 编辑后的摘要
         "user_notes": "重要参考资料",
         "user_rating": 5,
         "created_at": ISODate("...")
       }
     ],
     "items_count": 3,
     "created_at": ISODate("..."),
     "updated_at": ISODate("...")
   }
   ```

---

### Phase 5: 档案管理

#### 5.1 查询档案列表

**用途**: 用户查看自己创建的所有档案

**API调用**:
```bash
GET /api/v1/nl-search/archives?user_id=1001&limit=20&offset=0
```

**响应**:
```json
{
  "total": 5,
  "items": [
    {
      "archive_id": "507f1f77bcf86cd799439011",
      "archive_name": "西藏相关新闻汇总",
      "description": "2024年西藏相关重要新闻报道",
      "tags": ["西藏", "人权", "2024"],
      "items_count": 3,
      "created_at": "2025-11-22T10:00:00Z",
      "updated_at": "2025-11-22T10:00:00Z"
    }
  ],
  "page": 1,
  "page_size": 20
}
```

**前端展示**:
```
┌─────────────────────────────────────────────┐
│  我的档案 (共 5 个)                          │
├─────────────────────────────────────────────┤
│  📁 西藏相关新闻汇总                        │
│     标签: #西藏 #人权 #2024                │
│     包含 3 条内容                           │
│     创建于: 2025-11-22                      │
│     [查看] [编辑] [删除]                    │
├─────────────────────────────────────────────┤
│  📁 AI技术进展总结                          │
│     标签: #AI #技术                        │
│     包含 10 条内容                          │
│     创建于: 2025-11-20                      │
│     [查看] [编辑] [删除]                    │
└─────────────────────────────────────────────┘
```

#### 5.2 查看档案详情

**用途**: 查看档案的完整信息和所有条目

**API调用**:
```bash
GET /api/v1/nl-search/archives/507f1f77bcf86cd799439011?user_id=1001
```

**响应**:
```json
{
  "archive_id": "507f1f77bcf86cd799439011",
  "user_id": 1001,
  "archive_name": "西藏相关新闻汇总",
  "description": "2024年西藏相关重要新闻报道",
  "tags": ["西藏", "人权", "2024"],
  "search_log_id": "248728141926559744",
  "items_count": 3,
  "items": [
    {
      "id": 1,
      "news_result_id": "249832360786370562",
      "title": "留学生因支持藏人被捕",  // 显示标题 (优先显示edited_title)
      "content": "张雅笛原定到英国伦敦...",  // 显示内容 (优先显示edited_summary)
      "edited_title": "留学生因支持藏人被捕",
      "edited_summary": "张雅笛原定...",
      "user_notes": "重要参考资料",
      "user_rating": 5,
      "category": {"大类": "安全情报", "类别": "涉藏", "地域": "东亚"},
      "source": "chineseyouthstandfortibet.substack.com",
      "created_at": "2025-11-22T10:00:00Z"
    }
  ],
  "created_at": "2025-11-22T10:00:00Z",
  "updated_at": "2025-11-22T10:00:00Z"
}
```

**前端展示**:
```
┌─────────────────────────────────────────────┐
│  📁 西藏相关新闻汇总                        │
├─────────────────────────────────────────────┤
│  描述: 2024年西藏相关重要新闻报道          │
│  标签: #西藏 #人权 #2024                   │
│  创建时间: 2025-11-22 10:00                │
│  包含 3 条内容                             │
├─────────────────────────────────────────────┤
│  1. 留学生因支持藏人被捕 ⭐⭐⭐⭐⭐         │
│     来源: chineseyouthstandfortibet...     │
│     分类: 安全情报 > 涉藏 > 东亚           │
│     备注: 重要参考资料                     │
│     内容: 张雅笛原定到英国伦敦...          │
│     [查看完整内容]                         │
├─────────────────────────────────────────────┤
│  2. 北美藏汉青年交流会议 ⭐⭐⭐⭐           │
│     来源: starshiner.substack.com          │
│     分类: 安全情报 > 涉藏 > 北美           │
│     备注: 需要跟进                         │
│     内容: 2025年3月北加州...               │
│     [查看完整内容]                         │
└─────────────────────────────────────────────┘
│  [编辑档案] [删除档案] [导出]              │
└─────────────────────────────────────────────┘
```

#### 5.3 更新档案信息

**用途**: 修改档案名称、描述、标签

**API调用**:
```bash
PUT /api/v1/nl-search/archives/507f1f77bcf86cd799439011?user_id=1001
Content-Type: application/json

{
  "archive_name": "西藏人权新闻汇总 (2024)",
  "description": "2024年西藏相关人权新闻的系统整理",
  "tags": ["西藏", "人权", "2024", "留学生"]
}
```

**后端处理**:
```python
# 验证权限: 只能修改自己的档案
archive = await db["user_archives"].find_one({
    "_id": ObjectId(archive_id),
    "user_id": user_id
})

if not archive:
    raise HTTPException(404, "档案不存在或无权访问")

# 更新档案信息
await db["user_archives"].update_one(
    {"_id": ObjectId(archive_id)},
    {
        "$set": {
            "archive_name": new_name,
            "description": new_description,
            "tags": new_tags,
            "updated_at": datetime.utcnow()
        }
    }
)
```

#### 5.4 删除档案

**用途**: 删除不再需要的档案

**API调用**:
```bash
DELETE /api/v1/nl-search/archives/507f1f77bcf86cd799439011?user_id=1001
```

**后端处理**:
```python
# 验证权限并删除
result = await db["user_archives"].delete_one({
    "_id": ObjectId(archive_id),
    "user_id": user_id
})

if result.deleted_count == 0:
    raise HTTPException(404, "档案不存在或无权删除")
```

---

## 数据流总结

### 完整数据流图

```
用户查询 (NL Search 或 RAG)
    ↓
news_results 表 (数据源)
    ↓
前端展示结果列表 (带 mongo_id)
    ↓
┌────────────────────────────────────┐
│  用户操作分支                       │
├────────────────────────────────────┤
│  分支A: 直接创建档案                │
│      └─ 跳过编辑，直接创建          │
│                                     │
│  分支B: 批量编辑 → 创建档案         │
│      ├─ POST /user-edits/batch     │
│      │     └─ 保存到 user_edited_results
│      └─ POST /nl-search/archives   │
│            └─ 自动合并编辑内容      │
└────────────────────────────────────┘
    ↓
POST /nl-search/archives (创建档案)
    ↓
系统处理:
    1. 从 news_results 创建快照
    2. 从 user_edited_results 读取编辑 (如果有)
    3. 合并编辑内容 (优先级规则)
    4. 构建档案文档
    5. 保存到 user_archives
    ↓
返回档案信息
    ↓
前端显示"创建成功"
```

---

## 关键技术要点

### 1. mongo_id 的作用

`mongo_id` 是整个流程的**核心纽带**:

```
RAG/NL Search 返回 → mongo_id
                        ↓
                = news_results._id
                        ↓
用于批量编辑 (record_id = mongo_id)
用于档案创建 (news_result_id = mongo_id)
用于查看详情 (GET /rag-content/{mongo_id})
```

### 2. 编辑内容合并策略

**优先级规则** (从高到低):
1. API请求中提供的 `edited_title`/`edited_summary`
2. `user_edited_results` 中保存的编辑
3. `news_results` 中的原始数据

**代码实现**:
```python
edited_title = (
    item.get("edited_title") or  # 优先级1
    (edited_record.get("edited_title") if edited_record else None) or  # 优先级2
    snapshot.get("title")  # 优先级3
)
```

### 3. 快照机制

**为什么使用快照？**
- ✅ 档案内容独立，不受原始数据变化影响
- ✅ 即使 `news_results` 被删除，档案仍保留完整信息
- ❌ 无法获取最新数据更新

**快照包含的字段**:
- `title`: 标题
- `content`: 内容
- `category`: 分类
- `published_at`: 发布时间
- `source`: 来源
- `media_urls`: 媒体URL列表

---

## API端点速查

| 功能 | 方法 | 端点 | 说明 |
|------|------|------|------|
| NL Search | POST | `/nl-search` | 外部搜索入库 |
| RAG查询 | POST | `/nl-search/rag-query` | 内部检索 |
| 查看详情 | GET | `/nl-search/rag-content/{mongo_id}` | 获取markdown和url |
| 批量编辑 | POST | `/user-edits/batch` | 保存编辑到user_edited_results |
| **创建档案** | **POST** | **`/nl-search/archives`** | **核心：创建档案** |
| 查询档案列表 | GET | `/nl-search/archives?user_id=...` | 用户档案列表 |
| 查看档案详情 | GET | `/nl-search/archives/{archive_id}` | 完整档案信息 |
| 更新档案 | PUT | `/nl-search/archives/{archive_id}` | 修改名称描述标签 |
| 删除档案 | DELETE | `/nl-search/archives/{archive_id}` | 删除档案 |

---

## 前端开发建议

### 1. 状态管理

```typescript
interface ArchiveCreationState {
  selectedItems: string[];  // mongo_id 数组
  editedItems: Map<string, EditedContent>;  // 已编辑的内容
  archiveInfo: {
    name: string;
    description: string;
    tags: string[];
  };
  itemNotes: Map<string, {notes: string, rating: number}>;
}
```

### 2. 用户流程优化

**推荐流程**:
1. 批量选择 → 批量编辑 → 创建档案 (适合需要大量编辑的场景)
2. 批量选择 → 直接创建档案 → 后续单独编辑档案 (快速归档场景)

**UX建议**:
- ✅ 提供"批量编辑"和"直接创建"两个选项
- ✅ 已编辑的内容在列表中标记 (如: 🖊️ 图标)
- ✅ 创建档案时预览已选择的内容
- ✅ 提供"保存草稿"功能 (暂存档案信息)

### 3. 错误处理

```typescript
try {
  const response = await createArchive(archiveData);
  showSuccess("档案创建成功！");
  navigateTo(`/archives/${response.archive_id}`);
} catch (error) {
  if (error.status === 400) {
    showError("请检查输入信息是否完整");
  } else if (error.status === 404) {
    showError("部分内容不存在，请重新选择");
  } else {
    showError("创建失败，请稍后重试");
  }
}
```

---

## 常见问题

### Q1: 用户编辑和批量编辑有什么区别？

**A**:
- **批量编辑** (`POST /user-edits/batch`): 保存到 `user_edited_results`，可多次修改
- **档案创建时编辑**: 在创建档案请求中提供 `edited_title`/`edited_summary`，仅在创建时使用

**推荐策略**:
- 需要反复修改 → 使用批量编辑
- 一次性归档 → 档案创建时直接编辑

### Q2: 如果批量编辑后，创建档案时又提供了新的编辑内容，会使用哪个？

**A**: 使用档案创建请求中提供的内容（优先级最高）

### Q3: 档案创建后，可以修改条目内容吗？

**A**: 目前只能修改档案基本信息（名称、描述、标签），**无法单独修改条目**。

**未来计划**:
- ✅ 新增档案条目编辑API
- ✅ 支持添加/删除档案条目

### Q4: 删除档案会删除 news_results 中的数据吗？

**A**: **不会**。档案只是引用 `news_results`，删除档案不影响原始数据。

---

**文档维护**: Claude Code - Backend & Architect Personas
**审查状态**: 完成
**最后更新**: 2025-11-22
