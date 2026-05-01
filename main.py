#!/usr/bin/env python3
"""超星学习通签到 - 命令行工具"""
import sys
import os

from chaoxing_sign import ChaoxingClient, SignType
from config import config




def clear_screen():
    print("\033[2J\033[H", end="")


def print_header():
    print("=" * 50)
    print("   超星学习通签到工具 v2.0 (Python)")
    print("=" * 50)


def get_credentials(config: dict) -> tuple[str, str]:
    """获取账号密码: 环境变量 > 配置文件 > 手动输入"""
    phone = os.environ.get("CHAOXING_PHONE", "")
    password = os.environ.get("CHAOXING_PASSWORD", "")

    if phone and password:
        return phone, password

    # 尝试配置文件
    phone = config.get("phone", "")
    password = config.get("password", "")

    if phone and password:
        print(f"\n  使用配置文件账号: {phone}")
        return phone, password

    # 手动输入
    print()
    phone = input("  手机号: ").strip()
    import getpass
    password = getpass.getpass("  密码:   ").strip()
    return phone, password


def get_location_config(config: dict) -> dict:
    """获取位置签到默认配置"""
    loc = config.get("location", {})
    return {
        "longitude": loc.get("longitude", "116.404"),
        "latitude": loc.get("latitude", "39.915"),
        "name": loc.get("name", "北京市"),
    }


def select_course(client: ChaoxingClient):
    """选择课程"""
    print("\n正在获取课程列表...")
    courses = client.get_courses()

    if not courses:
        print("  没有获取到课程，请检查账户状态。")
        return None

    print(f"\n共 {len(courses)} 门课程：\n")
    for i, course in enumerate(courses, 1):
        teacher = f" - {course.teacher}" if course.teacher else ""
        print(f"  [{i}] {course.name}{teacher}")

    print("\n  [0] 退出")
    print("  [A] 显示全部课程签到任务")

    while True:
        choice = input("\n请选择: ").strip()
        if choice == "0":
            return None
        if choice.upper() == "A":
            return "ALL"
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(courses):
                return courses[idx]
        except ValueError:
            pass
        print("  输入无效，请重试")


def select_task(client: ChaoxingClient, course) -> list:
    """获取课程的签到任务"""
    if isinstance(course, str) and course == "ALL":
        courses = client.get_courses()
        all_tasks = []
        for c in courses:
            tasks = client.get_sign_tasks(c)
            all_tasks.extend(tasks)
        return all_tasks

    print(f"\n正在获取 [{course.name}] 的签到任务...")
    tasks = client.get_sign_tasks(course)
    return tasks


def show_and_select_tasks(tasks: list) -> list:
    """显示签到任务列表"""
    if not tasks:
        print("  当前没有签到任务。")
        return []

    active_tasks = [t for t in tasks if t.status == "active"]
    ended_tasks = [t for t in tasks if t.status != "active"]

    type_names = {
        SignType.NORMAL: "普通签到",
        SignType.PHOTO: "拍照签到",
        SignType.GESTURE: "手势签到",
        SignType.LOCATION: "位置签到",
        SignType.QRCODE: "二维码签到",
        SignType.CODE: "签到码签到",
    }

    print(f"\n活动签到 ({len(active_tasks)} 个):")
    for i, task in enumerate(active_tasks, 1):
        type_name = type_names.get(task.sign_type, "未知")
        print(f"  [{i}] [{type_name}] {task.name} - {task.course_name}")

    if ended_tasks:
        print(f"\n已结束签到 ({len(ended_tasks)} 个):")
        for task in ended_tasks:
            type_name = type_names.get(task.sign_type, "未知")
            print(f"  [-] [{type_name}] {task.name} - {task.course_name}")

    if not active_tasks:
        return []

    print("\n  [0] 返回")
    print("  [*] 一键签到全部")

    while True:
        choice = input("\n请选择: ").strip()
        if choice == "0":
            return []
        if choice == "*":
            return active_tasks

        try:
            if "," in choice:
                indices = [int(x.strip()) - 1 for x in choice.split(",")]
                return [active_tasks[i] for i in indices if 0 <= i < len(active_tasks)]
            idx = int(choice) - 1
            if 0 <= idx < len(active_tasks):
                return [active_tasks[idx]]
        except ValueError:
            pass
        print("  输入无效，请重试")


