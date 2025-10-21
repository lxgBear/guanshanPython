# SearchTask 字段关系 UML 图解

## 1. 类图 (Class Diagram)

### SearchTask 实体结构

```plantuml
@startuml
class SearchTask {
  ' 主键
  +id: Union[str, UUID]

  ' 基本信息
  +name: str
  +description: Optional[str]

  ' 核心字段
  +query: str
  +target_website: Optional[str]
  +crawl_url: Optional[str]
  +search_config: Dict[str, Any]

  ' 调度配置
  +schedule_interval: str
  +is_active: bool
  +status: TaskStatus

  ' 元数据
  +created_by: str
  +created_at: datetime
  +updated_at: datetime
  +last_executed_at: Optional[datetime]
  +next_run_time: Optional[datetime]

  ' 统计信息
  +execution_count: int
  +success_count: int
  +failure_count: int
  +total_results: int
  +total_credits_used: int

  ' 方法
  +extract_target_website(): Optional[str]
  +sync_target_website(): None
  +get_schedule_interval(): ScheduleInterval
  +record_execution(success: bool, ...): None
}

class SearchConfig {
  ' 搜索参数
  +limit: int
  +sources: List[str]
  +language: str

  ' 域名过滤
  +include_domains: List[str]
  +exclude_domains: List[str]

  ' 时间范围
  +time_range: Optional[str]

  ' 高级选项
  +scrape_formats: List[str]
  +only_main_content: bool
}

SearchTask "1" *-- "1" SearchConfig : search_config
note right of SearchTask::target_website
  **仅用于前端显示**
  自动从 include_domains[0] 同步
end note

note right of SearchTask::crawl_url
  **决定执行模式**
  存在 → Scrape API (忽略 query 和 include_domains)
  不存在 → Search API (使用 query 和 include_domains)
end note

note right of SearchConfig::include_domains
  **仅在 Search API 模式生效**
  转换为 site: 操作符
  例: ["a.com", "b.com"] → "(site:a.com OR site:b.com) query"
end note
@enduml
```

---

## 2. 执行流程图 (Sequence Diagram)

### 场景1: Search API 模式 (crawl_url 为空)

```plantuml
@startuml
actor User
participant Frontend
participant TaskScheduler
participant FirecrawlSearchAdapter
participant FirecrawlAPI

User -> Frontend: 创建任务\n(query + include_domains)
Frontend -> TaskScheduler: create_task(\n  query="Myanmar economy",\n  search_config={\n    include_domains: ["www.gnlm.com.mm"]\n  }\n)

TaskScheduler -> TaskScheduler: sync_target_website()
note right
  target_website = include_domains[0]
  = "www.gnlm.com.mm"
end note

TaskScheduler -> TaskScheduler: schedule_task()

alt 定时触发
  TaskScheduler -> TaskScheduler: _execute_search_task(task_id)
  TaskScheduler -> TaskScheduler: 检查 crawl_url
  note right
    crawl_url is None
    → 使用 Search API 模式
  end note

  TaskScheduler -> FirecrawlSearchAdapter: search(\n  query="Myanmar economy",\n  user_config={\n    include_domains: ["www.gnlm.com.mm"]\n  }\n)

  FirecrawlSearchAdapter -> FirecrawlSearchAdapter: _build_request_body()
  note right
    转换 include_domains → site: 操作符
    final_query = "site:www.gnlm.com.mm Myanmar economy"
  end note

  FirecrawlSearchAdapter -> FirecrawlAPI: POST /v2/search\n{\n  query: "site:www.gnlm.com.mm Myanmar economy",\n  limit: 20\n}

  FirecrawlAPI --> FirecrawlSearchAdapter: 返回搜索结果
  FirecrawlSearchAdapter --> TaskScheduler: SearchResultBatch
  TaskScheduler -> TaskScheduler: 保存结果到数据库
  TaskScheduler -> TaskScheduler: 更新任务统计
end

TaskScheduler --> Frontend: 任务执行完成
Frontend --> User: 显示结果\n(target_website: "www.gnlm.com.mm")
@enduml
```

---

### 场景2: Scrape API 模式 (crawl_url 存在)

