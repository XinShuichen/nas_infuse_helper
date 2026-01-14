# NAS Infuse Helper

> [**中文说明 (Chinese README)**](README_zh-CN.md) | [**User Manual (English)**](docs/manual_en.md) | [**用户手册 (中文)**](docs/manual_cn.md)

> 🚀 **100% Created by [Trae](https://trae.ai) SOLO in approx. 2 days of spare time.**

**NAS Infuse Helper** is an automated tool designed to organize chaotic media libraries (Movies, TV Shows) on your NAS for perfect metadata scraping in Infuse (or Plex/Emby/Jellyfin), **without modifying the original files**.

It uses **Symbolic Links (Symlinks)** to create a clean, organized directory structure (e.g., `Movies/Avatar (2009)/Avatar.mkv`, `TV Shows/Breaking Bad/Season 1/S01E01.mkv`) pointing to your original messy download folder. This ensures your P2P seeding remains intact while your media player sees a pristine library.

## 🌟 Key Features

![Web Dashboard](docs/pic/main_page.png)

*   **Non-Destructive**: Uses symlinks. Original files are never moved or renamed. Seeding continues uninterrupted.
*   **Auto-Match**: Automatically identifies Movies and TV Shows using TMDB API.
*   **Smart Organization**: 
    *   Renames files to standard `SxxExx` format for TV Shows.
    *   Groups movies into folders `Name (Year)`.
    *   Handles multi-file movies and complex nested folders.
*   **Web Dashboard**: A modern, responsive Web UI to manage your library, view stats, and manually fix unmatched items.
*   **Manual Match**: Powerful manual matching with support for:
    *   Keyword search.
    *   Direct TMDB ID lookup (`tmdb-12345`).
    *   **Forced Type Lookup**: Force a Movie ID (`tmdb-movie-12345`) or TV ID (`tmdb-tv-12345`) to resolve conflicts.
    *   **Batch Mode**: Apply a match to all files in a directory (perfect for TV Show seasons).
*   **Real-time Monitoring**: Watches your source directory for new downloads and organizes them instantly.
*   **Path Mapping**: Supports complex setups where the NAS path (e.g., `/volume1/data`) differs from the mount path on the server (e.g., `/mnt/nas/data`).

## 🏗 Architecture & Topology

This project was built for a specific but common use case:

*   **Storage**: Synology NAS (hosting the raw files).
*   **Compute**: Intel i3 Server (running this helper).
*   **Playback**: Apple TV (Infuse).

### Setup Diagram

1.  **NAS**: Exports the download folder via NFS/SMB.
2.  **Server**: Mounts the NAS folder.
    *   **Source**: `/mnt/nas/downloads` (Messy raw files).
    *   **Target**: `/mnt/nas/media_library` (Organized Symlinks).
3.  **NAS Infuse Helper**: Runs on the Server. It scans `Source`, identifies content, and creates symlinks in `Target`.
4.  **Infuse (Apple TV)**: Points to `Target` (via SMB/NFS/WebDAV from the NAS or Server). It sees a perfect library structure.

## 🚀 Getting Started

### Prerequisites

*   Python 3.9+
*   A TMDB API Key (Free from [themoviedb.org](https://www.themoviedb.org/))
*   Network access to your media files.

### Installation

1.  Clone the repository:
    ```bash
    git clone https://github.com/XinShuichen/nas_infuse_helper.git
    cd nas_infuse_helper
    ```

2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

3.  Configure:
    Copy `config.example.yaml` to `config.yaml` and edit it:
    ```bash
    cp config.example.yaml config.yaml
    nano config.yaml
    ```
    *   `source_dir`: Where your raw downloads are.
    *   `target_dir`: Where you want the organized links.
    *   `tmdb_api_key`: Your API key.
    *   `path_mapping`: (Optional) If running in Docker or across network mounts.

4.  Run:
    ```bash
    python3 main.py server
    ```
    The Web UI will be available at `http://localhost:5000`.

## 📖 Usage Guide

See [User Manual](docs/manual_en.md) for detailed instructions on:
*   **Path Mapping Configuration** (Critical!).
*   Automatic Matching Logic.
*   Manual Matching & Advanced Syntax.
*   Batch Processing for TV Shows.
*   Troubleshooting.

## ⚠️ Protocol Warning

*   **Recommended**: Use **SMB** or **NFS** to share your library with Infuse.
*   **Avoid**: Do NOT use **WebDAV**. The WebDAV protocol generally does not support symbolic links, and Infuse will not be able to see your files.

## 🤝 Contributing

We welcome contributions! Please see the [Development Guide](docs/manual_en.md#contributing) in the manual.

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.

---
*Built with ❤️ by Trae AI.*
