**The English introduction is placed below the Chinese version.**

本项目基于selenium和PyQt5实现了一个淘宝商品自动筛选器，能够自动筛选价格区间，以及各种关键词的淘宝商品。  
用户只需在软件中登录淘宝账号，设置搜索关键词和过滤选项（如退货宝、运费险等），即可便捷地将商品加入购物车，减少了用户手工一件件添加商品的负担。

![](https://i-blog.csdnimg.cn/direct/16d00dfa333746c5abc6dcf3b2f407ae.png)

## 使用步骤

#### 1.	添加账号
初次运行软件后，首先点击“添加账号”按钮，在下载edgedriver环境的初始化步骤之后，系统会自动打开一个Edge浏览器。  
在打开的浏览器中登录淘宝网页，完成后再关闭浏览器，软件会自动保存账号的登录状态，如cookie、token等信息，便于下次使用。  
此外，如果账号在使用软件过程中意外退出，还可以先在左侧列表选择账号，再单击“重新登录”按钮，恢复登录状态。  

#### 2.	搜索商品
首先在左侧选择要使用的账号，然后输入商品搜索关键词，并选择商品的过滤条件：  
再点击“搜索并加入购物车”按钮，就会自动打开浏览器搜索。在当前搜索到的一整页商品中，自动将符合条件的商品加入购物车。  
是否加入成功的信息会输出在“日志”中。如果商品加入成功，软件会关闭商品的详情页。如果加入不成功，软件会保留商品的详情页不关闭，以便于用户手动加入。  
全部加入完成之后，需要关闭浏览器。关闭浏览器一段时间之后，软件会自动同步加入成功的商品到列表中。如果切换了账号，多个账号添加到购物车的商品不会重复。  
如果登录的账号设置了搜索结果默认展示成“列表式”，需要改成“卡片式”，便于软件自动操作。  
此外，如果遇到商品已经售罄，需要进一步选择款式等特殊情况，软件就不会添加商品，而是保留浏览器窗口不关闭，便于用户手动处理。  
**筛选条件：**
筛选条件的白框“☐”代表商品不能符合这个条件，“√”代表必须符合这个条件，默认的“■”代表商品既可以符合条件，也可以不符合。  
**价格：**
两个价格输入框分别表示价格区间的最大值和最小值，注意价格是包含最大值和最小值的。如果没有选中复选框，则输入的价格会被忽略。  
**搜索页数：**
搜索页数代表了在淘宝搜索多少页。一般淘宝的一页结果包含了48个商品。  
**最大商品数：**
一次最多添加多少件商品到购物车。此外如果搜索页数太小，或者筛选范围过窄，实际添加的商品数量会达不到这个数值。  

#### 3.	移除账号
首先在左侧账号页面中选中需要删除的账号，再点击“移除账号”按钮，确认删除之后可以移除账号的登录状态。  

#### 4.	自定义商品过滤条件
点击“筛选条件”列表上方的“自定义”按钮，即可自己添加商品过滤条件。注意过滤条件需要和网页上的原文一致，否则软件会无法识别。  

## 开发技术
软件基于Python开发，应用了selenium库调用Edge浏览器，实现自动操作淘宝网页，并基于PyQt5实现图形界面。此外，软件自动初始化edgedriver环境的部分还用了requests和tqdm库，其中tqdm库用于显示进度条。  

## 运行环境
软件依赖于PyQt5、selenium、requests和tqdm库，可通过命令`pip install selenium pyqt5 requests tqdm`安装，安装完成后运行`main.py`即可启动软件。  
初次在本软件启动Edge浏览器时，会自动下载Edge版本对应的`msedgedriver.exe`，并保存到软件安装目录的driver目录下，无需用户再手动初始化selenium环境。  
如果使用过程中出现了edgedriver损坏，或者Edge浏览器自动更新导致旧的edgedriver无法运行的情况，可以删除软件安装目录下的driver文件夹，软件会自动重新下载。  
此外，程序默认将配置数据，以及登录账号的数据保存在`C:\Users\<用户名>\AppData\Roaming\taobao-auto-selector`目录下。  

## 如何构建项目

在Windows中，首先启动`cmd.exe`，然后在当前目录运行`build_pyinstaller.bat`即可，会生成`build`和`dist`目录。  
如果要用Inno Setup打包项目，则需要在Inno Script Studio打开`inno\setup.iss`，点击“项目” -> “编译”（或手动从命令行调用inno setup），生成本软件的安装包。  


This project implements an automatic product filter for Taobao using selenium and PyQt5, enabling users to filter products by price range and various keywords automatically. Users can log in to their Taobao account through the software, set search keywords and filtering options (e.g., "7-Day Returns," "Shipping Insurance"), and conveniently add selected products to their cart, reducing the manual effort required for adding items one by one.  

![](https://i-blog.csdnimg.cn/direct/16d00dfa333746c5abc6dcf3b2f407ae.png)

## Usage Instructions

#### Step 1: Add an Account  
When you first run the software, click the "Add Account" button. After the software automatically downloads Edge driver, an Edge browser will be automatically opened.  
Log in to the Taobao website inside the opened browser and close the browser, then the software will automatically save the login state for future use, including cookies and tokens.  
If the account logs out unexpectedly, select the account from the list on the left and click "Re-login" to restore the login state.  

#### Step 2: Search Products  
Select the account you want to use from the list on the left, then enter the product search keywords and choose filtering options.  
Click the "Search and Add to Cart" button to open a browser and perform a search. The software will automatically add products that meet the specified criteria from the current page of search results to the cart.  
Success or failure messages will be logged in the "Log" section. If a product is added successfully, the software will close its detail page. If not, the detail page will remain open for manual addition.  
After all items have been processed, close the browser. After some time, the software will sync the successfully added products to the list. Products added to the cart under different accounts will not overlap.  

**Important Notes:**  
1. If the account's search results are displayed in "List View" by default, switch to "Card View" for the software to operate correctly.  
2. For products marked as sold out, requiring style selection, or other special situations, the software will not add them automatically and will leave the browser window open for manual handling.  

**Filtering Options:**  
- A white checkbox "☐" means the product must not meet the condition.  
- A checked box "√" means the product must meet the condition.  
- A filled box "■" (default) means the product may or may not meet the condition.  

**Price:**  
Enter the minimum and maximum prices in the two input fields. Prices are inclusive of the maximum and minimum values. If the checkbox is unchecked, the input prices will be ignored.  

**Search Pages:**  
This determines how many pages of search results the software will process. Typically, each page on Taobao contains 48 products.  

**Maximum Products:**  
This sets the maximum number of products to add to the cart in one operation. If the number of search pages is too small or the filtering range is too narrow, the actual number of products added may fall short of this value.  

#### Step 3: Remove an Account  
Select the account you want to remove from the list on the left, then click the "Remove Account" button. Confirm the action to delete the account's login state.  

#### Step 4: Customize Product Filtering Conditions  
Click the "Customize" button above the filtering options list to add custom filtering conditions. Ensure the conditions match the original text on the web page; otherwise, the software may fail to recognize them.  

## Development Framework
  The software is developed using Python with the **Selenium** library for automating Taobao web interactions and **PyQt5** for the graphical user interface.  
  Additionally, the **requests** and **tqdm** libraries are used for downloading and displaying progress bars during EdgeDriver initialization.  

## Runtime Environment
  The software depends on the following libraries:  
  ```bash
  pip install selenium pyqt5 requests tqdm
  ```  
  After installation, run `main.py` to start the software.  

  When launching the Edge browser for the first time, the software will automatically download the appropriate `msedgedriver.exe` for the installed Edge version and save it to the `driver` directory in the software's installation path. Manual Selenium environment setup is unnecessary.  

  If the EdgeDriver becomes corrupted or fails due to Edge browser updates, delete the `driver` folder in the software installation path. The software will redownload it automatically.  

  Configuration data, including login information, is saved in:  
  ```
  C:\Users\<username>\AppData\Roaming\taobao-auto-selector
  ```  

## How to Build

Open `cmd.exe` on Windows, navigate to the current directory, and run:  
```bash
build_pyinstaller.bat
```  
This will generate the `build` and `dist` directories.  

To package the project using Inno Setup, open `inno\setup.iss` in **Inno Script Studio**, then click "Project" -> "Compile" (or run Inno Setup from the command line) to create the installation package.  