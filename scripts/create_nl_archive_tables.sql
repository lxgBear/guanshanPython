-- ============================================
-- NL Search 用户档案系统数据库表
-- 版本: v1.0.0
-- 创建日期: 2025-11-17
-- 用途: 存储用户创建的档案和档案条目
-- ============================================

-- 档案主表：存储档案元数据
CREATE TABLE IF NOT EXISTS nl_user_archives (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '档案唯一ID',
    user_id BIGINT NOT NULL COMMENT '用户ID（关联用户系统）',
    archive_name VARCHAR(255) NOT NULL COMMENT '档案名称（用户命名）',
    description TEXT NULL COMMENT '档案描述（可选）',
    tags JSON NULL COMMENT '档案标签（可选，JSON数组）',
    search_log_id BIGINT NULL COMMENT '关联的搜索记录ID（可选，nl_search_logs表）',
    items_count INT DEFAULT 0 COMMENT '档案中的条目数量',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间',

    -- 索引
    INDEX idx_user_id (user_id) COMMENT '用户查询索引',
    INDEX idx_search_log_id (search_log_id) COMMENT '搜索记录关联索引',
    INDEX idx_created_at (created_at DESC) COMMENT '创建时间索引（降序）',

    -- 外键约束（可选，依赖用户系统表）
    -- FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (search_log_id) REFERENCES nl_search_logs(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='NL Search 用户档案主表';

-- 档案条目表：存储档案中的具体新闻条目
CREATE TABLE IF NOT EXISTS nl_user_selections (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '条目唯一ID',
    archive_id BIGINT NOT NULL COMMENT '所属档案ID',
    user_id BIGINT NOT NULL COMMENT '用户ID（冗余存储，便于查询）',
    news_result_id VARCHAR(255) NOT NULL COMMENT '新闻结果ID（MongoDB中的ObjectId）',

    -- 用户编辑字段
    edited_title VARCHAR(500) NULL COMMENT '用户编辑后的标题（可选）',
    edited_summary TEXT NULL COMMENT '用户编辑后的摘要（可选）',
    user_notes TEXT NULL COMMENT '用户备注（可选）',
    user_rating INT NULL COMMENT '用户评分（1-5，可选）',

    -- 快照存储（防止原始数据被删除）
    snapshot_data JSON NOT NULL COMMENT '原始新闻数据快照（完整JSON）',
    -- snapshot_data 结构示例：
    -- {
    --   "original_title": "新闻原始标题",
    --   "original_content": "新闻原始内容",
    --   "category": {"大类": "安全情报", "类别": "维稳", "地域": "东亚"},
    --   "published_at": "2023-10-23T12:00:00",
    --   "source": "example.com",
    --   "media_urls": ["https://example.com/image1.jpg"]
    -- }

    -- 显示顺序
    display_order INT DEFAULT 0 COMMENT '档案内显示顺序（用户可调整）',

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '添加到档案的时间',

    -- 索引
    INDEX idx_archive_id (archive_id) COMMENT '档案查询索引',
    INDEX idx_user_id (user_id) COMMENT '用户查询索引',
    INDEX idx_news_result_id (news_result_id) COMMENT '新闻结果关联索引',
    INDEX idx_display_order (archive_id, display_order) COMMENT '显示顺序索引',

    -- 外键约束
    FOREIGN KEY (archive_id) REFERENCES nl_user_archives(id) ON DELETE CASCADE,

    -- 唯一约束：同一档案内不允许重复添加同一新闻
    UNIQUE KEY uk_archive_news (archive_id, news_result_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='NL Search 用户档案条目表';

-- ============================================
-- 初始化统计信息
-- ============================================

-- 创建触发器：自动更新档案条目数量
DELIMITER $$

CREATE TRIGGER trg_archive_items_insert
AFTER INSERT ON nl_user_selections
FOR EACH ROW
BEGIN
    UPDATE nl_user_archives
    SET items_count = items_count + 1,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = NEW.archive_id;
END$$

CREATE TRIGGER trg_archive_items_delete
AFTER DELETE ON nl_user_selections
FOR EACH ROW
BEGIN
    UPDATE nl_user_archives
    SET items_count = items_count - 1,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = OLD.archive_id;
END$$

DELIMITER ;

-- ============================================
-- 验证语句（可选执行）
-- ============================================

-- 查看表结构
-- DESCRIBE nl_user_archives;
-- DESCRIBE nl_user_selections;

-- 查看索引
-- SHOW INDEX FROM nl_user_archives;
-- SHOW INDEX FROM nl_user_selections;

-- 查看触发器
-- SHOW TRIGGERS LIKE 'nl_user_%';
