#!/usr/bin/env python3
"""
Demonstration script for the enhanced Docker command generation with OS awareness.
This script shows how the enhanced prompts work with different operating systems.
"""

import sys
from pathlib import Path

# Add the project root to Python path
sys.path.append(str(Path(__file__).resolve().parent))

from core.docker_commands import DockerCommandGenerator, create_docker_command_examples
from core.prompts import (
    DOCKER_COMMAND_GENERATION_PROMPT,
    generate_docker_command_prompt,
    detect_os_from_shell,
    format_docker_command_for_os,
    generate_os_specific_dockerfile_template
)


def demo_os_detection():
    """Demonstrate OS detection from shell information."""
    print("=== OS Detection Demo ===")
    
    shell_examples = [
        "powershell.exe",
        "cmd.exe",
        "bash",
        "zsh",
        "Windows PowerShell v5.1",
        "/bin/bash"
    ]
    
    for shell in shell_examples:
        detected_os = detect_os_from_shell(shell)
        print(f"Shell: '{shell}' -> OS: {detected_os}")
    
    print()


def demo_command_formatting():
    """Demonstrate OS-specific command formatting."""
    print("=== Command Formatting Demo ===")
    
    command_parts = [
        "docker build",
        "--tag myapp:latest",
        "--build-arg NODE_ENV=production",
        "--file Dockerfile",
        "."
    ]
    
    os_types = ["Windows", "Linux", "macOS"]
    shell_types = {"Windows": ["PowerShell", "CMD"], "Linux": ["bash"], "macOS": ["zsh"]}
    
    for os_type in os_types:
        print(f"\n--- {os_type} ---")
        for shell in shell_types.get(os_type, ["default"]):
            formatted_cmd = format_docker_command_for_os(command_parts, os_type, shell)
            print(f"{shell}: {formatted_cmd}")
    
    print()


def demo_dockerfile_templates():
    """Demonstrate OS-specific Dockerfile templates."""
    print("=== Dockerfile Templates Demo ===")
    
    service_types = ["node", "react", "python"]
    os_types = ["Windows", "Linux"]
    
    for service_type in service_types:
        print(f"\n--- {service_type.upper()} Service ---")
        for os_type in os_types:
            print(f"\n{os_type} deployment context:")
            template = generate_os_specific_dockerfile_template(service_type, os_type)
            # Show first few lines of template
            lines = template.split('\n')[:15]
            for line in lines:
                print(f"  {line}")
            print("  ... (truncated)")
    
    print()


def demo_command_examples():
    """Demonstrate pre-built command examples for different OS."""
    print("=== Command Examples Demo ===")
    
    os_types = ["Windows", "Linux"]
    
    for os_type in os_types:
        print(f"\n--- {os_type} Examples ---")
        examples = create_docker_command_examples(os_type)
        
        for example_name, example_cmd in examples.items():
            print(f"\n{example_name}:")
            print(example_cmd)
    
    print()


def demo_prompt_generation():
    """Demonstrate Docker command prompt generation."""
    print("=== Prompt Generation Demo ===")
    
    # Show the base prompt structure
    print("Base Docker Command Generation Prompt:")
    print("-" * 50)
    print(DOCKER_COMMAND_GENERATION_PROMPT[:500] + "... (truncated)")
    
    print("\n" + "="*50)
    
    # Show OS-specific prompt generation 
    os_types = ["Windows", "Linux", "macOS"]
    
    for os_type in os_types:
        print(f"\n--- {os_type} Specific Prompt ---")
        specific_prompt = generate_docker_command_prompt(os_type)
        # Show just the OS-specific part
        lines = specific_prompt.split('\n')[-3:]
        for line in lines:
            print(line)
    
    print()


def main():
    """Run all demonstrations."""
    print("🐳 Enhanced Docker Command Generation Demo")
    print("=" * 60)
    
    try:
        demo_os_detection()
        demo_command_formatting()
        demo_dockerfile_templates()
        demo_command_examples()
        demo_prompt_generation()
        
        print("✅ All demonstrations completed successfully!")
        print("\nKey Features Demonstrated:")
        print("- OS detection from shell information")
        print("- OS-specific command formatting (line continuations)")
        print("- Dockerfile templates with OS context")
        print("- Pre-built command examples")
        print("- Dynamic prompt generation")
        
    except Exception as e:
        print(f"❌ Error during demonstration: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())