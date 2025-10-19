"""
Core module for orchestrator-ai containing Docker generation and analysis functionality.
"""

from .prompts import (
    SYSTEM_PROMPT,
    DOCKER_COMMAND_GENERATION_PROMPT,
    generate_docker_command_prompt,
    detect_os_from_shell,
    format_docker_command_for_os,
    detect_react_framework,
    get_build_output_directory,
    generate_nginx_config,
)

from .generator import generate_docker_configuration
from .llm import GeminiClient
from .docker_commands import DockerCommandGenerator, create_docker_command_examples

__all__ = [
    'SYSTEM_PROMPT',
    'DOCKER_COMMAND_GENERATION_PROMPT',
    'generate_docker_command_prompt',
    'detect_os_from_shell',
    'format_docker_command_for_os',
    'detect_react_framework',
    'get_build_output_directory',
    'generate_nginx_config',
    'generate_docker_configuration',
    'GeminiClient',
    'DockerCommandGenerator',
    'create_docker_command_examples'
]