# 关山Python项目文档中心

**版本**: v2.1.3
**最后更新**: 2025-11-21
**文档总数**: 27 个活动文档 + 8 个归档文档

---

## 📚 文档导航

### 🏗️ 核心系统文档 (`core/`)

基础架构、数据库设计和系统级重构文档。

| 文档 | 描述 | 更新日期 |
|------|------|----------|
| [数据库设置指南](core/DATABASE_SETUP_GUIDE.md) | MongoDB 数据库配置和初始化 | 2025-11 |
| [API 综合分析报告](core/API_COMPREHENSIVE_ANALYSIS_REPORT.md) | 项目 API 架构和端点分析 | 2025-11 |
| [Repository 重构 V3](core/REPOSITORY_REFACTORING_V3_SUMMARY.md) | 数据访问层重构总结 | 2025-11 |

---

### ✨ 功能模块文档 (`features/`)

#### 🔍 NL Search (自然语言搜索) - `features/nl-search/`

完整的自然语言搜索系统，包含 LLM 分析和用户选择跟踪。

| 文档 | 描述 | 更新日期 |
|------|------|----------|
| [**NL Search 主指南**](features/nl-search/NL_SEARCH_MASTER_GUIDE.md) ⭐ | **综合实现指南** - API、数据库、实现细节 | 2025-11-17 |
| [API 配置指南](features/nl-search/NL_SEARCH_API_CONFIGURATION_GUIDE.md) | API 端点配置和使用说明 | 2025-11 |
| [归档系统设计](features/nl-search/NL_SEARCH_ARCHIVE_SYSTEM_DESIGN.md) | 搜索结果归档架构 | 2025-11 |
| [MongoDB 迁移指南](features/nl-search/NL_SEARCH_MONGODB_MIGRATION.md) | 数据库迁移步骤 | 2025-11 |
| [API 测试报告](features/nl-search/NL_SEARCH_API_TEST_REPORT.md) | 功能测试结果 | 2025-11 |
| [关系图](features/nl-search/nl_search_relations.md) | 数据关系快速参考 | 2025-11 |
| [**去重分析报告**](features/nl-search/Deduplication_Analysis_Report.md) | URL 和内容去重机制分析 | 2025-11-21 |
| [**去重实施总结**](features/nl-search/Deduplication_Implementation_Summary.md) | 去重功能实施详情和效果评估 | 2025-11-21 |
| [GPT-5 API 分析](features/nl-search/gpt5_search_api_analysis.md) | GPT-5 Search API 配置和 response_format | 2025-11-20 |
| [PDF 过滤验证](features/nl-search/PDF_Filter_Verification_Report.md) | PDF URL 过滤功能验证报告 | 2025-11-21 |

**核心功能**:
- 5 个 API 端点（查询搜索日志、查看单条日志、提交用户选择等）
- 2 个 MongoDB 集合（nl_search_logs、user_selection_events）
- 完整的 Repository-Service-API 三层架构
- LLM 驱动的查询分析和搜索结果排序

---

#### 👤 User Curation (用户精选) - `features/user-curation/`

用户批量编辑和内容精选系统。

| 文档 | 描述 | 更新日期 |
|------|------|----------|
| [**用户精选完整指南**](features/user-curation/USER_CURATION_COMPLETE_GUIDE.md) ⭐ | **综合方案对比** - 简化批量编辑 vs 完整工作流 | 2025-11-18 |
| [批量编辑实现总结](features/user-curation/BATCH_EDIT_IMPLEMENTATION_SUMMARY.md) | 批量编辑功能实现细节 | 2025-11 |
| [快速参考](features/user-curation/USER_CURATION_QUICK_REFERENCE.md) | API 和功能速查表 | 2025-11 |

**核心功能**:
- **方案一**: 简化批量编辑（5 个 API 端点，3-5 天开发）
- **方案二**: 完整精选工作流（11 个 API 端点，10-13 天开发，包含审核流程）
- 数据模型：user_edited_results 或 curated_search_results
- 批量操作、版本历史、编辑审核等功能

