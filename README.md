# 超星学习通签到工具 (Python)

基于 Python 实现的超星学习通自动化签到工具，支持 **Web 前端 + CLI 命令行** 两种使用方式，集成 **好友系统**、**代签功能**、**课程缓存** 和 **全局日志系统**。

## 功能

### 签到类型
| 类型 | 说明 |
|------|------|
| 普通签到 | 一键提交 |
| 拍照签到 | 无需上传图片 |
| 手势签到 | 前端九宫格手势锁绘制，生成手势码 |
| 位置签到 | 自定义经纬度 + 高德地图选点 + 三角定位自动求解 |
| 二维码签到 | 摄像头扫码自动识别 |
| 指定位置二维码签到 | 扫码 + 地图选点 |
| 签到码签到 | 输入签到码 |

### 好友系统
- 超星登录自动注册，UID 作为唯一标识
- 双向好友关系（MySQL 存储）
- 好友列表管理（添加 / 删除）
- 超星会话持久化（代签时用好友自己的会话签到）

### 代签功能
- 扫码页勾选好友 → 扫描二维码 / 输入签到码 / 绘制手势 / 地图选点 → 自己 + 好友批量签到
- 已签任务可进入代签页帮好友签到
- 签到日志实时展示结果，每条结果附带失败原因
- 代签记录入库（`proxy_records`），记录操作人和好友列表

### 课程缓存
- 首次登录自动拉取课程列表存入数据库
- `/api/courses?source=0` 从数据库读取，秒级响应
- `/api/courses?source=1` 从超星 API 同步并更新数据库
- 前端课程页提供「同步」按钮手动刷新

### 全局日志系统
- 控制台彩色输出 + 文件持久化
- `logs/info.log` — 全量日志（INFO 及以上）
- `logs/error.log` — 错误日志子集
- 日志文件自动轮转（默认 10MB × 5 备份）
- `.env` 可配置日志级别、开关、路径

### 其他
- 课程活跃任务检测（首页展示）
- 已签/未签状态自动检测
- 用户头像自动下载入库
- 三角定位求解指定地点签到（五探测点 + Gauss-Newton）
- 定位缓存复用

## 快速开始

### 环境要求

- Python 3.10+
- MySQL 5.7+（好友/代签/课程缓存功能需要，纯签到可跳过）

### 1. 克隆项目

```bash
git clone https://github.com/yourname/chaoxing-sign-python.git
cd chaoxing-sign-python
```

### 2. 创建虚拟环境

```bash
python -m venv .venv
source .venv/bin/activate   # Linux / macOS
# .venv\Scripts\activate    # Windows
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 初始化数据库

登录 MySQL 创建数据库（表会在首次启动时自动建）：

```sql
CREATE DATABASE IF NOT EXISTS chaoxing_sign DEFAULT CHARACTER SET utf8mb4;
```

### 5. 配置 `.env`

从模板复制并填入真实信息：

```bash
cp .env.example .env
```

必填项：

| 配置项 | 说明 |
|--------|------|
| `CHAOXING_PHONE` | 超星账号手机号 |
| `CHAOXING_PASSWORD` | 超星密码 |
| `database__host` | MySQL 地址 |
| `database__password` | MySQL 密码 |
| `jwt_secret` | 随机字符串（`openssl rand -hex 32`） |
| `amap_key` | 高德 Web 服务 Key（[申请](https://console.amap.com)） |

### 6. 启动

```bash
python main.py -s
```

浏览器访问 `http://localhost:8000`，输入超星账号密码即可登录。


## 部署

### Systemd 服务（推荐）

创建 `/etc/systemd/system/chaoxing-sign.service`：

```ini
[Unit]
Description=超星学习通签到服务
After=network.target mysql.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/chaoxing-sign-python
ExecStart=/opt/chaoxing-sign-python/.venv/bin/python -m uvicorn chaoxing_sign.server:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
Environment="PATH=/opt/chaoxing-sign-python/.venv/bin"

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now chaoxing-sign
sudo systemctl status chaoxing-sign
```

### Nginx 反向代理

```nginx
server {
    listen 80;
    server_name sign.yourdomain.com;

    client_max_body_size 10m;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias /opt/chaoxing-sign-python/static/;
        expires 7d;
        add_header Cache-Control "public, immutable";
    }
}
```

