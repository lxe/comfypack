import ast
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
import asyncio
import os
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger("uvicorn")

@dataclass
class ModelInfo:
    """Data class for model information"""
    filename: str
    required_by: List[str]
    node_info: Optional[Dict] = None

class NodeVisitor(ast.NodeVisitor):
    """Base visitor for finding model folder requirements in node classes."""
    
    def __init__(self, source_file: Path):
        self.source_file = source_file
        self.class_folders: Dict[str, Dict[str, str]] = {}
        self.current_class: Optional[str] = None
        
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Visit class definitions to find INPUT_TYPES methods."""
        self.current_class = node.name
        
        # Find the INPUT_TYPES classmethod
        for item in node.body:
            if (isinstance(item, ast.FunctionDef) and 
                item.name == "INPUT_TYPES" and
                any(isinstance(dec, ast.Name) and dec.id == "classmethod" 
                    for dec in item.decorator_list)):
                
                self._find_folders_in_method(item)
                
        self.generic_visit(node)
        
    def visit_Call(self, node: ast.Call) -> None:
        """Find folder_paths.get_filename_list calls and extract the folder name."""
        try:
            if (isinstance(node.func, ast.Attribute) and 
                isinstance(node.func.value, ast.Name) and
                node.func.value.id == "folder_paths" and
                node.func.attr == "get_filename_list" and
                len(node.args) > 0 and
                isinstance(node.args[0], ast.Constant)):
                
                folder_name = node.args[0].value
                if self.current_class:  # Only store if we're in a class context
                    if self.current_class not in self.class_folders:
                        self.class_folders[self.current_class] = {}
                    self.class_folders[self.current_class][folder_name] = folder_name
                    logger.debug(f"Found model folder '{folder_name}' in class '{self.current_class}'")
                
        except Exception as e:
            logger.error(f"Error processing folder path in {self.source_file}: {e}")
            
        self.generic_visit(node)
        
    def _find_folders_in_method(self, node: ast.FunctionDef) -> None:
        """Find folder requirements in a method body."""
        self.generic_visit(node)

class ModelPathInference:
    """Main class for inferring model paths"""
    
    # Common model type patterns and their folders
    MODEL_PATTERNS = {
        "vae": "vae",
        "lora": "loras",
        "embedding": "embeddings",
        "checkpoint": "checkpoints",
        "upscale": "upscale_models",
        "controlnet": "controlnet",
        "clip": "clip",
        "hypernetwork": "hypernetworks",
        "t2i": "checkpoints",  # text to image models are usually checkpoints
        "sd": "checkpoints",   # stable diffusion models
    }
    
    def __init__(self, custom_nodes_path: Path):
        self.custom_nodes_path = custom_nodes_path
        self.node_class_folders: Dict[str, Dict[str, str]] = {}
        self.required_node_types: Set[str] = set()
        self.node_class_mappings: Dict[str, str] = {}
        
    def _load_node_class_mappings(self) -> None:
        """Load NODE_CLASS_MAPPINGS from Python files to map display names to class names."""
        try:
            for file_path in self.custom_nodes_path.rglob("*.py"):
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    if "NODE_CLASS_MAPPINGS" not in content:
                        continue
                    
                    tree = ast.parse(content)
                    for node in ast.walk(tree):
                        if (isinstance(node, ast.Assign) and 
                            len(node.targets) == 1 and
                            isinstance(node.targets[0], ast.Name) and
                            node.targets[0].id == "NODE_CLASS_MAPPINGS" and
                            isinstance(node.value, ast.Dict)):
                            
                            # Extract key-value pairs from the dictionary
                            for key, value in zip(node.value.keys, node.value.values):
                                if isinstance(key, ast.Constant) and isinstance(value, ast.Name):
                                    self.node_class_mappings[key.value] = value.id
                            
        except Exception as e:
            logger.error(f"Error loading NODE_CLASS_MAPPINGS: {e}")

    def _find_python_files(self) -> List[Path]:
        """Find all Python files in the custom nodes directory."""
        return [
            path for path in self.custom_nodes_path.rglob("*.py")
            if not any(part.startswith(".") for part in path.parts)
        ]

    def _analyze_file(self, file_path: Path) -> Dict[str, Dict[str, str]]:
        """Analyze a single Python file for node classes and their folder requirements."""
        try:
            # Quick check for INPUT_TYPES before parsing
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                if "INPUT_TYPES" not in content:
                    return {}

            # Only parse if INPUT_TYPES is found
            tree = ast.parse(content)
            visitor = NodeVisitor(file_path)
            visitor.visit(tree)
            
            if visitor.class_folders:
                logger.info(f"Found {len(visitor.class_folders)} class folders in {file_path}")
                return visitor.class_folders
                
        except Exception as e:
            logger.error(f"Error analyzing {file_path}: {e}")
        
        return {}

    async def _analyze_node_classes(self) -> None:
        """Analyze all Python files to find node classes and their folder requirements."""
        python_files = self._find_python_files()
        logger.info(f"Analyzing {len(python_files)} Python files...")
        
        # Use ThreadPoolExecutor for file I/O operations
        with ThreadPoolExecutor(max_workers=min(32, os.cpu_count() * 4)) as executor:
            loop = asyncio.get_event_loop()
            tasks = []
            
            for file_path in python_files:
                task = loop.run_in_executor(executor, self._analyze_file, file_path)
                tasks.append(task)
            
            # Wait for all tasks to complete
            results = await asyncio.gather(*tasks)
            
            # Process results and check for early exit
            for class_folders in results:
                self.node_class_folders.update(class_folders)
                
                # Check if we've found all required node types
                if self.required_node_types and all(
                    node_type in self.node_class_folders 
                    for node_type in self.required_node_types
                ):
                    logger.debug("Found all required node types, stopping analysis")
                    break

    def _guess_model_folder(self, filename: str) -> Optional[str]:
        """Make an educated guess about which folder a model belongs in based on its filename."""
        filename_lower = filename.lower()
        
        for pattern, folder in self.MODEL_PATTERNS.items():
            if pattern in filename_lower:
                logger.debug(f"Guessed folder '{folder}' for model '{filename}'")
                return folder
                
        return None

    async def infer_model_paths(self, models_data: Dict) -> Dict:
        """Process models data and infer their paths"""
        # Load node class mappings first
        self._load_node_class_mappings()
        
        # Collect required node types for early exit optimization
        self.required_node_types = {
            self.node_class_mappings.get(node_type, node_type)  # Try to map display name to class name
            for model in models_data.get("models", [])
            for node_type in model["needed_by"]
        }
        
        # Analyze node classes asynchronously
        logger.info("Analyzing node classes...")
        await self._analyze_node_classes()
        
        result = {"models": []}
        
        logger.info("Inferring model paths...")
        for model in models_data.get("models", []):
            model_info = ModelInfo(
                filename=model["filename"],
                required_by=model["needed_by"]
            )
            
            # Try to find folder from node class requirements first
            inferred_folder = None
            for display_name in model["needed_by"]:
                # Try both the display name and the mapped class name
                node_type = self.node_class_mappings.get(display_name, display_name)
                if node_type in self.node_class_folders:
                    folders = self.node_class_folders[node_type]
                    if folders:
                        inferred_folder = next(iter(folders.values()))
                        model_info.node_info = {
                            "model_folders": folders,
                            "source_file": "found_in_class_definition",
                            "node_class": node_type,
                            "display_name": display_name
                        }
                        break
            
            # Fall back to filename-based guessing if needed
            if not inferred_folder:
                inferred_folder = self._guess_model_folder(model["filename"])
                if inferred_folder:
                    model_info.node_info = {
                        "model_folders": {inferred_folder: inferred_folder},
                        "source_file": "guessed_from_filename"
                    }
            
            result["models"].append({
                "filename": model_info.filename,
                "required_by": model_info.required_by,
                "node_info": model_info.node_info,
                "inferred_path": f"models/{inferred_folder}/{model_info.filename}" if inferred_folder else None
            })
            
        return result 