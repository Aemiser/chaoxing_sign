# 超星学习通签到工具 (Python)

基于 Python 实现的超星学习通自动化签到工具，支持 **Web 前端 + CLI 命令行** 两种使用方式，集成 **好友系统** 和 **代签功能**。

## 功能

### 签到类型
| 类型 | 说明 |
|------|------|
| 普通签到 | 一键提交 |
| 拍照签到 | 无需上传图片 |
| 手势签到 | 前端九宫格手势锁绘制，生成手势码 |
| 位置签到 | 自定义经纬度 + 高德地图选点 |
| 二维码签到 | 摄像头扫码 / 图片 / 文本 / enc 四种方式 |
| 签到码签到 | 输入签到码 + PC 端点 signIn 回退 |

### 好友系统
- 超星登录自动注册，UID 作为唯一标识
- 双向好友关系（MySQL 存储）
- 好友列表管理（添加 / 删除）
- 超星会话持久化（代签时用好友自己的会话签到）

### 代签功能
- 扫码页勾选好友 → 扫描二维码 / 输入签到码 / 绘制手势 → 自己 + 好友批量签到
- 已签任务可进入代签页帮好友签到
- 签到日志实时展示结果

### 其他
- 课程活跃任务检测（首页展示）
- 已签/未签状态自动检测（preSign 端点）
- 用户头像自动下载入库
- 加载动画、localStorage 缓存优化

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置数据库

在 `config.json` 中添加 MySQL 连接信息：

```json
{
    "phone": "你的手机号",
    "password": "你的密码",
    "location": {
        "longitude": "116.404",
        "latitude": "39.915",
        "name": "北京市"
    },
    "database": {
        "host": "localhost",
        "port": 3306,
        "user": "root",
        "password": "your-db-password",
        "database": "chaoxing_sign"
    },
    "jwt_secret": "随机字符串"
}
```

数据库不可用时签到功能正常运行，仅好友/代签功能暂不可用。

### 3. 启动 Web 服务

```bash
python server.py
```

访问 `http://localhost:8000`

### 4. CLI 交互模式

```bash
python main.py
```

## 项目结构

```
chaoxing-sign-python/
├── main.py                     # CLI 入口
├── server.py                   # FastAPI Web 服务
├── config.example.json         # 配置文件模板
├── requirements.txt
├── chaoxing_sign/              # 核心包
│   ├── client.py               # 超星 API 客户端
│   ├── types.py                # 数据类型
│   ├── utils.py                # 工具函数
│   ├── models.py               # ORM 模型
│   ├── database.py             # 数据库连接池
│   └── auth.py                 # JWT 认证
├── static/                     # Web 前端
│   ├── index.html
│   ├── css/style.css
│   ├── js/app.js
│   └── images/avatars/
├── tests/                      # 测试
│   ├── test_all.py
│   ├── test_auth.py
│   ├── test_friends.py
│   └── test_proxy_sign.py
└── ARCHITECTURE.md             # 架构文档
```

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/login` | 超星登录（自动注册用户 + 返回 JWT） |
| POST | `/api/logout` | 退出登录 |
| GET | `/api/session` | 检查会话状态 |
| GET | `/api/courses` | 获取课程列表 |
| GET | `/api/tasks/{cid}/{clid}` | 获取签到任务（含已签检测） |
| GET | `/api/active-courses` | 获取有活跃签到任务的课程 |
| POST | `/api/sign` | 执行签到 |
| POST | `/api/checkin/qrcode` | 二维码代签（自己 + 好友） |
| GET | `/api/friends` | 获取好友列表 |
| POST | `/api/friends` | 添加好友 |
| DELETE | `/api/friends/{id}` | 删除好友 |
| GET | `/api/location_config` | 获取默认位置 |
| GET | `/api/config` | 获取公开配置 |

## 代签流程

```
用户登录 → 自动注册入库 + 会话持久化
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
