# Copyright (c) 2025 Trae AI. All rights reserved.

import typer
from src.cli.main import app as cli_app
from src.server.app import Server

app = typer.Typer(help="NAS Infuse Helper - Organize your media files for Infuse.")

# Add CLI commands
app.registered_commands.extend(cli_app.registered_commands)

@app.command("server")
def run_server(config_path: str = "config.yaml"):
    """
    Run the Web Server and Management UI.
    """
    server = Server(config_path)
    server.run()

if __name__ == "__main__":
    app()
