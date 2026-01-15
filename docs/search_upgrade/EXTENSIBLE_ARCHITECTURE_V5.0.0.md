# 可扩展系统架构设计文档

## 文档信息

| 项目 | 内容 |
|------|------|
| 文档版本 | v5.0.0 |
| 创建日期 | 2025-01-14 |
| 设计目标 | 模块化、可扩展、易维护 |
| 架构师 | Claude (Architect Persona) |

---

## 1. 架构愿景

### 1.1 设计原则

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         可扩展架构设计原则                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │   SOLID 原则    │  │   插件化架构    │  │   配置驱动      │             │
│  │                 │  │                 │  │                 │             │
│  │ • 单一职责      │  │ • 核心最小化    │  │ • 环境配置      │             │
│  │ • 开闭原则      │  │ • 扩展点设计    │  │ • 运行时配置    │             │
│  │ • 依赖倒置      │  │ • 热插拔能力    │  │ • 特性开关      │             │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘             │
│                                                                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │   事件驱动      │  │   分层隔离      │  │   接口抽象      │             │
│  │                 │  │                 │  │                 │             │
│  │ • 解耦通信      │  │ • 清晰边界      │  │ • 协议契约      │             │
│  │ • 异步处理      │  │ • 独立部署      │  │ • 版本兼容      │             │
│  │ • 可观测性      │  │ • 独立扩展      │  │ • Mock 测试     │             │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 架构目标

| 目标 | 描述 | 度量 |
|------|------|------|
| 可扩展 | 新功能可通过插件/配置添加 | 新增功能无需修改核心代码 |
| 可替换 | 各层/组件可独立替换 | 替换组件不影响其他层 |
| 可测试 | 各模块可独立测试 | 单元测试覆盖率 ≥ 80% |
| 可观测 | 全链路可追踪 | 日志、指标、追踪完备 |
| 可配置 | 行为可通过配置调整 | 无代码修改即可调整行为 |

---

## 2. 整体架构

### 2.1 分层架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              API Gateway Layer                              │
│                                                                             │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐                   │
│  │   REST API    │  │   WebSocket   │  │     SSE       │                   │
│  └───────┬───────┘  └───────┬───────┘  └───────┬───────┘                   │
└──────────┼──────────────────┼──────────────────┼────────────────────────────┘
           │                  │                  │
           ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Orchestration Layer                                │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      ChatOrchestrator                                │   │
│  │  • 任务协调        • 层调度         • 错误处理                       │   │
│  │  • 并行控制        • 状态管理       • 超时处理                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
           ┌───────────────────────┼───────────────────────┐
           ▼                       ▼                       ▼
┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐
│  Search Engine      │  │   AI Processing     │  │   (Future Layers)   │
│  Layer              │  │   Layer             │  │                     │
│                     │  │                     │  │  • 知识图谱层       │
│  • LangGraph 6节点  │  │  • 远程 AI 服务    │  │  • 实时推送层       │
│  • NL Search 回退   │  │  • SSE 流处理      │  │  • 缓存层           │
│  • 结果存储         │  │  • 对话历史        │  │  • 审计层           │
└──────────┬──────────┘  └──────────┬──────────┘  └─────────────────────┘
           │                       │
           ▼                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Infrastructure Layer                               │
│                                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │  MongoDB    │  │   Redis     │  │   Firecrawl │  │   Claude    │        │
│  │  Repository │  │   Cache     │  │   Client    │  │   Client    │        │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘        │
│                                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │  Event Bus  │  │   Logger    │  │   Metrics   │  │   Tracer    │        │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘        │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 模块依赖图

