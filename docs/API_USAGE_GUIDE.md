# 定时搜索任务 API 使用指南

## 快速开始

### 1. 获取调度器状态

首先检查调度器是否正常运行：

```bash
curl -X GET "http://localhost:8000/api/v1/scheduler/status" \
  -H "accept: application/json"
```

响应：
```json
{
  "status": "running",
  "active_jobs": 3,
  "next_run_time": "2025-10-12T09:00:00",
  "jobs": []
}
```

### 2. 获取调度间隔选项

查看可用的调度间隔：

```bash
curl -X GET "http://localhost:8000/api/v1/search-tasks/schedule-intervals" \
  -H "accept: application/json"
```

响应：
```json
[
  {
    "value": "HOURLY_1",
    "label": "每小时",
    "description": "每小时执行一次",
    "interval_minutes": 60
  },
  {
    "value": "DAILY",
    "label": "每天",
    "description": "每天上午9点执行",
    "interval_minutes": 1440
  }
]
```

### 3. 创建搜索任务

```bash
curl -X POST "http://localhost:8000/api/v1/search-tasks" \
  -H "accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "AI技术动态监控",
    "description": "监控人工智能领域最新技术动态",
    "query": "人工智能 机器学习 深度学习 最新技术",
    "search_config": {
      "limit": 20,
      "sources": ["web", "news"],
      "language": "zh",
      "include_domains": [
        "www.36kr.com",
        "tech.sina.com.cn",
        "www.ithome.com"
      ],
      "time_range": "day",
      "enable_ai_summary": true
    },
    "schedule_interval": "DAILY",
    "is_active": true
  }'
```

## 常用工作流程

### 工作流程 1：创建和管理日常监控任务

#### 步骤 1: 创建每日新闻监控任务

```bash
curl -X POST "http://localhost:8000/api/v1/search-tasks" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "科技新闻每日监控",
    "description": "每天监控主要科技媒体的AI相关新闻",
    "query": "人工智能 ChatGPT 大模型",
    "search_config": {
      "limit": 30,
      "sources": ["news"],
      "language": "zh",
      "include_domains": [
        "www.36kr.com",
        "tech.sina.com.cn",
        "www.pingwest.com",
        "www.geekpark.net"
      ],
      "time_range": "day",
      "enable_ai_summary": true
    },
    "schedule_interval": "DAILY",
    "is_active": true
  }'
```

#### 步骤 2: 获取创建的任务ID (假设为 "123456789012345")

#### 步骤 3: 立即测试执行任务

```bash
curl -X POST "http://localhost:8000/api/v1/scheduler/tasks/123456789012345/execute" \
  -H "accept: application/json"
```

#### 步骤 4: 检查任务执行结果

```bash
curl -X GET "http://localhost:8000/api/v1/search-tasks/123456789012345" \
  -H "accept: application/json"
```

### 工作流程 2：高频监控特定技术趋势

#### 步骤 1: 创建每小时监控任务

```bash
curl -X POST "http://localhost:8000/api/v1/search-tasks" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "GPU市场动态追踪",
    "description": "每小时监控GPU市场价格和供应情况",
    "query": "GPU 显卡 价格 库存 RTX 4090",
    "search_config": {
      "limit": 15,
      "sources": ["web", "news"],
      "language": "zh",
      "include_domains": [
        "item.jd.com",
        "detail.tmall.com",
        "www.chiphell.com"
      ],
      "time_range": "day"
    },
    "schedule_interval": "HOURLY_1",
    "is_active": true
  }'
```

#### 步骤 2: 监控任务执行情况

```bash
curl -X GET "http://localhost:8000/api/v1/scheduler/running-tasks" \
  -H "accept: application/json"
```

### 工作流程 3：任务管理和控制

> **完整的调度器API参考**: 请参阅 [`API_FIELD_REFERENCE.md`](./API_FIELD_REFERENCE.md) 的"调度器管理API"章节

#### 暂停任务（例如维护期间）

