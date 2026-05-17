# ui/services/autostart.py
# 开启自启动
import os
import sys
import winreg

APP_NAME = "MintNTE"

def get_exe_path():
    """获取当前程序的可执行文件路径"""
    if getattr(sys, 'frozen', False):
        # 打包后的路径
        return sys.executable
    else:
        # 开发环境
        return os.path.abspath(sys.argv[0])

def is_auto_start_enabled():
    """检查注册表中是否已设置开机启动"""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_READ
        )
        value, _ = winreg.QueryValueEx(key, APP_NAME)
        winreg.CloseKey(key)
        return value == get_exe_path()
    except FileNotFoundError:
        return False

def set_auto_start(enabled: bool):
    """设置或取消开机启动"""
    key = winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Run",
        0, winreg.KEY_SET_VALUE
    )
    if enabled:
        exe_path = get_exe_path()
        # 如果路径包含空格，需要加引号
        if ' ' in exe_path:
            exe_path = f'"{exe_path}"'
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, exe_path)
    else:
        try:
            winreg.DeleteValue(key, APP_NAME)
        except FileNotFoundError:
            pass
    winreg.CloseKey(key)