```
                    ┌─────────────────────┐
                    │    API Endpoints    │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │  ChatOrchestrator   │
                    └──────────┬──────────┘
                               │
          ┌────────────────────┼────────────────────┐
          │                    │                    │
          ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ ISearchLayer    │  │ IAILayer        │  │ ILayer (扩展)   │
│ (接口)          │  │ (接口)          │  │                 │
└────────┬────────┘  └────────┬────────┘  └─────────────────┘
         │                    │
         ▼                    ▼
┌─────────────────┐  ┌─────────────────┐
│SearchEngineLayer│  │AIProcessingLayer│
│ (实现)          │  │ (实现)          │
└────────┬────────┘  └────────┬────────┘
         │                    │
         ▼                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Infrastructure Services                     │
│  (Repositories, Clients, Event Bus, Logging, Metrics)           │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. 核心接口设计

### 3.1 层接口 (ILayer)

```python
# src/core/interfaces/layer.py

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, AsyncGenerator
from dataclasses import dataclass

@dataclass
class LayerConfig:
    """层配置基类"""
    enabled: bool = True
    timeout: int = 300
    retry_count: int = 3
    retry_delay: float = 1.0

@dataclass
class LayerResult:
    """层执行结果基类"""
    status: str  # "completed" | "failed" | "timeout"
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = None