```plantuml
@startuml
actor User
participant Frontend
participant TaskScheduler
participant FirecrawlAdapter
participant FirecrawlAPI

User -> Frontend: 创建任务\n(crawl_url)
Frontend -> TaskScheduler: create_task(\n  crawl_url="https://www.gnlm.com.mm/"\n)

TaskScheduler -> TaskScheduler: schedule_task()

alt 定时触发
  TaskScheduler -> TaskScheduler: _execute_search_task(task_id)
  TaskScheduler -> TaskScheduler: 检查 crawl_url
  note right
    crawl_url 存在
    → 使用 Scrape API 模式
    **忽略 query 和 include_domains**
  end note

  TaskScheduler -> TaskScheduler: _execute_crawl_task_internal()
  TaskScheduler -> FirecrawlAdapter: scrape(\n  url="https://www.gnlm.com.mm/",\n  scrape_options={...}\n)

  FirecrawlAdapter -> FirecrawlAPI: POST /v1/scrape\n{\n  url: "https://www.gnlm.com.mm/",\n  formats: ["markdown", "html"]\n}

  FirecrawlAPI --> FirecrawlAdapter: 返回页面内容
  FirecrawlAdapter --> TaskScheduler: CrawlResult
  TaskScheduler -> TaskScheduler: 转换为 SearchResult
  TaskScheduler -> TaskScheduler: 保存结果到数据库
  TaskScheduler -> TaskScheduler: 更新任务统计
end

TaskScheduler --> Frontend: 任务执行完成
Frontend --> User: 显示结果
@enduml
```

---

## 3. 状态图 (State Diagram)

### 任务执行模式切换

```plantuml
@startuml
[*] --> 任务创建

任务创建 : 用户创建 SearchTask

任务创建 --> 模式检测 : 调度器触发

state 模式检测 <<choice>>
模式检测 --> ScrapeMod : crawl_url 存在
模式检测 --> SearchMode : crawl_url 为空

state ScrapeMod {
  [*] --> 直接爬取URL
  直接爬取URL : 使用 Firecrawl Scrape API
  直接爬取URL : ❌ 忽略 query
  直接爬取URL : ❌ 忽略 include_domains
  直接爬取URL --> 返回单页结果
  返回单页结果 --> [*]
}

state SearchMode {
  [*] --> 关键词搜索
  关键词搜索 : 使用 Firecrawl Search API
  关键词搜索 : ✅ 使用 query
  关键词搜索 : ✅ 应用 include_domains
  关键词搜索 --> 域名过滤
  域名过滤 : 转换为 site: 操作符
  域名过滤 --> 返回多页结果
  返回多页结果 --> [*]
}

ScrapeMod --> 保存结果
SearchMode --> 保存结果
保存结果 --> 更新统计
更新统计 --> [*]
@enduml
```

---

## 4. 组件图 (Component Diagram)

### 字段依赖关系

```plantuml
@startuml
package "SearchTask Entity" {
  component [target_website] as tw
  component [crawl_url] as cu
  component [query] as q
  component [search_config] as sc
}

package "search_config Details" {
  component [include_domains] as id
  component [exclude_domains] as ed
  component [limit] as lim
  component [language] as lang
}

package "Execution Layer" {
  component [TaskScheduler] as ts
  component [FirecrawlSearchAdapter] as fsa
  component [FirecrawlAdapter] as fa
}

package "External API" {
  component [Firecrawl Search API] as fsapi
  component [Firecrawl Scrape API] as fscapi
}

' 字段关系
sc *-- id
sc *-- ed
sc *-- lim
sc *-- lang

tw ..> id : 自动同步\nfrom include_domains[0]

' 执行流程
cu --> ts : 决定模式
ts --> fa : crawl_url 存在
ts --> fsa : crawl_url 为空

fa --> fscapi : 使用 crawl_url
fsa --> fsapi : 使用 query + include_domains

q --> fsa : 搜索关键词
id --> fsa : 域名过滤

note right of tw
  **仅用于前端显示**
  不影响爬取逻辑
end note

note right of cu
  **模式决策者**
  存在 → Scrape API
  不存在 → Search API
end note

note bottom of id
  **仅在 Search API 模式生效**
  转换为 site: 操作符
end note
@enduml
```

---

## 5. 活动图 (Activity Diagram)

### 任务创建与字段验证

