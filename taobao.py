from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchWindowException,TimeoutException,ElementClickInterceptedException,StaleElementReferenceException,JavascriptException
from urllib.parse import quote
from warnings import warn
from math import inf
import sys,os,time,json,traceback

DEFAULT_OPTIONS=[
"退货宝",
"退货运费险",
"7天无理由退换",
"大促价保",
"买贵必赔",
"假一赔四",
"包邮",
"消费券",
]
def list_diff(lst,sub_lst): # 列表的作差，找出在lst但不在sub_lst中的元素
    result=[]
    for item in lst:
        if item not in sub_lst:
            result.append(item)
    return result
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

        priceInts = element.find_elements(By.XPATH, ".//span[starts-with(@class, 'priceInt--')]")
        priceFloats = element.find_elements(By.XPATH, ".//span[starts-with(@class, 'priceFloat--')]")
        if len(priceInts)!=1 or len(priceFloats)!=1:
            self.price=None
        else:
            try:
                self.price=float(priceInts[0].text.strip()+priceFloats[0].text.strip()) # 搜索页价格
            except ValueError:
                self.price=None
        self.more_guarantees=None
        self.detail_page=None
        self.current_price=None
        self.detail_price=set()
    def open_page(self): # 打开商品详情页面，并获取更多的保障信息，如运费险
        self.detail_page=self.tabm.open(self.url,switch=True)
        self.more_guarantees=[]
        wait = WebDriverWait(self.driver, 30) # 超时为30秒 (等待用户通过验证码)
        try:guarantee_divs = wait.until(EC.presence_of_all_elements_located((By.XPATH, "//div[starts-with(@class, 'guaranteeListWrap')]")))
        except TimeoutException:
            breakpoint()
            guarantee_divs=[]
        if not guarantee_divs:return
        guarantee_div = guarantee_divs[0]

        icon_elements = guarantee_div.find_elements(By.XPATH, ".//i[starts-with(@class, 'taobaowebicon')]")
        if icon_elements:
            try:
                icon_elements[0].click()  # 相当于JS的click()
            except ElementClickInterceptedException:
                warn("商品按钮点击失败，使用driver.get代替")
                self.driver.get(self.url)
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

        self.update_highlight_price()
        more_prices=self.driver.find_elements(By.XPATH,".//span[starts-with(@class,'priceText')]")
        for price in more_prices:
            try:self.detail_price.add(float(price.text))
            except Exception:pass
    def update_highlight_price(self):
        price_div=self.driver.find_elements(By.XPATH,".//div[starts-with(@class,'highlightPrice')]")
        if not price_div:
            warn("获取高亮价格失败: 未能获取div");return
        for div in price_div: # 可能有多个高亮的价格标签
            texts=div.find_elements(By.XPATH,".//span[starts-with(@class,'text')]")
            if not texts:
                warn('获取高亮价格失败: 未能获取<span class="text--xxx">');return
            try:self.current_price=float("".join(span.text.strip() for span in texts))
            except ValueError:
                warn('获取高亮价格失败: 未能转换为浮点数 (%s)'%repr("".join(span.text.strip() for span in texts)))
    def close_page(self):
        if self.detail_page:
            pre_page=self.driver.current_window_handle
            self.driver.switch_to.window(self.detail_page)
            self.driver.close()
            try:self.driver.switch_to.window(pre_page)
            except NoSuchWindowException:
                warn("The previous window is already closed.")
            self.detail_page=None
    def choose_default_pattern(self):
        # 选择默认的商品款式，避免添加失败
        #self.driver.execute_script("window.scrollTo(0, 500);")
        content_elements = self.driver.find_elements(By.XPATH, "//div[starts-with(@class, 'content')]")

        # 遍历每个content元素
        names=set()
        for i in range(len(content_elements)):
            content=content_elements[i]
            is_selected = False
            try:
                value_items = content.find_elements(By.XPATH, ".//div[starts-with(@class, 'valueItem')]")
            except Exception: # 通常是StaleElementReferenceException
                continue
            if not value_items:continue

            for value_item in value_items:
                try:attrs=self.driver.execute_script("return Object.keys(arguments[0]);", value_item)
                except JavascriptException:
                    warn("获取单个款式属性失败")
                    attrs=[]
                if any(attr.startswith('isSelected') for attr in attrs): # 找到有商品已经选中
                    name="".join(span.text for span in value_item.find_elements(".//span"))
                    print("系统已选择款式:",name)
                    is_selected = True;break

            if not is_selected:
                value_item = None
                for item in value_items:
                    attrs=self.driver.execute_script("return Object.keys(arguments[0]);", value_item)
                    if not any(attr.startswith('isDisabled') for attr in attrs):
                        value_item=item;break # 默认选择能够选的第一项
                if value_item is None:
                    warn("该分类下找不到款式可选")
                name="".join(span.text for span in value_item.find_elements(By.XPATH,".//span"))
                if name in names:continue
                names.add(name)
                print("已选择默认的款式:",name)
                try:
                    self.driver.execute_script("arguments[0].click()",value_item)  # 点击第一个valueItem
                except Exception as err:
                    warn("选择默认商品款式失败 (%s) : %s" % (type(err).__name__,str(err)))
                else:
                    time.sleep(1)
                    # 页面可能会刷新，需要重新获取元素
                    wait = WebDriverWait(self.driver, 15) # 超时为15秒
                    try:content_elements = wait.until(EC.presence_of_all_elements_located((By.XPATH,"//div[starts-with(@class, 'content')]")))
                    except TimeoutException:
                        warn("未找到新的商品款式元素");break
                    if i==len(content_elements)-1:break # 已到达最后一个元素

    def add_to_cart(self): # 加入购物车
        if self.driver.current_window_handle!=self.detail_page:
            self.driver.switch_to.window(self.detail_page) # 切换到当前产品的页面

        buttons=self.driver.find_elements(By.XPATH, "//button[starts-with(@class, 'btn') and .//span[text()='加入购物车']]")
        if buttons:
            try:self.driver.execute_script("document.getElementById('J_TBPC_POP_detail').remove();") # 关闭弹出提示，避免遮挡
            except Exception:pass

            try:buttons[0].click()
            except ElementClickInterceptedException:
                try:
                    self.driver.execute_script("arguments[0].click()",buttons[0]) # 再次尝试
                except Exception:
                    return False,"点击添加按钮失败，请手动添加商品"

            wait = WebDriverWait(self.driver, 15)
            try:dialog=wait.until(EC.visibility_of_element_located((By.XPATH, "//div[starts-with(@id, 'message_dialog')]"))) # 等待消息框弹出
            except TimeoutException:
                warn("Failed to locate the message box")
                return False,"未知是否已加入成功"
            texts=dialog.find_elements(By.XPATH,".//span[starts-with(@class, 'mainTitle')]")
            if not texts:
                texts=dialog.find_elements(By.XPATH,".//div[starts-with(@class, 'dialogText')]") # 查找其他元素
                if not texts:
                    return False,"未知是否已加入成功"
            if texts[0].text.strip()=="成功加入购物车":
                return True,texts[0].text
            else:
                return False,texts[0].text

        else:
            return False,"未找到加入购物车的按钮"

