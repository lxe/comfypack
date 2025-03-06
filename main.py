import asyncio
from fastapi import FastAPI, Request, UploadFile, File, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse
from contextlib import asynccontextmanager
import json
from typing import Dict, Any, AsyncIterator
from channels import ChannelManager
import logging
from uvicorn.logging import logging
from pathlib import Path
from model_path_inference import ModelPathInference
from model_finder import ModelFinder
from workflow_processor import extract_nodes, transform_nodes_data, clone_repos
import time

logger = logging.getLogger("uvicorn")

class AppState:
    def __init__(self):
        self.config: Dict[str, Any] = {}
        self.is_initialized: bool = False
        self.workflow_storage: Dict[str, Any] = {}

    async def initialize(self):
        """Initialize application state."""
        if self.is_initialized:
            return
        
        self.channel_manager = ChannelManager()
        self.model_finder = ModelFinder()
        await self.model_finder.setup()

        self.is_initialized = True

    async def cleanup(self):
        """Cleanup application state."""
        self.is_initialized = False
        self.config.clear()
        self.workflow_storage.clear()
        await self.model_finder.cleanup()

# Create a global state instance
app_state = AppState()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for the FastAPI application.
    Handles startup and shutdown events.
    """
    # Startup
    logger.info("Starting up the application...")
    await app_state.initialize()
    
    yield  # Server is running and handling requests here
    
    # Shutdown
    logger.info("Shutting down the application...")
    await app_state.cleanup()

app = FastAPI(lifespan=lifespan)

# Mount static files directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# Set up templates
templates = Jinja2Templates(directory="templates")

@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

async def process_workflow(workflow_data: dict) -> AsyncIterator[str]:
    """Process workflow and yield progress updates."""
    try:
        # Extract and transform nodes
        message = json.dumps({"status": "extracting", "message": "Extracting nodes...", "progress": 0})
        logger.debug(f"Sending message: {message}")
        yield message
        
        nodes = extract_nodes(workflow_data, app_state.channel_manager)
        transformed_data = transform_nodes_data(nodes)
        
        # delay 1 second
        # await asyncio.sleep(1)

        # Clone repositories
        message = json.dumps({"status": "cloning", "message": "Cloning repositories...", "progress": 25})
        logger.debug(f"Sending message: {message}")
        yield message
        
        await clone_repos(transformed_data["repos"])
        # delay 1 second
        # await asyncio.sleep(1)
        
        # Infer model paths
        message = json.dumps({"status": "inferring", "message": "Inferring model paths...", "progress": 50})
        logger.debug(f"Sending message: {message}")
        yield message
        
        model_path_inference = ModelPathInference(Path("custom_nodes"))
        model_paths = await model_path_inference.infer_model_paths(transformed_data)
        transformed_data.update(model_paths)
        
        # Find models online
        total_models = len(transformed_data["models"])
        for i, model in enumerate(transformed_data["models"], 1):
            message = json.dumps({
                "status": "searching",
                "message": f"Finding model {i}/{total_models}: {model['filename']}",
                "progress": (i / total_models) * 100
            })
            logger.debug(f"Sending message: {message}")
            yield message
            model["url"] = await app_state.model_finder.find_model_online(model["filename"])
        
        # Create summary of custom nodes and models
        summary = {
            "custom_nodes": [repo["url"] for repo in transformed_data["repos"] if repo["url"] != "https://github.com/comfyanonymous/ComfyUI"],
            "models": [{"url": model["url"], "filepath": model["inferred_path"]} for model in transformed_data["models"]]
        }
        
        # Send final data
        message = json.dumps({
            "status": "complete",
            "message": "Processing complete",
            "data": summary
        })

        logger.debug(f"Sending final message: {message}")
        yield message
        
    except Exception as e:
        logger.error(f"Error processing workflow: {e}")
        message = json.dumps({"status": "error", "message": str(e)})
        logger.debug(f"Sending error message: {message}")
        yield message

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    contents = await file.read()
    workflow_data = json.loads(contents)
    return EventSourceResponse(process_workflow(workflow_data))
