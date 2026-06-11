import requests, json, re

GITHUB_REPO = "daoqi/MintNTE"
API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

try:
    req = requests.get(API_URL, headers={"User-Agent": "MintNTE"}, timeout=10, verify=False)
    req.raise_for_status()
    data = req.json()
    body = data.get("body", "")

    print("=== 远程 Release body ===")
    print(body)
    print("=========================")

    # 与 updater.py 完全相同的正则
    m = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', body, re.DOTALL)
    if m:
        versions = json.loads(m.group(1))
        print("解析出的插件版本:", versions)
    else:
        print("未匹配到任何插件版本信息")
except Exception as e:
    print("网络错误:", e)