#!/usr/bin/env python3
"""检测指定签到活动是否已签到"""
import json
from chaoxing_sign import ChaoxingClient
from chaoxing_sign.utils import safe_json_loads

PRE_SIGN_URL = "https://mobilelearn.chaoxing.com/widget/sign/pcStuSignController/preSign"


def check_sign_status(client: ChaoxingClient, active_id: int, class_id: int,
                      course_id: int, fid: int = 1993) -> dict:
    """返回 preSign 解析结果"""
    resp = client.session.get(PRE_SIGN_URL, params={
        "activeId": active_id,
        "classId": class_id,
        "courseId": course_id,
        "fid": fid,
    }, timeout=15)

    if not resp.ok:
        return {"ok": False, "http_status": resp.status_code, "text": resp.text[:200]}

    text = resp.text

    # 已签到标志
    if "签到成功" in text or "已签到" in text or "您已签到" in text:
        return {"ok": True, "signed": True, "message": "已完成签到"}

    # 尝试 JSON 解析
    data = safe_json_loads(text)
    if data:
        return {"ok": True, "signed": False, "data": data}

    # HTML 判断
    if "签到" in text:
        return {"ok": True, "signed": False, "message": "未签到，可以签到"}

    return {"ok": True, "signed": False, "raw": text[:500]}


def main():
    client = ChaoxingClient()
    if not client.login("13043459114", "hu431024.1"):
        print("登录失败")
        return

    print(f"登录成功: uid={client.uid}")

    result = check_sign_status(
        client,
        active_id=3000158056066,
        class_id=146256641,
        course_id=263432266,
    )

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
