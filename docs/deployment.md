# 启动与部署文档

## 1. 环境要求

### 硬件要求

| 项目 | 最低要求 | 推荐配置 |
|---|---|---|
| CPU | 2 核 | 4 核及以上 |
| 内存 | 2 GB | 4 GB 及以上 |
| 硬盘 | 5 GB | 20 GB（含模型文件） |
| 摄像头 | USB 2.0 | USB 3.0，720p 及以上 |

### 软件依赖

| 软件 | 版本 | 说明 |
|---|---|---|
| Python | 3.8 - 3.11 | 3.12+ 暂不兼容 dlib |
| Node.js | 16.x - 20.x | 推荐 18.x LTS |
| CMake | 3.15+ | 编译 dlib 需要 |
| C++ 编译器 | GCC 7+ / MSVC 2019+ | 编译 dlib 需要 |
| Git | 2.x | 克隆代码 |

### 操作系统支持

- Ubuntu 18.04 / 20.04 / 22.04
- CentOS 7 / 8
- macOS 12+
- Windows 10 / 11（需额外配置）

---

## 2. 快速启动（开发环境）

### 2.1 克隆项目

```bash
git clone git@github.com:storewang/go-face-demo.git
cd go-face-demo
```

### 2.2 后端启动

```bash
cd backend

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate        # Linux/macOS
# venv\Scripts\activate         # Windows

# 安装依赖
pip install -r requirements.txt

# 初始化数据库（创建表 + 默认配置）
python -m app.init_db

# 启动服务
python run.py
```

启动成功后可访问：

| 地址 | 说明 |
|---|---|
| http://localhost:8000 | API 根路径 |
| http://localhost:8000/health | 健康检查 |
| http://localhost:8000/docs | Swagger API 文档 |

### 2.3 前端启动

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

启动成功后访问 http://localhost:5173。

### 2.4 验证运行

1. 浏览器打开 http://localhost:5173
2. 确认首页正常加载，显示统计数据
3. 点击"用户注册"，确认摄像头页面正常
4. 点击导航栏"登录"，输入默认密码 `admin123`，确认登录流程正常
5. 登录后确认"考勤记录"和"用户管理"菜单可见

---

## 3. 配置说明

### 3.1 后端配置

在 `backend/` 目录下创建 `.env` 文件（不要提交到 Git）：

```bash
# 必填
ADMIN_PASSWORD=your_secure_password

# 可选（以下为默认值，按需修改）
DEBUG=true
DATABASE_URL=sqlite:///./data/face_scan.db
FACE_THRESHOLD=0.6
LIVENESS_FRAMES=5
```

| 环境变量 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `ADMIN_PASSWORD` | string | `admin123` | 管理员登录密码 |
| `DEBUG` | bool | `true` | 开启后 uvicorn 自动重载，关闭后提升性能 |
| `DATABASE_URL` | string | `sqlite:///./data/face_scan.db` | 数据库连接地址 |
| `FACE_THRESHOLD` | float | `0.6` | 人脸识别置信度阈值（0.0-1.0，越高越严格） |
| `LIVENESS_FRAMES` | int | `5` | 活体检测需要的连续帧数 |
| `LIVENESS_MODEL_PATH` | string | `models/shape_predictor_68_face_landmarks.dat` | 活体检测模型路径 |

### 3.2 前端配置

开发环境配置 `frontend/.env.development`（已存在，无需修改）：

```
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000/ws/face-stream
```

生产环境配置 `frontend/.env.production`（部署前必须修改）：

```
VITE_API_BASE_URL=https://your-domain.com
VITE_WS_URL=wss://your-domain.com/ws/face-stream
```

> 将 `your-domain.com` 替换为实际部署域名或 IP 地址。

---

## 4. 活体检测模型（可选）

活体检测需要额外下载 dlib 人脸关键点模型（约 61MB），不下载不影响人脸采集和识别功能，系统会自动跳过活体检测。

```bash
cd backend

# 下载模型
mkdir -p models
wget http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2 -O models/shape_predictor_68_face_landmarks.dat.bz2

# 解压
bunzip2 models/shape_predictor_68_face_landmarks.dat.bz2

# 验证
ls -la models/shape_predictor_68_face_landmarks.dat
```

