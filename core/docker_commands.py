"""
Docker command generation module with OS-specific formatting.
"""

import platform
from typing import Dict, List, Optional
from core.llm import GeminiClient
from core.prompts import (
    DOCKER_COMMAND_GENERATION_PROMPT,
    detect_os_from_shell,
    format_docker_command_for_os,
    detect_react_framework,
    get_build_output_directory,
)


class DockerCommandGenerator:
    """
    Generates OS-specific Docker commands and Dockerfiles using LLM.
    """
    
    def __init__(self, llm_client: GeminiClient):
        self.llm_client = llm_client
    
    def detect_user_os(self, shell_hint: str = None) -> str:
        """
        Detect user's operating system.
        
        Args:
            shell_hint: Optional shell information for OS detection
            
        Returns:
            Detected OS name
        """
        if shell_hint:
            return detect_os_from_shell(shell_hint)
        
        # Fallback to platform detection
        system = platform.system().lower()
        if system == "windows":
            return "Windows"
        elif system == "darwin":
            return "macOS"
        else:
            return "Linux"
    
    def generate_docker_commands(
        self,
        project_info: Dict,
        user_os: str = None,
        shell_type: str = None
    ) -> Dict[str, str]:
        """
        Generate OS-specific Docker commands for a project.
        
        Args:
            project_info: Project information dictionary
            user_os: Target operating system
            shell_type: Specific shell type (PowerShell, CMD, bash, etc.)
            
        Returns:
            Dictionary containing generated commands and Dockerfiles
        """
        if not user_os:
            user_os = self.detect_user_os()
        
        # Create the prompt with OS context
        prompt = f"""
{DOCKER_COMMAND_GENERATION_PROMPT}

## User Context
- Operating System: {user_os}
- Shell Type: {shell_type or 'Default'}
- Project Info: {project_info}

Please generate Docker commands and Dockerfiles appropriate for {user_os}.
Include build commands, run commands, and a properly formatted Dockerfile.

Format your response with clear sections:
1. Detected OS confirmation
2. Docker build command (OS-specific syntax)
3. Docker run command (OS-specific syntax)
4. Dockerfile (multi-line, well-formatted)
5. Additional notes for {user_os} users
"""
        
        print(f"Generating Docker commands for {user_os}...")
        response = self.llm_client.generate_content(prompt)
        
        return {
            "os": user_os,
            "shell_type": shell_type,
            "response": response,
            "project_info": project_info
        }
    
    def format_build_command(
        self,
        image_name: str,
        dockerfile_path: str = "Dockerfile",
        context_path: str = ".",
        build_args: Dict[str, str] = None,
        user_os: str = "Windows",
        shell_type: str = "PowerShell"
    ) -> str:
        """
        Format Docker build command for specific OS.
        
        Args:
            image_name: Name for the Docker image
            dockerfile_path: Path to Dockerfile
            context_path: Build context path
            build_args: Optional build arguments
            user_os: Target operating system
            shell_type: Shell type for formatting
            
        Returns:
            Formatted Docker build command
        """
        command_parts = ["docker build"]
        
        # Add build arguments
        if build_args:
            for key, value in build_args.items():
                command_parts.append(f"--build-arg {key}={value}")
        
        # Add tag
        command_parts.append(f"--tag {image_name}")
        
        # Add dockerfile path if not default
        if dockerfile_path != "Dockerfile":
            command_parts.append(f"--file {dockerfile_path}")
        
        # Add context path
        command_parts.append(context_path)
        
        return format_docker_command_for_os(command_parts, user_os, shell_type)
    
    def format_run_command(
        self,
        image_name: str,
        ports: List[str] = None,
        volumes: List[str] = None,
        env_vars: Dict[str, str] = None,
        container_name: str = None,
        user_os: str = "Windows",
        shell_type: str = "PowerShell"
    ) -> str:
        """
        Format Docker run command for specific OS.
        
        Args:
            image_name: Docker image name
            ports: List of port mappings (e.g., ["3000:3000"])
            volumes: List of volume mounts
            env_vars: Environment variables
            container_name: Optional container name
            user_os: Target operating system
            shell_type: Shell type for formatting
            
        Returns:
            Formatted Docker run command
        """
        command_parts = ["docker run"]
        
        # Add detached mode
        command_parts.append("-d")
        
        # Add container name
        if container_name:
            command_parts.append(f"--name {container_name}")
        
        # Add port mappings
        if ports:
            for port in ports:
                command_parts.append(f"-p {port}")
        
        # Add volume mounts
        if volumes:
            for volume in volumes:
                command_parts.append(f"-v {volume}")
        
        # Add environment variables
        if env_vars:
            for key, value in env_vars.items():
                command_parts.append(f"-e {key}={value}")
        
        # Add image name
        command_parts.append(image_name)
        
        return format_docker_command_for_os(command_parts, user_os, shell_type)
    
    def generate_dockerfile_for_service(
        self,
        service_type: str,
        service_config: Dict,
        user_os: str = "Windows"
    ) -> str:
        """
        Generate Dockerfile for a specific service type using LLM.
        
        Args:
            service_type: Type of service (node, react, python, etc.)
            service_config: Service configuration
            user_os: Target OS for deployment context
            
        Returns:
            Generated Dockerfile content
        """
        # Detect framework if it's a React project
        framework_info = ""
        if service_type.lower() in ["react", "frontend", "vite"]:
            package_json = service_config.get("package_json", {})
            if package_json:
                framework_type = detect_react_framework(package_json)
                build_dir = get_build_output_directory(framework_type)
                framework_info = f"""
Framework Detected: {framework_type}
Build Output Directory: {build_dir}
"""
        
        prompt = f"""
Generate an optimized, production-ready Dockerfile for a {service_type} service.

{framework_info}

Target OS Context: {user_os}

Service Configuration:
{service_config}

Requirements:
1. Use multi-stage builds for optimization
2. Run as non-root user for security
3. Proper layer caching (dependencies before source code)
4. Include health checks
5. Use specific base image versions (not 'latest')
6. Format with proper line breaks and comments
7. For React/Vite projects, ensure correct build output directory
8. Include nginx configuration if it's a frontend service

Return ONLY the Dockerfile content, properly formatted with line breaks.
"""
        
        response = self.llm_client.generate_content(prompt)
        return response


