import requests

url = "https://captcha.chaoxing.com/captcha/check/verification/result?callback=cx_captcha_function&captchaId=Qt9FIw9o4pwRjOyqM6yizZBh682qN2TU&type=slide&token=F84EDDA0700803B20E1E3131DFCDF19D&textClickArr=%5B%7B%22x%22%3A136%7D%5D&coordinate=%5B%5D&runEnv=10&version=1.1.20&t=a&iv=d4a0177e32dc65fdf0be742bf34a02b7&_=1777565975046"
method = "GET"
headers = {
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate",
    "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
    "Cookie": "fid=1993; _uid=302078632; UID=302078632; xxtenc=51b6811c3a65ee7a4bd8ad163bb59bca; fidsCount=3; _industry=5; sso_role=3; _tid=255337516; sso_puid=302078632; wfwIncode=wd68445; wfwfid=1993; spaceFid=1993; source=num2; wfwEnc=94907F80F6A17A2FF253B5785167601B; route=c17caf14c9dd9ac7be8390c41e5ffc18; _d=1777552932849; vc3=AeHMuHjUanDQEel8aLIb05sSiKoG5NTPs6ZBxNz42o4cE1uk4FlZ6qdAE55i1A3NM9JiF%2BeRt4O9UMpCLvMPnFJ3Tyz7MxsM%2F3eOLyq6pKyf7SqJdNVIU0DsZWq3jE3QM3WahSNlpvAG4I%2FgfqAYVvPdatEORso9nPlAu3YjXO4%3Da959dbbe887eab4dd358e2b773e82738; uf=b2d2c93beefa90dcf61611c3df896a108d9254ac33fb1fc0d3d29c38c74757bd8c428e795b3b128e47bc569a0c4af5d481a6c9ddee30899fd807a544f7930b6aed1e6c11a143bb563b0339d97cdac4ba25f53c4a93c9149fe5851b744f8aa02c9fb3947ed09a594c90a4723594f054d139100e5fc81c3cf577f3529634f9ce7abb63bf7c8137d67cfb8113302dc8d8b070b5a05e402d2a6370184964ffe8c27c6cbc342c64c271fb721c8b0e772fe5cfb1f899d50c1c3fa3aa2ebad65cd196bb; cx_p_token=2b6e98b611fee899439a7c49f42da794; p_auth_token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1aWQiOiIzMDIwNzg2MzIiLCJsb2dpblRpbWUiOjE3Nzc1NTI5MzI4NTEsImV4cCI6MTc3ODE1NzczMn0.5SwPj3NS45WYsMFNoBVXcWa-997m3TsnLv86JN8oKH0; DSSTASH_LOG=C_38-UN_359-US_302078632-T_1777552932851; KI4SO_SERVER_EC=RERFSWdRQWdsckJiQXZ5ZmdkWW10dkw3ZkdodVB3MERqZFdPU2wxMlRaRjk0MVB5ZFR0YktoS2k5%0ANkN0bk9aakRtU2djWlRjU2NTVQp1NG13bWtscWxRVEREMTRTSzhMbG5rS0c1N3UzazI4N3dlclJt%0ARDFtdWE0OVd4bXBHSTZodmR0eHN2ZGdiU1hyTldUSnA0VnRKekh1Ck5EcWZVcTVkZnJISWZ0cjJx%0ASWlLWmdSR2F5UW9KZUdhMzl1cDR3V0NMYUpXOFk5bERvRG9ZODA4d002UEFoQkw1NWZMR1hYd3Rm%0AL3EKRXNpYXFmR0wrQzFVYXZZaytuamcwOGNodEJGR3lkMml3ako0UWZOeE1kYTdRVHdDRlVJQ2tw%0AUXdCZE16ZU9EVHh5RzBFVVpWclpRawp1bjJlYXBzQm9Kbis2Y3p2RVlEaU5ndnM0aHJqd3JJeERj%0AUFRIUVdqQTgyTzQ1NVQ5bzJzT2pmK0lIaUpCRUFOSExFbndPUENzakVOCnc5TWRibVF2Vlo5NWlN%0AbEhmaXlkc3BmUmR0TDIzdWkrNGdwVFMwOEJrSDNyNmpRcnBwc2hkTkVmdlFuMDh2VEgzbHJuP2Fw%0AcElkPTEma2V5SWQ9MQ%3D%3D",
    "Referer": "https://mobilelearn.chaoxing.com/newsign/preSign?courseId=263432266&classId=146256641&activePrimaryId=3000158419647&general=1&sys=1&ls=1&appType=15&&tid=255337516&uid=302078632&ut=s",
    "Sec-Fetch-Dest": "script",
    "Sec-Fetch-Mode": "no-cors",
    "Sec-Fetch-Site": "same-site",
    "User-Agent": "Mozilla/5.0 (Linux; Android 9; SHARK PAR-A0 Build/PQ3A.190705.01301014; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/91.0.4472.114 Safari/537.36 com.chaoxing.mobile/ChaoXingStudy_3_4.7.4_android_phone_593_53 (@Kalimdor)_8bb93f1b4b4f45f6b00149c8e128762e",
    "X-Requested-With": "com.chaoxing.mobile",
}
data = None
response = requests.request(method, url, headers=headers, data=data)
print(response.text)
