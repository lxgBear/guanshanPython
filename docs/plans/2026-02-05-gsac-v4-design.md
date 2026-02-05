# GSAC V4 设计文档

## 版本信息
- 日期: 2026-02-05
- 版本: V4

## 主要改动

### 1. 相关性验证状态变更

**旧状态** (V3):
- `keep` - 保留
- `downgrade` - 降级
- `discard` - 丢弃

**新状态** (V4):
- `high_relevance` - 与事件高度吻合 (置信度 >= 0.5)
- `low_relevance` - 明显无关内容 (置信度 < 0.5)

**改动原因**:
- 保留所有搜索结果，不再丢弃
- 由下游模块/前端决定如何使用低相关性结果
- 便于后续分析和审计

**影响的模型**:
- `RelevanceResult.relevance`: `Literal["high_relevance", "low_relevance"]`
- `ClassifiedSource.relevance_status`: `Literal["high_relevance", "low_relevance"]`

### 2. 日志增强

在以下节点增加了详细日志，便于服务器排查问题:

#### scrape_single_url 节点
- `scrape_start`: 开始抓取
- `scrape_attempt`: 抓取尝试
- `scrape_success`: 抓取成功（含内容长度）
- `scrape_empty_content`: 返回空内容
- `scrape_error`: 抓取异常
- `scrape_final_failure`: 最终失败

#### validate_relevance 节点
- `validate_relevance_input`: 输入状态
- `validate_relevance_config`: 验证配置
- `validate_relevance_item`: 每条结果验证详情
- `validate_relevance_summary`: 验证汇总

#### classify_sources 节点
- `classify_sources_input`: 输入状态
- `classify_sources_llm_input`: LLM输入
- `classify_sources_llm_result`: LLM返回数量
- `classify_sources_item`: 每条分类结果
- `classify_sources_summary`: 分类汇总
- `classify_sources_llm_error`: LLM错误
- `classify_sources_fallback_summary`: 降级分类汇总

### 3. 部署脚本优化

解决的问题:
- 镜像缓存导致代码不更新
- 旧容器没有完全清理
- 悬空镜像占用空间

新增功能:
```bash
./deploy.sh          # 完整部署（清理+强制重建+测试）
./deploy.sh quick    # 快速部署（使用缓存）
./deploy.sh restart  # 仅重启应用容器
./deploy.sh logs     # 查看实时日志
./deploy.sh clean    # 仅清理旧容器和镜像
./deploy.sh health   # 仅执行健康检查
```

清理策略:
1. `docker-compose down --remove-orphans` - 移除孤立容器
2. `docker container prune -f` - 移除停止的容器
3. `docker image prune -f` - 移除悬空镜像
4. 移除旧的 guanshan 应用镜像
5. `docker-compose build --no-cache --pull` - 强制重建不使用缓存
6. `docker-compose up -d --force-recreate` - 强制重建容器

## 向后兼容性

- `discarded_count` 字段保留，值始终为 0
- 底层 `calculate_relevance_score` 仍返回 `keep/downgrade/discard`
- 在节点层做状态映射: `keep` -> `high_relevance`, `downgrade/discard` -> `low_relevance`
