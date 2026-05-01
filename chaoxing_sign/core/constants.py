"""API 端点常量"""
from __future__ import annotations

PASSPORT_HOST = "https://passport2.chaoxing.com"
MOBILE_API = "https://mobilelearn.chaoxing.com"
MOOC_API = "https://mooc1-api.chaoxing.com"
SSO_API = "https://sso.chaoxing.com"

LOGIN_URL = f"{PASSPORT_HOST}/fanyalogin"
USER_INFO_URL = f"{SSO_API}/apis/login/userLogin4UAP.do"
COURSE_LIST_URL = f"{MOOC_API}/mycourse/backclazzdata"
ACTIVE_TASK_URL = f"{MOBILE_API}/ppt/activeAPI/taskactivelist"

PRESIGN_URL = f"{MOBILE_API}/newsign/preSign"
STUSIGN_URL = f"{MOBILE_API}/pptSign/stuSignajax"
SIGN_IN_URL = f"{MOBILE_API}/widget/sign/pcStuSignController/signIn"
QRCODE_SIGN_URL = f"{MOBILE_API}/ppt/activeAPI/qrcodeSign"
LOCATION_SIGN_URL = f"{MOBILE_API}/ppt/activeAPI/locationSign"

ANDROID_UA = (
    "Dalvik/2.1.0 (Linux; U; Android 13; SM-G981B Build/TP1A.220624.014) "
    "com.chaoxing.mobile/ChaoXingStudy_3.0_48_20231201_android"
)

HEADERS = {
    "User-Agent": ANDROID_UA,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.8",
    "X-Requested-With": "com.chaoxing.mobile",
}

EARTH_RADIUS = 6371000.0
