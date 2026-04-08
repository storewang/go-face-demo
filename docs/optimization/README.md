# 总体改造计划

## 概览

基于项目分析结果，制定五个方向的优化改造计划。

---

## 改造文档索引

| 文档 | 方向 | 预估工时 | 优先级 |
|------|------|----------|--------|
| [01-security.md](./01-security.md) | 安全性增强 | 7.5h | 🔴 最高 |
| [02-performance.md](./02-performance.md) | 性能优化 | 11.5h | 🟡 高 |
| [03-operations.md](./03-operations.md) | 运维改进 | 10h | 🟡 高 |
| [04-features.md](./04-features.md) | 功能扩展 | 20h | 🟢 中 |
| [05-cluster.md](./05-cluster.md) | 集群部署 | 17h | 🟢 中 |

**总预估工时：66h**

---

## 实施路线图

### Phase 1：安全加固（1-2 天）
> 必须最先完成，消除安全隐患

- [ ] 移除硬编码密码，改为环境变量注入（0.5h）
- [ ] JWT Token 替换内存 Token（2h）
- [ ] CORS 白名单配置（0.5h）
- [ ] 请求速率限制（1h）
- [ ] 文件上传校验（1h）
- [ ] 安全 Headers（0.5h）
- [ ] HTTPS 反向代理（1.5h）
- [ ] 单元测试 + 验收（0.5h）

**里程碑：安全评分 ≥ 9/10**

### Phase 2：运维基础（1-2 天）
> 为后续开发建立良好的运维基础

- [ ] 结构化日志（structlog）（2h）
- [ ] Alembic 数据库迁移（1.5h）
- [ ] 健康检查增强（1h）
- [ ] Docker 多阶段构建（1h）
- [ ] 自动化备份脚本（1.5h）
- [ ] Prometheus 指标埋点（3h）

**里程碑：日志可检索、数据库可迁移、监控可视化**

### Phase 3：性能优化（1-2 天）
> 提升系统性能上限

- [ ] Redis 缓存层（2h）
- [ ] FAISS 向量搜索（3h）
- [ ] WebSocket 帧优化（1.5h）
- [ ] 数据库索引优化（1h）
- [ ] 启动优化（1h）
- [ ] 异步任务队列（可选，3h）

**里程碑：1000 用户识别 < 200ms**

### Phase 4：功能扩展（3-4 天）
> 扩展业务能力

- [ ] 角色权限管理 RBAC（4h）
- [ ] 多门禁点管理（4h）
- [ ] 考勤统计与分析（4h）
- [ ] 通知推送系统（3h）
- [ ] 用户自助服务（3h）
- [ ] API 文档增强（2h）

**里程碑：完整的企业级门禁考勤系统**

### Phase 5：集群部署（2-3 天）
> 支持多机集群和 K8s 弹性伸缩

- [ ] SQLite → PostgreSQL 迁移（2h）
- [ ] JWT 无状态认证 + Redis 黑名单（1h）
- [ ] 本地文件 → MinIO/S3 对象存储（3h）
- [ ] Redis Pub/Sub WebSocket 广播（3h）
- [ ] 人脸特征库跨节点同步（4h）
- [ ] Nginx 负载均衡（1h）
- [ ] K8s 部署配置（2h）
- [ ] 集群 docker-compose（1h）

**里程碑：支持水平扩展，单节点宕机不影响服务**

---

## 技术依赖关系

```
Phase 1 (安全)
    │
    ├── Phase 2 (运维) ─── Redis ──→ Phase 3 (性能)
    │                                    │
    └────────────────────────────────────┴──→ Phase 4 (功能)
                                         │
     Phase 1 (JWT) + Phase 2 (Alembic) ───→ Phase 5 (集群)
```

- Phase 1 和 Phase 2 可以并行
- Phase 3 依赖 Phase 2 的 Redis 服务
- Phase 4 依赖 Phase 1 的 JWT 和 Phase 2 的 Alembic
- Phase 5 依赖 Phase 1（JWT）、Phase 2（Redis/Alembic）、Phase 3（可选 FAISS）

---

## 风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| dlib 编译问题 | Docker 构建失败 | 使用预编译 wheel 或多阶段构建 |
| SQLite 并发限制 | 多进程部署异常 | Phase 3 可选迁移 PostgreSQL |
| FAISS 与现有代码兼容 | 识别准确率变化 | 保留切换开关，A/B 测试 |
| 前端改动量较大 | 开发周期延长 | 可分批次上线 |

---

## 分支策略

- `main` — 生产分支，保持稳定
- `feature/optimization-plan` — 本方案文档分支 ✅ 当前
- `feature/phase1-security` — Phase 1 安全改造
- `feature/phase2-operations` — Phase 2 运维改进
- `feature/phase3-performance` — Phase 3 性能优化
- `feature/phase4-features` — Phase 4 功能扩展
- `feature/phase5-cluster` — Phase 5 集群部署

每个 Phase 完成后合并到 `main`，确保每个 Phase 都是可独立部署的。
