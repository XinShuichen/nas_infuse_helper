# Copyright (c) 2025 Trae AI. All rights reserved.

import typer
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.progress import Progress
from ..core.config import Config
from ..core.scanner import Scanner
from ..core.aggregator import Aggregator
from ..core.classifier import Classifier
from ..core.renamer import Renamer
from ..core.linker import Linker
from ..db.manager import DatabaseManager

app = typer.Typer(help="NAS Infuse Helper - Organize your media files for Infuse.")
console = Console()


from ..core.searcher import Searcher

# ... existing code ...

@app.command("list")
def list_items(config_path: str = "config.yaml", search: bool = False):
    """
    List all detected media items and their suggested organization.
    """
    try:
        config = Config.load(config_path)
    except Exception as e:
        console.print(f"[red]Error loading config:[/red] {e}")
        raise typer.Exit(1)

    subtitle_extensions = getattr(config, "subtitle_extensions", [])
    if not isinstance(subtitle_extensions, (list, tuple, set)):
        subtitle_extensions = []
    scanner = Scanner(config.video_extensions, subtitle_extensions=list(subtitle_extensions))
    aggregator = Aggregator(config.source_dir, subtitle_extensions=list(subtitle_extensions))
    classifier = Classifier(config.video_extensions)
    renamer = Renamer()
    searcher = Searcher(config.tmdb_api_key) if search else None

    console.print(f"Scanning [cyan]{config.source_dir}[/cyan]...")
    files = scanner.scan(config.source_dir)
    items = aggregator.aggregate(files)

    table = Table(title="Detected Media Items")
    table.add_column("Original Name", style="magenta")
    table.add_column("Type", style="green")
    table.add_column("Search Status", style="cyan")
    table.add_column("Suggested Name", style="yellow")

    for item in items:
        item = classifier.classify(item)
        if searcher:
            item = searcher.search(item)
        
        video_files = [f for f in item.files if classifier.is_video(f)]
        suggested_path = ""
        if video_files:
            suggested_path = str(renamer.get_suggested_path(item, video_files[0]))

        table.add_row(
            item.name,
            item.media_type.value,
            item.search_status,
            suggested_path,
        )

    console.print(table)
    console.print(f"\nFound [bold]{len(items)}[/bold] items.")


@app.command("link")
def link_items(config_path: str = "config.yaml", dry_run: bool = False, search: bool = True):
    """
    Create soft links to organize media files.
    """
    try:
        config = Config.load(config_path)
    except Exception as e:
        console.print(f"[red]Error loading config:[/red] {e}")
        raise typer.Exit(1)

    subtitle_extensions = getattr(config, "subtitle_extensions", [])
    if not isinstance(subtitle_extensions, (list, tuple, set)):
        subtitle_extensions = []
    scanner = Scanner(config.video_extensions, subtitle_extensions=list(subtitle_extensions))
    aggregator = Aggregator(config.source_dir, subtitle_extensions=list(subtitle_extensions))
    classifier = Classifier(config.video_extensions)
    renamer = Renamer()
    searcher = Searcher(config.tmdb_api_key) if search else None
    db_manager = DatabaseManager(config.database_path)
    linker = Linker(config.target_dir, db_manager, config.path_mapping)

    console.print(f"Scanning [cyan]{config.source_dir}[/cyan]...")
    files = scanner.scan(config.source_dir)
    items = aggregator.aggregate(files)

    console.print(f"Organizing [bold]{len(items)}[/bold] items to [cyan]{config.target_dir}[/cyan]...")

    if searcher:
        console.print("Searching for official titles...")

    # Sort items by earliest mtime to preserve import order for Infuse
    items.sort(key=lambda x: x.earliest_mtime)

    with Progress() as progress:
        task = progress.add_task("[green]Linking...", total=len(items))

        total_links = 0
        unknown_items = 0
        for item in items:
            item = classifier.classify(item)
            if searcher:
                item = searcher.search(item)

            # Record in DB regardless of success
            if searcher and item.search_status != "found":
                unknown_items += 1
                # If not found or uncertain, we still record but maybe with no target path
                if not dry_run:
                    db_manager.add_mapping(
                        item.original_path,
                        None,
                        item.media_type.value,
                        title_cn=item.title_cn,
                        title_en=item.title_en,
                        tmdb_id=item.tmdb_id,
                        year=item.year,
                        search_status=item.search_status,
                    )
                progress.update(task, advance=1)
                continue

            suggested_mappings = []
            for file in item.files:
                suggested_path = renamer.get_suggested_path(item, file)
                suggested_mappings.append((file, suggested_path))

            if not dry_run:
                # Update DB with full info when linking
                for file, suggested_path in suggested_mappings:
                    db_manager.add_mapping(
                        file.path,
                        suggested_path,
                        item.media_type.value,
                        title_cn=item.title_cn,
                        title_en=item.title_en,
                        tmdb_id=item.tmdb_id,
                        year=item.year,
                        search_status=item.search_status,
                    )
                total_links += linker.link_item(item, suggested_mappings)

            progress.update(task, advance=1)

    if dry_run:
        console.print("[yellow]Dry run completed. No links created.[/yellow]")
    else:
        console.print(f"[green]Successfully created {total_links} links.[/green]")
        if unknown_items > 0:
            console.print(f"[yellow]{unknown_items} items were skipped due to uncertain search results (recorded in DB).[/yellow]")


if __name__ == "__main__":
    app()