---

## 5. 生产环境部署

### 5.1 后端部署（Nginx + Uvicorn）

#### 安装系统依赖（Ubuntu）

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv \
    build-essential cmake libopencv-dev \
    nginx
```

#### 部署后端

```bash
# 克隆代码
git clone git@github.com:storewang/go-face-demo.git /opt/face-scan
cd /opt/face-scan/backend

# 创建虚拟环境并安装依赖
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 初始化数据库
python -m app.init_db

# 创建 .env 配置文件
cat > .env << 'EOF'
ADMIN_PASSWORD=your_secure_password
DEBUG=false
DATABASE_URL=sqlite:///./data/face_scan.db
FACE_THRESHOLD=0.6
EOF

# 下载活体检测模型（可选）
mkdir -p models
wget -q http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2 -O models/shape_predictor_68_face_landmarks.dat.bz2
bunzip2 models/shape_predictor_68_face_landmarks.dat.bz2
```

#### 创建 systemd 服务

```bash
sudo cat > /etc/systemd/system/face-scan.service << 'EOF'
[Unit]
Description=Face Scan Backend
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/face-scan/backend
Environment=PATH=/opt/face-scan/backend/venv/bin
ExecStart=/opt/face-scan/backend/venv/bin/python -m uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 1 \
    --timeout-keep-alive 120
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable face-scan
sudo systemctl start face-scan

# 验证
sudo systemctl status face-scan
curl http://localhost:8000/health
```

> **注意**：face_recognition 是 CPU 密集型库，`--workers` 建议设为 1。多 worker 会重复加载人脸特征到内存，造成浪费。

### 5.2 前端部署

```bash
cd /opt/face-scan/frontend

# 安装依赖
npm install

# 修改生产环境配置
# 编辑 .env.production，将域名替换为实际地址
# VITE_API_BASE_URL=https://your-domain.com
# VITE_WS_URL=wss://your-domain.com/ws/face-stream

