@echo off
rem 删除之前的打包残留文件，再调用pyinstaller打包
if exist build (
    rmdir /s /q build
    if exist build echo Error deleting build folder. & exit /B
)
if exist dist (
    rmdir /s /q dist
    if exist dist echo Error deleting dist folder. & exit /B
)
pyinstaller main.py -i taobao.ico -w --hidden-import=appdirs --exclude=tkinter --name taobao-auto-selector
copy taobao.ico dist\taobao-auto-selector\taobao.ico