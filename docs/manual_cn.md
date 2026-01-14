# 用户手册

## 目录
1.  [自动匹配原理](#自动匹配原理)
2.  [手动匹配指南](#手动匹配指南)
3.  [批量处理模式](#批量处理模式)
4.  [高级配置 (路径映射)](#高级配置)

---

## 自动匹配原理

系统会持续监控您的 `source_dir` (下载目录)。当检测到新文件时，流程如下：

1.  **扫描**: 识别符合配置扩展名 (`.mp4`, `.mkv` 等) 的视频文件。
2.  **清洗**: 分析文件名，去除杂乱信息（如 "BluRay", "x264", 制作组名称），提取核心的 标题、年份、季、集 信息。
3.  **搜索**: 使用提取的标题和年份查询 TMDB API。
4.  **匹配**:
    *   检查标题和年份是否精确匹配。
    *   对于剧集，验证季/集结构是否符合逻辑。
5.  **链接**:
    *   如果找到高置信度的匹配，会在 `target_dir` 创建一个标准命名的符号链接。
    *   如果没有匹配或置信度低，将该项目标记为“Uncertain (不确定)”或“Not Found (未找到)”，等待人工处理。

---

## 手动匹配指南

如果文件未被自动识别，您可以通过 Web 控制台手动修复。

### 基础搜索
1.  在列表中的 "Uncertain" 或 "Not Found" 标签页找到该文件。
2.  点击 **Manual Match (手动匹配)** 按钮。
3.  在搜索框输入正确的电影/剧集名称。
4.  从结果列表中选择正确的条目。

![Manual Match Interface](pic/manual_match.png)

### 高级语法 (强制 ID)
有时 TMDB 搜索结果不准确（例如同名电影、翻拍版）。您可以使用 TMDB ID 强制指定。

![Force TMDB ID Match](pic/force_tmdb_id_match.png)

*   **标准 ID**: 输入 `tmdb-12345` (尝试在当前分类下查找 ID 12345)。
*   **强制电影**: 输入 `tmdb-movie-12345` (强制系统将其视为电影 ID 12345，即使文件名看起来像剧集)。
*   **强制剧集**: 输入 `tmdb-tv-12345` (强制系统将其视为剧集 ID 12345)。

> **提示**: 您可以在 TMDB 官网的 URL 中找到 ID (例如 `themoviedb.org/movie/63168` -> ID 为 63168)。

---

## 批量处理模式

这是整理剧集的神器。当您下载了一整季剧集在一个文件夹内时（例如 `Season 1/`），使用此功能可以一次性搞定。

**场景**: 文件夹 `/Downloads/Cyberpunk/` 内包含 `Ep01.mkv`, `Ep02.mkv` 等，但系统未能自动识别。

**使用方法:**
1.  对该文件夹内的 *任意一个* 文件点击 **Manual Match**。
2.  搜索 "边缘行者" 或输入 ID `tmdb-tv-94605`。
3.  **勾选底部的 "Apply to all files in this directory (应用到此目录所有文件)" 选项。**
4.  点击确认。

**结果**:
系统会将选定的剧集信息（边缘行者）应用到该文件夹下的 **所有** 视频文件。它会根据文件名（或文件排序）智能分配季/集编号（S01E01, S01E02...）。

---

## 高级配置

### 路径映射 (Path Mapping)

这是本工具最容易配置错误的地方，请仔细阅读。

**核心问题**: 软链接本质上是一个“快捷方式”，它存储的是**文本路径**。
如果您的服务器（创建软链接的地方）和您的播放器（Infuse/Apple TV）看到的路径不一致，Infuse 点击软链接时就会找不到目标文件。

#### ⚠️ 重要提示：协议选择
*   ✅ **推荐使用 SMB 或 NFS**：Infuse 对 SMB/NFS 的软链接支持很好。
*   ❌ **不要使用 WebDAV**：WebDAV 协议本身通常不支持软链接，Infuse 无法识别。

#### 场景 1: 需要路径映射 (推荐)
这是最常见的拓扑：NAS 存储文件，Linux 服务器挂载 NAS 进行计算，Infuse 连接 NAS 观看。

*   **NAS 真实路径**: `/volume1/Media/Downloads` (这是文件在 NAS 硬盘上的实际位置)
*   **服务器挂载路径**: `/mnt/nas/downloads` (服务器通过 NFS 挂载 NAS 后的路径)
*   **Infuse 连接方式**: Infuse 通过 SMB 直接连接 NAS，它看到的路径是 `/Media/Downloads` (或者 `/volume1/Media/Downloads`，取决于 SMB 配置)。

**如果本工具直接创建指向 `/mnt/nas/downloads/movie.mkv` 的软链接，Infuse 会报错，因为它无法访问服务器的 `/mnt` 目录。**

**配置方法**:
告诉工具：“当你在 `/mnt/nas/downloads` 看到文件时，创建的软链接应该指向 `/volume1/Media/Downloads`”。

`config.yaml`:
```yaml
path_mapping:
  # "服务器上的挂载路径": "NAS 上的真实路径"
  "/mnt/nas/downloads": "/volume1/Media/Downloads"
```

#### 场景 2: 不需要路径映射 (极简模式)
如果您不想折腾路径映射，可以在运行本工具的服务器上开启 SMB 服务，让 Infuse 直接连接**这台服务器**而不是 NAS。

1.  服务器挂载 NAS 到 `/mnt/nas/downloads`。
2.  服务器生成软链接到 `/mnt/nas/media_library`。
3.  **在服务器上开启 SMB**，共享 `/mnt/nas/media_library`。
4.  Infuse 连接服务器的 SMB。

此时，Infuse 看到的路径和服务器看到的路径是一致的，**不需要配置 path_mapping**。

---

## 贡献与开发

欢迎提交 Pull Request 或 Issue！本项目目前由 Trae AI 辅助开发。

### 开发环境搭建
1.  Clone 代码。
2.  `pip install -r requirements.txt`
3.  `python main.py server`

### 贡献指南
*   如果你发现了 Bug，请提交 Issue 并附上日志。
*   如果你想增加新功能（比如适配 Jellyfin 命名规则），欢迎 PR。
*   保持代码简单，逻辑清晰。