```bash
curl -X POST "http://localhost:8000/api/v1/scheduler/tasks/123456789012345/pause" \
  -H "accept: application/json"
```

#### 恢复任务

```bash
curl -X POST "http://localhost:8000/api/v1/scheduler/tasks/123456789012345/resume" \
  -H "accept: application/json"
```

#### 修改任务配置

```bash
curl -X PUT "http://localhost:8000/api/v1/search-tasks/123456789012345" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "科技新闻每日监控（已优化）",
    "search_config": {
      "limit": 50,
      "sources": ["web", "news"],
      "language": "zh",
      "include_domains": [
        "www.36kr.com",
        "tech.sina.com.cn",
        "www.pingwest.com",
        "www.geekpark.net",
        "www.ifanr.com"
      ],
      "time_range": "day",
      "enable_ai_summary": true,
      "extract_metadata": true
    }
  }'
```

## 高级用例

### 用例 1：多语言内容监控

创建监控英文技术博客的任务：

```bash
curl -X POST "http://localhost:8000/api/v1/search-tasks" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "English Tech Blog Monitor",
    "description": "Monitor English technical blogs for AI advances",
    "query": "artificial intelligence machine learning breakthrough",
    "search_config": {
      "limit": 25,
      "sources": ["web"],
      "language": "en",
      "include_domains": [
        "blog.openai.com",
        "ai.googleblog.com",
        "engineering.fb.com",
        "blog.deepmind.com"
      ],
      "time_range": "week",
      "enable_ai_summary": true
    },
    "schedule_interval": "DAILY",
    "is_active": true
  }'
```

### 用例 2：竞争对手分析

监控特定公司的产品发布和技术动态：

```bash
curl -X POST "http://localhost:8000/api/v1/search-tasks" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "竞争对手产品动态",
    "description": "监控主要竞争对手的产品发布和技术更新",
    "query": "Tesla 自动驾驶 FSD 更新 发布",
    "search_config": {
      "limit": 20,
      "sources": ["web", "news"],
      "language": "zh",
      "exclude_domains": [
        "spam-site.com",
        "fake-news.org"
      ],
      "time_range": "day",
      "enable_ai_summary": true
    },
    "schedule_interval": "HOURLY_6",
    "is_active": true
  }'
```

## 错误处理

### 常见错误及解决方案

#### 错误 1：任务创建失败

```json
{
  "detail": "无效的调度间隔: INVALID_INTERVAL"
}
```

**解决方案**：使用 `/schedule-intervals` 端点获取有效的调度间隔选项。

#### 错误 2：任务不存在

```json
{
  "detail": "任务不存在: 123456789012345"
}
```

**解决方案**：检查任务ID是否正确，或使用任务列表API确认任务存在。

#### 错误 3：调度器未运行

```json
{
  "detail": "调度器未运行，无法添加任务"
}
```

**解决方案**：启动调度器服务。

```bash
curl -X POST "http://localhost:8000/api/v1/scheduler/start" \
  -H "accept: application/json"
```

## 监控和维护

### 系统健康检查

定期检查调度器健康状态：

```bash
curl -X GET "http://localhost:8000/api/v1/scheduler/health" \
  -H "accept: application/json"
```

### 获取任务列表和状态

```bash
# 获取所有任务
curl -X GET "http://localhost:8000/api/v1/search-tasks?page=1&page_size=20" \
  -H "accept: application/json"

# 只获取活跃任务
curl -X GET "http://localhost:8000/api/v1/search-tasks?is_active=true" \
  -H "accept: application/json"

# 搜索特定任务
curl -X GET "http://localhost:8000/api/v1/search-tasks?query=AI" \
  -H "accept: application/json"
```

### 性能优化建议

1. **合理设置搜索限制**：根据实际需求设置 `limit` 参数，避免过度消耗资源
2. **使用域名过滤**：通过 `include_domains` 和 `exclude_domains` 提高搜索精准度
3. **适当的执行频率**：根据内容更新频率选择合适的 `schedule_interval`
4. **监控任务性能**：定期检查任务执行统计，优化查询关键词和配置

