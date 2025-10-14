// MongoDB初始化脚本
// 创建应用数据库和用户

// 切换到智能系统数据库
db = db.getSiblingDB('intelligent_system');

// 创建应用用户（供Python应用连接）
db.createUser({
  user: 'app_user',
  pwd: 'apppass123',
  roles: [
    {
      role: 'readWrite',
      db: 'intelligent_system'
    }
  ]
});

// 创建集合并添加索引
// 搜索任务集合
db.createCollection('search_tasks');
db.search_tasks.createIndex({ "created_by": 1 });
db.search_tasks.createIndex({ "status": 1 });
db.search_tasks.createIndex({ "is_active": 1 });
db.search_tasks.createIndex({ "schedule_interval": 1 });
db.search_tasks.createIndex({ "next_run_time": 1 });
db.search_tasks.createIndex({ "created_at": -1 });

// 搜索结果集合
db.createCollection('search_results');
db.search_results.createIndex({ "task_id": 1 });
db.search_results.createIndex({ "execution_time": -1 });
db.search_results.createIndex({ "task_id": 1, "execution_time": -1 });
db.search_results.createIndex({ "created_at": -1 });

// 生成安全的雪花算法风格ID（模拟）
// 实际生产环境中应使用真实的雪花算法生成器
function generateSecureId() {
  // 时间戳部分（当前时间 - 2024-01-01）
  const epoch = 1704067200000; // 2024-01-01 00:00:00 UTC
  const timestamp = Date.now() - epoch;
  
  // 数据中心ID（0-31）
  const datacenterId = 1;
  
  // 机器ID（0-31） 
  const machineId = 1;
  
  // 序列号（0-4095）
  const sequence = Math.floor(Math.random() * 4096);
  
  // 组装ID（简化版雪花算法）
  const id = (timestamp << 22) | (datacenterId << 17) | (machineId << 12) | sequence;
  
  return id.toString();
}

// 插入安全的测试数据
const secureTaskId = generateSecureId();

db.search_tasks.insertOne({
  "_id": secureTaskId,
  "name": "AI新闻监控测试",
  "description": "使用安全ID的人工智能新闻监控任务",
  "query": "人工智能 机器学习 最新进展",
  "search_config": {
    "limit": 10,
    "sources": ["web", "news"],
    "language": "zh"
  },
  "schedule_interval": "DAILY",
  "is_active": true,
  "status": "active",
  "created_by": "admin",
  "created_at": new Date(),
  "updated_at": new Date(),
  "execution_count": 0,
  "success_count": 0,
  "failure_count": 0,
  "total_results": 0,
  "total_credits_used": 0
});

print("安全测试数据已插入，任务ID: " + secureTaskId);

print("MongoDB数据库初始化完成！");
print("- 数据库: intelligent_system");
print("- 应用用户: app_user / apppass123");
print("- 管理用户: admin / password123");
print("- 集合: search_tasks, search_results");
print("- 测试数据已插入");