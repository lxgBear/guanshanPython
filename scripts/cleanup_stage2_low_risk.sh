#!/bin/bash
# cleanup_stage2_low_risk.sh
# 阶段2: 低风险清理 - 过期备份和测试脚本
# 生成时间: 2025-11-14
# 风险等级: 🟡 低风险（需确认）

set -e  # 遇到错误立即退出

echo "╔════════════════════════════════════════════════════════════╗"
echo "║     关山项目代码清理 - 阶段2: 低风险清理                    ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# 记录开始时间
START_TIME=$(date +%s)

# 进入项目根目录
cd "$(dirname "$0")/.."

# 1. 归档过期备份
echo "🗄️  [1/2] 归档过期备份目录..."
echo ""

ARCHIVE_NAME="backup_archive_$(date +%Y%m%d_%H%M%S).tar.gz"
BACKUP_EXISTS=0

# 检查是否有备份目录需要归档
if [ -d ".backup" ] || [ -d "backups" ]; then
    BACKUP_EXISTS=1

    echo "发现以下备份目录:"
    if [ -d ".backup" ]; then
        BACKUP_SIZE=$(du -sh .backup | cut -f1)
        echo "  - .backup/ ($BACKUP_SIZE)"
        BACKUP_AGE=$(find .backup -type f -exec stat -f "%Sm" -t "%Y-%m-%d" {} \; | sort -u | tail -1)
        echo "    最新文件日期: $BACKUP_AGE"
    fi

    if [ -d "backups" ]; then
        BACKUPS_SIZE=$(du -sh backups | cut -f1)
        echo "  - backups/ ($BACKUPS_SIZE)"
        BACKUPS_AGE=$(find backups -type f -exec stat -f "%Sm" -t "%Y-%m-%d" {} \; | sort -u | tail -1)
        echo "    最新文件日期: $BACKUPS_AGE"
    fi
    echo ""

    # 确认是否归档
    read -p "是否创建归档文件 $ARCHIVE_NAME？(y/n) " -n 1 -r
    echo ""

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "正在创建归档..."
        tar -czf "$ARCHIVE_NAME" .backup/ backups/ 2>/dev/null || true

        if [ -f "$ARCHIVE_NAME" ]; then
            ARCHIVE_SIZE=$(du -sh "$ARCHIVE_NAME" | cut -f1)
            echo "  ✅ 已创建归档: $ARCHIVE_NAME ($ARCHIVE_SIZE)"
            echo "  📁 位置: $(pwd)/$ARCHIVE_NAME"
            echo ""

            # 确认是否删除原目录
            read -p "确认删除 .backup/ 和 backups/ 目录吗？(y/n) " -n 1 -r
            echo ""

            if [[ $REPLY =~ ^[Yy]$ ]]; then
                rm -rf .backup/ backups/
                echo "  ✅ 备份目录已删除"
                echo ""
                echo "  💡 恢复命令: tar -xzf $ARCHIVE_NAME"
            else
                echo "  ⏸️  保留备份目录"
            fi
        else
            echo "  ❌ 归档创建失败"
        fi
    else
        echo "  ⏸️  跳过归档"
    fi
else
    echo "  ℹ️  未发现备份目录，跳过此步骤"
fi

echo ""

# 2. 移动测试脚本到archive
echo "📦 [2/2] 移动一次性测试脚本到archive..."
echo ""

ARCHIVE_DIR="scripts/archive/test_scripts_$(date +%Y%m%d)"
mkdir -p "$ARCHIVE_DIR"

# 统计test_*.py脚本
TEST_SCRIPT_COUNT=$(find scripts -maxdepth 1 -name "test_*.py" -type f | wc -l | tr -d ' ')

if [ "$TEST_SCRIPT_COUNT" -gt 0 ]; then
    echo "发现 $TEST_SCRIPT_COUNT 个 test_*.py 脚本"
    echo ""
    echo "脚本列表:"
    find scripts -maxdepth 1 -name "test_*.py" -type f -exec basename {} \; | sort | sed 's/^/  - /'
    echo ""

    read -p "是否移动这些测试脚本到 $ARCHIVE_DIR？(y/n) " -n 1 -r
    echo ""

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        MOVED_COUNT=0
        for script in scripts/test_*.py; do
            if [ -f "$script" ]; then
                mv "$script" "$ARCHIVE_DIR/"
                ((MOVED_COUNT++))
            fi
        done
        echo "  ✅ 已移动 $MOVED_COUNT 个测试脚本"
    else
        echo "  ⏸️  保留测试脚本"
    fi
else
    echo "  ℹ️  未发现test_*.py脚本"
fi

echo ""

# 询问是否移动check_*.py和analyze_*.py脚本
CHECK_SCRIPT_COUNT=$(find scripts -maxdepth 1 \( -name "check_*.py" -o -name "analyze_*.py" -o -name "verify_*.py" -o -name "validate*.py" \) -type f | wc -l | tr -d ' ')

if [ "$CHECK_SCRIPT_COUNT" -gt 0 ]; then
    echo "发现 $CHECK_SCRIPT_COUNT 个检查/验证脚本:"
    find scripts -maxdepth 1 \( -name "check_*.py" -o -name "analyze_*.py" -o -name "verify_*.py" -o -name "validate*.py" \) -type f -exec basename {} \; | sort | sed 's/^/  - /'
    echo ""

    read -p "是否也移动这些脚本到archive？(y/n) " -n 1 -r
    echo ""

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        MOVED_COUNT=0
        for script in scripts/check_*.py scripts/analyze_*.py scripts/verify_*.py scripts/validate*.py; do
            if [ -f "$script" ]; then
                mv "$script" "$ARCHIVE_DIR/" 2>/dev/null || true
                ((MOVED_COUNT++))
            fi
        done
        echo "  ✅ 已移动 $MOVED_COUNT 个检查/验证脚本"
    else
        echo "  ⏸️  保留检查/验证脚本"
    fi
fi

echo ""

# 显示archive目录内容
if [ -d "$ARCHIVE_DIR" ] && [ "$(ls -A $ARCHIVE_DIR 2>/dev/null)" ]; then
    ARCHIVE_COUNT=$(ls -1 "$ARCHIVE_DIR" | wc -l | tr -d ' ')
    echo "📋 归档目录内容 ($ARCHIVE_COUNT 个文件):"
    ls -1 "$ARCHIVE_DIR" | sed 's/^/  - /'
    echo ""
fi

# 计算清理时间
END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))

# 显示清理结果
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                    清理完成统计                              ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

if [ -f "$ARCHIVE_NAME" ]; then
    echo "  备份归档:     已创建 ($ARCHIVE_NAME)"
else
    echo "  备份归档:     未创建"
fi

if [ -d "$ARCHIVE_DIR" ]; then
    SCRIPT_COUNT=$(ls -1 "$ARCHIVE_DIR" 2>/dev/null | wc -l | tr -d ' ')
    echo "  脚本归档:     $SCRIPT_COUNT 个文件"
else
    echo "  脚本归档:     0 个文件"
fi

echo "  总耗时:       ${ELAPSED}秒"
echo ""

echo "✅ 阶段2清理完成！"
echo ""
echo "💡 下一步:"
echo "  1. 再次运行 uvicorn src.main:app --reload 验证系统"
echo "  2. 测试核心功能（创建任务、执行搜索）"
echo "  3. 执行 cleanup_stage3_git_commit.sh 提交代码"
echo ""