### 最佳实践

1. **测试任务**：创建任务后先手动执行一次验证效果
2. **逐步扩展**：从少量任务开始，根据系统负载逐步增加
3. **定期清理**：删除不再需要的任务，保持系统整洁
4. **备份配置**：定期备份重要任务的配置信息
5. **监控日志**：关注系统日志，及时发现和解决问题

## 集成示例

### Python 客户端示例

```python
import requests
import json

class TimedSearchClient:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
    
    def create_task(self, task_config):
        """创建搜索任务"""
        url = f"{self.base_url}/api/v1/search-tasks"
        response = requests.post(url, json=task_config)
        return response.json()
    
    def execute_task(self, task_id):
        """立即执行任务"""
        url = f"{self.base_url}/api/v1/scheduler/tasks/{task_id}/execute"
        response = requests.post(url)
        return response.json()
    
    def get_scheduler_status(self):
        """获取调度器状态"""
        url = f"{self.base_url}/api/v1/scheduler/status"
        response = requests.get(url)
        return response.json()

# 使用示例
client = TimedSearchClient()

# 创建任务
task_config = {
    "name": "Python API 监控",
    "query": "Python API 最佳实践",
    "search_config": {
        "limit": 10,
        "sources": ["web"],
        "language": "zh"
    },
    "schedule_interval": "DAILY",
    "is_active": True
}

result = client.create_task(task_config)
task_id = result["id"]

# 立即执行测试
execution_result = client.execute_task(task_id)
print(f"任务执行结果: {execution_result}")
```

### 批量任务管理脚本

```bash
#!/bin/bash

# 批量创建监控任务
BASE_URL="http://localhost:8000"

# 任务配置数组
declare -A TASKS=(
    ["AI新闻"]="人工智能 ChatGPT 大模型"
    ["区块链动态"]="区块链 比特币 以太坊"
    ["新能源汽车"]="新能源汽车 电动车 特斯拉"
)

# 创建任务
for name in "${!TASKS[@]}"; do
    query="${TASKS[$name]}"
    
    curl -X POST "${BASE_URL}/api/v1/search-tasks" \
        -H "Content-Type: application/json" \
        -d "{
            \"name\": \"${name}监控\",
            \"query\": \"${query}\",
            \"search_config\": {
                \"limit\": 20,
                \"sources\": [\"web\", \"news\"],
                \"language\": \"zh\",
                \"time_range\": \"day\"
            },
            \"schedule_interval\": \"DAILY\",
            \"is_active\": true
        }"
    
    echo "Created task: ${name}"
done

# 检查调度器状态
curl -X GET "${BASE_URL}/api/v1/scheduler/status" | jq '.'
```

## 前端集成指南

### 调度间隔选项集成

#### TypeScript类型定义

```typescript
// types/schedule.ts
export interface ScheduleInterval {
  value: string;           // 枚举值,用于API提交
  label: string;           // 显示名称
  description: string;     // 详细说明
  interval_minutes: number; // 间隔分钟数
}
```

### React集成示例

#### 基础React组件

```jsx
import React, { useState, useEffect } from 'react';

function TaskScheduleForm() {
  const [intervals, setIntervals] = useState([]);
  const [selectedInterval, setSelectedInterval] = useState('DAILY');

  // 加载调度选项
  useEffect(() => {
    fetch('/api/v1/search-tasks/schedule-intervals')
      .then(res => res.json())
      .then(data => setIntervals(data))
      .catch(err => console.error('加载调度选项失败:', err));
  }, []);

  return (
    <div className="schedule-form">
      <label>调度频率:</label>
      <select
        value={selectedInterval}
        onChange={(e) => setSelectedInterval(e.target.value)}
      >
        {intervals.map(interval => (
          <option key={interval.value} value={interval.value}>
            {interval.label} - {interval.description}
          </option>
        ))}
      </select>
    </div>
  );
}

export default TaskScheduleForm;
```

#### Ant Design组件

