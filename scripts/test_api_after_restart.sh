#!/bin/bash
# NL Search API 重启后测试脚本

echo "=========================================="
echo "NL Search MongoDB 迁移 - API 测试"
echo "=========================================="
echo ""

# 测试 1: 状态检查
echo "测试 1: 检查 NL Search 状态"
curl -s "http://127.0.0.1:8000/api/v1/nl-search/status" | python3 -m json.tool || echo "❌ 状态接口失败"
echo ""

# 测试 2: 获取搜索历史
echo "测试 2: 获取搜索历史列表"
curl -s "http://127.0.0.1:8000/api/v1/nl-search?limit=2&offset=0" | python3 -m json.tool | head -30 || echo "❌ 列表接口失败"
echo ""

# 测试 3: 健康检查
echo "测试 3: 系统健康检查"
curl -s "http://127.0.0.1:8000/health" | python3 -m json.tool || echo "❌ 健康检查失败"
echo ""

echo "=========================================="
echo "测试完成"
echo "=========================================="
