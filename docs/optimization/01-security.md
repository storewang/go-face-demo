# 01 - 安全性增强方案

## 目标
消除所有已知安全风险，将安全评分从 5/10 提升至 9/10。

---

## 1. 移除硬编码密码

### 现状
```python
# config.py
ADMIN_PASSWORD: str = "admin123"
```
```yaml
# docker-compose.yml
environment:
  - ADMIN_PASSWORD=admin123
```

### 改造方案
- 从 `config.py` 和 `docker-compose.yml` 中移除默认密码
- 密码**必须**通过环境变量 `ADMIN_PASSWORD` 注入，无默认值（启动时缺失则报错）
- 首次部署提供 `scripts/setup-admin.py` 交互式设置密码（bcrypt 哈希后存入 `.env`）
- `.env` 文件加入 `.gitignore`（当前已忽略但需确认）

### 涉及文件
- `backend/app/config.py` — 移除默认值，改为 `Optional` + 校验
- `docker-compose.yml` — 移除明文密码，改用 `env_file: .env`
- 新增 `backend/scripts/setup-admin.py`
- 新增 `backend/.env.example`

### 代码示例

**config.py 改造：**
```python
class Settings(BaseSettings):
    # Admin - 密码必须通过环境变量注入
    ADMIN_PASSWORD_HASH: Optional[str] = None
    JWT_SECRET_KEY: str = ""  # 必填，启动时校验非空

    @validator("JWT_SECRET_KEY")
    def jwt_secret_required(cls, v):
        if not v:
            raise ValueError("JWT_SECRET_KEY 环境变量必须设置")
        return v
```

**.env.example：**
```env
# 必填项
ADMIN_PASSWORD_HASH=  # 通过 python scripts/setup-admin.py 生成
JWT_SECRET_KEY=       # 随机生成: python -c "import secrets; print(secrets.token_hex(32))"

# 可选项
DEBUG=false
FACE_THRESHOLD=0.6
```

---

## 2. JWT Token 替换内存 Token

### 现状
```python
# utils/auth.py
_active_tokens: Set[str] = set()  # 内存存储，重启丢失
TOKEN_EXPIRE_SECONDS = 8 * 3600  # 8小时，但无自动过期清理
```

### 改造方案
- 使用 `python-jose` 实现 JWT，支持自动过期
- Token 中携带用户信息，无需服务端存储
- 支持 Token 黑名单（用于登出），存储在 Redis（见性能方案）

### 涉及文件
- `backend/app/utils/auth.py` — 完全重写
- `backend/requirements.txt` — 新增 `python-jose[cryptography]`, `passlib[bcrypt]`
- `backend/app/config.py` — 新增 `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `JWT_EXPIRE_HOURS`

### 代码示例

```python
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(hours=settings.JWT_EXPIRE_HOURS))
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

def verify_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload if payload.get("type") == "access" else None
    except JWTError:
        return None
```

---

## 3. CORS 白名单

### 现状
```python
allow_origins=["*"]
```

### 改造方案
- 从环境变量读取允许的域名列表
- 提供合理的默认值（仅本地开发）
- 生产环境必须显式配置

### 涉及文件
- `backend/app/config.py` — 新增 `CORS_ORIGINS: List[str]`
- `backend/app/main.py` — 使用配置值
- `docker-compose.yml` — 新增环境变量
- `backend/.env.example` — 新增示例

### 代码示例

```python
# config.py
CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:80"]

# main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)
```

---

## 4. 请求速率限制

### 现状
无任何速率限制，API 可被暴力破解。

### 改造方案
- 使用 `slowapi`（基于 `limits`）实现速率限制
- 登录接口：5次/分钟
- 人脸注册：10次/分钟
- WebSocket 帧发送：30次/分钟
- 通用 API：60次/分钟
- 超限返回 429 Too Many Requests

### 涉及文件
- `backend/requirements.txt` — 新增 `slowapi`
- `backend/app/main.py` — 添加 limiter 中间件
- `backend/app/api/auth.py` — 登录限流
- `backend/app/api/face.py` — 注册限流
- `backend/app/api/websocket.py` — 帧发送限流

### 代码示例

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

# auth.py
@router.post("/login")
@limiter.limit("5/minute")
def login(request: Request, body: LoginRequest):
    ...
```

