# 超星学习通签到工具 (Python)

基于 Python 重构的超星学习通签到工具，只实现核心签到功能。

## 功能

支持以下签到类型：
- 普通签到
- 拍照签到（无需上传图片）
- 手势签到（无需知道手势）
- 位置签到（可自定义经纬度）
- 二维码签到（支持 enc 参数）
- 签到码签到（无需签到码）

## 安装

```bash
pip install -r requirements.txt
```

## 使用

### 交互模式

```bash
python main.py
```

### 环境变量登录

```bash
# Windows
set CHAOXING_PHONE=你的手机号
set CHAOXING_PASSWORD=你的密码
python main.py

# Linux/macOS
export CHAOXING_PHONE=你的手机号
export CHAOXING_PASSWORD=你的密码
python main.py
```

### 编程调用

```python
from chaoxing_sign import ChaoxingClient

client = ChaoxingClient()
client.login("手机号", "密码")

# 获取课程
courses = client.get_courses()
for c in courses:
    print(c.name)

# 获取签到任务
tasks = client.get_sign_tasks(courses[0])
for t in tasks:
    print(t.name, t.sign_type)

# 执行签到
client.sign(tasks[0])
```

## 免责声明

本项目基于 GPL-3.0，仅供技术学习和交流。使用本项目产生的各类纠纷、法律问题，均由其本人承担。