class ILayer(ABC):
    """层接口 - 所有层必须实现"""

    @property
    @abstractmethod
    def layer_name(self) -> str:
        """层名称"""
        pass

    @property
    @abstractmethod
    def layer_type(self) -> str:
        """层类型: search | ai | cache | audit"""
        pass

    @abstractmethod
    async def execute(
        self,
        context: "LayerContext",
    ) -> LayerResult:
        """执行层逻辑

        Args:
            context: 层执行上下文

        Returns:
            LayerResult: 执行结果
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """健康检查"""
        pass

    def get_config(self) -> LayerConfig:
        """获取层配置"""
        return LayerConfig()

@dataclass
class LayerContext:
    """层执行上下文 - 在层之间传递"""
    task_id: str
    user_id: str
    query: str
    options: Dict[str, Any]
    shared_data: Dict[str, Any]  # 层间共享数据
    metadata: Dict[str, Any]
```

### 3.2 搜索层接口 (ISearchLayer)

```python
# src/core/interfaces/search_layer.py

from abc import abstractmethod
from typing import List, Dict, Any, Optional
from .layer import ILayer, LayerResult, LayerContext

@dataclass
class SearchResult:
    """搜索结果"""
    url: str
    title: str
    snippet: str
    content: Optional[str]
    layer: int
    score: float
    metadata: Dict[str, Any]

@dataclass
class SearchLayerResult(LayerResult):
    """搜索层结果"""
    results: List[SearchResult] = None
    statistics: Dict[str, Any] = None

class ISearchLayer(ILayer):
    """搜索层接口"""

    @property
    def layer_type(self) -> str:
        return "search"

    @abstractmethod
    async def execute(
        self,
        context: LayerContext,
    ) -> SearchLayerResult:
        """执行搜索"""
        pass

    @abstractmethod
    async def get_search_status(
        self,
        task_id: str,
    ) -> str:
        """获取搜索状态"""
        pass
```

### 3.3 AI 层接口 (IAILayer)

```python
# src/core/interfaces/ai_layer.py

from abc import abstractmethod
from typing import AsyncGenerator, Dict, Any
from .layer import ILayer, LayerResult, LayerContext

@dataclass
class SSEEvent:
    """SSE 事件"""
    event_type: str  # "chunk" | "source" | "stream_end" | "error"
    data: Dict[str, Any]
    timestamp: datetime = None

    @classmethod
    def from_dict(cls, data: Dict) -> "SSEEvent":
        return cls(
            event_type=data.get("type"),
            data=data.get("data", {}),
            timestamp=datetime.utcnow(),
        )

class IAILayer(ILayer):
    """AI 处理层接口"""

    @property
    def layer_type(self) -> str:
        return "ai"

    @abstractmethod
    async def execute(
        self,
        context: LayerContext,
    ) -> LayerResult:
        """执行 AI 处理"""
        pass

    @abstractmethod
    async def stream(
        self,
        context: LayerContext,
    ) -> AsyncGenerator[SSEEvent, None]:
        """流式执行 AI 处理"""
        pass
```

### 3.4 协调器接口 (IOrchestrator)

```python
# src/core/interfaces/orchestrator.py

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from .layer import ILayer, LayerContext

@dataclass
class OrchestratorConfig:
    """协调器配置"""
    parallel_execution: bool = True
    max_concurrent_layers: int = 5
    global_timeout: int = 600
    retry_failed_layers: bool = True

@dataclass
class OrchestratorResult:
    """协调器结果"""
    task_id: str
    status: str
    layer_results: Dict[str, LayerResult]
    total_time_ms: int
    errors: List[str]

class IOrchestrator(ABC):
    """协调器接口"""

    @abstractmethod
    def register_layer(
        self,
        layer: ILayer,
        priority: int = 0,
        dependencies: Optional[List[str]] = None,
    ) -> None:
        """注册层

        Args:
            layer: 层实例
            priority: 优先级 (越小越先执行)
            dependencies: 依赖的层名称列表
        """
        pass

    @abstractmethod
    async def execute(
        self,
        context: LayerContext,
    ) -> OrchestratorResult:
        """执行所有层"""
        pass

    @abstractmethod
    async def execute_layer(
        self,
        layer_name: str,
        context: LayerContext,
    ) -> LayerResult:
        """执行单个层"""
        pass
```

---

## 4. 插件系统设计

### 4.1 插件架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Plugin Manager                                     │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        Plugin Registry                               │   │
│  │  • 插件注册          • 生命周期管理      • 依赖解析                   │   │
│  │  • 版本管理          • 健康检查          • 热加载/卸载               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐                   │
│  │ Layer Plugins │  │ Filter Plugins│  │ Event Plugins │                   │
│  │               │  │               │  │               │                   │
│  │ • 搜索层插件  │  │ • 结果过滤器  │  │ • 事件处理器  │                   │
│  │ • AI 层插件   │  │ • 质量门控    │  │ • 监控插件    │                   │
│  │ • 缓存层插件  │  │ • 安全过滤    │  │ • 审计插件    │                   │
│  └───────────────┘  └───────────────┘  └───────────────┘                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 插件接口

```python
# src/core/interfaces/plugin.py

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

class PluginType(Enum):
    LAYER = "layer"
    FILTER = "filter"
    EVENT = "event"
    MIDDLEWARE = "middleware"

@dataclass
class PluginMetadata:
    """插件元数据"""
    name: str
    version: str
    plugin_type: PluginType
    description: str
    author: str
    dependencies: List[str] = None  # 依赖的其他插件

class IPlugin(ABC):
    """插件基接口"""

    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        """插件元数据"""
        pass

    @abstractmethod
    async def initialize(self, config: Dict[str, Any]) -> None:
        """初始化插件"""
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        """关闭插件"""
        pass

    async def health_check(self) -> bool:
        """健康检查"""
        return True

class ILayerPlugin(IPlugin):
    """层插件接口"""

    @abstractmethod
    def create_layer(self) -> ILayer:
        """创建层实例"""
        pass

class IFilterPlugin(IPlugin):
    """过滤器插件接口"""

    @abstractmethod
    async def filter(
        self,
        data: Any,
        context: LayerContext,
    ) -> Any:
        """执行过滤"""
        pass

class IEventPlugin(IPlugin):
    """事件插件接口"""

    @abstractmethod
    async def handle_event(
        self,
        event: Any,
    ) -> None:
        """处理事件"""
        pass

    @property
    @abstractmethod
    def subscribed_events(self) -> List[str]:
        """订阅的事件类型"""
        pass
```

### 4.3 插件管理器

```python
# src/core/plugin/manager.py

class PluginManager:
    """插件管理器"""

    def __init__(self):
        self._plugins: Dict[str, IPlugin] = {}
        self._layers: Dict[str, ILayer] = {}
        self._filters: List[IFilterPlugin] = []
        self._event_handlers: Dict[str, List[IEventPlugin]] = {}

    async def load_plugin(
        self,
        plugin_class: Type[IPlugin],
        config: Dict[str, Any] = None,
    ) -> None:
        """加载插件"""
        plugin = plugin_class()
        await plugin.initialize(config or {})

        metadata = plugin.metadata
        self._plugins[metadata.name] = plugin

        # 根据类型注册
        if isinstance(plugin, ILayerPlugin):
            layer = plugin.create_layer()
            self._layers[layer.layer_name] = layer

        elif isinstance(plugin, IFilterPlugin):
            self._filters.append(plugin)

        elif isinstance(plugin, IEventPlugin):
            for event_type in plugin.subscribed_events:
                if event_type not in self._event_handlers:
                    self._event_handlers[event_type] = []
                self._event_handlers[event_type].append(plugin)

        logger.info(f"Loaded plugin: {metadata.name} v{metadata.version}")

    async def unload_plugin(self, name: str) -> None:
        """卸载插件"""
        if name in self._plugins:
            plugin = self._plugins[name]
            await plugin.shutdown()
            del self._plugins[name]
            logger.info(f"Unloaded plugin: {name}")

    def get_layer(self, name: str) -> Optional[ILayer]:
        """获取层"""
        return self._layers.get(name)

    def get_all_layers(self) -> List[ILayer]:
        """获取所有层"""
        return list(self._layers.values())

    async def apply_filters(
        self,
        data: Any,
        context: LayerContext,
    ) -> Any:
        """应用所有过滤器"""
        result = data
        for filter_plugin in self._filters:
            result = await filter_plugin.filter(result, context)
        return result

    async def emit_event(self, event: Any) -> None:
        """发送事件"""
        event_type = type(event).__name__
        handlers = self._event_handlers.get(event_type, [])
        for handler in handlers:
            await handler.handle_event(event)
```

### 4.4 内置插件示例

#### 搜索层插件

```python
# src/plugins/search/langgraph_plugin.py

class LangGraphSearchPlugin(ILayerPlugin):
    """LangGraph 搜索插件"""

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="langgraph-search",
            version="4.6.0",
            plugin_type=PluginType.LAYER,
            description="LangGraph 6-node search workflow",
            author="GuanShan",
        )

    async def initialize(self, config: Dict[str, Any]) -> None:
        self._config = LangGraphSearchConfig.from_env()
        self._config.update(config)

    async def shutdown(self) -> None:
        pass

    def create_layer(self) -> ILayer:
        return SearchEngineLayer(
            config=self._config,
            search_adapter=SearchEngineAdapter(self._config),
            result_repository=LangGraphResultRepository(),
        )
```

#### AI 层插件

```python
# src/plugins/ai/remote_ai_plugin.py

class RemoteAIPlugin(ILayerPlugin):
    """远程 AI 服务插件"""

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="remote-ai",
            version="1.0.0",
            plugin_type=PluginType.LAYER,
            description="Remote AI service with SSE streaming",
            author="GuanShan",
        )

    async def initialize(self, config: Dict[str, Any]) -> None:
        self._service_url = config.get(
            "service_url",
            "http://192.168.0.5:8035/chat"
        )
        self._timeout = config.get("timeout", 300)

    async def shutdown(self) -> None:
        pass

    def create_layer(self) -> ILayer:
        return AIProcessingLayer(
            service_url=self._service_url,
            timeout=self._timeout,
            result_repository=LangGraphResultRepository(),
            history_repository=ChatHistoryRepository(),
        )
```

---

## 5. 配置系统设计

### 5.1 配置层级

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Configuration Hierarchy                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  优先级 (高 → 低):                                                          │
│                                                                             │
│  1. ┌─────────────────────────────────────────────────────────────────┐    │
│     │  运行时配置 (Runtime Config)                                     │    │
│     │  • API 请求参数                                                  │    │
│     │  • 用户偏好设置                                                  │    │
│     └─────────────────────────────────────────────────────────────────┘    │
│                                    ▼                                        │
│  2. ┌─────────────────────────────────────────────────────────────────┐    │
│     │  环境变量 (Environment Variables)                               │    │
│     │  • SEARCH_ENGINE=langgraph                                      │    │
│     │  • AI_SERVICE_URL=http://192.168.0.5:8035/chat                  │    │
│     │  • ENABLE_PARALLEL_EXECUTION=true                               │    │
│     └─────────────────────────────────────────────────────────────────┘    │
│                                    ▼                                        │
│  3. ┌─────────────────────────────────────────────────────────────────┐    │
│     │  配置文件 (config/settings.yaml)                                │    │
│     │  • 层配置                                                       │    │
│     │  • 插件配置                                                     │    │
│     │  • 特性开关                                                     │    │
│     └─────────────────────────────────────────────────────────────────┘    │
│                                    ▼                                        │
│  4. ┌─────────────────────────────────────────────────────────────────┐    │
│     │  默认配置 (Default Config)                                      │    │
│     │  • 代码中的默认值                                               │    │
│     └─────────────────────────────────────────────────────────────────┘    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 配置文件结构

```yaml
# config/settings.yaml

# 系统配置
system:
  name: "GuanShan Search"
  version: "5.0.0"
  environment: "production"  # development | staging | production

# 协调器配置
orchestrator:
  parallel_execution: true
  max_concurrent_layers: 5
  global_timeout: 600
  retry_failed_layers: true

# 层配置
layers:
  # 搜索引擎层
  search_engine:
    enabled: true
    implementation: "langgraph"  # langgraph | nl_search
    timeout: 300
    fallback: "nl_search"
    config:
      max_concurrent_searches: 5
      enable_parallel_layers: true
      checkpoint_enabled: true

  # AI 处理层
  ai_processing:
    enabled: true
    service_url: "${AI_SERVICE_URL:http://192.168.0.5:8035/chat}"
    timeout: 300
    stream_enabled: true
    retry_count: 3

  # 缓存层 (可选)
  cache:
    enabled: false
    ttl: 3600
    backend: "redis"

# 插件配置
plugins:
  # 已启用插件列表
  enabled:
    - "langgraph-search"
    - "remote-ai"
    - "quality-filter"

  # 插件特定配置
  settings:
    langgraph-search:
      enable_layer_0: true
      enable_layer_1: true
      enable_layer_2: true
      enable_layer_3: true
      enable_layer_4: true

    quality-filter:
      min_score: 0.6
      max_results: 100

# 特性开关
features:
  parallel_execution: true
  skip_summary_option: true
  search_only_endpoint: true
  event_driven_mode: false  # 未来启用

# 日志配置
logging:
  level: "INFO"
  format: "json"
  include_trace_id: true

# 指标配置
metrics:
  enabled: true
  export_interval: 30
  include_layer_metrics: true
```

### 5.3 配置加载器

```python
# src/core/config/loader.py

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
import yaml
import os

@dataclass
class SystemConfig:
    """系统配置"""
    name: str = "GuanShan Search"
    version: str = "5.0.0"
    environment: str = "development"

@dataclass
class LayerConfig:
    """层配置"""
    enabled: bool = True
    implementation: str = ""
    timeout: int = 300
    fallback: Optional[str] = None
    config: Dict[str, Any] = field(default_factory=dict)

@dataclass
class OrchestratorConfig:
    """协调器配置"""
    parallel_execution: bool = True
    max_concurrent_layers: int = 5
    global_timeout: int = 600
    retry_failed_layers: bool = True

@dataclass
class AppConfig:
    """应用配置"""
    system: SystemConfig = field(default_factory=SystemConfig)
    orchestrator: OrchestratorConfig = field(default_factory=OrchestratorConfig)
    layers: Dict[str, LayerConfig] = field(default_factory=dict)
    plugins: Dict[str, Any] = field(default_factory=dict)
    features: Dict[str, bool] = field(default_factory=dict)

class ConfigLoader:
    """配置加载器"""

    def __init__(self, config_path: str = "config/settings.yaml"):
        self.config_path = config_path
        self._config: Optional[AppConfig] = None

    def load(self) -> AppConfig:
        """加载配置"""
        if self._config:
            return self._config

        # 1. 加载默认配置
        config_data = self._get_defaults()

        # 2. 加载配置文件
        if os.path.exists(self.config_path):
            with open(self.config_path, "r") as f:
                file_config = yaml.safe_load(f)
                config_data = self._merge_config(config_data, file_config)

        # 3. 应用环境变量
        config_data = self._apply_env_vars(config_data)

        # 4. 转换为配置对象
        self._config = self._to_config_object(config_data)
        return self._config

    def _apply_env_vars(self, config: Dict) -> Dict:
        """应用环境变量替换"""
        # 递归替换 ${VAR:default} 格式
        def replace_env(value):
            if isinstance(value, str) and value.startswith("${"):
                match = re.match(r'\$\{(\w+):?([^}]*)\}', value)
                if match:
                    env_var, default = match.groups()
                    return os.getenv(env_var, default)
            return value

        return self._recursive_apply(config, replace_env)

    def get_feature(self, name: str, default: bool = False) -> bool:
        """获取特性开关"""
        return self._config.features.get(name, default)

    def get_layer_config(self, layer_name: str) -> Optional[LayerConfig]:
        """获取层配置"""
        return self._config.layers.get(layer_name)
```

---

## 6. 事件系统设计

### 6.1 事件类型

```python
# src/core/events/types.py

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional

@dataclass
class BaseEvent:
    """事件基类"""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class TaskCreatedEvent(BaseEvent):
    """任务创建事件"""
    task_id: str
    user_id: str
    query: str

@dataclass
class SearchStartedEvent(BaseEvent):
    """搜索开始事件"""
    task_id: str
    user_id: str
    search_type: str  # "langgraph" | "nl_search"

@dataclass
class SearchCompletedEvent(BaseEvent):
    """搜索完成事件"""
    task_id: str
    user_id: str
    result_count: int
    duration_ms: int

@dataclass
class SearchFailedEvent(BaseEvent):
    """搜索失败事件"""
    task_id: str
    user_id: str
    error: str

@dataclass
class AIProcessingStartedEvent(BaseEvent):
    """AI 处理开始事件"""
    task_id: str
    user_id: str

@dataclass
class AIProcessingCompletedEvent(BaseEvent):
    """AI 处理完成事件"""
    task_id: str
    user_id: str
    duration_ms: int

@dataclass
class LayerExecutionEvent(BaseEvent):
    """层执行事件"""
    layer_name: str
    layer_type: str
    status: str
    duration_ms: int
    details: Dict[str, Any] = field(default_factory=dict)
```

### 6.2 事件总线

```python
# src/core/events/bus.py

from typing import Callable, Dict, List, Any
from asyncio import Queue
import logging

logger = logging.getLogger(__name__)

EventHandler = Callable[[BaseEvent], Any]

class EventBus:
    """事件总线 - 支持发布/订阅模式"""

    def __init__(self):
        self._handlers: Dict[str, List[EventHandler]] = {}
        self._queue: Queue = Queue()
        self._running = False

    def subscribe(
        self,
        event_type: str,
        handler: EventHandler,
    ) -> None:
        """订阅事件"""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        logger.debug(f"Subscribed to {event_type}")

    def unsubscribe(
        self,
        event_type: str,
        handler: EventHandler,
    ) -> None:
        """取消订阅"""
        if event_type in self._handlers:
            self._handlers[event_type].remove(handler)

    async def publish(self, event: BaseEvent) -> None:
        """发布事件"""
        event_type = type(event).__name__
        handlers = self._handlers.get(event_type, [])

        for handler in handlers:
            try:
                result = handler(event)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"Event handler error: {e}")

        # 同时放入队列供异步处理
        await self._queue.put(event)

    async def start(self) -> None:
        """启动事件处理循环"""
        self._running = True
        while self._running:
            event = await self._queue.get()
            # 可在此添加事件持久化、日志等
            logger.info(f"Event processed: {type(event).__name__}")

    async def stop(self) -> None:
        """停止事件处理"""
        self._running = False
```

---

## 7. 扩展点设计

### 7.1 扩展点清单

| 扩展点 | 描述 | 实现方式 |
|--------|------|----------|
| 搜索引擎 | 添加新的搜索引擎 | 实现 ISearchLayer 接口 |
| AI 服务 | 替换 AI 服务 | 实现 IAILayer 接口 |
| 结果过滤 | 自定义过滤规则 | 实现 IFilterPlugin 接口 |
| 事件处理 | 添加审计/监控 | 实现 IEventPlugin 接口 |
| 中间件 | 请求/响应处理 | 实现 IMiddleware 接口 |
| 缓存策略 | 自定义缓存逻辑 | 实现 ICacheLayer 接口 |

### 7.2 扩展示例: 添加新搜索引擎

```python
# src/plugins/search/elasticsearch_plugin.py

class ElasticsearchSearchPlugin(ILayerPlugin):
    """Elasticsearch 搜索插件示例"""

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="elasticsearch-search",
            version="1.0.0",
            plugin_type=PluginType.LAYER,
            description="Elasticsearch search backend",
            author="Custom",
        )

    async def initialize(self, config: Dict[str, Any]) -> None:
        self._es_client = AsyncElasticsearch(
            hosts=config.get("hosts", ["localhost:9200"])
        )
        self._index = config.get("index", "search_results")

    async def shutdown(self) -> None:
        await self._es_client.close()

    def create_layer(self) -> ILayer:
        return ElasticsearchSearchLayer(
            client=self._es_client,
            index=self._index,
        )

class ElasticsearchSearchLayer(ISearchLayer):
    """Elasticsearch 搜索层实现"""

    @property
    def layer_name(self) -> str:
        return "elasticsearch-search"

    async def execute(self, context: LayerContext) -> SearchLayerResult:
        # Elasticsearch 搜索实现
        response = await self._client.search(
            index=self._index,
            body={
                "query": {
                    "multi_match": {
                        "query": context.query,
                        "fields": ["title", "content"],
                    }
                }
            }
        )

        results = [
            SearchResult(
                url=hit["_source"]["url"],
                title=hit["_source"]["title"],
                snippet=hit["_source"]["snippet"],
                score=hit["_score"],
            )
            for hit in response["hits"]["hits"]
        ]

        return SearchLayerResult(
            status="completed",
            results=results,
        )
```

### 7.3 扩展示例: 添加审计插件

```python
# src/plugins/audit/audit_plugin.py

class AuditPlugin(IEventPlugin):
    """审计插件 - 记录所有操作"""

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="audit",
            version="1.0.0",
            plugin_type=PluginType.EVENT,
            description="Audit logging for all operations",
            author="GuanShan",
        )

    @property
    def subscribed_events(self) -> List[str]:
        return [
            "TaskCreatedEvent",
            "SearchCompletedEvent",
            "AIProcessingCompletedEvent",
            "LayerExecutionEvent",
        ]

    async def initialize(self, config: Dict[str, Any]) -> None:
        self._audit_collection = get_audit_collection()

    async def shutdown(self) -> None:
        pass

    async def handle_event(self, event: BaseEvent) -> None:
        """记录审计日志"""
        await self._audit_collection.insert_one({
            "event_id": event.event_id,
            "event_type": type(event).__name__,
            "timestamp": event.timestamp,
            "data": asdict(event),
        })
```

---

## 8. 目录结构

### 8.1 推荐目录结构

```
src/
├── api/
│   └── v1/
│       └── endpoints/
│           └── chat.py                 # API 端点 (简化)
│
├── core/
│   ├── interfaces/                     # 核心接口
│   │   ├── __init__.py
│   │   ├── layer.py                    # ILayer, LayerContext, LayerResult
│   │   ├── search_layer.py             # ISearchLayer
│   │   ├── ai_layer.py                 # IAILayer
│   │   ├── orchestrator.py             # IOrchestrator
│   │   └── plugin.py                   # IPlugin, ILayerPlugin, etc.
│   │
│   ├── config/                         # 配置系统
│   │   ├── __init__.py
│   │   ├── loader.py                   # ConfigLoader
│   │   └── models.py                   # 配置数据模型
│   │
│   ├── events/                         # 事件系统
│   │   ├── __init__.py
│   │   ├── types.py                    # 事件类型
│   │   └── bus.py                      # EventBus
│   │
│   └── domain/
│       └── entities/                   # 领域实体
│
├── services/
│   ├── orchestrator.py                 # ChatOrchestrator 实现
│   │
│   ├── layers/                         # 层实现
│   │   ├── __init__.py
│   │   ├── search_engine_layer.py      # SearchEngineLayer
│   │   └── ai_processing_layer.py      # AIProcessingLayer
│   │
│   └── langgraph_search/               # LangGraph 搜索 (现有)
│       ├── service.py
│       ├── config.py
│       └── nodes/
│
├── plugins/                            # 插件目录
│   ├── __init__.py
│   ├── manager.py                      # PluginManager
│   │
│   ├── search/                         # 搜索层插件
│   │   ├── langgraph_plugin.py
│   │   └── nl_search_plugin.py
│   │
│   ├── ai/                             # AI 层插件
│   │   └── remote_ai_plugin.py
│   │
│   ├── filter/                         # 过滤器插件
│   │   ├── quality_filter_plugin.py
│   │   └── security_filter_plugin.py
│   │
│   └── audit/                          # 审计插件
│       └── audit_plugin.py
│
├── infrastructure/                     # 基础设施
│   ├── persistence/
│   │   └── repositories/
│   ├── llm/
│   └── crawlers/
│
└── config/                             # 配置文件
    └── settings.yaml
```

---

## 9. 迁移策略

### 9.1 渐进式迁移步骤

```
Phase 1: 接口定义 (不修改现有代码)
├── 创建 core/interfaces/ 目录
├── 定义所有接口
└── 无功能变化

Phase 2: 层封装 (封装现有代码)
├── 创建 SearchEngineLayer (封装现有逻辑)
├── 创建 AIProcessingLayer (封装现有逻辑)
└── 内部重构，外部无感知

Phase 3: 协调器引入
├── 创建 ChatOrchestrator
├── 修改 chat.py 使用协调器
└── 功能等价验证

Phase 4: 配置外部化
├── 创建 config/settings.yaml
├── 实现 ConfigLoader
└── 硬编码值迁移到配置

Phase 5: 插件系统
├── 实现 PluginManager
├── 将层转换为插件
└── 支持动态加载

Phase 6: 事件系统
├── 实现 EventBus
├── 添加事件发布
└── 添加审计插件
```

### 9.2 兼容性保证

```python
# 迁移期间保持 API 兼容

# chat.py - 过渡版本
@router.post("/chat/sync")
async def chat_sync_endpoint(...):
    # 使用特性开关控制新旧逻辑
    if config.get_feature("use_new_orchestrator"):
        return await orchestrator.execute_parallel(...)
    else:
        return await legacy_chat_handler(...)  # 原有逻辑
```

---

## 10. 验收标准

### 10.1 架构验收

| 编号 | 验收项 | 标准 |
|------|--------|------|
| AV-1 | 接口抽象 | 所有层实现统一接口 |
| AV-2 | 插件化 | 层可通过插件动态加载 |
| AV-3 | 配置驱动 | 行为可通过配置文件调整 |
| AV-4 | 事件驱动 | 关键操作发送事件 |
| AV-5 | 可测试性 | 各层可独立 Mock 测试 |

### 10.2 扩展性验收

| 编号 | 验收项 | 标准 |
|------|--------|------|
| EV-1 | 新增搜索引擎 | 无需修改核心代码 |
| EV-2 | 新增 AI 服务 | 无需修改核心代码 |
| EV-3 | 新增过滤器 | 通过插件注册 |
| EV-4 | 新增事件处理 | 通过订阅机制 |

---

## 11. 附录

### 11.1 相关文档

| 文档 | 说明 |
|------|------|
| LAYER_SEPARATION_REQUIREMENTS_V5.0.0.md | 层分离需求分析 |
| INTELLIGENT_SEARCH_FLOW_V4.6.0.md | 现有架构文档 |
| requirements.md | 搜索系统需求 |

### 11.2 版本历史

| 版本 | 日期 | 作者 | 变更说明 |
|------|------|------|----------|
| v5.0.0 | 2025-01-14 | Claude (Architect) | 可扩展系统架构设计 |
