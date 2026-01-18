# 项目文件说明

| 文件名 | 功能描述 |
| :--- | :--- |
| recreate_structure.py | 根据 `tree.txt` 中的文件结构在 `raw` 目录下重建目录和空文件。 |
| replace.py | 批量修复/替换软链接的目标路径前缀（用于解决跨服务器挂载路径不一致问题）。 |
| README.md | 项目详细说明文档，包含工具用法和开发计划。 |
| config.yaml | 配置文件，定义源目录、目标目录和允许的文件后缀等。 |
| requirements.txt | 项目依赖列表。 |
| main.py | 项目入口脚本，提供命令行接口。 |
| src/core/models.py | 定义媒体文件和条目的数据模型。 |
| src/core/config.py | 负责加载和管理配置信息。 |
| src/core/scanner.py | 扫描文件系统，过滤并获取视频和元数据文件。 |
| src/core/aggregator.py | 将零散的文件聚类为逻辑上的影视条目。 |
| src/core/classifier.py | 自动识别条目类型（电影或电视剧）。 |
| src/core/searcher.py | 通过 TMDB API 在线搜索影视的中英文名、年份及 TMDB ID，包含速率限制逻辑。 |
| src/core/renamer.py | 核心重命名引擎，建议符合 Infuse 规范的路径（支持 {tmdb-id}）。 |
| src/core/linker.py | 负责创建软链接并调用数据库记录映射。 |
| src/server/app.py | 基于 Flask 的 Web 服务器，提供 API 和界面。 |
| src/server/task_manager.py | 后台任务和进度管理模块。 |
| src/templates/index.html | Web 管理界面的 HTML 模板。 |
| src/db/manager.py | (Deprecated) 旧版数据库管理模块。 |
| src/cli/main.py | CLI 逻辑实现，包括 `list` 和 `link` 命令。 |
| src/infrastructure/db/database.py | 新版数据库连接与Schema管理。 |
| src/infrastructure/db/repository.py | 数据访问层 (Repository Pattern)，封装 DB 操作。 |
| src/services/scan_service.py | 扫描服务，编排扫描、聚合、分类、匹配流程。 |
| src/services/match_service.py | 匹配服务，封装 TMDB 搜索与元数据处理。 |
| src/services/link_service.py | 链接服务，处理软链接创建与 DB 记录。 |
| src/services/watch_service.py | 监听服务，基于轮询 (Polling) 的增量文件变动检测，替代了旧版的 Watchdog。 |
| scripts/rebuild_db.py | 数据库重建脚本，从 `target_dir` 恢复数据库。 |
| tests/test_rules.py | 针对重命名和分类规则的单元测试。 |
| tests/test_linker_mapping.py | 针对链接器路径映射功能的单元测试。 |
| tests/test_sanitization.py | 针对文件名Samba兼容性清理规则的单元测试。 |
| tests/test_renamer_tv.py | 针对TV剧集重命名逻辑（增加英文名前缀）的单元测试。 |
| tests/unit/test_services.py | 针对 Service 层的单元测试。 |
| tests/unit/test_polling.py | 针对轮询机制的单元测试（增量、删除、忽略隐藏文件）。 |
| tests/unit/test_optimization.py | 针对同剧集元数据复用优化的单元测试。 |
| tests/unit/test_new_features.py | 针对近期新增能力（TMDB号提取、目录判定剧集、BDMV识别、字幕处理）的单元测试。 |
| tests/e2e/specs/workflow.cy.js | Cypress 端到端测试脚本。 |
| test_tmdb.py | 用于测试 TMDB API 连接性的简单脚本，支持显示代理配置。 |
| file.md | 记录项目中各文件的功能说明。 |
