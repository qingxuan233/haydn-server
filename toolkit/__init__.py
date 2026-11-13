"""haydn-server 通用改造工具链（零第三方依赖）。

子包 ``toolkit.repurpose`` 提供 Android 手机改造通用 CLI：
detect / probe / assess / plan / new-profile / index / validate / preflight。

入口：
    python -m toolkit.repurpose --help

工具链只做**只读探测、离线评估、代码/文档生成与校验**，不执行刷机、
不写设备、不连接真机以外的前置条件由 ADB 提供。
"""

__version__ = "0.1.0-alpha"
