-- ===================================================================
-- NL Search 数据表创建脚本 (简化版)
-- ===================================================================
-- 版本: v1.0.0-beta
-- 日期: 2025-11-14
-- 说明: 创建自然语言搜索所需的数据表和索引
-- ===================================================================

-- 1. 创建 nl_search_logs 表
CREATE TABLE IF NOT EXISTS nl_search_logs (
  id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
  query_text TEXT NOT NULL COMMENT '原始用户输入',
  llm_analysis JSON NULL COMMENT '大模型解析结构（关键词、实体、时间范围等）',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',

  -- 索引
  INDEX idx_created (created_at DESC) COMMENT '时间排序索引'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='自然语言搜索记录表（简化版）';

-- 2. 验证表创建
SELECT
  TABLE_NAME as '表名',
  TABLE_COMMENT as '表注释',
  ENGINE as '存储引擎',
  TABLE_COLLATION as '排序规则',
  CREATE_TIME as '创建时间'
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME = 'nl_search_logs';

-- 3. 验证索引
SHOW INDEX FROM nl_search_logs;

-- 4. 查看表结构
DESC nl_search_logs;

-- ===================================================================
-- 可选：扩展 search_results 表（如需关联）
-- ===================================================================
-- 说明: 如果需要将 NL Search 与现有 search_results 表关联，
--      可以添加 nl_search_log_id 字段。
--      ⚠️ 当前为可选功能，不影响核心功能。
-- ===================================================================

-- ALTER TABLE search_results
-- ADD COLUMN nl_search_log_id BIGINT NULL COMMENT '关联的NL搜索记录ID',
-- ADD INDEX idx_nl_search_log (nl_search_log_id);

-- ===================================================================
-- 可选：创建关联表 (高级功能)
-- ===================================================================
-- 说明: 如果需要多对多关系（一个 NL Search 对应多个结果），
--      可以创建独立的关联表。
--      ⚠️ 当前为可选功能，Phase 1 不实现。
-- ===================================================================

-- CREATE TABLE IF NOT EXISTS nl_search_result_relations (
--   id BIGINT AUTO_INCREMENT PRIMARY KEY,
--   nl_search_log_id BIGINT NOT NULL COMMENT 'NL搜索记录ID',
--   result_id BIGINT NOT NULL COMMENT '搜索结果ID',
--   result_type ENUM('search_result', 'news_result') DEFAULT 'search_result',
--   created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
--   INDEX idx_log (nl_search_log_id),
--   INDEX idx_result (result_id, result_type),
--   UNIQUE KEY uk_log_result (nl_search_log_id, result_id, result_type)
-- ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ===================================================================
-- 数据验证查询
-- ===================================================================

-- 查看当前数据库中的所有表
SHOW TABLES LIKE '%nl_search%';

-- 统计 NL Search 记录数
-- SELECT COUNT(*) as total_records FROM nl_search_logs;

-- ===================================================================
-- 完成
-- ===================================================================
-- 执行成功后，nl_search_logs 表已创建完成。
-- 可以开始使用 NLSearchLogRepository 进行数据操作。
-- ===================================================================
