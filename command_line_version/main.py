from selenium import webdriver # 懒加载selenium库
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options
from warnings import warn
import sys,os,importlib,traceback,time,shutil,_thread,json
from downloader import download_edgedriver
from selenium.common.exceptions import TimeoutException

def cookie_to_json(cookie_list):
    # 将cookie的列表转换为字典
    cookies={}
    for cookie in cookie_list:
        cookie=cookie.copy()
        domain,name=cookie.pop("domain"),cookie.pop("name")
        if domain in cookies:
            cookies[domain][name]=cookie
        else:
            cookies[domain]={name:cookie}
    return cookies
def cookie_to_list(cookie_dict):
    # 返回一个生成器，将字典格式的cookie转换为列表
    for domain in cookie_dict:
        for name in cookie_dict[domain]:
            cookie=cookie_dict[domain][name].copy()
            cookie["domain"]=domain
            cookie["name"]=name
            yield cookie
def daemon(driver):
    while True:
        try:
            time.sleep(1)
            cookies = driver.get_cookies()
            with open(COOKIE_FILE, "w", encoding="utf-8") as file:  
                json.dump(cookie_to_json(cookies), file)
            driver.execute_script(
                "try{Object.defineProperty(navigator, 'webdriver', {get: () => undefined});}catch(e){}"
            )
        except Exception as err:
            warn("Failed (%s): %s" % (type(err).__name__,str(err))) # 直到主线程退出时，线程才退出

USER_DATA="user_data" # 存放用户数据的路径
DRIVER_PATH="driver"
COOKIE_FILE="cookies.json"
def main():
    import taobao # 用于热加载
    driver_executable=os.path.join(DRIVER_PATH,"msedgedriver.exe")
    if not os.path.isfile(driver_executable):
        download_edgedriver() # 自动下载edgedriver
    service = Service(executable_path=driver_executable)
    options = Options()
    #options.add_argument("user-data-dir=%s"%USER_DATA)  
    driver = webdriver.Edge(service=service,options=options)
    print("已启动 Edge")
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
       "source": """Object.defineProperty(navigator, 'webdriver', {get: () => undefined})""",
    }) # 将window.navigator.webdriver设为undefined，隐藏selenium痕迹
    _thread.start_new_thread(daemon,(driver,))
    pre_timeout=30 # TODO: driver未提供获取原先超时的功能
    try:
        driver.set_page_load_timeout(0.5)
        driver.get("https://www.taobao.com")
    except TimeoutException:
        pass
    driver.set_page_load_timeout(pre_timeout)
    if os.path.isfile(COOKIE_FILE):
        with open(COOKIE_FILE, encoding="utf-8") as file:  
            cookies = json.load(file)
        
        taobao_cookie={}
        for domain in cookies: # 筛选出淘宝的cookie
            if "taobao.com" in domain:
                taobao_cookie[domain]=cookies[domain]
        for cookie in cookie_to_list(cookies):  
            try:
                driver.add_cookie(cookie)
            except Exception as err:
                print("Failed to add cookie %s: %s\n(%s): %s" % (cookie["domain"],
                     cookie["name"],type(err).__name__,str(err)),file=sys.stderr)
    driver.refresh() # 再次刷新
    input("请登录淘宝，再搜索一个商品，并保持在搜索界面，然后按下Enter开始 ...")
    while True: # 热重载taobao.py模块，修改taobao.py之后可热重载程序，不需要重启selenium和重新登录
        try:
            if not driver.window_handles:break
        except Exception as err:
            print("Exiting (%s): %s" % (type(err).__name__,str(err)))
            break
        try:
            taobao=importlib.reload(taobao) # 热重载taobao.py模块
            taobao.run(driver)
        except Exception:
            traceback.print_exc() # 打印错误
        except KeyboardInterrupt:
            traceback.print_exc() # 打印错误
        #time.sleep(5)
        input("完成。现在您可以打开新的搜索页面，或者切换账号。\n按 Enter 继续下一次操作，按Ctrl+C退出 ...")
    driver.quit()

if __name__=="__main__":main()