```plantuml
@startuml
start

:用户填写表单;

if (选择模式?) then (URL爬取模式)
  :填写 crawl_url;
  :可选填写 target_website;
  note right
    query 和 include_domains
    会被忽略，无需填写
  end note
  :验证 crawl_url 格式;
  if (URL 格式有效?) then (是)
    :创建任务\n(Scrape模式);
  else (否)
    :显示错误: 无效URL;
    stop
  endif
else (关键词搜索模式)
  :填写 query;
  :填写 include_domains;
  :可选填写 target_website;
  note right
    target_website 会自动
    从 include_domains[0] 同步
  end note
  :验证必填字段;
  if (query 和 include_domains 都填写?) then (是)
    :创建任务\n(Search模式);
    :自动同步 target_website;
  else (否)
    :显示错误: 缺少必填字段;
    stop
  endif
endif

:保存到数据库;
:添加到调度器;
:返回任务ID;

stop
@enduml
```

---

## 6. 部署图 (Deployment Diagram)

### 系统架构与字段流转

```plantuml
@startuml
node "前端应用" {
  component [UI表单] as ui
  component [API客户端] as apic
}

node "后端服务" {
  component [REST API] as api
  component [任务调度器] as scheduler
  database [MongoDB] as db
}

node "搜索服务" {
  component [Search Adapter] as sa
  component [Crawl Adapter] as ca
}

cloud "Firecrawl API" {
  component [Search Endpoint] as se
  component [Scrape Endpoint] as sce
}

ui --> apic : 提交任务\n(target_website,\ncrawl_url, query,\ninclude_domains)
apic --> api : POST /search-tasks
api --> db : 保存任务
api --> scheduler : 注册调度

scheduler --> sa : crawl_url 为空
scheduler --> ca : crawl_url 存在

sa --> se : query + include_domains\n转换为 site: 操作符
ca --> sce : crawl_url

se --> sa : 搜索结果
sce --> ca : 页面内容

sa --> db : 保存结果
ca --> db : 保存结果

db --> api : 查询结果
api --> apic : 返回数据\n(含 target_website)
apic --> ui : 显示给用户

note right of scheduler
  **模式决策点**
  crawl_url 存在 → Scrape API
  crawl_url 为空 → Search API
end note

note bottom of sa
  **include_domains 生效**
  转换为 site: 操作符
end note

note bottom of ca
  **include_domains 无效**
  直接爬取指定 URL
end note
@enduml
```

---

## 7. 对象图 (Object Diagram)

### Search 模式实例

```plantuml
@startuml
object task1 {
  name = "GNLM Economy News"
  query = "Myanmar economy"
  target_website = "www.gnlm.com.mm"
  crawl_url = null
  search_config = {...}
}

object search_config1 {
  limit = 20
  language = "en"
  include_domains = ["www.gnlm.com.mm"]
  time_range = "week"
}

object execution1 {
  mode = "Search API"
  final_query = "site:www.gnlm.com.mm Myanmar economy"
  used_fields = ["query", "include_domains"]
  ignored_fields = ["crawl_url"]
}

task1 *-- search_config1
task1 ..> execution1 : 执行时

note right of task1
  target_website 自动从
  search_config.include_domains[0]
  同步得到
end note

note right of execution1
  include_domains 转换为
  site: 操作符
end note
@enduml
```

---

### Crawl 模式实例

```plantuml
@startuml
object task2 {
  name = "GNLM Homepage Monitor"
  query = ""
  target_website = "www.gnlm.com.mm"
  crawl_url = "https://www.gnlm.com.mm/"
  search_config = {...}
}

object search_config2 {
  wait_for = 2000
  include_tags = ["article", "main"]
  exclude_tags = ["nav", "footer"]
}

object execution2 {
  mode = "Scrape API"
  direct_url = "https://www.gnlm.com.mm/"
  used_fields = ["crawl_url"]
  ignored_fields = ["query", "include_domains"]
}

task2 *-- search_config2
task2 ..> execution2 : 执行时

note right of task2
  crawl_url 存在
  → 忽略 query 和 include_domains
end note

note right of execution2
  直接爬取指定 URL
  不涉及域名过滤
end note
@enduml
```

---

## 8. 用例图 (Use Case Diagram)

