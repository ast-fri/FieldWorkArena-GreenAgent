from pathlib import Path
from typing import Any

import os
import yaml

from google.adk.models.lite_llm import LiteLlm

def get_litellm_model(
        llm_name: str = "openai",
        model_name: str = "gpt-4o")-> LiteLlm:
    """Get LiteLlm model based on the specified llm_name."""
    try:
        API_KEY = os.getenv("OPENAI_API_KEY", "")

        if llm_name == "openai":
            llm = "openai/" + model_name
            return LiteLlm(
                model=llm,
                api_key=API_KEY,
            )
        else:
            raise ValueError(f"Unsupported llm_name: {llm_name}")
    except Exception as e:
        raise RuntimeError(f"Failed to initialize LiteLlm: {e}")

def load_yaml_config(config_name: str) -> dict[str, Any]:
    """Load configuration from YAML file.

    Args:
        config_name (str): Name of the config file (without .yaml extension)

    Returns:
        dict[str, Any]: Configuration dictionary loaded from YAML file

    Raises:
        FileNotFoundError: If the config file doesn't exist
        yaml.YAMLError: If the YAML file is malformed
    """
    # Build config file path
    config_path = Path(__file__).parent.parent / "prompts" / f"{config_name}.yaml"

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    try:
        with open(config_path, encoding="utf-8") as file:
            config = yaml.safe_load(file)
        if not isinstance(config, dict):
            raise ValueError(f"Config file must contain a dictionary, got {type(config).__name__}")
        return config
    except yaml.YAMLError as e:
        raise yaml.YAMLError(f"Error parsing YAML file {config_path}: {e}")