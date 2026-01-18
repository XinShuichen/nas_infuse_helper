# Copyright (c) 2025 Trae AI. All rights reserved.

from flask import Flask, jsonify, request, render_template
from flask_apscheduler import APScheduler
import threading
import time
from pathlib import Path
from ..core.config import Config
from ..core.models import MediaType, MediaItem, MediaFile
from ..infrastructure.db.database import Database
from ..infrastructure.db.repository import MediaRepository, LogRepository, SymlinkRepository
from ..services.scan_service import ScanService
from ..services.match_service import MatchService
from ..services.link_service import LinkService
from ..services.watch_service import WatchService
from .task_manager import task_manager

class Server:
    def __init__(self, config_path: str = "config.yaml"):
        # Configure logging
        import logging
        import sys
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler(sys.stdout)]
        )
        self.logger = logging.getLogger("src.server.app")
        
        self.config = Config.load(config_path)
        self.app = Flask(__name__, template_folder="../templates", static_folder="../static")
        self.scheduler = APScheduler()
        
        # Infrastructure
        self.db = Database(Path(self.config.database_path))
        
        # In testing environment with in-memory DB, we need to ensure schema is created
        # because Database() only creates schema if DB file doesn't exist, 
        # but for :memory:, it always "doesn't exist" initially but _init_db might check path existence.
        # Actually Database._init_db handles schema creation.
        # The issue in tests is likely that 'server' fixture creates a new Server instance,
        # which creates a new Database instance.
        # If config.database_path is ":memory:", Database.__init__ calls _init_db.
        # Let's check Database._init_db again.
        
        self.media_repo = MediaRepository(self.db)
        self.log_repo = LogRepository(self.db)
        self.symlink_repo = SymlinkRepository(self.db)
        
        # Services
        self.link_service = LinkService(self.config, self.media_repo, self.symlink_repo, self.log_repo)
        self.match_service = MatchService(self.config, self.media_repo, self.log_repo)
        self.scan_service = ScanService(self.config, self.media_repo, self.log_repo, self.match_service, self.link_service)
        self.watch_service = WatchService(self.config, self.scan_service, self.media_repo)
        
        self._setup_routes()
        self._setup_scheduler()
        
        # Start Watcher
        self.watch_service.start()

    def _setup_routes(self):
        @self.app.route("/")
        def index():
            return render_template("index.html")

        @self.app.route("/api/media")
        def get_media():
            status_filter = request.args.get("status")
            mappings = self.media_repo.get_all(status_filter)
            return jsonify(mappings)

        @self.app.route("/api/scan", methods=["POST"])
        def trigger_scan():
            task_id = "full_scan"
            if task_manager.get_task_status(task_id) and task_manager.get_task_status(task_id)["status"] == "running":
                return jsonify({"error": "Scan already in progress"}), 400
            
            def run_scan():
                task_manager.start_task(task_id)
                try:
                    self.scan_service.run_full_scan(lambda p, m: task_manager.update_progress(task_id, p, m))
                    task_manager.complete_task(task_id, "Scan complete")
                except Exception as e:
                    task_manager.fail_task(task_id, str(e))

            thread = threading.Thread(target=run_scan)
            thread.start()
            return jsonify({"task_id": task_id})

        @self.app.route("/api/scan/incremental", methods=["POST"])
        def trigger_incremental_scan():
            task_id = "incremental_scan"
            if task_manager.get_task_status(task_id) and task_manager.get_task_status(task_id)["status"] == "running":
                return jsonify({"error": "Scan already in progress"}), 400
            
            def run_inc_scan():
                task_manager.start_task(task_id)
                try:
                    self.scan_service.run_incremental_scan(lambda p, m: task_manager.update_progress(task_id, p, m))
                    task_manager.complete_task(task_id, "Incremental scan complete")
                except Exception as e:
                    task_manager.fail_task(task_id, str(e))

            thread = threading.Thread(target=run_inc_scan)
            thread.start()
            return jsonify({"task_id": task_id})

        @self.app.route("/api/reprocess", methods=["POST"])
        def trigger_reprocess():
            task_id = "reprocess_unknown"
            if task_manager.get_task_status(task_id) and task_manager.get_task_status(task_id)["status"] == "running":
                return jsonify({"error": "Reprocess already in progress"}), 400
            
            def run_reprocess():
                task_manager.start_task(task_id)
                try:
                    # Get all unknown/uncertain
                    unknowns = self.media_repo.get_all("not_found")
                    uncertains = self.media_repo.get_all("uncertain")
                    pendings = self.media_repo.get_all("pending")
                    all_items = unknowns + uncertains + pendings
                    
                    if not all_items:
                        task_manager.complete_task(task_id, "No items to reprocess")
                        return

                    paths = [item["original_path"] for item in all_items]
                    task_manager.update_progress(task_id, 0, f"Reprocessing {len(paths)} items...")
                    
                    # We can use scan_service.process_paths but we want progress updates
                    # scan_service.process_paths doesn't report progress via callback yet.
                    # For now, just call it. It logs to DB.
                    self.scan_service.process_paths(paths)
                    
                    task_manager.complete_task(task_id, "Reprocess complete")
                except Exception as e:
                    task_manager.fail_task(task_id, str(e))

            thread = threading.Thread(target=run_reprocess)
            thread.start()
            return jsonify({"task_id": task_id})

        @self.app.route("/api/reset", methods=["POST"])
        def reset_system():
            try:
                # 1. Clear database
                # We need a method in repo to clear all? Or direct DB access?
                # Using direct DB for reset is fine or add method to repo.
                with self.db.get_connection() as conn:
                    conn.execute("DELETE FROM media_mapping")
                    conn.execute("DELETE FROM symlink_map")
                    conn.execute("DELETE FROM operation_logs")
                
                # 2. Delete all symlinks in target directory
                target_dir = self.config.target_dir
                if target_dir.exists():
                    import shutil
                    for item in target_dir.iterdir():
                        if item.is_dir():
                            shutil.rmtree(item)
                        else:
                            item.unlink()
                    (target_dir / "Movies").mkdir(exist_ok=True)
                    (target_dir / "TV Shows").mkdir(exist_ok=True)
                
                self.logger.warning("[User Action] System reset triggered! Clearing DB and Symlinks.")
                
                # Double check cleanup: remove any dangling symlinks in target_dir recursively
                # This helps remove invalid links like 'log' file if they exist
                if target_dir.exists():
                     for item in target_dir.rglob('*'):
                         if item.is_symlink():
                             try:
                                 # If link is broken or points to invalid file type
                                 target = item.resolve()
                                 if not target.exists():
                                     item.unlink()
                                 elif target.is_file() and target.suffix.lower() not in self.config.video_extensions:
                                      self.logger.warning(f"Removing invalid symlink: {item} -> {target}")
                                      item.unlink()
                             except Exception as e:
                                 pass

                return jsonify({"status": "success"})
            except Exception as e:
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/status")
        def get_status():
            return jsonify(task_manager.get_all_tasks())

        @self.app.route("/api/search", methods=["GET"])
        def manual_search():
            name = request.args.get("name")
            media_type_str = request.args.get("type", "Movie")
            if not name:
                return jsonify({"error": "Name is required"}), 400
            
            media_type = MediaType.MOVIE if media_type_str == "Movie" else MediaType.TV_SHOW
            
            self.logger.info(f"[User Action] Manual search request: name='{name}', type='{media_type.value}'")
            
            candidates = self.match_service.manual_search(name, media_type)
            return jsonify(candidates)

        @self.app.route("/api/config", methods=["GET", "POST"])
        def handle_config():
            if request.method == "GET":
                cfg = self.config
                return jsonify({
                    "source_dir": str(cfg.source_dir),
                    "target_dir": str(cfg.target_dir),
                    "tmdb_api_key": "********" if cfg.tmdb_api_key else "",
                    "server_port": cfg.server_port,
                    "scan_interval_minutes": cfg.scan_interval_minutes,
                    "verbose": cfg.verbose
                })
            else:
                data = request.json
                new_key = data.get("tmdb_api_key")
                if new_key == "********":
                    data["tmdb_api_key"] = self.config.tmdb_api_key
                
                import yaml
                with open("config.yaml", "r", encoding="utf-8") as f:
                    raw_cfg = yaml.safe_load(f)
                
                raw_cfg.update(data)
                with open("config.yaml", "w", encoding="utf-8") as f:
                    yaml.safe_dump(raw_cfg, f, allow_unicode=True)
                
                self.config = Config.load("config.yaml")
                # Update WatchService config
                if hasattr(self, 'watch_service'):
                    self.watch_service.config = self.config
                
                # Reload services with new config? 
                # Ideally yes, but simpler to restart. 
                # User can restart service.
                self.logger.info("[User Action] Configuration updated.")
                return jsonify({"status": "success"})

        @self.app.route("/api/stats")
        def get_stats():
            # Use repo
            # We need count methods in repo
            # For now direct query is fine as it's efficient
            with self.db.get_connection() as conn:
                total = conn.execute("SELECT COUNT(*) FROM media_mapping").fetchone()[0]
                matched = conn.execute("SELECT COUNT(*) FROM media_mapping WHERE search_status = 'found'").fetchone()[0]
                uncertain = conn.execute("SELECT COUNT(*) FROM media_mapping WHERE search_status = 'uncertain'").fetchone()[0]
                failed = conn.execute("SELECT COUNT(*) FROM media_mapping WHERE search_status = 'not_found'").fetchone()[0]
            
            return jsonify({
                "total": total,
                "matched": matched,
                "uncertain": uncertain,
                "failed": failed
            })

        @self.app.route("/api/confirm", methods=["POST"])
        def confirm_selection():
            data = request.json
            original_path = Path(data["original_path"])
            selection = data["selection"]
            media_type_str = data.get("type", "Movie")
            alias = data.get("alias")
            apply_batch = data.get("apply_batch", False) # New Flag

            tmdb_id_val = selection.get("tmdb_id")
            if tmdb_id_val is None or tmdb_id_val == "":
                return jsonify({"error": "tmdb_id is required"}), 400
            if isinstance(tmdb_id_val, str):
                if not tmdb_id_val.isdigit():
                    return jsonify({"error": "tmdb_id must be an integer"}), 400
                tmdb_id_val = int(tmdb_id_val)
            if not isinstance(tmdb_id_val, int):
                return jsonify({"error": "tmdb_id must be an integer"}), 400
            
            media_type = MediaType.MOVIE if media_type_str == "Movie" else MediaType.TV_SHOW
            
            # Type Correction from Selection
            # If searcher returned a different media_type (e.g. via ID lookup fallback), use it.
            if selection.get("media_type"):
                new_type_str = selection.get("media_type")
                if new_type_str != media_type_str:
                    self.logger.info(f"[User Action] Type switch detected: {media_type_str} -> {new_type_str}")
                    media_type = MediaType.MOVIE if new_type_str == "Movie" else MediaType.TV_SHOW
            
            from ..core.scanner import Scanner
            from ..core.renamer import Renamer
            # We need MediaFile to wrap single file
            from ..core.models import MediaFile
            
            subtitle_extensions = getattr(self.config, "subtitle_extensions", [])
            if not isinstance(subtitle_extensions, (list, tuple, set)):
                subtitle_extensions = []
            scanner = Scanner(self.config.video_extensions, subtitle_extensions=list(subtitle_extensions))
            
            items_to_process = [] # List of MediaItem
            
            # Logic for Batch Processing
            if apply_batch and media_type == MediaType.TV_SHOW and original_path.is_file():
                parent_dir = original_path.parent
                
                # Safety Check: Do not batch scan if parent is source_root
                # Use resolve() to compare absolute paths
                if parent_dir.resolve() == self.config.source_dir.resolve():
                    self.logger.warning(f"[User Action] Batch match requested but file is in source root. Falling back to single file match for safety.")
                    files = [MediaFile(path=original_path, extension=original_path.suffix, size=original_path.stat().st_size if original_path.exists() else 0)]
                else:
                    self.logger.info(f"[User Action] Batch match requested. Scanning {parent_dir} for siblings.")
                    files = scanner.scan(parent_dir)
                    # Filter: Only keep video files (already done by scanner)
                    # And maybe filter out if we want stricter control? No, Scanner handles extensions.
                
                # For batch processing, we must process EACH file individually to extract its specific S/E
                # But apply the SAME Show Metadata (Title, ID, Year)
                
                # Sort files by name to ensure sequential processing
                # This is CRITICAL for cases where S/E detection fails and we fallback to sequential assignment
                files.sort(key=lambda f: f.path.name)
                
                for index, file in enumerate(files):
                    # Create a temporary item for classification
                    # We treat each file as a separate item initially to get its S/E
                    temp_item = MediaItem(
                        name=file.path.name,
                        original_path=file.path,
                        files=[file],
                        media_type=MediaType.TV_SHOW
                    )
                    
                    # Use Classifier to extract S/E
                    # Note: Classifier might fail if filename is weird. 
                    # But we trust it does its best.
                    classified_item = self.scan_service.classifier.classify(temp_item)
                    
                    # FALLBACK: If classification failed to find Episode (e.g. "Cyberpunk...02..."),
                    # AND we are in batch mode for TV Show, assign based on sort order.
                    # Assumption: User matched a folder of episodes.
                    if classified_item.episode is None:
                        classified_item.season = 1 # Default to S1
                        classified_item.episode = index + 1
                        self.logger.info(f"Fallback S/E assignment for {file.path.name}: S1E{index+1}")
                    
                    # Override Metadata with User Selection
                    classified_item.media_type = media_type # Force correct type (Classifier defaults single files to Movie)
                    classified_item.tmdb_id = tmdb_id_val
                    classified_item.title_cn = selection.get("title_cn")
                    classified_item.title_en = selection.get("title_en")
                    classified_item.year = selection.get("year") or classified_item.year
                    classified_item.alias = alias
                    classified_item.search_status = "found"
                    
                    items_to_process.append(classified_item)
                    
            elif apply_batch and media_type == MediaType.MOVIE and original_path.is_file():
                 # Similar logic for movies? User usually puts movies in folders too.
                 # But movies don't have S/E.
                 # If user says "This folder is Matrix", maybe it has "Matrix.mp4" and "Matrix-Trailer.mp4".
                 # Be careful. 
                 # For now, let's allow it but treat all files as THE SAME MOVIE (e.g. CD1, CD2, or just duplicates).
                 # Or maybe the user wants to apply "Matrix Collection" to a folder? No, ID is specific.
                 
                 # Let's implement it similar to TV Show: Apply same ID to all files.
                 parent_dir = original_path.parent
                 if parent_dir.resolve() == self.config.source_dir.resolve():
                    files = [MediaFile(path=original_path, extension=original_path.suffix, size=original_path.stat().st_size if original_path.exists() else 0)]
                 else:
                    files = scanner.scan(parent_dir)

                 for file in files:
                    item = MediaItem(
                        name=file.path.name,
                        original_path=file.path,
                        files=[file],
                        media_type=MediaType.MOVIE,
                        title_cn=selection.get("title_cn"),
                        title_en=selection.get("title_en"),
                        tmdb_id=tmdb_id_val,
                        year=selection.get("year"),
                        alias=alias,
                        search_status="found"
                    )
                    items_to_process.append(item)
            else:
                # Single file or Directory path (Legacy/Standard mode)
                files_to_process = scanner.scan(original_path) if original_path.is_dir() else [
                    MediaFile(path=original_path, extension=original_path.suffix, size=original_path.stat().st_size if original_path.exists() else 0)
                ]
                
                # For single match, we bundle them into ONE item (e.g. CD1+CD2)?
                # OR if it's a directory match (old logic), we treated it as one item.
                # Let's stick to creating one MediaItem per file if it's a file path, 
                # or one item for the dir if it's a dir path.
                
                # Actually, the original logic bundled all files into ONE item if it was a directory match.
                # If it was a single file match, it was one item.
                
                item_name = original_path.name
                item = MediaItem(
                    name=item_name,
                    original_path=original_path,
                    files=files_to_process,
                    media_type=media_type,
                    title_cn=selection.get("title_cn"),
                    title_en=selection.get("title_en"),
                    tmdb_id=tmdb_id_val,
                    year=selection.get("year"),
                    alias=alias,
                    search_status="found"
                )
                
                # If it's a TV Show, we might still want to parse S/E for renaming?
                # The old logic didn't explicit calls classifier here.
                # It relied on Renamer using `item.season` / `item.episode`.
                # But where do those come from if we construct MediaItem manually?
                # They are None by default!
                # THIS WAS A BUG IN OLD LOGIC TOO? 
                # If I manually confirm a TV Show, it won't have S/E unless I run classifier.
                # Let's fix this for single file too.
                
                if media_type == MediaType.TV_SHOW:
                    item = self.scan_service.classifier.classify(item)
                    # Re-apply selection in case classify overwrote them (it shouldn't overwrite if not found, but safety)
                    item.tmdb_id = tmdb_id_val
                    item.title_cn = selection.get("title_cn")
                    item.title_en = selection.get("title_en")
                    # item.year = ...
                
                items_to_process.append(item)

            # Process all items (Save & Link)
            processed_count = 0
            renamer = Renamer()
            
            for item in items_to_process:
                suggested_mappings = []
                for file in item.files:
                    suggested_path = renamer.get_suggested_path(item, file)
                    suggested_mappings.append((file, suggested_path))
                    processed_count += 1
                
                # Update DB
                for file, suggested_path in suggested_mappings:
                    self.media_repo.delete_by_path(file.path)
                    self.media_repo.save({
                        "original_path": str(file.path),
                        "target_path": str(suggested_path),
                        "media_type": item.media_type.value,
                        "title_cn": item.title_cn,
                        "title_en": item.title_en,
                        "tmdb_id": item.tmdb_id,
                        "year": item.year,
                        "alias": item.alias,
                        "search_status": item.search_status,
                        "last_scanned_at": time.time()
                    })
                
                # Link
                self.link_service.link_item(item, suggested_mappings)
            
            self.logger.info(f"[User Action] Manually matched {processed_count} files (Batch={apply_batch}).")
            
            return jsonify({"status": "success", "processed_count": processed_count})

        @self.app.route("/api/logs")
        def get_logs():
            logs = self.log_repo.get_recent(limit=100)
            return jsonify(logs)

        @self.app.route("/api/media/hide", methods=["POST"])
        def hide_media():
            data = request.json
            original_path = Path(data.get("original_path"))
            
            if not original_path:
                return jsonify({"error": "Original path is required"}), 400

            try:
                # 1. Update DB to hidden
                existing = self.media_repo.get_by_path(original_path)
                if not existing:
                     return jsonify({"error": "Item not found"}), 404
                     
                existing["search_status"] = "hidden"
                self.media_repo.save(existing)
                
                # 2. Unlink if exists
                target_path_str = existing.get("target_path")
                if target_path_str:
                    target_path = Path(target_path_str)
                    if target_path.exists() or target_path.is_symlink():
                        target_path.unlink()
                
                # 3. Log
                self.log_repo.add("HIDE", str(original_path), "User hidden item")
                self.logger.info(f"[User Action] Hidden item: {original_path}")
                
                return jsonify({"status": "success"})
            except Exception as e:
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/media/unhide", methods=["POST"])
        def unhide_media():
            data = request.json
            original_path = Path(data.get("original_path"))
            
            if not original_path:
                return jsonify({"error": "Original path is required"}), 400

            try:
                # 1. Update DB to pending
                existing = self.media_repo.get_by_path(original_path)
                if not existing:
                     return jsonify({"error": "Item not found"}), 404
                     
                existing["search_status"] = "pending"
                self.media_repo.save(existing)
                
                # 2. Log
                self.log_repo.add("UNHIDE", str(original_path), "User unhidden item - Scheduled for re-scan")
                self.logger.info(f"[User Action] Unhidden item: {original_path} (Triggering re-scan)")
                
                # 3. Trigger re-process for this item immediately?
                # Or wait for next scan? User message says "processed again in next scan"
                # But immediate action is better UX.
                # Let's spawn a quick process thread for just this item.
                def reprocess_one():
                    try:
                        from src.core.models import MediaFile
                        mf = MediaFile(
                            path=original_path,
                            extension=original_path.suffix.lower(),
                            size=original_path.stat().st_size if original_path.exists() else 0,
                            mtime=original_path.stat().st_mtime if original_path.exists() else 0
                        )
                        self.scan_service.process_paths([mf])
                    except Exception as e:
                        print(f"Error reprocessing unhidden item: {e}")

                threading.Thread(target=reprocess_one).start()
                
                return jsonify({"status": "success"})
            except Exception as e:
                return jsonify({"error": str(e)}), 500

    def _setup_scheduler(self):
        self.scheduler.init_app(self.app)
        # Scheduled full scan removed in favor of WatchService polling
        self.scheduler.start()

    def run(self):
        self.app.run(host=self.config.server_host, port=self.config.server_port)

if __name__ == "__main__":
    server = Server()
    server.run()
