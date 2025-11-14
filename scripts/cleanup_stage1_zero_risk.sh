#!/bin/bash
# cleanup_stage1_zero_risk.sh
# 阶段1: 零风险清理 - 临时文件、覆盖率报告、空目录
# 生成时间: 2025-11-14
# 风险等级: 🟢 零风险

set -e  # 遇到错误立即退出

echo "╔════════════════════════════════════════════════════════════╗"
echo "║     关山项目代码清理 - 阶段1: 零风险清理                    ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# 记录开始时间
START_TIME=$(date +%s)

# 进入项目根目录
cd "$(dirname "$0")/.."

# 1. 删除根目录临时文件
echo "📝 [1/3] 清理根目录临时日志和JSON文件..."
FILES_REMOVED=0

if [ -f "api.log" ]; then
    echo "  - 删除 api.log"
    rm -f api.log
    ((FILES_REMOVED++))
fi

if [ -f "uvicorn.log" ]; then
    echo "  - 删除 uvicorn.log"
    rm -f uvicorn.log
    ((FILES_REMOVED++))
fi

if [ -f "test_url_filtering_output.log" ]; then
    echo "  - 删除 test_url_filtering_output.log"
    rm -f test_url_filtering_output.log
    ((FILES_REMOVED++))
fi

# 删除crawl_result_*.json文件
for json_file in crawl_result_*.json; do
    if [ -f "$json_file" ]; then
        echo "  - 删除 $json_file"
        rm -f "$json_file"
        ((FILES_REMOVED++))
    fi
done

echo "  ✅ 删除了 $FILES_REMOVED 个临时文件"
echo ""

# 2. 删除覆盖率报告
echo "📊 [2/3] 清理覆盖率报告..."
COVERAGE_REMOVED=0

if [ -d "htmlcov" ]; then
    COVERAGE_SIZE=$(du -sh htmlcov | cut -f1)
    echo "  - 删除 htmlcov/ ($COVERAGE_SIZE)"
    rm -rf htmlcov
    ((COVERAGE_REMOVED++))
fi

if [ -f ".coverage" ]; then
    COVERAGE_FILE_SIZE=$(du -sh .coverage | cut -f1)
    echo "  - 删除 .coverage ($COVERAGE_FILE_SIZE)"
    rm -f .coverage
    ((COVERAGE_REMOVED++))
fi

echo "  ✅ 删除了 $COVERAGE_REMOVED 个覆盖率相关项"
echo ""

# 3. 删除空目录
echo "📂 [3/3] 清理空目录..."
DIRS_REMOVED=0

if [ -d "archive" ]; then
    # 检查archive目录是否为空或只包含空子目录
    if [ -z "$(find archive -type f)" ]; then
        echo "  - 删除 archive/ (空目录)"
        rm -rf archive
        ((DIRS_REMOVED++))
    else
        echo "  ⚠️  archive/ 包含文件，跳过删除"
    fi
fi

echo "  ✅ 删除了 $DIRS_REMOVED 个空目录"
echo ""

# 计算清理时间
END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))

# 显示清理结果
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                    清理完成统计                              ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "  临时文件:     $FILES_REMOVED 个"
echo "  覆盖率报告:   $COVERAGE_REMOVED 个"
echo "  空目录:       $DIRS_REMOVED 个"
echo "  总耗时:       ${ELAPSED}秒"
echo ""

# 验证清理结果
echo "📋 验证根目录文件..."
echo "剩余文件（不包括隐藏文件和目录）:"
ls -lh | grep "^-" | awk '{print "  - " $9 " (" $5 ")"}'
echo ""

echo "✅ 阶段1清理完成！"
echo ""
echo "💡 下一步:"
echo "  1. 运行 uvicorn src.main:app --reload 验证系统启动"
echo "  2. 检查 logs/uvicorn.log 确认无错误"
echo "  3. 执行 cleanup_stage2_low_risk.sh 继续清理"
echo ""
