import subprocess
from pathlib import Path
from typing import List, Dict, TypedDict
import logging

logger = logging.getLogger("uvicorn")

class RepoInfo(TypedDict):
    url: str
    needed_by: List[str]

class ModelInfo(TypedDict):
    filename: str
    needed_by: List[str]

class NodesData(TypedDict):
    node_types: List[str]
    unmapped_nodes: List[str]
    repos: List[RepoInfo]
    models: List[ModelInfo]

def extract_models_from_node(node: dict) -> list[str]:
    """Extract model filenames from workflow data nodes' widget values."""
    model_files = set()
    model_extensions = ('.safetensors', '.pt', '.pth', '.onnx', '.bin', '.ckpt')
    
    for value in node.get("widgets_values", []):
        if isinstance(value, str) and value.lower().endswith(model_extensions):
            model_files.add(value)
    
    return list(model_files)

def extract_nodes(workflow_data: dict, channel_manager) -> list[dict]:
    """Extract unique node types from workflow data, excluding group nodes."""
    node_types = set()
    group_node_types = set()
    all_nodes = []  # Changed to list instead of set

    # Add all nodes in the workflow
    all_nodes.extend(workflow_data.get("nodes", []))
    
    # Collect all group node types
    for group_name, group_data in workflow_data.get("extra", {}).get("groupNodes", {}).items():
        group_node_types.add(group_name)
        all_nodes.extend(group_data.get("nodes", []))

    results = []
    for node in all_nodes:
        node_type = node["type"]
        if node_type in group_node_types:
            continue

        repo = channel_manager.get_repo_from_node_type(node_type)
        model = extract_models_from_node(node)
        node_types.add(node_type)
        results.append({
            "type": node_type,
            "model": model,
            "repo": repo
        })
           
    return sorted(results, key=lambda x: x["type"])

def transform_nodes_data(nodes: list[dict]) -> NodesData:
    """Transform nodes data into a structured format with node types, repos, and models."""
    result: NodesData = {
        "node_types": [],
        "unmapped_nodes": [],
        "repos": [],
        "models": []
    }
    
    # Collect unique node types
    node_types = sorted(list(set(node["type"] for node in nodes)))
    result["node_types"] = node_types
    
    # Collect unmapped nodes (nodes without repo)
    result["unmapped_nodes"] = sorted(list(set(node["type"] for node in nodes if node["repo"] is None)))
    
    # Build repos mapping
    repos_dict = {}
    for node in nodes:
        if node["repo"]:
            if node["repo"] not in repos_dict:
                repos_dict[node["repo"]] = {"url": node["repo"], "needed_by": set()}
            repos_dict[node["repo"]]["needed_by"].add(node["type"])
    
    # Convert sets to sorted lists for JSON serialization
    for repo in repos_dict.values():
        repo["needed_by"] = sorted(list(repo["needed_by"]))
    result["repos"] = list(repos_dict.values())
    
    # Build models mapping
    models_dict = {}
    for node in nodes:
        for model in node["model"]:
            if model not in models_dict:
                models_dict[model] = {"filename": model, "needed_by": set()}
            models_dict[model]["needed_by"].add(node["type"])
    
    # Convert sets to sorted lists for JSON serialization
    for model in models_dict.values():
        model["needed_by"] = sorted(list(model["needed_by"]))
    result["models"] = list(models_dict.values())
    
    return result

async def clone_repos(repos: List[RepoInfo]) -> None:
    """Clone repositories if they don't exist."""
    Path("custom_nodes").mkdir(parents=True, exist_ok=True)
    for repo in repos:
        repo_url = repo["url"]
        repo_path = Path(f"custom_nodes/{repo_url.split('/')[-1]}")
        if not repo_path.exists():
            logger.info(f"Cloning repository {repo_url}...")
            subprocess.run([
                "git", "clone", "--depth", "1", "--recurse-submodules",
                repo_url, str(repo_path)]) 