### Docker（可选）

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["python", "-m", "uvicorn", "chaoxing_sign.server:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
docker build -t chaoxing-sign .
docker run -d -p 8000:8000 --env-file .env --name chaoxing-sign chaoxing-sign
```

### 生产环境注意事项

- `.env` 中的 `jwt_secret` 务必改为强随机字符串
- `log__level` 建议设为 `WARNING` 减少磁盘写入
- 数据库建议做定期备份（`mysqldump chaoxing_sign`）
- 不要将 `.env` 提交到版本控制（已在 `.gitignore` 中）
- 高德地图 Key 需在控制台添加域名白名单

## 项目结构

```
chaoxing-sign-python/
├── .env                             # 配置文件（不纳入版本控制）
├── .env.example                     # 配置文件模板
├── requirements.txt
├── chaoxing_sign/                   # 核心包
│   ├── __init__.py                  # 包入口，初始化日志
│   ├── __main__.py                  # python -m chaoxing_sign 入口
│   ├── client.py                    # 超星 API 客户端
│   ├── types.py                     # 数据类型（Course / SignTask / SignType）
│   ├── models.py                    # ORM 模型（User / Friendship / ProxyRecord / CourseRecord / UserSession）
│   ├── database.py                  # SQLAlchemy 连接池
│   ├── config.py                    # Pydantic Settings 配置管理
│   ├── logging_config.py            # 全局日志初始化（控制台 + 文件）
│   ├── server.py                    # FastAPI 应用实例
│   ├── trilateration.py             # 三角定位算法
│   ├── api/                         # FastAPI 路由层
│   │   ├── app.py                   # 应用工厂
│   │   ├── deps.py                  # 依赖注入
│   │   ├── schemas.py               # 请求/响应模型
│   │   ├── router_auth.py           # 登录/登出
│   │   ├── router_courses.py        # 课程/任务/活跃课程
│   │   ├── router_sign.py           # 签到/扫码签到
│   │   ├── router_friends.py        # 好友管理
│   │   └── router_config.py         # 配置/健康检查
│   ├── auth/                        # 认证模块
│   │   ├── jwt.py                   # JWT 签发/验证
│   │   └── session.py               # Session 管理池
│   ├── cli/                         # CLI 交互
│   │   └── app.py                   # 命令行签到工具
│   ├── core/                        # 核心业务
│   │   ├── constants.py             # API 端点常量
│   │   └── sign.py                  # 签到策略执行器
│   ├── geo/                         # 地理计算
│   │   └── cache.py                 # 三角定位缓存
│   └── utils/                       # 工具函数
│       ├── crypto.py                # 加密
│       ├── geo.py                   # 逆地理编码（OSM / 高德）
│       ├── http.py                  # Cookie 解析
│       ├── json_utils.py            # 安全 JSON 解析
│       └── parser.py                # URL / QR 解析
├── static/                          # Web 前端
│   ├── index.html
│   ├── css/style.css
│   ├── js/app.js
│   └── images/
├── tests/                           # 测试
│   ├── test_all.py
│   ├── test_code.py
│   └── test_proxy_sign.py
└── logs/                            # 日志文件（不纳入版本控制）
    ├── info.log
    └── error.log
```

## API 端点

### 认证
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/login` | 超星登录（自动注册用户 + 缓存课程 + 返回 JWT） |
| POST | `/api/logout` | 退出登录 |
| GET | `/api/session` | 检查会话状态 |

### 课程
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/courses?source=0&user_id=N` | 从数据库读取课程列表（默认） |
| GET | `/api/courses?source=1&user_id=N` | 从超星 API 同步课程并更新数据库 |
| GET | `/api/tasks/{course_id}/{class_id}` | 获取签到任务（含已签检测） |
| GET | `/api/active-courses` | 获取有活跃签到任务的课程 |

### 签到
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/sign` | 执行签到，返回 `(ok, message)` |
| POST | `/api/checkin/qrcode` | 扫码签到（自己 + 好友批量代签） |

### 好友
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/friends` | 获取好友列表 |
| POST | `/api/friends` | 添加好友 |
| DELETE | `/api/friends/{id}` | 删除好友 |

### 配置
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/config` | 获取公开配置（地图 key、三角定位开关等） |
| GET | `/api/location_config` | 获取默认签到位置 |
| GET | `/health` | 健康检查 |

## 数据库表

| 表名 | 说明 |
|------|------|
| `users` | 用户信息（超星 UID + 昵称 + 学校 + 头像） |
| `friendships` | 双向好友关系 |
| `proxy_records` | 代签记录（操作人 + 好友列表 + 结果） |
| `course_records` | 课程缓存（按用户存储） |
| `task_sign_cache` | 签到任务缓存 |
| `user_sessions` | 用户超星会话持久化 |

## 代签流程

```
用户登录 → 自动注册入库 + 课程缓存 + 会话持久化
    │
    ├─ 首页：查看活跃任务课程
    │
    ├─ 课程 → 任务列表 → 点击签到类型
    │       ├─ 二维码 → 扫码页（好友勾选 → 摄像头扫码 → 自动签到）
    │       ├─ 手势 → 九宫格绘制 → 确认签到
    │       ├─ 签到码 → 输入签到码 → 确认签到
    │       ├─ 位置 → 地图选点 → 确认签到
    │       └─ 普通/拍照 → 直接签到
    │
    └─ 已签任务 → 「代签」按钮 → 扫码页代签好友
```

## 免责声明

本项目基于 GPL-3.0，仅供技术学习和交流。使用本项目产生的各类纠纷、法律问题，本人均不承担。
