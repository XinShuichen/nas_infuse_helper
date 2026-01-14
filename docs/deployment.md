# NAS Infuse Helper 部署指南 (Fedora / systemd)

本项目支持在 Fedora 等 Linux 系统上作为 systemd 服务运行，并具备文件系统实时监控功能。

## 1. 环境准备

### 安装依赖
确保系统中已安装 Python 3.9+ 和 pip：
```bash
sudo dnf install -y python3 python3-pip
```

### 克隆代码并安装 Python 依赖
```bash
cd /opt
sudo git clone <your-repo-url> nas_infuse_helper
cd nas_infuse_helper
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 2. 配置

编辑 `config.yaml`，确保以下路径和配置正确：
- `source_dir`: 你的 NAS 原始资源目录
- `target_dir`: 存放软链接的目标目录
- `tmdb_api_key`: 你的 TMDB API Key
- `server_port`: 5010 (已默认配置)

## 3. 部署为 systemd 服务

创建服务文件 `/etc/systemd/system/nas-infuse.service`：

```ini
[Unit]
Description=NAS Infuse Helper Web Service
After=network.target
After=datanas.mount RK.mount
Wants=datanas.mount RK.mount

[Service]
# 修改为你的实际运行用户
User=bytedance
Group=bytedance
WorkingDirectory=/opt/nas_infuse_helper
# 设置环境变量
Environment="PYTHONPATH=/opt/nas_infuse_helper"
Environment="PATH=/opt/nas_infuse_helper/venv/bin"
# 启动命令
ExecStart=/opt/nas_infuse_helper/venv/bin/python3 main.py server
Restart=always
RestartSec=5
StartLimitIntervalSec=300
StartLimitBurst=5

[Install]
WantedBy=multi-user.target
```

### 启动服务
```bash
sudo systemctl daemon-reload
sudo systemctl enable nas-infuse
sudo systemctl start nas-infuse
```

### 查看日志
```bash
sudo journalctl -u nas-infuse -f
```

## 4. 关于文件监控 (fnotify/watchdog)

系统已集成 `watchdog` 模块，会自动监控 `source_dir`：
- **自动触发**: 当检测到新文件（下载完成）或文件移动时，会自动触发一次扫描。
- **防抖逻辑 (Debounce)**: 针对“一集一集下载”的情况，系统设置了 60 秒的防抖延迟。只有在源目录 60 秒内没有新的写入活动时，才会启动扫描任务，避免因频繁下载导致的重复扫描和性能开销。
- **安全性**: 扫描任务在后台异步运行，不会影响 Web 界面的正常访问。

## 5. 防火墙配置 (如果需要)
```bash
sudo firewall-cmd --permanent --add-port=5010/tcp
sudo firewall-cmd --reload
```