---

#### 🕷️ Web Crawling (网页爬取) - `features/crawling/`

Map+Scrape 执行器和 URL 过滤系统。

| 文档 | 描述 | 更新日期 |
|------|------|----------|
| [Map+Scrape 实现 (v2.1.0-v2.1.2)](features/crawling/MAP_SCRAPE_IMPLEMENTATION_V2.1.0-V2.1.2.md) | 地图爬取和内容抓取实现 | 2025-11 |
| [URL 限制功能 (v2.1.3)](features/crawling/URL_LIMITING_FEATURE_V2.1.3.md) | URL 过滤和限制系统 | 2025-11 |
| [时间范围分析](features/crawling/CRAWL_WEBSITE_TIME_RANGE_ANALYSIS.md) | 爬取时间范围功能分析 | 2025-11 |

**核心功能**:
- Map+Scrape 双执行器架构
- URL 白名单/黑名单过滤系统
- 时间范围查询优化
- 性能监控和错误处理

---

#### 🧹 Cleanup Tools (清理工具) - `features/cleanup/`

数据清理和维护脚本。

| 文档 | 描述 | 更新日期 |
|------|------|----------|
| [清理 Pending 记录指南](features/cleanup/CLEANUP_PENDING_RECORDS_GUIDE.md) | pending 状态记录清理工具使用说明 | 2025-11-18 |
| [清理脚本实现总结](features/cleanup/CLEANUP_SCRIPT_SUMMARY_2025-11-18.md) | 清理脚本技术实现细节 | 2025-11-18 |

**核心功能**:
- `cleanup_pending_news_results.py` 脚本
- Dry-run 预览模式
- 按时间过滤（--days 参数）
- 删除确认和结果验证

---

### 📦 版本发布文档 (`releases/`)

项目版本历史和发布说明。

| 文档 | 描述 | 版本 |
|------|------|------|
| [V2.1.1 完整总结](releases/V2.1.1_COMPLETE_SUMMARY.md) | v2.1.1 版本完整发布说明和 bug 修复 | v2.1.1 |
| [API 文档更新](releases/API_DOCUMENTATION_UPDATE_v2.1.0.md) | v2.1.0 API 文档更新 | v2.1.0 |
| [归档系统 MongoDB 完成](releases/ARCHIVE_SYSTEM_MONGODB_COMPLETION.md) | 归档系统 MongoDB 实现完成 | 2025-11 |

---

### 📦 归档文档 (`archived/2025-11-pre-cleanup/`)

历史文档归档（2025-11-18 之前的版本）。

共 8 个归档文档（约 153KB），包括早期的 NL Search 实现路线图、阶段性完成报告、代码清理分析和旧的文档清理计划。

---

## 🚀 快速开始

### 新开发者入门

1. **了解项目架构**: 阅读 [API 综合分析报告](core/API_COMPREHENSIVE_ANALYSIS_REPORT.md)
2. **设置数据库**: 参考 [数据库设置指南](core/DATABASE_SETUP_GUIDE.md)
3. **理解核心功能**:
   - NL Search: [主指南](features/nl-search/NL_SEARCH_MASTER_GUIDE.md)
   - User Curation: [完整指南](features/user-curation/USER_CURATION_COMPLETE_GUIDE.md)

### 功能开发者

- **开发 NL Search 功能**: 参考 [NL Search 主指南](features/nl-search/NL_SEARCH_MASTER_GUIDE.md)
- **开发用户编辑功能**: 参考 [用户精选完整指南](features/user-curation/USER_CURATION_COMPLETE_GUIDE.md)
- **爬虫功能**: 参考 [Map+Scrape 实现](features/crawling/MAP_SCRAPE_IMPLEMENTATION_V2.1.0-V2.1.2.md)

### 运维维护

