"""
Configuration manager for Claude PR Reviewer.
"""

import os
import json
from typing import Dict, Any


class ConfigManager:
    """Class to manage configuration"""
    
    def __init__(self, config_path: str = "~/.claude_pr_reviewer.json"):
        """Initialize with config file path"""
        self.config_path = os.path.expanduser(config_path)
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    return json.load(f)
            else:
                return self._create_default_config()
        except Exception as e:
            print(f"Error loading config: {e}")
            return self._create_default_config()
    
    def _create_default_config(self) -> Dict[str, Any]:
        """Create default configuration"""
        config = {
            "api_key": "",
            "model": "claude-3-haiku-20240307",
            "max_diff_size": 10000,  # Max characters to send to Claude
        }
        
        # Prompt for API key if not in environment
        api_key = os.environ.get("CLAUDE_API_KEY")
        if not api_key:
            print("Claude API key not found.")
            api_key = input("Please enter your Claude API key: ").strip()
        
        config["api_key"] = api_key
        
        # Save the config
        self._save_config(config)
        return config
    
    def _save_config(self, config: Dict[str, Any]) -> None:
        """Save configuration to file"""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def get(self, key: str) -> Any:
        """Get configuration value"""
        return self.config.get(key)
    
    def set(self, key: str, value: Any) -> None:
        """Set configuration value"""
        self.config[key] = value
        self._save_config(self.config)