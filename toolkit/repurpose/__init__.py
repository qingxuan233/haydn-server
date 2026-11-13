"""repurpose CLI 实现（零第三方依赖）。

模块职责：
- ``util``       路径/时间/JSON I-O/错误类型等公共设施
- ``frontmatter`` flat YAML front matter 解析（容忍 BOM/CRLF）
- ``docpolicy``  文档体积/协议/命名/治理/归档窗口/manifest 分片上限策略（缺失时回退默认）
- ``adb``        AdbTransport（真实 adb）与 FixtureTransport（离线回放）
- ``profile``    device-profile.v1 读写与结构校验
- ``detect``     采集 profile 骨架（只读命令）
- ``probe``      在 profile 上补 capabilities/verdicts（只读命令）
- ``assess``     离线路线评估（A/B/C/D 与门禁）
- ``plan``       P0-P6 阶段计划（json/md）
- ``rootcheck``  离线 Root 实验技术姿态检查（repurpose.rootcheck.v1，不改变 assess 顺序）
- ``rescuekit``  救援包 SHA-256 清单生成/校验（G-L1 辅助，只操作本地目录）
- ``indexgen``   生成根摘要 agent-manifest.json + agent-manifest.d/ 四层分片；index --check 只读一致性校验
- ``governance`` 协议/命名/PIT/ADR/CHANGELOG 归档/backlog/Agent 回归的机器契约检查
- ``validate``   front matter/ID/链接/JSON/治理契约/doc-policy/分片一致性校验
- ``cli``        argparse 入口与退出码约定（含 preflight 统一质量门 0/3/4 三态）
"""

__version__ = "0.3.0-alpha"
