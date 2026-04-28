#!/usr/bin/env python3
"""测试签到码签到（PC 端点 signIn）"""
import json
from chaoxing_sign import ChaoxingClient
from chaoxing_sign.utils import safe_json_loads

SIGN_IN_URL = "https://mobilelearn.chaoxing.com/widget/sign/pcStuSignController/signIn"


def sign_in_with_code(client: ChaoxingClient, active_id: int, class_id: int,
                      course_id: int, sign_code: str, validate: str = "") -> dict:
    """使用签到码签到"""
    resp = client.session.get(SIGN_IN_URL, params={
        "activeId": active_id,
        "classId": class_id,
        "courseId": course_id,
        "signCode": sign_code,
        "validate": validate or "",
    }, timeout=15)

    if not resp.ok:
        return {"ok": False, "http_status": resp.status_code, "text": resp.text[:200]}

    text = resp.text
    if text == "success":
        return {"ok": True, "signed": True, "message": "签到成功"}
    if "成功" in text or "已签到" in text:
        return {"ok": True, "signed": True, "message": "已完成签到"}

    data = safe_json_loads(text)
    if data:
        return {"ok": True, "data": data}

    return {"ok": False, "text": text[:500]}


def main():
    client = ChaoxingClient()
    if not client.login("13043459114", "hu431024.1"):
        print("登录失败")
        return

    print(f"登录成功: uid={client.uid}")

    result = sign_in_with_code(
        client,
        active_id=3000158057313,
        class_id=146256641,
        course_id=263432266,
        sign_code="1111",
    )

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
