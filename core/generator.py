import json
import re
from typing import Dict, Any, List
from core.llm import GeminiClient
from core.prompts import SYSTEM_PROMPT

def _generate_user_prompt(project_structure: Dict[str, Any]) -> str:
    """
    Generates the user prompt for the AI.
    """
    return f"""Please generate optimized Dockerfiles and a docker-compose.yml file for the following project structure:

{json.dumps(project_structure, indent=2)}

Remember to:
1. Create multi-stage Dockerfiles for each service
2. Use appropriate base images based on service type
3. Configure proper networking between services
4. Set up volumes for persistent data
5. Include health checks where appropriate
6. Configure environment variables
7. Set up proper dependencies with depends_on

Respond with ONLY the JSON object as specified in the output format. Do not include any markdown formatting or code blocks."""

def _parse_llm_response(response_text: str) -> Dict[str, Any]:
    """
    Parses the JSON response from the LLM, cleaning up markdown.
    """
    # Remove markdown code block fences
    cleaned_response = re.sub(r'```json\n?|```', '', response_text.strip())
    
    try:
        parsed_json = json.loads(cleaned_response)
        # Basic validation
        if "dockerfiles" not in parsed_json or "docker_compose" not in parsed_json:
            raise ValueError("Invalid JSON structure in LLM response.")
        return parsed_json
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON from LLM response: {e}")
        print(f"Raw response:\n{response_text}")
        raise

def generate_docker_configuration(project_structure: Dict[str, Any], llm_client: GeminiClient) -> Dict[str, Any]:
    """
    Generates Dockerfiles and docker-compose.yml using the LLM.
    """
    user_prompt = _generate_user_prompt(project_structure)
    full_prompt = f"{SYSTEM_PROMPT}\n\n---\n\n{user_prompt}"
    
    print("Generating Docker configuration via LLM...")
    response_text = llm_client.generate_content(full_prompt)
    
    print("Parsing LLM response...")
    docker_config = _parse_llm_response(response_text)
    
    return docker_config
