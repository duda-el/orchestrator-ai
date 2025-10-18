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
from core.analyzer import analyze_repository
from core.generator import generate_docker_configuration
from core.llm import GeminiClient

# Load environment variables from .env file
# Look for .env file in the project root directory
project_root = Path(__file__).resolve().parents[1]
env_path = project_root / '.env'
load_dotenv(env_path)

def handle_remove_readonly(func, path, exc):
    """
    Error handler for shutil.rmtree on Windows to handle read-only files.
    """
    if os.path.exists(path):
        # Make the file writable and try again
        os.chmod(path, stat.S_IWRITE)
        func(path)

def safe_rmtree(path):
    """
    Safely remove a directory tree, handling Windows permission issues.
    """
    if os.path.exists(path):
        shutil.rmtree(path, onerror=handle_remove_readonly)

def clone_repo(repo_url: str) -> str:
    """
    Clones a Git repository to a temporary directory.
    """
    tmpdir = tempfile.mkdtemp(prefix="orchai_")
    try:
        subprocess.check_call(["git", "clone", "--depth", "1", repo_url, tmpdir])
        return tmpdir
    except subprocess.CalledProcessError as e:
        safe_rmtree(tmpdir)
        raise click.ClickException(f"Failed to clone repository: {e}")
    except FileNotFoundError:
        safe_rmtree(tmpdir)
        raise click.ClickException("Git is not installed or not in your PATH.")

@click.group()
def cli():
    """Orchestrator AI CLI"""
    pass

@cli.command()
@click.argument('repo_url')
def analyze(repo_url):
    """Analyzes a Git repository and prints the structure as JSON."""
    tmpdir = None
    try:
        click.echo(f"Cloning repository from {repo_url}...")
        tmpdir = clone_repo(repo_url)
        
        repo_structure = analyze_repository(tmpdir)
        click.echo(json.dumps(repo_structure, indent=4))
    except (ValueError, click.ClickException) as e:
        click.echo(f"Error: {e}", err=True)
    finally:
        if tmpdir:
            safe_rmtree(tmpdir)

@cli.command()
@click.argument('repo_url')
@click.option('--output-dir', default='output', help='Directory to save generated files.')
def generate(repo_url, output_dir):
    """Generates Dockerfiles and docker-compose.yml from a Git repository."""
    tmpdir = None
    try:
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)

        # Clone repository
        click.echo(f"Cloning repository from {repo_url}...")
        tmpdir = clone_repo(repo_url)

        # Analyze repository
        click.echo(f"Analyzing repository at {tmpdir}...")
        repo_structure = analyze_repository(tmpdir)
        
        # Initialize LLM client
        click.echo("Initializing Gemini client...")
        llm_client = GeminiClient()

        # Generate Docker configuration
        docker_config = generate_docker_configuration(repo_structure, llm_client)

        # Save Dockerfiles
        for dockerfile_info in docker_config.get("dockerfiles", []):
            path = dockerfile_info.get("path")
            content = dockerfile_info.get("content")
            if not path or not content:
                click.echo(f"Warning: Skipping invalid Dockerfile entry.", err=True)
                continue
            
            # Create service-specific directory inside output_dir
            service_dir = os.path.join(output_dir, os.path.dirname(path))
            os.makedirs(service_dir, exist_ok=True)
            
            dockerfile_path = os.path.join(output_dir, path)
            with open(dockerfile_path, "w", encoding="utf-8") as f:
                f.write(content)
            click.echo(f"Generated Dockerfile: {dockerfile_path}")

        # Save docker-compose.yml
        docker_compose_content = docker_config.get("docker_compose")
        if docker_compose_content:
            compose_path = os.path.join(output_dir, "docker-compose.yml")
            with open(compose_path, "w", encoding="utf-8") as f:
                f.write(docker_compose_content)
            click.echo(f"Generated docker-compose.yml: {compose_path}")
        
        click.echo("\nGeneration complete.")

    except (ValueError, click.ClickException) as e:
        click.echo(f"Error: {e}", err=True)
    except Exception as e:
        click.echo(f"An unexpected error occurred: {e}", err=True)
    finally:
        if tmpdir:
            safe_rmtree(tmpdir)

if __name__ == '__main__':
    cli()
