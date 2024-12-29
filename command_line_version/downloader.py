import os  
import requests,tqdm
import zipfile  
from pyobject import browse,search
from packaging.version import Version  

def download_file(url, destination):  
    """下载文件，使用 User-Agent 头部"""  
    headers = {  
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
               '(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 '
               'Edg/130.0.0.0'
    }  
    response = requests.get(url, headers=headers, stream=True)  
    if response.status_code == 200:  
        block_size = 1<<18  # 每次下载的块大小  
        total_size = int(response.headers['content-length'])

        # 使用 tqdm 显示进度条  
        with open(destination, 'wb') as file, tqdm.tqdm(  
                total=total_size, unit='iB', unit_scale=True) as bar:  
            for data in response.iter_content(block_size): 
                file.write(data)  # 写入文件  
                bar.update(len(data))  # 更新进度条
        print(f"下载完成: {destination}")

def unzip_file(zip_path, extract_to):  
    """解压ZIP文件"""  
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:  
        zip_ref.extractall(extract_to)  
    print(f"解压完成: {extract_to}")  

DRIVER_PATH="driver"
FILENAME="edgedriver_win64.zip"
def download_edgedriver():
    print("正在自动下载 msedgedriver.exe ...")
    edge_path = os.path.join(os.getenv("programfiles(x86)"),
                             r"Microsoft\Edge\Application")
    edge_versions=[folder for folder in os.listdir(edge_path)
                    if os.path.isdir(os.path.join(edge_path,folder))
                     and all(s.isdigit() for s in folder.split("."))]

    if not edge_versions:
        raise OSError("Edge version not found")

    edge_versions.sort(reverse=True,key=Version)
    edge_version=edge_versions[0]
    print(f"Edge 版本: {edge_version}")  

    # 根据版本下载 EdgeDriver  
    driver_url = f"https://msedgedriver.azureedge.net/{edge_version}/{FILENAME}"  
    zip_file = os.path.join(DRIVER_PATH,FILENAME)
    os.makedirs(DRIVER_PATH,exist_ok=True)

    # 下载 EdgeDriver  
    download_file(driver_url, zip_file)  

    # 解压 EdgeDriver  
    unzip_file(zip_file, DRIVER_PATH)
    os.remove(zip_file)

if __name__=="__main__":download_edgedriver()