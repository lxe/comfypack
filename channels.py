from typing import Dict, List, Optional, Tuple, Generator
from cached_request import CachedRequest
import logging
import json
import itertools
logger = logging.getLogger("uvicorn")

class ChannelManager:
    KNOWN_NODES = {
        "rgthree": "https://github.com/rgthree/rgthree-comfy",
        "crystools": "https://github.com/crystian/ComfyUI-Crystools"
    }

    CHANNELS_URL = "https://raw.githubusercontent.com/ltdrdata/ComfyUI-Manager/main/channels.list.template"

    def __init__(self):
        self.requester = CachedRequest()
        self.repo_mappings = {}
        self.populate_repo_mappings()

    def get_channel_urls(self) -> Dict[str, str]:
        """Parse channels.list.template into a dict of channel URLs"""
        response = self.requester.get(self.CHANNELS_URL)
        content = response.text
        if response.headers.get('content-type', '').startswith('application/json'):
            content = json.dumps(response.json())
            
        channels = {}
        for line in content.splitlines():
            if not line.strip():
                continue
            parts = line.split("::")
            if len(parts) == 2:
                channel_name, url = parts
                channels[channel_name] = url.strip()
        return channels
  
    def find_repo_by_pattern(self, node_type: str) -> Optional[str]:
        """Find repository URL by matching node type against known patterns"""
        for pattern, repo in self.KNOWN_NODES.items():
            if pattern.lower() in node_type.lower():
                logger.debug(f"Matched node {node_type} to repo {repo} via pattern {pattern}")
                return repo
        return None

    def get_node_mappings(self, channel_url: str) -> Dict[str, List]:
        """Get node->repo mappings from a channel"""
        url = f"{channel_url}/extension-node-map.json"
        logger.debug(f"Fetching node mappings from {url}")
        response = self.requester.get(url)
        return response.json()

    def populate_repo_mappings(self):
        channels = self.get_channel_urls()
        repo_map = {}  # node_type -> repo_url mapping

        for channel_name, channel_url in channels.items():
            mappings = self.get_node_mappings(channel_url)
            # logger.info(f"Mappings: {mappings}")
            for repo_url, nodes_info in mappings.items():
                if isinstance(nodes_info, list) and len(nodes_info) >= 1:
                    nodes = nodes_info[0]  # First element contains nodes
                    for node in nodes:
                        repo_map[node] = repo_url

        self.repo_mappings = repo_map

    def get_repo_from_node_type(self, node_type: str) -> Optional[str]:
        """Get repository URL from node type"""
        repo = self.repo_mappings.get(node_type)
        if not repo:
            logger.warning(f"No repo found for node type {node_type}, trying to find by pattern")
            repo = self.find_repo_by_pattern(node_type)
        
        if not repo:    
            logger.warning(f"No repo found for node type {node_type}")

        return repo