---

## 5. 文件上传校验

### 现状
人脸注册时未校验上传的图片类型和大小。

### 改造方案
- 校验文件类型（仅允许 JPEG/PNG）
- 校验文件大小（最大 5MB）
- 校验图片尺寸（最小 100x100）
- 校验图片内容（确保是真实图片，非伪装文件）

### 涉及文件
- `backend/app/utils/validators.py` — 新增文件校验模块
- `backend/app/api/face.py` — 注册时调用校验
- `backend/app/services/face_service.py` — 注册流程增加校验

### 代码示例

```python
# utils/validators.py
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png"}
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB
MIN_IMAGE_DIMENSION = 100

def validate_image(file_bytes: bytes, filename: str) -> str:
    """校验图片文件，返回错误信息或空字符串"""
    if len(file_bytes) > MAX_IMAGE_SIZE:
        return "图片大小不能超过 5MB"

    # 使用 imghdr 或 python-magic 校验真实类型
    img_type = imghdr.what(None, h=file_bytes)
    if img_type not in ("jpeg", "png"):
        return "仅支持 JPEG/PNG 格式"

    img = Image.open(io.BytesIO(file_bytes))
    if img.width < MIN_IMAGE_DIMENSION or img.height < MIN_IMAGE_DIMENSION:
        return "图片尺寸过小，最小 100x100"

    return ""
```

---

## 6. HTTPS 支持

### 现状
无 HTTPS 配置，WebSocket 使用 `ws://`。

### 改造方案
- `docker-compose.yml` 中新增 Caddy/NGINX 反向代理服务
- 自动 HTTPS（Caddy）或手动证书（NGINX + Let's Encrypt）
- WebSocket 升级为 `wss://`

### 涉及文件
- `docker-compose.yml` — 新增 caddy/nginx 服务
- 新增 `nginx/nginx.conf` 或 `Caddyfile`
- `frontend/src/composables/useWebSocket.ts` — 支持 wss:// 协议

---

## 7. 安全 Headers

### 现状
未设置安全相关的 HTTP Headers。

### 改造方案
- 使用 `starlette-secure-headers` 或手动添加中间件
- 添加 Headers：`X-Content-Type-Options`, `X-Frame-Options`, `Content-Security-Policy` 等

### 涉及文件
- `backend/requirements.txt` — 新增 `starlette-secure-headers`
- `backend/app/main.py` — 添加安全 headers 中间件

---

## 改造优先级

| 序号 | 改造项 | 优先级 | 预估工时 | 风险 |
|------|--------|--------|----------|------|
| 1 | 移除硬编码密码 | 🔴 P0 | 1h | 低 |
| 2 | JWT Token | 🔴 P0 | 2h | 中 |
| 3 | CORS 白名单 | 🔴 P0 | 0.5h | 低 |
| 4 | 速率限制 | 🟡 P1 | 1h | 低 |
| 5 | 文件上传校验 | 🟡 P1 | 1h | 低 |
| 6 | HTTPS | 🟡 P1 | 1.5h | 中 |
| 7 | 安全 Headers | 🟢 P2 | 0.5h | 低 |

**总预估工时：7.5h**

---

## 验收标准
- [ ] 代码中无任何硬编码密码或密钥
- [ ] 登录接口 5次/分钟后返回 429
- [ ] CORS 仅允许配置的白名单域名
- [ ] Token 使用 JWT，支持自动过期
- [ ] 图片上传有类型/大小/尺寸校验
- [ ] 部署时支持 HTTPS + WSS
- [ ] 响应包含安全 Headers
