"""测试 fixture 包。

- ``adb-haydn.json``：假 ADB 输出（离线 detect/probe）
- ``profile-haydn-locked.json``：documented profile（离线 assess/plan）
- ``repo_builder``：临时仓库生成器（index/validate 测试）
"""

from .repo_builder import (  # noqa: F401
    DEFAULT_UPDATED,
    build_sample_repo,
    make_front_matter,
    write_doc,
)
