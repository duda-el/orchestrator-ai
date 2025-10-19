import sys
from pathlib import Path

# Add the project root to the Python path to allow imports from 'core'
sys.path.append(str(Path(__file__).resolve().parents[1]))

import os
import json
import click
from dotenv import load_dotenv
import tempfile
import shutil
import subprocess
import stat
import time
from contextlib import redirect_stderr
from collections import Counter
from datetime import datetime
from urllib.parse import urlparse

from rich.console import Console
from rich.theme import Theme
from rich.panel import Panel
from rich.table import Table
from rich.box import ROUNDED, HEAVY
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    MofNCompleteColumn,
    TimeElapsedColumn,
)
from rich.align import Align

from core.analyzer import analyze_repository
from core.generator import generate_docker_configuration
from core.llm import GeminiClient
from core.docker_commands import DockerCommandGenerator, create_docker_command_examples

# Load environment variables from .env file in project root
project_root = Path(__file__).resolve().parents[1]
env_path = project_root / ".env"
load_dotenv(env_path)

# Console + Theme (no emojis)
theme = Theme(
    {
        "success": "bold green",
        "error": "bold red",
        "warning": "bold yellow",
        "info": "bold cyan",
        "dim": "dim",
        "highlight": "bold magenta",
        "banner": "bold white on blue",
        "title": "bold cyan",
    }
)
console = Console(theme=theme)


def banner(title: str, subtitle: str | None = None) -> None:
    header = f"{title}"
    if subtitle:
        header += f"\n[dim]{subtitle}[/dim]"
    console.print(Panel.fit(Align.center(header), box=HEAVY, style="banner"))


def msg_success(text: str) -> None:
    console.print(text, style="success")


def msg_error(text: str) -> None:
    console.print(text, style="error")


def msg_info(text: str) -> None:
    console.print(text, style="info")


def msg_warn(text: str) -> None:
    console.print(text, style="warning")


def handle_remove_readonly(func, path, exc):
    if os.path.exists(path):
        os.chmod(path, stat.S_IWRITE)
        func(path)


def safe_rmtree(path):
    if os.path.exists(path):
        shutil.rmtree(path, onerror=handle_remove_readonly)


# ----------------- helpers for persistent clone by default -----------------
def _repo_name_from_url(repo_url: str) -> str:
    """
    Extract repo name from URL. Examples:
      https://github.com/octocat/Hello-World.git -> Hello-World
      git@github.com:octo/hello.git -> hello
    """
    parsed = urlparse(repo_url)
    tail = parsed.path or repo_url.split(":")[-1]
    name = tail.rstrip("/").split("/")[-1]
    if name.endswith(".git"):
        name = name[:-4]
    return name or "repo"


def _default_persistent_clone_dir(repo_url: str) -> Path:
    """
    Default persistent directory under <project_root>/clones/<repo-name>.
    If exists and non-empty, append timestamp to avoid collisions.
    """
    clones_base = project_root / "clones"
    clones_base.mkdir(parents=True, exist_ok=True)
    base = clones_base / _repo_name_from_url(repo_url)
    if base.exists() and any(base.iterdir()):
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        base = clones_base / f"{base.name}-{stamp}"
    return base