def check_attr(attributes,includes,excludes): # 判断商品是否满足属性
    for attr in excludes:
        if attr in attributes:
            return False
    for attr in includes:
        if attr not in attributes:
            return False
    return True
def select_products(driver,keyword,added_products,failed_products,
                    includes,excludes,min_price=None,max_price=None,
                    max_pages=1,max_items=inf):
    pre_handles=driver.window_handles.copy()
    driver.get("https://s.taobao.com/search?page=1&q=%s"%quote(keyword))
    for window in list_diff(driver.window_handles,pre_handles):
        try:
            driver.switch_to.window(window) # 清理之前打开的窗口
            driver.close()
        except NoSuchWindowException:pass
    tabm = TabManager(driver)
    products=[]
    try:
        for page_id in range(1,max_pages+1):
            for i in range(10): # 最多等待30秒
                elements = driver.find_elements(By.XPATH, "//a[starts-with(@class, 'doubleCardWrapper')]") # 目前仅支持卡片视图
                if not elements:time.sleep(3) # 如果商品为空
                else:break
            print("查询中 ...\n找到: %d 个商品" % len(elements))
            for elem in elements:
                try:product=Product(tabm,elem)
                except StaleElementReferenceException:
                    warn("获取商品属性失败，元素过期");continue
                products.append(product)
                print("品名：%s 价格：%.2f 属性：%s 店铺：%s" % (
                      product.name,product.price,product.attributes,product.shop))

            # 点击按钮切换到下一页，经测试淘宝的反爬虫机制，使得无法直接通过URL切换
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight-1500);") # 滚动到底部
            buttons=driver.find_elements(By.XPATH, "//div[@class='next-pagination-list']/button") # 找出翻页按钮
            if page_id==max_pages:break # 下一轮不再需要自动翻页了
            for i in range(len(buttons)):
                button=buttons[i]
                spans = button.find_elements(By.XPATH, ".//span[@class='next-btn-helper']")
                if not spans:continue
            for i in range(len(buttons)):
                button=buttons[i]
                spans = button.find_elements(By.XPATH, ".//span[@class='next-btn-helper']")
                if not spans:continue
                num=int(spans[0].text.strip())
                if page_id<=num<=page_id+1: # 如果是当前页面，或者下一个页面
                    WebDriverWait(driver, 15).until(EC.element_to_be_clickable(button))
                    try:
                        button.click()
                        #driver.execute_script(r'document.querySelector("#search-content-leftWrap > div > div > div > div > div > button:nth-child(%d)").click()'%(i+1))
                    except ElementClickInterceptedException:
                        print("其他元素遮挡了翻页按钮，请手动关闭其他弹窗，或将浏览器窗口最大化")
                    except Exception:
                        print("点击翻页按钮 %d 失败" % page_id)
                    else:
                        time.sleep(4)
                    if num==page_id+1:break
            else:
                print("未找到翻页按钮")
    except Exception:
        traceback.print_exc()

    print("\n开始自动加入购物车，请勿中途关闭页面 ...")

    for i in range(len(products)):
        if len(added_products)>=max_items: #已到达最大数量
            break

        product=products[i]
        if [product.name,product.shop,product.url] in added_products:
            print("商品 %s 已添加过" % product.name)
            continue

        try:product.open_page()
        except NoSuchWindowException:
            print("用户可能中断了商品添加")
            try:driver.window_handles
            except Exception: # 所有窗口均已关闭
                break
        except Exception:
            print('打开商品页面 "%s" 失败：'%product.name)
            traceback.print_exc()
            time.sleep(2);continue

        try:product.choose_default_pattern()
        except Exception as err:
            warn("选择默认商品款式失败")
            traceback.print_exc()

        product.update_highlight_price() # 根据新选择的样式，更新价格
        price=product.current_price
        if price is None:
            price=max(product.detail_price) if product.detail_price else None
        price_format="%.2f"%price if price is not None else "None"
        if not (price is None or
               (min_price is None or price>=min_price) and\
               (max_price is None or price<=max_price)): # 如果价格不符，不打开详情页面
            print("商品 %s 价格不符 (%s)" % (product.name,price_format))
            product.close_page();driver.switch_to.window(tabm.start_page)
            time.sleep(3)
            continue

        attributes=(product.attributes or []) + (product.more_guarantees or [])
        if check_attr(attributes,includes,excludes):
            print("处理商品 (%d/%d): %s 价格：%s 商品属性：%s" % (
                  i+1, len(products), product.name,
                  price_format, attributes))
            try:
                success,message=product.add_to_cart()
            except Exception:
                print('商品 "%s" 加入购物车失败：'%product.name)
                traceback.print_exc()
                failed_products.append([product.name,product.shop,product.url])
            else:
                print("%s: %s" % (message,product.name))
                if success:
                    added_products.append([product.name,product.shop,product.url])
                    product.close_page() # 成功加入时，关闭标签页
                else:
                    failed_products.append([product.name,product.shop,product.url])
        else:
            print("商品标签不符 (%d/%d): %s 价格：%s 商品属性：%s" % (
                  i+1, len(products), product.name,
                  price_format, attributes))
            product.close_page()
        time.sleep(5)
        driver.switch_to.window(tabm.start_page) # 切换到起始搜索页，避免异常

    # 关闭和清理打开的商品窗口
    #for product in products:
    #    try:product.close_page()
    #    except NoSuchWindowException:
    #        warn('Window "%s" has been already closed.'%product.name)
