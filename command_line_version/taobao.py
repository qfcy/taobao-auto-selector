from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchWindowException
from warnings import warn
import os,time,json,traceback

AVAILABLE_OPTIONS=[
"7天无理由退换",
"退货宝",
"大促价保",
"买贵必赔",
"假一赔四",
"包邮",
"消费券"
]
class TabManager: # 管理标签页，用于替代selenium的window_handle的实现
    def __init__(self,driver):
        self.driver=driver
        try:
            self.start_page=driver.current_window_handle
        except NoSuchWindowException:
            warn("Window is already closed. Using driver.window_handles[0] instead.")
            self.start_page=driver.window_handles[0]
            self.driver.switch_to.window(self.start_page)
        self.excludes=[] # 忽略之前打开的其他标签页
        self.opened=[] # 新打开的标签页
        for page in driver.window_handles:
            if page!=self.start_page:
                self.excludes.append(page)
    def open(self,url,switch=True):
        # 打开新标签页，并返回新打开的窗口的句柄。switch:是否切换到新标签页
        self.driver.execute_script("window.open('%s', '_blank');"%url)
        new_pages=[]
        for page in self.driver.window_handles:
            if page!=self.start_page and page not in self.excludes+self.opened:
                new_pages.append(page)
        if len(new_pages)>1:
            warn("More than 1 pages have been opened.")
        self.opened.append(new_pages[0])
        self.driver.switch_to.window(new_pages[0])
        self.driver.execute_script( # 隐藏selenium痕迹
            "try{Object.defineProperty(navigator, 'webdriver', {get: () => undefined});}catch(e){}"
        )
        if not switch:
            self.driver.switch_to.window(self.start_page)
        return new_pages[0]

class Product:
    def __init__(self,tabm,element):
        self.tabm=tabm
        self.driver=tabm.driver
        self.source_page=self.driver.current_window_handle
        self.url=element.get_property("href").strip()
        title_divs=element.find_elements(By.XPATH, ".//div[starts-with(@class, 'title--')]")
        if title_divs:
            self.name=" ".join(span.text for span in title_divs[0].find_elements(By.XPATH, ".//span")).strip()
        else:
            self.name=None
        sub_icon_wrappers = element.find_elements(By.XPATH, ".//div[starts-with(@class, 'subIconWrapper--')]")
        if sub_icon_wrappers:
            # 下方商品属性，如：退货宝，跨店每300减50
            self.attributes=[attr.strip() for attr in sub_icon_wrappers[0].text.split()]
        else:
            self.attributes=None
        nick_spans = element.find_elements(By.XPATH, ".//span[starts-with(@class, 'shopNameText--')]")
        if nick_spans:
            self.shop=nick_spans[0].text.strip() # 商品店铺名称
        else:
            self.shop=None
        self.more_guarantees=None
        self.detail_page=None
    def open_page(self): # 打开商品详情页面，并获取更多的保障信息，如运费险
        self.detail_page=self.tabm.open(self.url,switch=True)
        self.more_guarantees=[]
        wait = WebDriverWait(self.driver, 15) # 超时为15秒
        guarantee_divs = wait.until(EC.presence_of_all_elements_located((By.XPATH, "//div[starts-with(@class, 'guaranteeListWrap')]")))
        if not guarantee_divs:return
        guarantee_div = guarantee_divs[0]

        icon_elements = guarantee_div.find_elements(By.XPATH, ".//i[starts-with(@class, 'taobaowebicon')]")
        if icon_elements:
            icon_elements[0].click()  # 相当于JS的click()
            wait.until(EC.visibility_of_element_located((By.XPATH, "//div[starts-with(@class, 'moreGuaranteeListInnerWrap')]"))) # 等待列表弹出

            mixinItems=guarantee_div.find_elements(By.XPATH, ".//div[starts-with(@class, 'mixinItem')]")
            if mixinItems:
                self.more_guarantees.extend(item.text for mixinItem in mixinItems \
                                            for item in mixinItem.find_elements(By.XPATH,".//span[starts-with(@class,'descItem')]"))
            else:
                more_guarantee_items = guarantee_div.find_elements(By.XPATH, ".//div[starts-with(@class, 'moreGuaranteeItem')]")
                if more_guarantee_items:
                    self.more_guarantees.extend(item.text for item in more_guarantee_items)
        else:
            guarantee_texts=guarantee_div.find_elements(By.XPATH,".//span[starts-with(@class,'guaranteeText')]")
            if guarantee_texts:
                self.more_guarantees.extend(span.text for span in guarantee_texts)

        if self.more_guarantees:
            self.more_guarantees=[item.strip() for item in self.more_guarantees]
        else: # 空列表
            self.more_guarantees=None
    def close_page(self):
        if self.detail_page:
            pre_page=self.driver.current_window_handle
            self.driver.switch_to.window(self.detail_page)
            self.driver.close()
            try:self.driver.switch_to.window(pre_page)
            except NoSuchWindowException:
                warn("The previous window is already closed.")
            self.detail_page=None
    def add_to_cart(self): # 加入购物车
        if self.driver.current_window_handle!=self.detail_page:
            self.driver.switch_to.window(self.detail_page)
        buttons=self.driver.find_elements(By.XPATH, "//button[starts-with(@class, 'btn') and .//span[text()='加入购物车']]")
        if buttons:
            buttons[0].click()
        else:
            raise ValueError("Failed to locate the button element")

PRODUCTS_FILE="added_products.json"
def run(driver):
    if os.path.isfile(PRODUCTS_FILE):
        with open(PRODUCTS_FILE,encoding="utf-8") as f:
            added_products=json.load(f)
    else:
        added_products=[]
    tabm = TabManager(driver)
    elements = driver.find_elements(By.XPATH, "//a[starts-with(@class, 'doubleCardWrapper')]") # 目前仅支持卡片视图
    print("查询中 ...\n找到: %d 个商品" % len(elements))
    products=[]
    for elem in elements:
        product=Product(tabm,elem)
        products.append(product)
        print("品名：%s 属性：%s 店铺：%s" % (product.name,product.attributes,product.shop))
    print("\n开始自动加入购物车，请勿中途关闭页面 ...")

    for i in range(len(products)):
        product=products[i]
        try:product.open_page()
        except Exception:
            print('打开商品页面 "%s" 失败：'%product.name)
            traceback.print_exc()
            time.sleep(2);continue

        attributes=(product.attributes or []) + (product.more_guarantees or [])
        print("处理商品 (%d/%d): %s 商品属性：%s" % (
              i+1,len(products),product.name,attributes))
        if "退货运费险" not in attributes and "退货宝" not in attributes\
            and [product.name,product.shop] not in added_products:
            try:
                product.add_to_cart()
            except Exception:
                print('商品 "%s" 加入购物车失败：'%product.name)
                traceback.print_exc()
            else:
                print("成功加入购物车:",product.name)
                added_products.append([product.name,product.shop])
                with open(PRODUCTS_FILE,"w",encoding="utf-8") as f: # 确保商品不重复
                    json.dump(added_products,f)

        time.sleep(5)

    input("添加完毕，按Enter键关闭全部商品详情页面 ...")
    for product in products:
        try:product.close_page()
        except NoSuchWindowException:
            warn('Window "%s" has been already closed.'%product.name)
