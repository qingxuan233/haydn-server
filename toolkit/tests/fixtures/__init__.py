"""测试 fixture 包。

- ``adb-haydn.json``：假 ADB 输出（离线 detect/probe）
- ``profile-haydn-locked.json``：documented profile（离线 assess/plan）
- ``profile-root-lab-ready.json``：Root 实验设备 ready 样本（rootcheck）
- ``repo_builder``：临时仓库生成器（index/validate/governance/preflight 测试）

``repo_builder`` 生成的仓库结构完整（含 AGENTS.md/backlog/CHANGELOG/adr），
``validate --strict`` 可全绿；各 ``write_*`` 辅助函数可构造违规样本。
"""

from .repo_builder import (  # noqa: F401
    ADR_REQUIRED_SECTIONS,
    AGENTS_REQUIRED_SECTIONS,
    DEFAULT_UPDATED,
    PITFALL_REQUIRED_SECTIONS,
    build_sample_repo,
    make_backlog_item,
    make_front_matter,
    make_pitfall_body,
    write_adr,
    write_adr_index,
    write_agents_md,
    write_backlog,
    write_backlog_raw,
    write_changelog,
    write_changelog_archive,
    write_changelog_with_archive,
    write_doc,
    write_pitfall,
    write_preflight_harness,
    write_text,
    write_unindexed_archive,
)
