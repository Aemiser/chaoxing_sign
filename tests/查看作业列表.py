from chaoxing_sign import ChaoxingClient
from chaoxing_sign.client import ACTIVE_TASK_URL


def get_homework_list():
 pass
def main():
    client = ChaoxingClient()
    if not client.login("13043459114", "hu431024.1"):
        print("登录失败")
        return
    courses = client.get_courses()
    for course in courses:
        print(course)
        # for homework in course.get_homeworks():
        #     print(f"  {homework.name}")
        #     for item in homework.get_items():
        #         print(f"    {item.name}")

    resp =client.session.get("https://mobilelearn.chaoxing.com/ppt/activeAPI/homeworklist", params={
        "courseId": courses[1].course_id,
        "classId": courses[1].class_id,
        "fid": "0",
        "showNotStartedActive": "0",
    }, timeout=15)
    print(resp.text)

if __name__ == '__main__':
    main()