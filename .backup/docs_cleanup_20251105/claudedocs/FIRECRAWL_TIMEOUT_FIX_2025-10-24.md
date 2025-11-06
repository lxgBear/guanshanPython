# Firecrawl 超时配置修复记录

**修复时间**: 2025-10-24 15:34
**问题单号**: 任务 #240011812325298176 失败分析
**执行人员**: Claude Code Backend Analyst

---

## 修复内容

### 配置变更

**文件**: `.env`
**行号**: 68

```diff
- FIRECRAWL_TIMEOUT=30
+ FIRECRAWL_TIMEOUT=60
```

### 变更原因

根据任务 `240011812325298176` 的失败分析:
- 4个子搜索中有1个因 Firecrawl API 请求超时(30秒)而失败
- 成功的3个子搜索执行时间为 8-10 秒
- 失败的查询 "MINTSD Pune training courses content" 可能需要爬取大量网页内容
- 30秒超时配置偏紧，建议增加到60秒

### 预期效果

- ✅ 降低超时失败率
- ✅ 提高智能搜索成功率 (从75% → 90%+)
- ⚠️ 单次查询等待时间增加 (最多60秒)
- ⚠️ 如果 Firecrawl API 慢，总执行时间会增加

---

## 生效方式

### 选项1: 热重启 (推荐)
```bash
# 如果服务支持热重载
kill -HUP <pid>
```

### 选项2: 完全重启
```bash
# 停止服务
pkill -f "uvicorn.*main:app"

# 重新启动
cd /Users/lanxionggao/Documents/guanshanPython
source venv/bin/activate  # 或 .venv/bin/activate
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

### 选项3: Docker 重启 (如果使用 Docker)
```bash
docker-compose restart
```

---

## 验证方法

### 1. 检查配置是否生效

```bash
# 查看环境变量
python3 -c "
import os
from dotenv import load_dotenv
load_dotenv()
print(f'FIRECRAWL_TIMEOUT = {os.getenv(\"FIRECRAWL_TIMEOUT\")}')
"

# 预期输出: FIRECRAWL_TIMEOUT = 60
```

### 2. 测试智能搜索

```bash
# 运行智能搜索测试脚本
python scripts/test_dgmi_smart_search_auto.py

# 观察日志中的超时设置
grep "timeout" /tmp/uvicorn.log
```

### 3. 观察超时率

**监控指标**:
- 智能搜索成功率应提高到 90%+
- 子搜索超时率应降低到 <5%
- 平均执行时间可能略微增加

**观察周期**: 1周

---

## 回滚方案

如果60秒超时导致用户等待时间过长，可以回滚到45秒:

```bash
# 修改 .env
FIRECRAWL_TIMEOUT=45

# 重启服务
```

---

## 后续优化

如果超时问题仍然存在 (超时率 >5%)，按照以下优先级实施:

### P1: 添加超时监控 (1周内)
- 在 `SmartSearchService` 中添加超时率统计
- 超时率 >10% 自动告警

### P2: 实现子搜索重试 (2周内)
- 子搜索失败后自动重试1次
- 重试间隔30秒
- 提高整体可靠性到 95%+

### P3: 优化 LLM 查询分解 (1个月内)
- 优化 LLM 提示词，生成更简洁的查询
- 减少复杂查询，降低超时风险

---

## 相关文档

- [任务失败分析报告](./TASK_240011812325298176_FAILURE_ANALYSIS.md)
- [智能搜索状态追踪验证报告](./smart_search_status_verification.md)

---

**修复状态**: ✅ 已应用，等待服务重启生效
**下次检查**: 2025-10-31 (1周后评估效果)
