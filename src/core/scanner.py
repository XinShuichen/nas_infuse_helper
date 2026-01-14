# Copyright (c) 2025 Trae AI. All rights reserved.

import os
from pathlib import Path
from typing import List, Set, Optional
from .models import MediaFile


class Scanner:
    """
    Scans directories for media files based on extensions.
    """

    def __init__(
        self,
        video_extensions: List[str],
        blacklist: List[str] = None,
    ):
        self.video_extensions = {ext.lower() for ext in video_extensions}
        self.blacklist = set(blacklist) if blacklist else {"#recycle", "@eaDir", ".DS_Store"}

    def scan(self, root_path: Path) -> List[MediaFile]:
        """
        Recursively scans the root_path for allowed video files.
        """
        media_files = []
        if not root_path.exists():
            return media_files

        for root, dirs, files in os.walk(root_path):
            # Modify dirs in place to skip blacklisted directories
            dirs[:] = [d for d in dirs if d not in self.blacklist]

            for file in files:
                if file in self.blacklist:
                    continue
                path = Path(root) / file
                ext = path.suffix.lower()
                # Only include video files based on user requirement
                if ext in self.video_extensions:
                    stat = path.stat() if path.exists() else None
                    media_files.append(
                        MediaFile(
                            path=path,
                            extension=ext,
                            size=stat.st_size if stat else 0,
                            mtime=stat.st_mtime if stat else 0,
                        )
                    )
        return media_files
