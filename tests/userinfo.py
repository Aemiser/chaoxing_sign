from chaoxing_sign import ChaoxingClient
from main import load_config, get_credentials


def main ():
    client = ChaoxingClient()
    if client.login("13043459114","hu431024.1"):
        print("登录成功")
    account = client.get_account_info()
    print(f"名字:{account.name}")
    print(f"uid:{account.uid}")
    print(f"头像：{account.avatar}")
    print(f"学校：{account.school}")

if __name__ == '__main__':
    main()