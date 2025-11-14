#!/bin/bash
# v2.1.1 修复验证监控脚本
# 监控任务 244887942339018752 的执行，验证 waitFor/timeout 修复效果

TASK_ID="244887942339018752"
LOG_FILE="/Users/lanxionggao/Documents/guanshanPython/logs/uvicorn.log"
REPORT_FILE="/Users/lanxionggao/Documents/guanshanPython/logs/v211_fix_verification_$(date +%Y%m%d_%H%M%S).log"

echo "=========================================="
echo "v2.1.1 修复验证监控"
echo "任务 ID: $TASK_ID"
echo "开始时间: $(date)"
echo "=========================================="
echo ""

# 监控关键日志模式
echo "📡 开始监控任务执行日志..."
echo "等待任务在 03:00:00 自动执行..."
echo ""

# 监控 10 分钟（足够任务完成）
timeout 600 tail -f "$LOG_FILE" | while read line; do
    # 检查任务 ID
    if echo "$line" | grep -q "$TASK_ID"; then
        echo "$line" | tee -a "$REPORT_FILE"
    fi

    # 检查关键参数
    if echo "$line" | grep -q "waitFor"; then
        echo "🔍 [PARAMETER] $line" | tee -a "$REPORT_FILE"
    fi

    # 检查成功率
    if echo "$line" | grep -q "成功率"; then
        echo "📊 [SUCCESS RATE] $line" | tee -a "$REPORT_FILE"
    fi

    # 检查 Scrape 完成
    if echo "$line" | grep -q "Scrape.*完成"; then
        echo "✅ [COMPLETE] $line" | tee -a "$REPORT_FILE"
    fi

    # 检查错误
    if echo "$line" | grep -q "Failed to scrape"; then
        echo "❌ [ERROR] $line" | tee -a "$REPORT_FILE"
    fi
done

echo ""
echo "=========================================="
echo "监控结束时间: $(date)"
echo "报告文件: $REPORT_FILE"
echo "=========================================="
