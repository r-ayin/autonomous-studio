#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""统一 profile 加载入口

profile.json 是 build 产物（只读），承载环境身份。
脚本和 bff_client.py 共用此模块，不自行拼路径。

查找路径：从 core/ 目录往上一级找 profile.json
即 dist/dataworks/profile.json
"""

import json
import os


def load_profile():
    """加载 profile.json（build 产物，只读）

    Returns:
        dict: profile 内容（env, auth, features, error_messages）

    Raises:
        FileNotFoundError: profile.json 不存在
    """
    core_dir = os.path.dirname(os.path.abspath(__file__))
    skill_dir = os.path.dirname(core_dir)  # core/ 的上级 = skill 根目录
    path = os.path.join(skill_dir, "profile.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
