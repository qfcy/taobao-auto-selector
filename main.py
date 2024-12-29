import sys,os,json,threading,queue,traceback
from PyQt5 import QtCore, QtGui, QtWidgets
from taobao_ui import Ui_MainWindow
from run import run_selenium
from taobao import select_products,DEFAULT_OPTIONS
from warnings import warn

ICON="taobao.ico"
_appdata=os.getenv("appdata") # 无法获取时自动使用程序安装目录
DATA_PATH=os.path.join(_appdata,"taobao-auto-selector") if _appdata else "."
ACCOUNT_PATH=os.path.join(DATA_PATH,"accounts")
CONFIG_FILE=os.path.join(DATA_PATH,"config.json")
LOGFILE=os.path.join(DATA_PATH,"last_run.log")
msg_queue=queue.Queue() # 其他线程将输出加入队列，主线程再出队并输出
def rename_key(dct,old_key,new_key):
    value=dct.pop(old_key)
    dct[new_key]=value
def is_main_thread():
    return threading.current_thread() is threading.main_thread()
def new_thread(target,*args,**kwargs):
    def target_wrapper(*args,**kw):
        try:
            target(*args,**kw)
        except BaseException:
            traceback.print_exc()
    return threading.Thread(target=target_wrapper,
        args=args,kwargs=kwargs)
def wait_thread(target,*args,**kwargs):
    # 等待线程完成，并自动处理事件，防止应用卡住
    result_queue = queue.Queue()
    def _result_wrapper(*args,**kwargs):
        result = target(*args,**kwargs)
        result_queue.put(result)

    t=new_thread(_result_wrapper,*args,**kwargs)
    t.start()
    while t.is_alive():
        while not msg_queue.empty():
            stream,msg=msg_queue.get()
            stream.write(msg)
        QtWidgets.QApplication.processEvents()
    if not len(QtWidgets.QApplication.topLevelWidgets()):
        os._exit() # 主窗口关闭后，强制退出其他线程
    return result_queue.get()

class AutoFlushWrapper: # 自动调用flush()的包装器
    def __init__(self,stream):
        self.stream=stream
    def write(self,message):
        result=self.stream.write(message)
        self.stream.flush()
        return result
    def __getattr__(self,attr):
        try:
            return super().__getattr__(self,attr)
        except AttributeError:
            return getattr(self.stream,attr) # 返回self.stream的属性和方法
