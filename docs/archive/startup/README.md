# 启动文档归档

**归档日期**: 2025-10-21

## 说明

此目录中的启动相关文档已被整合到项目根目录的 **[STARTUP_GUIDE.md](../../../STARTUP_GUIDE.md)** 中。

## 归档文件

| 文件 | 原路径 | 整合状态 |
|------|--------|----------|
| START_SERVER.md | 项目根目录 | ✅ 已整合 |
| PROJECT_SETUP.md | docs/ | ✅ 已整合 |
| VPN_CONNECTION_TEST_REPORT.md | docs/ | ✅ 参考内容已整合 |

## 新文档结构

所有项目启动相关的信息现在统一在：

### [STARTUP_GUIDE.md](../../../STARTUP_GUIDE.md)

**包含内容**:
- 快速开始
- 环境要求
- 安装步骤
- 启动方式（本地Docker、VPN远程、降级模式）
- 验证服务
- 配置说明
- 常用命令
- 故障排查
- 进阶配置

## 相关文档

- [完整启动指南](../../../STARTUP_GUIDE.md) - 主要启动文档
- [VPN数据库连接指南](../../VPN_DATABASE_GUIDE.md) - VPN连接详细配置
- [MongoDB配置](../../MONGODB_GUIDE.md) - 数据库配置
- [API使用指南](../../API_GUIDE.md) - API接口文档

## 查看旧版本

如需查看旧版本的启动文档，可以：
1. 查看此目录中的归档文件
2. 通过Git历史记录查看：
   ```bash
   git log --follow <文件名>
   git show <commit-hash>:<文件路径>
   ```

---

**整合原因**:
- 减少文档冗余
- 统一用户体验
- 简化文档维护
- 提供更完整的启动指南

**维护**: 未来所有启动相关的更新都应在 [STARTUP_GUIDE.md](../../../STARTUP_GUIDE.md) 中进行。
