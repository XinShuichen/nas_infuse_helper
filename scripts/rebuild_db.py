import sys
import os
import re
import yaml
from pathlib import Path
import logging

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.infrastructure.db.database import Database
from src.infrastructure.db.repository import MediaRepository, SymlinkRepository

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def load_config(config_path="config.yaml"):
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def parse_folder_name(folder_name):
    """
    Parses "Title (EnTitle) (Year) {tmdb-ID}"
    Returns (title_cn, title_en, year, tmdb_id)
    """
    # Extract TMDB ID
    tmdb_match = re.search(r"\{tmdb-(\d+)\}", folder_name)
    tmdb_id = int(tmdb_match.group(1)) if tmdb_match else None
    
    # Remove TMDB ID part
    remaining = re.sub(r"\s*\{tmdb-\d+\}", "", folder_name)
    
    # Extract Year
    year_match = re.search(r"\((\d{4})\)$", remaining)
    year = int(year_match.group(1)) if year_match else None
    
    # Remove Year part
    remaining = re.sub(r"\s*\(\d{4}\)$", "", remaining)
    
    # Extract Titles
    # Format: "CN (EN)" or just "CN"
    # Note: EnTitle might contain parentheses, so we look for the last set of parens if possible, 
    # but the construction logic was: f"{title_cn} ({title_en})"
    
    title_cn = remaining
    title_en = None
    
    if remaining.endswith(")"):
        # Find the last opening parenthesis
        last_open = remaining.rfind("(")
        if last_open != -1:
            title_cn = remaining[:last_open].strip()
            title_en = remaining[last_open+1:-1].strip()
    
    return title_cn, title_en, year, tmdb_id

def rebuild(config_path="config.yaml"):
    config = load_config(config_path)
    target_dir = Path(config["target_dir"])
    db_path = Path(config.get("database_path", "metadata.db"))
    
    logger.info(f"Target Dir: {target_dir}")
    logger.info(f"Database: {db_path}")
    
    db = Database(db_path)
    media_repo = MediaRepository(db)
    symlink_repo = SymlinkRepository(db)
    
    count = 0
    
    # Process Movies
    movies_dir = target_dir / "Movies"
    if movies_dir.exists():
        for item_dir in movies_dir.iterdir():
            if not item_dir.is_dir():
                continue
                
            title_cn, title_en, year, tmdb_id = parse_folder_name(item_dir.name)
            if not tmdb_id:
                logger.warning(f"Skipping non-standard folder: {item_dir.name}")
                continue
                
            for file_path in item_dir.iterdir():
                if file_path.is_symlink():
                    original_path = Path(os.readlink(file_path))
                    
                    # Insert into DB
                    media_repo.save({
                        "original_path": str(original_path),
                        "target_path": str(file_path),
                        "media_type": "Movie",
                        "title_cn": title_cn,
                        "title_en": title_en,
                        "tmdb_id": tmdb_id,
                        "year": year,
                        "search_status": "found"
                    })
                    symlink_repo.add(original_path, file_path)
                    count += 1
                    logger.info(f"Recovered Movie: {title_cn} -> {original_path.name}")

    # Process TV Shows
    tv_dir = target_dir / "TV Shows"
    if tv_dir.exists():
        for item_dir in tv_dir.iterdir():
            if not item_dir.is_dir():
                continue
                
            title_cn, title_en, year, tmdb_id = parse_folder_name(item_dir.name)
            if not tmdb_id:
                logger.warning(f"Skipping non-standard folder: {item_dir.name}")
                continue
                
            # TV Shows have Season folders
            for season_dir in item_dir.iterdir():
                if not season_dir.is_dir():
                    continue
                    
                for file_path in season_dir.iterdir():
                    if file_path.is_symlink():
                        original_path = Path(os.readlink(file_path))
                        
                        media_repo.save({
                            "original_path": str(original_path),
                            "target_path": str(file_path),
                            "media_type": "TV Show",
                            "title_cn": title_cn,
                            "title_en": title_en,
                            "tmdb_id": tmdb_id,
                            "year": year,
                            "search_status": "found"
                        })
                        symlink_repo.add(original_path, file_path)
                        count += 1
                        logger.info(f"Recovered TV Episode: {title_cn} -> {original_path.name}")

    logger.info(f"Rebuild complete. Recovered {count} items.")

if __name__ == "__main__":
    rebuild()