class OStream:
    # 输出流，用于重定向sys.stdout和sys.stderr
    def __init__(self, text_edit, original=None, color=(0, 0, 0), to_original=False):
        self.text_edit = text_edit
        if to_original and original is None:raise ValueError("original stream is required")
        self.original = original # 旧的输出流
        self.to_original=to_original # 是否同时输出到旧的输出流
        self.color = QtGui.QColor(*color)  # 将 RGB 元组转换为 QColor 对象

    def write(self, message):
        if self.to_original:self.original.write(message)
        if not is_main_thread():
            msg_queue.put((self,message)) # 加入队列，留给主线程写入消息
            return len(message)
        else: # 如果是主线程，直接写入
            # 设置新插入文本的颜色
            format = QtGui.QTextCharFormat()
            format.setForeground(QtGui.QColor(self.color)) # 设置新插入文本的颜色
            cursor = self.text_edit.textCursor()
            cursor.movePosition(QtGui.QTextCursor.End)
            cursor.insertText(message,format)
            self.text_edit.verticalScrollBar().setValue(
                self.text_edit.verticalScrollBar().maximum()) # 滚动到底部
        return len(message)
    def flush(self): # 兼容文件对象
        if self.to_original:self.original.flush()
    def __lshift__(self,arg):
        self.write(str(arg));return self

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self._backup_stdout=sys.stdout
        self._backup_stderr=sys.stderr
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        if os.path.isfile(ICON):
            self.setWindowIcon(QtGui.QIcon(ICON))
        self.redirect_stream()

        _wrap=self._wrap
        self.ui.pushButton_2.clicked.connect(_wrap(self.manage_account))  # 添加账号
        self.ui.pushButton_3.clicked.connect(_wrap(self.remove_account))  # 移除账号
        self.ui.pushButton_4.clicked.connect(_wrap(self.reset_options))  # 重置选项
        self.ui.pushButton_5.clicked.connect(self.ui.textEdit.clear)
        self.ui.pushButton_6.clicked.connect(_wrap(self.add_custom_filter))
        self.ui.pushButton_7.clicked.connect(_wrap(self.clear_products))
        self.ui.pushButton.clicked.connect(_wrap(self.search_and_add_to_cart))  # 搜索并加入购物车
        self.ui.lstAccount.itemSelectionChanged.connect(self.on_account_selected)
        self.ui.lstFilters.itemChanged.connect(self.on_item_changed)

        self.lstProducts={} # 每个账号的列表框，用于显示添加的产品
        os.makedirs(ACCOUNT_PATH,exist_ok=True)
        if os.path.isfile(CONFIG_FILE):
            with open(CONFIG_FILE,encoding="utf-8") as f:
                self.config=json.load(f)
                for name in self.config["accounts"]:
                    self.add_account_to_ui(name)
        else:
            self.config={"addedProducts":[],"accounts":{},
                         "account_products":{}, # 每个账号加入购物车的产品
                         "failed_products":{}, # 每个账号加入失败的产品
                         "includes":[],"excludes":[],
                         "filters":DEFAULT_OPTIONS}
        self.add_filters()

    # 界面实现部分
    def _wrap(self,orig_func): # 用于在当前任务未完成时，拒绝执行新的操作
        def func(_unused,*args,**kw):
            if self.ui.statusbar.currentMessage()!="就绪":
                QtWidgets.QMessageBox.warning(self, "警告", "请等待当前任务完成！")
                return
            orig_func(*args,**kw)
        return func
    def on_account_selected(self):
        items=self.ui.lstAccount.selectedItems()
        self.ui.pushButton_2.setText("重新登录" if len(items) else "添加账号")
    def manage_account(self):
        items=self.ui.lstAccount.selectedItems()
        if len(items):
            self.relogin(items[0].text())
        else:
            self.add_account()
    def add_account_to_ui(self,name):
        def event_wrapper():
            self.open_product(name) # 便于在回调中传递账号名称信息
        # 将账号添加到UI
        self.ui.lstAccount.addItem(name)
        tab = QtWidgets.QWidget()
        tab.setObjectName("tab")
        lstWidget = QtWidgets.QListWidget(tab)
        lstWidget.setGeometry(QtCore.QRect(0, 0, 271, 470))
        lstWidget.itemDoubleClicked.connect(self._wrap(event_wrapper))
        for product_name,shop,url in self.config["account_products"][name]:
            lstWidget.addItem("%s (%s)"%(product_name,shop))
        for product_name,shop,url in self.config["failed_products"][name]:
            item=QtWidgets.QListWidgetItem("%s (%s)"%(product_name,shop))
            item.setForeground(QtGui.QBrush(QtGui.QColor(255,0,0)))
            lstWidget.addItem(item)
        self.lstProducts[name]=lstWidget
        self.ui.tabWidget.addTab(tab, name)
    def add_filters(self):
        for filter_option in self.config["filters"]:
            item = QtWidgets.QListWidgetItem(filter_option)
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)  # 设置为可复选
            state=QtCore.Qt.PartiallyChecked # 默认选中一半
            if filter_option in self.config["includes"]:
                state=QtCore.Qt.Checked
            elif filter_option in self.config["excludes"]:
                state=QtCore.Qt.Unchecked
            item.setCheckState(state)
            self.ui.lstFilters.addItem(item)
    def add_custom_filter(self):
        filter, ok = QtWidgets.QInputDialog.getText(self, '添加商品筛选条件',
                                                  '请输入商品筛选条件 (如: 退货运费险):')

        if ok and filter.strip():
            self.config["filters"].append(filter.strip())
            self.save_config()
            item = QtWidgets.QListWidgetItem(filter)
            item.setCheckState(QtCore.Qt.PartiallyChecked)
            self.ui.lstFilters.addItem(item)
    def on_item_changed(self):
        # 判断要添加的筛选条件
        includes=[];excludes=[]
        for index in range(self.ui.lstFilters.count()):
            item = self.ui.lstFilters.item(index)
            check_state = item.checkState()
            if check_state==QtCore.Qt.Checked:
                includes.append(item.text())
            elif check_state==QtCore.Qt.Unchecked:
                excludes.append(item.text())
        self.config["includes"]=includes
        self.config["excludes"]=excludes
        self.save_config() # 保存上次的筛选条件记录
    def reset_options(self):
        for index in range(self.ui.lstFilters.count()):
            item = self.ui.lstFilters.item(index)
            item.setCheckState(QtCore.Qt.PartiallyChecked)  # 默认未选中
    def clear_products(self):
        if QtWidgets.QMessageBox.question(
            self,
            '确认',
            '确定要移除全部商品吗？',
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No  # 默认选择为“否”
        ) == QtWidgets.QMessageBox.No:return
        self.config["addedProducts"].clear()
        for lst in self.config["account_products"].values():
            lst.clear()
        for lst in self.config["failed_products"].values():
            lst.clear()
        self.save_config()
        for lstWidget in self.lstProducts.values():
            lstWidget.clear()
    def closeEvent(self, event): # 主窗口关闭时，退出其他线程
        os._exit(0)

    # 工具函数 (utility)
    def redirect_stream(self):
        # 重定向sys.stdout和sys.stderr
        logfile=AutoFlushWrapper(open(LOGFILE,"w",encoding="utf-8"))
        sys.stdout=OStream(self.ui.textEdit,logfile,to_original=True) # 同时记录到日志框和日志文件
        sys.stderr=logfile # sys.stderr直接记录到日志文件
        #sys.stderr=OStream(self.ui.textEdit,self._backup_stderr,
        #                   to_original=True,color=(255,0,0))
    def reset_stream(self):
        sys.stdout=self._backup_stdout
        sys.stderr=self._backup_stderr
    def allocate_json(self): # 为新账号申请json的文件名
        exists=[] # 已有的文件名整数序号的列表
        for file in os.listdir(ACCOUNT_PATH):
            try:exists.append(int(os.path.splitext(file)[0]))
            except Exception:pass
        if not exists:
            num=0
        else:
            num=max(exists)+1
        return os.path.join(ACCOUNT_PATH,"%d.json"%num)
    def save_config(self):
        try:
            with open(CONFIG_FILE,"w",encoding="utf-8") as f:
                json.dump(self.config,f)
        except Exception as err:
            QtWidgets.QMessageBox.critical(self, "错误",
                "保存配置文件到 %s 失败！\n%s: %s" % (CONFIG_FILE,type(err).__name__,str(err)))

    # 功能实现部分
    def add_account(self): # 新增账号
        if not self.config["accounts"]:
            # 针对新手用户显示说明
            QtWidgets.QMessageBox.information(self, "操作说明",
                "请在新打开的浏览器登录淘宝后，再手动关闭浏览器。", QtWidgets.QMessageBox.Ok)
        file=self.allocate_json()
        self.ui.statusbar.showMessage("浏览器运行中，等待登录结果 ...")
        wait_thread(run_selenium,
                    lambda _:None,cookie_path=file) # 用空函数调用run_selenium
        self.ui.statusbar.showMessage("就绪")
        try:
            with open(file,encoding="utf-8") as f:
                cookie=json.load(f) # 退出浏览器后，加载保存的cookie
        except Exception:
            name=None
        else:
            name=cookie.get(".taobao.com",{}).get("tracknick",{}).get("value") # 获取用户昵称

        if name is None:
            QtWidgets.QMessageBox.warning(self, "警告", "未检测到登录信息，请重试添加账号！")
            return
        self.config["accounts"][name]=file
        self.config["account_products"][name]=[]
        self.config["failed_products"][name]=[]
        self.save_config()
        self.add_account_to_ui(name)
        QtWidgets.QMessageBox.information(self, "信息", "添加账号成功：%s"%name, QtWidgets.QMessageBox.Ok)

    def relogin(self,account_name):
        file=self.config["accounts"][account_name]
        self.ui.statusbar.showMessage("浏览器运行中，等待登录结果 ...")
        wait_thread(run_selenium,
                    lambda _:None,cookie_path=file) # 用空函数调用run_selenium
        self.ui.statusbar.showMessage("就绪")
        try:
            with open(file,encoding="utf-8") as f:
                cookie=json.load(f)
        except Exception:
            new_name=None
        else:
            new_name=cookie.get(".taobao.com",{}).get("tracknick",{}).get("value")

        if new_name is None:
            QtWidgets.QMessageBox.warning(self, "警告", "未检测到登录信息，请重试添加账号！")
            return
        # 如果用户登录了其他账号名称，则重命名账号
        if new_name!=account_name:
            repeat=new_name in self.config["accounts"] # 是否和已有账号重复
            rename_key(self.config["accounts"],account_name,new_name)
            rename_key(self.config["account_products"],account_name,new_name)
            rename_key(self.config["failed_products"],account_name,new_name)
            rename_key(self.lstProducts,account_name,new_name)
            self.save_config()

            # 在界面修改名称
            for i in range(self.ui.tabWidget.count()):
                if self.ui.tabWidget.tabText(i) == account_name:
                    self.ui.tabWidget.setTabText(i, new_name)
            for i in range(self.ui.lstAccount.count()):
                item=self.ui.lstAccount.item(i)
                if item.text() == account_name:
                    item.setText(new_name)
            if repeat:
                QtWidgets.QMessageBox.information(self, "警告", "账号 %s 已存在，请移除重复的账号！"%new_name)
            else:
                QtWidgets.QMessageBox.information(self, "信息", "账号已从 %s 更改为 %s ！"%(account_name,new_name))
        else:
            QtWidgets.QMessageBox.information(self, "信息", "账号 %s 重新登录成功！"%account_name)
    def remove_account(self): # 移除账号
        selected_items = self.ui.lstAccount.selectedItems()
        if not selected_items:  # 如果有选中的项
            QtWidgets.QMessageBox.warning(self, "警告", "请在左侧列表选择要移除的账号！")
            return
        for item in selected_items:
            name=item.text()
            if QtWidgets.QMessageBox.question(
                    self,
                    '确认',
                    '确定要移除 %s 吗？' % name,
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                    QtWidgets.QMessageBox.No  # 默认选择为“否”
                ) == QtWidgets.QMessageBox.No:continue
            os.remove(self.config["accounts"][name]) # 删除账号数据文件
            del self.config["accounts"][name]
            for product in self.config["account_products"][name]:
                if product in self.config["addedProducts"]:
                    self.config["addedProducts"].remove(product) # 从所有账号的商品信息中，移除该账号的商品
                else:
                    warn('The product %s (%s) is not in self.config["addedProducts"]'%product)
            del self.config["account_products"][name]
            del self.config["failed_products"][name]
            for i in range(self.ui.tabWidget.count()):
                if self.ui.tabWidget.tabText(i)==name:
                    self.ui.tabWidget.removeTab(i)
                    break
            self.ui.lstAccount.takeItem(self.ui.lstAccount.row(item))  # 从列表中移除选中的项
        self.save_config()

    def search_and_add_to_cart(self): # 核心功能，筛选商品
        keyword=self.ui.lineEdit.text()
        if not keyword.strip():
            QtWidgets.QMessageBox.warning(self, "警告", "请输入要搜索的商品名称！")
            return
        selected_items = self.ui.lstAccount.selectedItems()
        if not selected_items:  # 如果没有选中的项
            QtWidgets.QMessageBox.warning(self, "警告", "请先在左侧列表选择账号！")
            return
        if not self.config["addedProducts"] and \
            not self.config["failed_products"]: # 如果全部账号没有添加失败过
            # 针对新手用户显示说明
            QtWidgets.QMessageBox.information(self, "操作说明",
                "浏览器会自动添加商品，请勿中途关闭浏览器。", QtWidgets.QMessageBox.Ok)

        if self.ui.chkMin.isChecked():
            min_price=self.ui.spinPriceMin.value()
        else:
            min_price=None
        if self.ui.chkMax.isChecked():
            max_price=self.ui.spinPriceMax.value()
        else:
            max_price=None
        if None not in (min_price,max_price) and\
                min_price>max_price:
            QtWidgets.QMessageBox.warning(self, "警告", "商品价格输入不正确，请重新输入价格！")
            return

        includes,excludes=self.config["includes"],self.config["excludes"]
        name=selected_items[0].text()
        cookie_file=self.config["accounts"][name]
        added_products=self.config["addedProducts"]
        failed_products=self.config["failed_products"][name]
        pre_length=len(added_products);pre_length_fail=len(failed_products)
        max_items = self.ui.spinBox.value()+pre_length  # 获取可新增的最大商品数，需加上现有的长度pre_length

        self.ui.statusbar.showMessage("浏览器运行中，关闭浏览器会使添加中断 ...")
        wait_thread(run_selenium,
                    select_products, keyword,
                    added_products, failed_products, # 会就地修改added_products和failed_products
                    includes, excludes, min_price, max_price,
                    self.ui.spinPageCnt.value(),
                    max_items=max_items,
                    cookie_path=cookie_file,
                    mainloop=False, # 不等待浏览器退出
                    update_cookie=False, # 不更新cookie，避免意外退出登录
                    quit=False) # 完成后不关闭浏览器

        self.ui.statusbar.showMessage("就绪")
        for product_name,shop,url in added_products[pre_length:]: # 添加商品到列表
            formatted_name="%s (%s)"%(product_name,shop)
            self.lstProducts[name].addItem(formatted_name)
            self.config["account_products"][name].append([product_name,shop,url])
        for product_name,shop,url in failed_products[pre_length_fail:]: # 添加失败商品
            formatted_name="%s (%s)"%(product_name,shop)
            item=QtWidgets.QListWidgetItem(formatted_name)
            item.setForeground(QtGui.QBrush(QtGui.QColor(255,0,0)))
            self.lstProducts[name].addItem(item)
            failed_products.append([product_name,shop,url])
        self.save_config()
        fail_msg="0 件添加失败。" if len(failed_products)==pre_length_fail \
                 else "\n%d 件添加失败，请手动添加！"%(len(failed_products)-pre_length_fail)
        QtWidgets.QMessageBox.information(self, "信息", ("已添加 %d 件商品！"+fail_msg) % (len(added_products)-pre_length))
    def open_product(self,name): # 单独打开一件商品的详情页面
        items=self.lstProducts[name].selectedItems()
        if not items:
            QtWidgets.QMessageBox.warning(self, "警告", "请选择要打开的商品！")
        text=items[0].text()
        for product_name,shop,url in self.config["account_products"][name]+\
                                     self.config["failed_products"][name]:
            if text.startswith(product_name):
                wait_thread(run_selenium,
                            lambda driver:driver.get(url),
                            cookie_path=self.config["accounts"][name],
                            mainloop=False,
                            update_cookie=False,
                            quit=False)
                break

if __name__ == "__main__":
    os.makedirs(DATA_PATH,exist_ok=True) # 初始化数据保存目录
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()  # 显示窗口
    sys.exit(app.exec_())  # 运行应用程序