```plantuml
@startuml
left to right direction

actor "前端用户" as user
actor "调度器" as scheduler
actor "Firecrawl API" as api

rectangle "定时任务系统" {
  usecase "创建任务\n(设置 target_website)" as UC1
  usecase "配置 Crawl 模式\n(设置 crawl_url)" as UC2
  usecase "配置 Search 模式\n(设置 query + include_domains)" as UC3
  usecase "自动同步 target_website" as UC4
  usecase "执行 Scrape API\n(使用 crawl_url)" as UC5
  usecase "执行 Search API\n(使用 query + include_domains)" as UC6
  usecase "查看任务结果\n(显示 target_website)" as UC7
}

user --> UC1
UC1 ..> UC2 : <<extends>>
UC1 ..> UC3 : <<extends>>
UC3 ..> UC4 : <<includes>>

scheduler --> UC5
scheduler --> UC6

UC2 ..> UC5 : 触发
UC3 ..> UC6 : 触发

UC5 --> api
UC6 --> api

user --> UC7

note right of UC4
  target_website 自动从
  include_domains[0] 提取
end note

note bottom of UC5
  crawl_url 模式
  忽略 query 和 include_domains
end note

note bottom of UC6
  Search 模式
  include_domains 转换为
  site: 操作符
end note
@enduml
```

---

## 9. 通信图 (Communication Diagram)

### 字段交互与数据流

```plantuml
@startuml
object User
object Frontend
object API
object TaskScheduler
object SearchAdapter
object CrawlAdapter
object Database

User -> Frontend : 1: 提交任务配置
Frontend -> API : 2: POST /search-tasks\n(target_website, crawl_url, query, include_domains)
API -> Database : 3: 保存任务
API -> API : 4: sync_target_website()\n(target_website ← include_domains[0])
API -> TaskScheduler : 5: 注册调度

alt crawl_url 为空 (Search 模式)
  TaskScheduler -> SearchAdapter : 6a: search(query, include_domains)
  SearchAdapter -> SearchAdapter : 6a.1: 转换 include_domains → site:
  SearchAdapter -> Database : 6a.2: 保存搜索结果
else crawl_url 存在 (Crawl 模式)
  TaskScheduler -> CrawlAdapter : 6b: scrape(crawl_url)
  CrawlAdapter -> Database : 6b.1: 保存爬取结果
end

Database -> Frontend : 7: 返回结果\n(包含 target_website)
Frontend -> User : 8: 显示任务状态

note right of API
  target_website 同步逻辑:
  if not target_website:
    target_website = include_domains[0]
end note

note bottom of SearchAdapter
  Search 模式:
  ✅ 使用 query
  ✅ 使用 include_domains
  ❌ 忽略 crawl_url
end note

note bottom of CrawlAdapter
  Crawl 模式:
  ✅ 使用 crawl_url
  ❌ 忽略 query
  ❌ 忽略 include_domains
end note
@enduml
```

---

## 10. 时序图总结 (Timing Diagram)

### 字段生效时间线

```plantuml
@startuml
robust "crawl_url" as cu
robust "query" as q
robust "include_domains" as id
robust "target_website" as tw

@0
cu is 未设置
q is 填写
id is 填写
tw is 空

@10
cu is 未设置
q is 填写
id is 填写
tw is 自动同步

@20
cu is 未设置
q is 生效
id is 生效
tw is 显示

@30
cu is 设置
q is 忽略
id is 忽略
tw is 显示

highlight 10 to 20 #lightblue : Search 模式
highlight 30 to 40 #lightgreen : Crawl 模式

@enduml
```

---

## 使用说明

### 查看 UML 图

这些 UML 图使用 PlantUML 语法编写，可以通过以下方式查看：

1. **在线渲染**: 访问 [PlantUML Web Server](http://www.plantuml.com/plantuml/uml/)，粘贴代码
2. **IDE 插件**:
   - VS Code: 安装 "PlantUML" 插件
   - IntelliJ IDEA: 内置 PlantUML 支持
3. **本地命令行**:
   ```bash
   npm install -g node-plantuml
   puml generate TASK_FIELDS_UML.md
   ```

### 图解说明

- **类图**: 展示 SearchTask 和 SearchConfig 的结构关系
- **序列图**: 展示 Search 和 Crawl 两种模式的执行流程
- **状态图**: 展示任务执行模式的切换逻辑
- **组件图**: 展示字段之间的依赖关系
- **活动图**: 展示任务创建和字段验证的流程
- **部署图**: 展示系统架构和字段在各层之间的流转
- **对象图**: 展示具体实例中字段的赋值
- **用例图**: 展示用户和系统之间的交互
- **通信图**: 展示字段在各组件之间的传递
- **时序图**: 展示字段在不同时间点的状态变化