def _docker_available() -> bool:
    try:
        subprocess.run(["docker", "--version"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


def _docker_daemon_running() -> bool:
    try:
        subprocess.run(["docker", "info"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


def _compose(args: list[str], project_dir: Path) -> None:
    """
    Run docker compose with args in the given project_dir.
    Prefers 'docker compose' (v2). Falls back to 'docker-compose' if needed.
    """
    cmds = [["docker", "compose"], ["docker-compose"]]
    for cmd in cmds:
        try:
            subprocess.run(cmd + args, cwd=str(project_dir), check=True)
            return
        except FileNotFoundError:
            continue
    raise click.ClickException("Neither 'docker compose' nor 'docker-compose' is available on PATH.")


# ---- clone_repo: persistent by default; temp only when dest_dir=None is explicitly passed ----
def clone_repo(repo_url: str, dest_dir: str | Path | None = "DEFAULT_PERSIST") -> str:
    """
    - If dest_dir == 'DEFAULT_PERSIST' (default), clone into a persistent folder under project_root/clones/<repo-name>.
    - If dest_dir is a path, clone there.
    - If dest_dir is None, clone into a temporary folder (deleted later by caller).
    """
    if dest_dir == "DEFAULT_PERSIST":
        dest_dir = _default_persistent_clone_dir(repo_url)

    if dest_dir is None:
        target_dir = tempfile.mkdtemp(prefix="orchai_")
    else:
        dest_dir = Path(dest_dir)
        dest_dir.parent.mkdir(parents=True, exist_ok=True)
        target_dir = str(dest_dir)

    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, target_dir],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return target_dir
    except subprocess.CalledProcessError as e:
        if dest_dir is None and os.path.exists(target_dir):
            safe_rmtree(target_dir)
        raise click.ClickException(f"Failed to clone repository: {e}")
    except FileNotFoundError:
        if dest_dir is None and os.path.exists(target_dir):
            safe_rmtree(target_dir)
        raise click.ClickException("Git is not installed or not in your PATH.")


def table_generated_files(docker_config, output_dir: str) -> Table:
    """Generate a table showing all generated files including nginx configs."""
    table = Table(
        title="Generated Files",
        show_header=True,
        header_style="bold magenta",
        border_style="blue",
        box=ROUNDED,
        title_style="title",
        expand=True,
    )
    table.add_column("File", style="cyan", no_wrap=True)
    table.add_column("Type", style="yellow", justify="center", width=16)
    table.add_column("Status", style="green", justify="center", width=12)

    # Add Dockerfiles
    for info in docker_config.get("dockerfiles", []) or []:
        path = info.get("path")
        status = "Created" if path else "Skipped"
        table.add_row(str(Path(output_dir) / path) if path else "—", "Dockerfile", status)

    # Add Nginx configs
    for info in docker_config.get("nginx_configs", []) or []:
        path = info.get("path")
        status = "Created" if path else "Skipped"
        table.add_row(str(Path(output_dir) / path) if path else "—", "Nginx Config", status)

    # Add docker-compose
    if docker_config.get("docker_compose"):
        table.add_row(str(Path(output_dir) / "docker-compose.yml"), "Compose", "Created")
    else:
        table.add_row("—", "Compose", "Skipped")

    return table


def pretty_repo_summary(repo_structure: dict) -> Panel:
    services = repo_structure.get("services", [])
    files = repo_structure.get("files", [])
    langs = repo_structure.get("languages", {})
    lang_text = ", ".join(f"[highlight]{k}[/highlight]: {v}" for k, v in langs.items()) or "—"

    body = (
        f"[bold]Services detected:[/bold] {len(services)}\n"
        f"[bold]Files scanned:[/bold] {len(files)}\n"
        f"[bold]Languages:[/bold] {lang_text}"
    )
    return Panel(body, title="Scan Summary", border_style="cyan", box=ROUNDED)


EXT_LANG = {
    ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript", ".jsx": "JavaScript",
    ".tsx": "TypeScript", ".java": "Java", ".go": "Go", ".rs": "Rust", ".cpp": "C++",
    ".cc": "C++", ".cxx": "C++", ".c": "C", ".cs": "C#", ".php": "PHP", ".rb": "Ruby",
    ".swift": "Swift", ".kt": "Kotlin", ".m": "Objective-C", ".sh": "Shell",
    ".yml": "YAML", ".yaml": "YAML", ".json": "JSON", ".toml": "TOML", ".ini": "INI",
    ".md": "Markdown", ".html": "HTML", ".css": "CSS", ".scss": "SCSS",
}


def fallback_scan(root: Path) -> tuple[list[str], dict]:
    files = []
    langs = Counter()
    for p in root.rglob("*"):
        if p.is_file() and ".git" not in p.parts:
            files.append(str(p.relative_to(root)))
            lang = EXT_LANG.get(p.suffix.lower())
            if lang:
                langs[lang] += 1
    return files, dict(langs)


@click.group()
def cli():
    """Orchestrator AI CLI"""
    pass


@cli.command()
@click.argument("repo_url")
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON only (no Rich UI).")
def inspect(repo_url, as_json):
    """Analyze a Git repository and print the structure."""
    tmpdir = None
    try:
        banner("Orchestrator-AI", "Repository Inspector")
        with console.status("[bold cyan]Cloning repository...", spinner="earth"):
            # For inspect we keep the original temp behavior; delete after.
            tmpdir = clone_repo(repo_url, dest_dir=None)

        with console.status("[bold cyan]Analyzing project structure...", spinner="dots"):
            repo_structure = analyze_repository(tmpdir)
            time.sleep(0.2)

        if as_json:
            console.print_json(data=repo_structure)
        else:
            console.print(pretty_repo_summary(repo_structure))
            console.print("\n[dim]Raw structure (preview):[/dim]")
            console.print_json(data=repo_structure)

        msg_success("Inspection completed successfully.")
    except (ValueError, click.ClickException) as e:
        msg_error(str(e))
    except Exception as e:
        msg_error(f"Unexpected error: {e}")
    finally:
        if tmpdir:
            with console.status("[bold cyan]Cleaning up...", spinner="bouncingBar"):
                safe_rmtree(tmpdir)


@cli.command()
@click.argument("repo_url")
@click.option("--output-dir", default="output",
              help="Directory to save generated files (ignored; kept for backward-compat).")
@click.option("--json", "as_json", is_flag=True, help="Also print raw JSON of repo structure.")
@click.option("--inplace", is_flag=True,
              help="(Kept for compatibility) Writes into the cloned repo root (default now).")
@click.option("--clone-dir", default=None, help="Clone into this directory; overrides default persistent folder.")
@click.option("--no-build", is_flag=True, help="Skip Docker build step (build runs by default).")
def analyze(repo_url, output_dir, as_json, inplace, clone_dir, no_build):
    """
    Clone (persistent), analyze, generate Docker files inside the cloned repo, and build by default.
    """
    tmpdir = None
    try:
        banner("Orchestrator-AI", "Analyze & Generate")

        # ---- Phase bars (clone + analyze) ----
        with Progress(
                SpinnerColumn(spinner_name="line"),
                TextColumn("[bold blue]{task.description}"),
                BarColumn(complete_style="green", finished_style="bold green"),
                TaskProgressColumn(),
                MofNCompleteColumn(),
                TimeElapsedColumn(),
                console=console,
                transient=True,
        ) as progress:
            t_clone = progress.add_task("Cloning repository...", total=1)
            t_an = progress.add_task("Analyzing repository...", total=1)

            # Persistent by default; --clone-dir overrides; no temp unless dest_dir=None is passed.
            dest = Path(clone_dir) if clone_dir else _default_persistent_clone_dir(repo_url)
            tmpdir = clone_repo(repo_url, dest_dir=dest)
            progress.update(t_clone, advance=1)

            repo_structure = analyze_repository(tmpdir)
            progress.update(t_an, advance=1)

        # ---- Fallback to populate files / languages if analyzer returned none ----
        if not repo_structure.get("files"):
            files, langs = fallback_scan(Path(tmpdir))
            repo_structure["files"] = files
            if not repo_structure.get("languages"):
                repo_structure["languages"] = langs

        # Optional JSON + summary
        if as_json:
            console.print("\n[highlight]--- Repository Structure (JSON) ---[/highlight]")
            console.print_json(data=repo_structure)
            console.print("[highlight]------------------------------------[/highlight]\n")

        console.print(pretty_repo_summary(repo_structure))

        if not repo_structure.get("services"):
            msg_warn("No services found. Skipping Docker generation.")
            msg_info(f"Repo cloned to: [highlight]{Path(tmpdir).resolve()}[/highlight]")
            return

        # ---- ONE LLM generation ----
        msg_info("Initializing LLM client")
        llm_client = GeminiClient()
        with console.status("[bold cyan]Generating Docker configuration...", spinner="dots"):
            with open(os.devnull, "w") as _null, redirect_stderr(_null):
                docker_config = generate_docker_configuration(repo_structure, llm_client)

        # ---- Write files directly into the cloned repo (correct structure) ----
        dockerfiles = docker_config.get("dockerfiles", []) or []
        nginx_configs = docker_config.get("nginx_configs", []) or []
        total_writes = len(dockerfiles) + len(nginx_configs) + (1 if docker_config.get("docker_compose") else 0)

        write_base = Path(tmpdir)
        with console.status("[bold cyan]Writing files...", spinner="bouncingBar"):
            with Progress(
                    SpinnerColumn(spinner_name="dots"),
                    TextColumn("[bold blue]{task.description}"),
                    BarColumn(complete_style="green", finished_style="bold green"),
                    TaskProgressColumn(),
                    MofNCompleteColumn(),
                    TimeElapsedColumn(),
                    console=console,
                    transient=True,
            ) as write_progress:
                t_write = write_progress.add_task("Writing files...", total=total_writes)

                # Dockerfiles
                for info in dockerfiles:
                    path = info.get("path")
                    content = info.get("content")
                    if not path or not content:
                        msg_warn("Skipping invalid Dockerfile entry.")
                        write_progress.update(t_write, advance=1)
                        continue
                    out_path = write_base / path
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    out_path.write_text(content, encoding="utf-8")
                    write_progress.update(t_write, advance=1)

                # Nginx configs
                for info in nginx_configs:
                    path = info.get("path")
                    content = info.get("content")
                    if not path or not content:
                        msg_warn("Skipping invalid Nginx config entry.")
                        write_progress.update(t_write, advance=1)
                        continue
                    out_path = write_base / path
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    out_path.write_text(content, encoding="utf-8")
                    write_progress.update(t_write, advance=1)

                # docker-compose.yml at repo root
                if docker_config.get("docker_compose"):
                    (write_base / "docker-compose.yml").write_text(
                        docker_config["docker_compose"], encoding="utf-8"
                    )
                    write_progress.update(t_write, advance=1)

        console.print(table_generated_files(docker_config, str(write_base)))
        repo_path = Path(tmpdir).resolve()
        msg_info(f"Repo cloned to: [highlight]{repo_path}[/highlight]")

        # ---- Build after generation (default) ----
        if not no_build:
            compose_path = repo_path / "docker-compose.yml"
            if not compose_path.exists():
                msg_warn("No docker-compose.yml found at repo root; skipping build.")
            else:
                if not _docker_available():
                    raise click.ClickException("Docker is not installed or not on PATH.")
                if not _docker_daemon_running():
                    raise click.ClickException(
                        "Docker daemon is not running. Please start Docker Desktop and try again."
                    )

                with console.status("[bold cyan]Validating docker-compose.yml...", spinner="dots"):
                    _compose(["config"], repo_path)

                with console.status("[bold cyan]Building images (docker compose build)...", spinner="earth"):
                    _compose(["build"], repo_path)

                msg_success("Docker images built successfully.")

                # --- START CONTAINERS AUTOMATICALLY ---
                with console.status("[bold green]Starting services (docker compose up -d)...", spinner="dots"):
                    _compose(["up", "-d"], repo_path)
                msg_success("Services started in the background (detached).")

        msg_success("Analysis and generation complete.")

    except (ValueError, click.ClickException) as e:
        msg_error(str(e))
    except Exception as e:
        msg_error(f"An unexpected error occurred: {e}")



@cli.command()
@click.argument("repo_url")
@click.option("--output-dir", default="output",
              help="Directory to save generated files (ignored; kept for backward-compat).")
@click.option("--inplace", is_flag=True,
              help="(Kept for compatibility) Writes into the cloned repo root (default now).")
@click.option("--clone-dir", default=None, help="Clone into this directory; overrides default persistent folder.")
def generate(repo_url, output_dir, inplace, clone_dir):
    """Generate Dockerfiles, nginx configs and docker-compose.yml from a Git repository."""
    tmpdir = None
    try:
        banner("Orchestrator-AI", "Docker Generator")

        # Persistent by default
        dest = Path(clone_dir) if clone_dir else _default_persistent_clone_dir(repo_url)
        with console.status("[bold cyan]Cloning repository...", spinner="earth"):
            tmpdir = clone_repo(repo_url, dest_dir=dest)

        with console.status("[bold cyan]Analyzing repository...", spinner="dots"):
            repo_structure = analyze_repository(tmpdir)

        if not repo_structure.get("services"):
            msg_warn("No services found. Nothing to generate.")
            msg_info(f"Repo cloned to: [highlight]{Path(tmpdir).resolve()}[/highlight]")
            return

        with console.status("[bold cyan]Initializing LLM client...", spinner="aesthetic"):
            llm_client = GeminiClient()

        with console.status("[bold cyan]Generating Docker configuration...", spinner="hamburger"):
            docker_config = generate_docker_configuration(repo_structure, llm_client)

        # Write into repo root
        dockerfiles = docker_config.get("dockerfiles", []) or []
        nginx_configs = docker_config.get("nginx_configs", []) or []
        total_tasks = len(dockerfiles) + len(nginx_configs) + (1 if docker_config.get("docker_compose") else 0)

        write_base = Path(tmpdir)
        with console.status("[bold cyan]Writing files...", spinner="bouncingBar"):
            with Progress(
                    SpinnerColumn(spinner_name="dots"),
                    TextColumn("[bold blue]{task.description}"),
                    BarColumn(complete_style="green", finished_style="bold green"),
                    TaskProgressColumn(),
                    MofNCompleteColumn(),
                    TimeElapsedColumn(),
                    console=console,
            ) as progress:
                task = progress.add_task("[green]Writing files...", total=total_tasks)

                # Dockerfiles
                for info in dockerfiles:
                    path = info.get("path")
                    content = info.get("content")
                    if not path or not content:
                        msg_warn("Skipping invalid Dockerfile entry.")
                        progress.update(task, advance=1)
                        continue
                    service_dir = write_base / Path(path).parent
                    service_dir.mkdir(parents=True, exist_ok=True)
                    dockerfile_path = write_base / path
                    dockerfile_path.write_text(content, encoding="utf-8")
                    progress.update(task, advance=1)

                # Nginx configs
                for info in nginx_configs:
                    path = info.get("path")
                    content = info.get("content")
                    if not path or not content:
                        msg_warn("Skipping invalid Nginx config entry.")
                        progress.update(task, advance=1)
                        continue
                    service_dir = write_base / Path(path).parent
                    service_dir.mkdir(parents=True, exist_ok=True)
                    nginx_path = write_base / path
                    nginx_path.write_text(content, encoding="utf-8")
                    progress.update(task, advance=1)

                # docker-compose.yml
                docker_compose_content = docker_config.get("docker_compose")
                if docker_compose_content:
                    compose_path = write_base / "docker-compose.yml"
                    compose_path.write_text(docker_compose_content, encoding="utf-8")
                    progress.update(task, advance=1)

        console.print(table_generated_files(docker_config, str(write_base)))
        repo_path = Path(tmpdir).resolve()
        msg_info(f"Repo cloned to: [highlight]{repo_path}[/highlight]")
        msg_success("Generation complete.")

    except (ValueError, click.ClickException) as e:
        msg_error(str(e))
    except Exception as e:
        msg_error(f"An unexpected error occurred: {e}")


@cli.command()
@click.argument("repo_url")
@click.option("--os", "target_os", default=None, help="Target OS: Windows, Linux, or macOS")
@click.option("--shell", "shell_type", default=None, help="Shell type: PowerShell, CMD, bash, zsh")
@click.option("--output-dir", default="output", help="Directory to save generated files.")
def commands(repo_url, target_os, shell_type, output_dir):
    """Generate OS-specific Docker commands for a repository."""
    tmpdir = None
    try:
        os.makedirs(output_dir, exist_ok=True)
        banner("Orchestrator-AI", "OS-Specific Docker Commands")

        with console.status("[bold cyan]Cloning repository...", spinner="earth"):
            tmpdir = clone_repo(repo_url, dest_dir=None)

        with console.status("[bold cyan]Analyzing repository...", spinner="dots"):
            repo_structure = analyze_repository(tmpdir)

        if not repo_structure.get("services"):
            msg_warn("No services found. Cannot generate Docker commands.")
            return

        # Initialize LLM and Docker command generator
        with console.status("[bold cyan]Initializing Docker command generator...", spinner="aesthetic"):
            llm_client = GeminiClient()
            cmd_generator = DockerCommandGenerator(llm_client)

        # Detect or use provided OS
        detected_os = target_os or cmd_generator.detect_user_os(shell_type)
        msg_info(f"Target OS: {detected_os}")
        if shell_type:
            msg_info(f"Shell: {shell_type}")

        # Generate OS-specific commands
        with console.status("[bold cyan]Generating OS-specific Docker commands...", spinner="hamburger"):
            command_result = cmd_generator.generate_docker_commands(
                repo_structure, detected_os, shell_type
            )

        # Display results in a nice table
        results_table = Table(
            title=f"Docker Commands for {detected_os}",
            show_header=True,
            header_style="bold magenta",
            border_style="blue",
            box=ROUNDED,
            expand=True,
        )
        results_table.add_column("Property", style="cyan", width=20)
        results_table.add_column("Value", style="white")

        results_table.add_row("Detected OS", detected_os)
        results_table.add_row("Shell Type", shell_type or "Default")
        results_table.add_row("Services Found", str(len(repo_structure.get("services", []))))

        console.print(results_table)

        # Show generated content
        console.print("\n" + "=" * 60)
        console.print("[bold cyan]Generated Docker Commands:[/bold cyan]")
        console.print("=" * 60)
        console.print(command_result["response"])

        # Save the response to a file
        commands_file = Path(output_dir) / f"docker-commands-{detected_os.lower()}.md"
        commands_content = f"""# Docker Commands for {detected_os}

**Repository:** {repo_url}
**Target OS:** {detected_os}
**Shell Type:** {shell_type or 'Default'}
**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S')}

## Services Detected
{json.dumps(repo_structure.get('services', []), indent=2)}

## Generated Commands

{command_result['response']}

## Command Examples

Here are some example commands formatted for {detected_os}:

"""

        # Add OS-specific examples
        examples = create_docker_command_examples(detected_os)
        for example_name, example_cmd in examples.items():
            commands_content += f"### {example_name.replace('_', ' ').title()}\n```\n{example_cmd}\n```\n\n"

        commands_file.write_text(commands_content, encoding="utf-8")

        # Show summary
        summary_table = Table(
            title="Generated Files",
            show_header=True,
            header_style="bold magenta",
            border_style="green",
            box=ROUNDED,
        )
        summary_table.add_column("File", style="cyan")
        summary_table.add_column("Type", style="yellow", justify="center")
        summary_table.add_column("OS", style="green", justify="center")

        summary_table.add_row(str(commands_file), "Commands", detected_os)

        console.print(summary_table)
        msg_success(f"OS-specific Docker commands generated for {detected_os}")

    except (ValueError, click.ClickException) as e:
        msg_error(str(e))
    except Exception as e:
        msg_error(f"An unexpected error occurred: {e}")
    finally:
        if tmpdir:
            with console.status("[bold cyan]Cleaning up...", spinner="bouncingBar"):
                safe_rmtree(tmpdir)


@cli.command()
@click.option("--os", "target_os", default="Windows", help="Target OS: Windows, Linux, or macOS")
def examples(target_os):
    """Show Docker command examples for different operating systems."""
    banner("Orchestrator-AI", f"Docker Command Examples for {target_os}")

    examples_dict = create_docker_command_examples(target_os)

    for example_name, example_cmd in examples_dict.items():
        console.print(f"\n[bold cyan]{example_name.replace('_', ' ').title()}:[/bold cyan]")
        console.print(Panel(example_cmd, border_style="blue", box=ROUNDED))

    msg_success(f"Examples shown for {target_os}")


if __name__ == "__main__":
    cli()