# 构建
npm run build
```

构建产物在 `frontend/dist/` 目录。

### 5.3 Nginx 配置

```bash
sudo cat > /etc/nginx/sites-available/face-scan << 'EOF'
server {
    listen 80;
    server_name your-domain.com;  # 替换为实际域名或 IP

    # 前端静态文件
    root /opt/face-scan/frontend/dist;
    index index.html;

    # 前端路由（SPA History 模式）
    location / {
        try_files $uri $uri/ /index.html;
    }

    # 后端 API 代理
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # 文件上传大小限制
        client_max_body_size 10M;
    }

    # WebSocket 代理
    location /ws/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 3600s;
    }

    # 静态资源缓存
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff2?)$ {
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/face-scan /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

### 5.4 HTTPS 配置（推荐）

```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d your-domain.com
```

> 配置 HTTPS 后，WebSocket 地址自动升级为 `wss://`，需同步修改前端 `.env.production` 中的 `VITE_WS_URL`。

---

## 6. 运维操作

### 6.1 更新代码

```bash
cd /opt/face-scan
git pull origin main

# 更新后端
cd backend
source venv/bin/activate
pip install -r requirements.txt
python -m app.init_db          # 数据库结构变更时执行
sudo systemctl restart face-scan

# 更新前端
cd ../frontend
npm install
npm run build
sudo systemctl reload nginx
```

### 6.2 数据备份

```bash
# 备份数据库
cp /opt/face-scan/backend/data/face_scan.db /opt/face-scan/backup/face_scan_$(date +%Y%m%d).db

# 备份人脸数据
cp -r /opt/face-scan/backend/data/faces/ /opt/face-scan/backup/faces_$(date +%Y%m%d)/
```

建议通过 crontab 设置每日自动备份：

```bash
# 每天凌晨 3 点备份
0 3 * * * cp /opt/face-scan/backend/data/face_scan.db /opt/face-scan/backup/face_scan_$(date +\%Y\%m\%d).db
```

### 6.3 查看日志

```bash
# 后端服务日志
sudo journalctl -u face-scan -f

# Nginx 日志
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### 6.4 服务管理

```bash
sudo systemctl start face-scan     # 启动
sudo systemctl stop face-scan      # 停止
sudo systemctl restart face-scan   # 重启
sudo systemctl status face-scan    # 查看状态
```

---

## 7. 常见问题

### Q: pip install dlib 编译失败

```
dlib 安装需要 CMake 和 C++ 编译器。

Ubuntu:
  sudo apt install cmake build-essential

CentOS:
  sudo yum install cmake gcc-c++ make

macOS:
  xcode-select --install

如果仍然失败，尝试使用预编译 wheel：
  pip install dlib==19.22.1
```

### Q: 摄像头无法打开

```
1. 确认摄像头已连接：ls /dev/video*
2. 确认权限：sudo usermod -a -G video $USER（需重新登录）
3. HTTPS 环境下浏览器才能访问摄像头（localhost 除外）
4. 确认浏览器没有禁用摄像头权限
```

### Q: 人脸识别速度慢

```
1. 首次识别较慢（加载 dlib 模型），后续会快
2. 减少 WebSocket 发帧频率（建议 200-300ms 间隔）
3. 降低摄像头分辨率（640x480 足够）
4. 关闭 DEBUG 模式（DEBUG=true 会增加额外开销）
```

### Q: WebSocket 连接断开

```
1. Nginx 默认 60s 超时，已在配置中设置为 3600s
2. 确认 Nginx 配置中 WebSocket 代理的 Upgrade 头已设置
3. 浏览器标签页切到后台时部分浏览器会限制 WebSocket
```

### Q: 前端页面刷新后 404

```
Nginx 配置中确认有 try_files $uri $uri/ /index.html;
SPA 路由需要将所有路径回退到 index.html
```

### Q: 上传图片报 413 错误

```
Nginx 默认上传限制 1MB，已在配置中设置为 10M。
如需更大，修改 client_max_body_size 值。
```

---

## 8. 项目目录结构

```
face-scan/
├── backend/
│   ├── app/
│   │   ├── api/              # API 路由（users, face, attendance, auth, websocket）
│   │   ├── models/           # SQLAlchemy 数据模型
│   │   ├── schemas/          # Pydantic 请求/响应模型
│   │   ├── services/         # 业务逻辑（人脸识别、活体检测、导出）
│   │   ├── utils/            # 工具函数（人脸处理、认证）
│   │   ├── websocket/        # WebSocket 连接管理
│   │   ├── config.py         # 配置（环境变量）
│   │   ├── database.py       # 数据库连接
│   │   ├── main.py           # FastAPI 入口
│   │   └── init_db.py        # 数据库初始化脚本
│   ├── data/                 # 运行时数据（数据库、人脸图片、特征文件）
│   ├── models/               # 活体检测模型文件
│   ├── requirements.txt      # Python 依赖
│   ├── run.py                # 启动脚本
│   └── .env                  # 环境配置（需手动创建）
├── frontend/
│   ├── src/
│   │   ├── api/              # API 请求模块
│   │   ├── assets/           # 静态资源
│   │   ├── components/       # 公共组件（Camera、NavBar）
│   │   ├── composables/      # Vue 组合式函数（摄像头、WebSocket）
│   │   ├── layouts/          # 页面布局
│   │   ├── router/           # 路由配置
│   │   ├── stores/           # Pinia 状态管理
│   │   ├── types/            # TypeScript 类型定义
│   │   ├── utils/            # 工具函数（请求、图片处理）
│   │   └── views/            # 页面组件
│   ├── .env.development      # 开发环境变量
│   ├── .env.production       # 生产环境变量
│   ├── vite.config.ts        # Vite 构建配置
│   └── package.json          # Node.js 依赖
├── docs/                     # 文档（API 文档、设计文档、实施计划）
├── .gitignore
├── AGENTS.md                 # AI 编码规范
└── README.md
```

---

## 9. 默认账号

| 角色 | 密码 | 说明 |
|---|---|---|
| 管理员 | `admin123` | 用于访问考勤记录和用户管理页面 |

> 首次部署后请立即修改密码，在 `backend/.env` 中设置 `ADMIN_PASSWORD`。
