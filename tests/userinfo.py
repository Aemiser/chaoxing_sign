from pprint import pprint

from chaoxing_sign import ChaoxingClient, Course
from main import load_config, get_credentials

client = ChaoxingClient()
if client.login("13043459114", "hu431024.1"):
    print("登录成功")
def info ():
    account = client.get_account_info()
    print(f"名字:{account.name}")
    print(f"uid:{account.uid}")
    print(f"头像：{account.avatar}")
    print(f"学校：{account.school}")

def active_task():
    course = Course(
        course_id="263432266",
    class_id="146256641",
    )
    list = client.get_sign_tasks(course)
    pprint(list)
if __name__ == '__main__':
    active_task()