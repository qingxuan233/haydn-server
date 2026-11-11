"""repurpose CLI 实现（零第三方依赖）。

模块职责：
- ``util``       路径/时间/JSON I-O/错误类型等公共设施
- ``frontmatter`` flat YAML front matter 解析（容忍 BOM/CRLF）
- ``adb``        AdbTransport（真实 adb）与 FixtureTransport（离线回放）
- ``profile``    device-profile.v1 读写与结构校验
- ``detect``     采集 profile 骨架（只读命令）
- ``probe``      在 profile 上补 capabilities/verdicts（只读命令）
- ``assess``     离线路线评估（A/B/C/D 与门禁）
- ``plan``       P0-P6 阶段计划（json/md）
- ``indexgen``   生成 agent-manifest.json
- ``validate``   front matter/ID/链接/JSON/manifest 校验
- ``cli``        argparse 入口与退出码约定
"""

__version__ = "0.1.0-alpha"
