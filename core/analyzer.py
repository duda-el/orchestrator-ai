import os
import json
import zipfile
import shutil
import tempfile
from typing import List, Dict, Any

def analyze_repository(repo_path: str) -> Dict[str, Any]:
    services = []
    datastores = []

    repo_path = repo_path.replace('\\', '/')
    
    if zipfile.is_zipfile(repo_path):
        temp_dir = tempfile.mkdtemp()
        try:
            with zipfile.ZipFile(repo_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            services = _find_services(temp_dir)
        finally:
            shutil.rmtree(temp_dir)
    elif os.path.isdir(repo_path):
        services = _find_services(repo_path)
    else:
        raise ValueError(f"The provided path is not a valid directory or zip file: {repo_path}")

    return {
        "services": services,
        "datastores": datastores
    }

def _find_services(directory: str) -> List[Dict[str, Any]]:
    """
    Finds services by looking for package.json files.
    """
    services = []
    for root, _, files in os.walk(directory):
        if "package.json" in files:
            package_json_path = os.path.join(root, "package.json")
            try:
                with open(package_json_path, "r", encoding='utf-8') as f:
                    package_data = json.load(f)
                
                dependencies = package_data.get("dependencies", {})
                dev_dependencies = package_data.get("devDependencies", {})
                all_dependencies = {**dependencies, **dev_dependencies}

                service_type = "Node"  # Default to Node
                if "react" in all_dependencies:
                    service_type = "React"

                start_command = package_data.get("scripts", {}).get("start")

                service_info = {
                    "name": package_data.get("name", os.path.basename(root)),
                    "path": os.path.relpath(root, directory).replace('\\', '/'),
                    "type": service_type,
                    "start_command": start_command
                }
                
                if service_info:
                    services.append(service_info)
            except json.JSONDecodeError:
                print(f"Warning: Could not parse JSON from {package_json_path}")
            except Exception as e:
                print(f"An error occurred while processing {package_json_path}: {e}")

    return services

if __name__ == '__main__':
  
    test_repo_dir = "test_repo"
    if os.path.exists(test_repo_dir):
        shutil.rmtree(test_repo_dir)
    
    frontend_dir = os.path.join(test_repo_dir, "my-react-app")
    backend_dir = os.path.join(test_repo_dir, "my-express-server")
    os.makedirs(frontend_dir)
    os.makedirs(backend_dir)

    frontend_pkg = {
        "name": "frontend-app",
        "dependencies": {"react": "18.2.0"}
    }
    with open(os.path.join(frontend_dir, "package.json"), "w") as f:
        json.dump(frontend_pkg, f, indent=2)

    backend_pkg = {
        "name": "backend-server",
        "dependencies": {"express": "4.18.2"}
    }
    with open(os.path.join(backend_dir, "package.json"), "w") as f:
        json.dump(backend_pkg, f, indent=2)

    print(f"Created dummy repository at: {os.path.abspath(test_repo_dir)}")

    try:
        analysis_result = analyze_repository(test_repo_dir)
        print("\n--- Analysis Result ---")
        print(json.dumps(analysis_result, indent=4))
        print("-----------------------\n")
    except Exception as e:
        print(f"An error occurred during analysis: {e}")
