# -*- coding: utf-8 -*-
"""启动器：双击 启动.bat 会走到这里，再由这里加载中文名的主程序。"""
import os
import sys
import importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, 'MSZ图片音乐.py')

spec = importlib.util.spec_from_file_location('msz_picmusic', TARGET)
mod = importlib.util.module_from_spec(spec)
sys.modules['msz_picmusic'] = mod
spec.loader.exec_module(mod)

if len(sys.argv) > 1:
    rc = mod._cli(sys.argv[1:])
    sys.exit(rc or 0)
mod.run_gui()