- **数据清理**: 参考 [清理 Pending 记录指南](features/cleanup/CLEANUP_PENDING_RECORDS_GUIDE.md)
- **数据库迁移**: 参考 [MongoDB 迁移指南](features/nl-search/NL_SEARCH_MONGODB_MIGRATION.md)

---

## 📊 文档统计

### 文档分布

| 类别 | 文档数量 | 主要内容 |
|------|---------|---------|
| 核心系统 (`core/`) | 3 | 架构、数据库、重构 |
| NL Search (`features/nl-search/`) | 10 | 自然语言搜索系统 |
| User Curation (`features/user-curation/`) | 3 | 用户编辑和精选 |
| Web Crawling (`features/crawling/`) | 3 | 爬虫和过滤 |
| Cleanup Tools (`features/cleanup/`) | 2 | 数据清理脚本 |
| Releases (`releases/`) | 3 | 版本发布说明 |
| Archived (`archived/`) | 8 | 历史归档 |
| **总计** | **32** | **活动文档: 24** |

### 文档健康度

✅ **优秀**: 文档结构清晰，内容完整，定期更新
✅ **已整合**: 2 个主要整合文档（NL Search、User Curation）
✅ **已归档**: 8 个历史文档已归档保存
✅ **组织良好**: 按功能模块分类，易于导航
✅ **最近清理**: 2025-11-21 完成根目录整理

---

## 🔍 文档搜索指南

### 按主题查找

| 主题 | 推荐文档 |
|------|---------|
| **API 设计** | [API 综合分析报告](core/API_COMPREHENSIVE_ANALYSIS_REPORT.md), [NL Search 主指南](features/nl-search/NL_SEARCH_MASTER_GUIDE.md) |
| **数据库设计** | [数据库设置指南](core/DATABASE_SETUP_GUIDE.md), [NL Search 主指南](features/nl-search/NL_SEARCH_MASTER_GUIDE.md) |
| **MongoDB 集合** | nl_search_logs, user_selection_events, user_edited_results |
| **实现细节** | 各功能模块的主指南文档 |
| **测试和部署** | [NL Search API 测试报告](features/nl-search/NL_SEARCH_API_TEST_REPORT.md) |
| **运维脚本** | [清理工具指南](features/cleanup/) |

### 按技术栈查找

- **FastAPI**: 所有 API 文档
- **MongoDB**: 数据库相关文档（core/, features/nl-search/）
- **Pydantic**: 数据模型相关文档
- **LLM/AI**: [NL Search 主指南](features/nl-search/NL_SEARCH_MASTER_GUIDE.md)
- **Web Scraping**: [features/crawling/](features/crawling/)

---

## 📝 文档维护指南

### 添加新文档

1. 确定文档类别（core/features/releases）
2. 放置在相应目录
3. 更新本 README 的相关部分
4. 更新文档统计

### 更新现有文档

1. 修改文档内容
2. 更新文档头部的"最后更新"日期
3. 如有重大变更，在 [CHANGELOG.md](CHANGELOG.md) 中记录

### 归档旧文档

1. 评估文档是否过时或已被新文档取代
2. 移动到 `archived/YYYY-MM-description/` 目录
3. 更新 README 归档部分
4. 保留 git 历史记录

---

## 🔗 相关链接

- **项目根目录**: `/Users/lanxionggao/Documents/guanshanPython`
- **源代码**: `src/`
- **测试**: `tests/`
- **脚本**: `scripts/`
- **文档**: `claudedocs/` (当前目录)

---

## 📞 联系和贡献

**文档维护**: Claude Code
**最近清理**: 2025-11-21
**清理计划**: [DOCUMENTATION_CONSOLIDATION_PLAN_2025-11-21.md](DOCUMENTATION_CONSOLIDATION_PLAN_2025-11-21.md)

---

**文档版本**: v1.0.0
**创建日期**: 2025-11-18
**文档结构**: 分层组织（core → features → releases → archived）