def create_docker_command_examples(user_os: str = "Windows") -> Dict[str, str]:
    """
    Create example Docker commands for different scenarios.
    
    Args:
        user_os: Target operating system
        
    Returns:
        Dictionary of example commands
    """
    examples = {}
    
    if user_os.lower() == "windows":
        examples.update({
            "build_powershell": """docker build `
  --tag myapp:latest `
  --file Dockerfile `
  .""",
            
            "run_powershell": """docker run `
  -d `
  --name myapp-container `
  -p 3000:3000 `
  -e NODE_ENV=production `
  myapp:latest""",
            
            "compose_powershell": """docker-compose `
  --file docker-compose.yml `
  up `
  --detach""",
            
            "build_with_args_powershell": """docker build `
  --tag myapp:latest `
  --build-arg NODE_ENV=production `
  --build-arg API_URL=https://api.example.com `
  ."""
        })
    else:
        examples.update({
            "build_unix": """docker build \\
  --tag myapp:latest \\
  --file Dockerfile \\
  .""",
            
            "run_unix": """docker run \\
  -d \\
  --name myapp-container \\
  -p 3000:3000 \\
  -e NODE_ENV=production \\
  myapp:latest""",
            
            "compose_unix": """docker-compose \\
  --file docker-compose.yml \\
  up \\
  --detach""",
            
            "build_with_args_unix": """docker build \\
  --tag myapp:latest \\
  --build-arg NODE_ENV=production \\
  --build-arg API_URL=https://api.example.com \\
  ."""
        })
    
    return examples