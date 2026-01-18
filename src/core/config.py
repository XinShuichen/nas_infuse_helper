# Copyright (c) 2025 Trae AI. All rights reserved.

import yaml
from pathlib import Path
from typing import List, Optional, Dict
from pydantic import BaseModel

class Config(BaseModel):
    source_dir: Path
    target_dir: Path
    database_path: Path
    video_extensions: List[str]
    subtitle_extensions: List[str] = [".srt", ".ass", ".ssa", ".sub", ".vtt"]
    tmdb_api_key: Optional[str] = None
    server_port: int = 5000
    server_host: str = "0.0.0.0"
    scan_interval_minutes: int = 60
    path_mapping: Optional[Dict[str, str]] = None
    verbose: bool = False

    @classmethod
    def load(cls, path: str = "config.yaml") -> "Config":
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls(**data)