```jsx
import { Select } from 'antd';
import { useEffect, useState } from 'react';

function TaskScheduleSelect({ value, onChange }) {
  const [intervals, setIntervals] = useState([]);

  useEffect(() => {
    fetch('/api/v1/search-tasks/schedule-intervals')
      .then(res => res.json())
      .then(data => setIntervals(data));
  }, []);

  return (
    <Select
      value={value}
      onChange={onChange}
      placeholder="选择调度频率"
      style={{ width: 300 }}
    >
      {intervals.map(interval => (
        <Select.Option
          key={interval.value}
          value={interval.value}
        >
          <div>
            <div><strong>{interval.label}</strong></div>
            <div style={{ fontSize: '12px', color: '#888' }}>
              {interval.description}
            </div>
          </div>
        </Select.Option>
      ))}
    </Select>
  );
}

export default TaskScheduleSelect;
```

### Vue 3集成示例

#### Composition API组件

```vue
<template>
  <div class="schedule-form">
    <label>调度频率:</label>
    <select v-model="selectedInterval">
      <option
        v-for="interval in intervals"
        :key="interval.value"
        :value="interval.value"
      >
        {{ interval.label }} - {{ interval.description }}
      </option>
    </select>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';

const intervals = ref([]);
const selectedInterval = ref('DAILY');

onMounted(async () => {
  try {
    const response = await fetch('/api/v1/search-tasks/schedule-intervals');
    intervals.value = await response.json();
  } catch (error) {
    console.error('加载调度选项失败:', error);
  }
});
</script>
```

#### Element Plus组件

```vue
<template>
  <el-select
    v-model="selectedInterval"
    placeholder="选择调度频率"
    style="width: 300px"
  >
    <el-option
      v-for="interval in intervals"
      :key="interval.value"
      :label="interval.label"
      :value="interval.value"
    >
      <div>
        <strong>{{ interval.label }}</strong>
        <div style="font-size: 12px; color: #888">
          {{ interval.description }}
        </div>
      </div>
    </el-option>
  </el-select>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { ElSelect, ElOption } from 'element-plus';

const intervals = ref([]);
const selectedInterval = ref('DAILY');

onMounted(async () => {
  const response = await fetch('/api/v1/search-tasks/schedule-intervals');
  intervals.value = await response.json();
});
</script>
```

### 实用工具函数

#### 创建任务

```javascript
const createTask = async (taskData) => {
  const response = await fetch('/api/v1/search-tasks', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      name: taskData.name,
      description: taskData.description,
      query: taskData.query,
      search_config: taskData.config,
      schedule_interval: taskData.scheduleInterval, // 使用value字段
      is_active: true
    })
  });

  return response.json();
};
```

#### 显示下次执行时间

```javascript
const getNextRunDescription = (interval) => {
  const now = new Date();
  const minutesUntilNext = interval.interval_minutes;
  const nextRun = new Date(now.getTime() + minutesUntilNext * 60 * 1000);

  return `下次执行: ${nextRun.toLocaleString('zh-CN')}`;
};
```

#### 间隔时间格式化

```javascript
const formatIntervalTime = (minutes) => {
  if (minutes < 60) {
    return `${minutes}分钟`;
  } else if (minutes < 1440) {
    const hours = Math.floor(minutes / 60);
    return `${hours}小时`;
  } else {
    const days = Math.floor(minutes / 1440);
    return `${days}天`;
  }
};
```

### 前端集成注意事项

1. **value字段**: 提交给后端时使用 `value` 字段（如 "DAILY"）
2. **label字段**: 显示给用户时使用 `label` 字段（如 "每天"）
3. **description字段**: 提供详细说明（如 "每天上午9点执行"）
4. **interval_minutes字段**: 可用于计算下次执行时间
5. **默认值**: 推荐使用 **`DAILY`** 作为默认调度频率

---

这个使用指南涵盖了从基础操作到高级用例的完整工作流程，帮助用户快速上手并有效使用定时搜索任务系统。