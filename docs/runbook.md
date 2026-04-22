# 运维手册 (Runbook)

## 日常运维

### 启动服务

```bash
# 开发环境
docker-compose -f docker-compose.dev.yml up

# 生产环境
docker-compose up -d
```

### 停止服务

```bash
docker-compose down
```

### 查看日志

```bash
# 后端日志
docker-compose logs -f backend

# 前端日志
docker-compose logs -f frontend
```

### 数据库备份

```bash
# SQLite 备份
cp backend/data/face_scan.db backend/data/face_scan_$(date +%Y%m%d).db.bak

# 人脸特征备份
tar czf face_encodings_$(date +%Y%m%d).tar.gz backend/data/faces/
```

### 数据库恢复

```bash
# 停止服务
docker-compose down

# 恢复数据库
cp face_scan_20240101.db.bak backend/data/face_scan.db

# 重启服务
docker-compose up -d
```

## 故障排查

### 人脸识别失败

**症状**: 用户刷脸无法识别

**排查步骤**:
1. 检查摄像头是否正常: 访问 `/scan` 页面，确认视频画面显示
2. 检查光线条件: 确保门禁点光线充足
3. 检查用户是否已注册: 管理后台查看用户状态
4. 检查置信度阈值: 当前默认 0.6，可在 `system_config` 表调整
5. 查看后端日志: `docker-compose logs backend | grep face`

### WebSocket 连接异常

**症状**: 扫描页面显示"未连接"

**排查步骤**:
1. 检查后端是否运行: `curl http://localhost:8000/health`
2. 检查 Nginx/代理配置: 确保 `/ws/` 路径正确代理
3. 检查浏览器控制台: F12 查看 WebSocket 错误信息
4. 检查 HTTPS 配置: 生产环境必须使用 WSS

### 设备离线

**症状**: 设备列表显示离线

**排查步骤**:
1. 检查设备心跳: 设备应每 30 秒发送心跳
2. 检查网络连通性: 从设备 ping 后端服务器
3. 检查设备注册: 确认设备已正确注册 device_code

### 磁盘空间不足

**排查步骤**:
1. 检查磁盘使用: `df -h`
2. 清理过期抓拍图: 调用 `POST /api/cleanup` 或等待自动清理（默认 30 天）
3. 清理 Docker 镜像: `docker system prune -a`

## 应急预案

### 摄像头故障

1. 使用 PIN 码开门: 扫描页面点击"PIN 码开门"按钮
2. 管理员后台手动开门: 考勤管理中手动添加记录

### 网络中断

1. 检查网络连接: `ping` 后端服务器
2. 使用 PIN 码开门（无需实时网络，PIN 在本地验证）
3. 恢复网络后系统自动重连

### 服务崩溃

1. 检查容器状态: `docker-compose ps`
2. 重启服务: `docker-compose restart backend`
3. 查看崩溃日志: `docker-compose logs --tail=100 backend`
4. 如持续崩溃: 检查磁盘空间和内存使用

## 监控告警

### Prometheus 指标

- 端点: `http://localhost:8000/metrics`
- 关键指标:
  - `http_requests_total` — HTTP 请求总数
  - `face_recognition_duration_seconds` — 识别耗时
  - `active_websocket_connections` — 活跃 WS 连接数

### 健康检查

- 基础健康: `GET /health`
- 就绪检查: `GET /health/ready`
- 存活检查: `GET /health/live`

## 数据安全

### 生物特征加密

- 人脸特征向量使用 Fernet 对称加密存储
- 加密密钥通过 `BIOMETRIC_ENCRYPTION_KEY` 环境变量配置
- 密钥丢失将导致所有人脸特征无法解密，需重新注册
- 迁移已有数据: `python scripts/encrypt_existing_encodings.py`

### 审计日志

- 所有敏感操作（登录、人脸注册、开门）自动记录审计日志
- 审计日志使用 HMAC-SHA256 签名防篡改
- 查询审计日志: `GET /api/audit/logs`
- 审计日志默认保留 180 天，可在配置中调整