def do_sign(client: ChaoxingClient, task, location_config: dict):
    """执行单个签到"""
    type_names = {
        SignType.NORMAL: "普通签到",
        SignType.PHOTO: "拍照签到",
        SignType.GESTURE: "手势签到",
        SignType.LOCATION: "位置签到",
        SignType.QRCODE: "二维码签到",
        SignType.CODE: "签到码签到",
    }

    type_name = type_names.get(task.sign_type, "未知")
    print(f"\n  >>> 正在签到: [{type_name}] {task.name}")

    # 先获取签到详情
    task = client.get_sign_detail(task)

    extra_kwargs = {}

    # 二维码签到
    if task.sign_type == SignType.QRCODE:
        if task.enc:
            extra_kwargs["enc"] = task.enc
        else:
            qr_input = input("  请输入二维码内容或 enc 参数: ").strip()
            if qr_input:
                extra_kwargs["qr_content"] = qr_input

    # 指定位置二维码签到 — enc + 经纬度
    if task.sign_type == SignType.QRCODE_LOCATION:
        if task.enc:
            extra_kwargs["enc"] = task.enc
        else:
            qr_input = input("  请输入二维码内容或 enc 参数: ").strip()
            if qr_input:
                extra_kwargs["qr_content"] = qr_input
        lng = location_config["longitude"]
        lat = location_config["latitude"]
        name = location_config["name"]
        loc = input(f"  经纬度 (格式: lng,lat，回车用默认 {name} {lng},{lat}): ").strip()
        if loc:
            parts = loc.split(",")
            if len(parts) == 2:
                extra_kwargs["longitude"] = parts[0].strip()
                extra_kwargs["latitude"] = parts[1].strip()
                extra_kwargs["location_name"] = name
        else:
            extra_kwargs["longitude"] = lng
            extra_kwargs["latitude"] = lat
            extra_kwargs["location_name"] = name

    # 位置签到 - 使用配置文件默认位置
    if task.sign_type == SignType.LOCATION:
        lng = location_config["longitude"]
        lat = location_config["latitude"]
        name = location_config["name"]
        loc = input(f"  经纬度 (格式: lng,lat，回车用默认 {name} {lng},{lat}): ").strip()
        if loc:
            parts = loc.split(",")
            if len(parts) == 2:
                extra_kwargs["longitude"] = parts[0].strip()
                extra_kwargs["latitude"] = parts[1].strip()
        else:
            extra_kwargs["longitude"] = lng
            extra_kwargs["latitude"] = lat
            extra_kwargs["location_name"] = name

    success = client.sign(task, **extra_kwargs)

    if success:
        print(f"  [OK] {task.name} 签到成功!")
    else:
        print(f"  [FAIL] {task.name} 签到失败!")

    return success

def main():
    """主流程"""
    location_config = get_location_config(config)

    clear_screen()
    print_header()

    phone, password = get_credentials(config)

    if not phone or not password:
        print("账号密码不能为空")
        sys.exit(1)

    print("\n正在登录...")
    client = ChaoxingClient()

    if not client.login(phone, password):
        print("登录失败! 请检查账号密码是否正确。")
        sys.exit(1)

    print(f"登录成功! 欢迎, {client.name or phone}")

    while True:
        course = select_course(client)
        if course is None:
            print("\n再见!")
            break

        tasks = select_task(client, course)
        selected = show_and_select_tasks(tasks)

        if not selected:
            continue

        success_count = 0
        fail_count = 0
        for task in selected:
            if do_sign(client, task, location_config):
                success_count += 1
            else:
                fail_count += 1

        print(f"\n签到完成: 成功 {success_count}, 失败 {fail_count}")


if __name__ == "__main__":
    main()
