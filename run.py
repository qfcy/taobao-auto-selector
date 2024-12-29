from selenium import webdriver # 懒加载selenium库
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options
from warnings import warn
import sys,os,importlib,traceback,time,shutil,_thread,json
from downloader import download_edgedriver
from selenium.common.exceptions import TimeoutException
from taobao import *

def hide_terminal(title): # 隐藏webdriver的控制台窗口
    if sys.platform=="win32":
        from ctypes import windll,c_char_p
        hwnd=windll.user32.FindWindowW(c_char_p(None),title)
        if hwnd!=0:
            windll.user32.ShowWindow(hwnd,0) # 0:SW_HIDE

COOKIE_FILE="cookies.json"
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
def add_cookies(driver,cookies,website):
    filtered_cookie={}
    for domain in cookies: # 筛选出特定网站的cookie
        if website in domain:
            filtered_cookie[domain]=cookies[domain]
    for cookie in cookie_to_list(filtered_cookie):
        try:
            driver.add_cookie(cookie)
        except Exception as err:
            print("Failed to add cookie %s: %s\n(%s): %s" % (cookie["domain"],
                 cookie["name"],type(err).__name__,str(err)),file=sys.stderr)
def daemon(driver,cookie_path):
    while True:
        try:
            time.sleep(1)
            try:
                if not driver.window_handles:break
            except Exception:
                break
            if cookie_path is not None:
                cookies = driver.get_cookies() # 每隔一段时间自动保存cookie
                with open(cookie_path, "w", encoding="utf-8") as file:
                    json.dump(cookie_to_json(cookies), file)
            driver.execute_script(
                "try{Object.defineProperty(navigator, 'webdriver', {get: () => undefined});}catch(e){}"
            )
        except Exception as err:
            warn("Failed (%s): %s" % (type(err).__name__,str(err))) # 直到主线程退出时，线程才退出

def _mainloop(driver): # 等待用户关闭浏览器
    while True:
        try:
            while driver.window_handles:
                time.sleep(1)
        except Exception:
            break

#USER_DATA="user_data" # 存放用户数据的路径
DRIVER_PATH="driver"
def run_selenium(func,*args,cookie_path=None,mainloop=True,
                 update_cookie=True,quit=True,hide_console=True,**kw):
    driver_executable=os.path.join(DRIVER_PATH,"msedgedriver.exe")
    if not os.path.isfile(driver_executable):
        download_edgedriver() # 自动下载edgedriver
    service = Service(executable_path=driver_executable)
    options = Options()
    #options.add_argument("user-data-dir=%s"%USER_DATA)
    driver = webdriver.Edge(service=service,options=options)
    if hide_console:hide_terminal(os.path.realpath(driver_executable))

    print("已启动 Edge")
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
       "source": """Object.defineProperty(navigator, 'webdriver', {get: () => undefined})""",
    }) # 将window.navigator.webdriver设为undefined，隐藏selenium痕迹
    _thread.start_new_thread(daemon,(driver,cookie_path if update_cookie else None,))

    # 加入cookie
    if cookie_path is not None and \
        os.path.isfile(cookie_path):
        with open(cookie_path, encoding="utf-8") as file:
            cookies = json.load(file)

        # 首先打开taobao.com (不需要加载完毕)，便于设置cookie
        pre_timeout=40 # TODO: driver未提供获取原先超时的功能
        try:
            driver.set_page_load_timeout(0.5)
            driver.get("https://www.taobao.com")
        except TimeoutException:
            pass
        driver.set_page_load_timeout(pre_timeout) # 设置回原先的时间
        driver.delete_all_cookies() # 删除未登录时的cookie，避免被未登录的状态影响
        add_cookies(driver,cookies,"taobao.com")
        driver.refresh() # 刷新页面，使cookie生效
    else:
        driver.get("https://www.taobao.com")

    result=None
    try:
        if func is not None:
            result=func(driver,*args,**kw) # 调用目标函数
        if mainloop:_mainloop(driver)
    except Exception:
        traceback.print_exc() # 打印错误
    if quit:driver.quit()
    return result
