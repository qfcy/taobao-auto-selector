@echo off
rem 将pyqt5的.ui文件转换为python代码
pyuic5 %1 -o %~dpn1_build.py