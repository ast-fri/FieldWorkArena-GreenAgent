"""
Task loader module for loading task IDs from configuration files.
"""

import json
import tomllib
from pathlib import Path
from typing import List, Dict, Any

from fieldworkarena.log.fwa_logger import getLogger
logger = getLogger(__name__)


class TaskLoader:
    """Loads task IDs from TOML configuration files."""

    def __init__(
            self, 
            tasks_dir:str = "benchmark/tasks/group2",
            ids_path:str="benchmark/all_task_ids.toml"
        ):
        self.tasks_dir = tasks_dir
        self.ids_path = ids_path

    def load_task_ids(self, target: str) -> List[str]:
        """
        Load task IDs from a TOML file based on the target category.

        Args:
            task_ids_path: Path to the TOML file containing task IDs
            target: Target category key (e.g., "factory", "warehouse", "custom", "retail", "all")
                   If "all" is specified, returns all task IDs except from "custom" category

        Returns:
            List of task IDs for the specified target category
        """
        # Convert to Path object for better path handling
        toml_path = Path(self.ids_path)
        
        # Check if file exists
        if not toml_path.exists():
            logger.error(f"Task IDs file not found: {self.ids_path}")
            raise FileNotFoundError(f"Task IDs file not found: {self.ids_path}")
        
        # Load TOML file
        try:
            with open(toml_path, 'rb') as f:
                data = tomllib.load(f)
        except Exception as e:
            logger.error(f"Failed to parse TOML file {self.ids_path}: {e}")
            raise ValueError(f"Failed to parse TOML file {self.ids_path}: {e}")
        
        # Check if target exists or is 'all'
        if target == 'all':
            # Extract all task IDs except from 'custom' category
            all_task_ids = []
            for key, value in data.items():
                if key != 'custom' and isinstance(value, list):
                    all_task_ids.extend(value)
            task_ids = all_task_ids
        else:
            if target not in data:
                available_targets = list(data.keys())
                logger.error(f"Target '{target}' not found in {self.ids_path}. ")
                logger.error(f"Available targets: {available_targets}")
                raise KeyError(
                    f"Target '{target}' not found in {self.ids_path}. "
                    f"Available targets: {available_targets}"
                )
            
            # Get task IDs for the target
            task_ids = data[target]
        
        # Ensure it's a list
        if not isinstance(task_ids, list):
            logger.error(f"Expected task IDs for target '{target}' to be a list, ")
            logger.error(f"but got {type(task_ids).__name__}")
            raise ValueError(
                f"Expected task IDs for target '{target}' to be a list, "
                f"but got {type(task_ids).__name__}"
            )
        
        # check task_ids is not empty
        if not task_ids:
            logger.error(f"Task IDs list for target '{target}' is empty in {self.ids_path}")
            raise ValueError(
                f"Task IDs list for target '{target}' is empty in {self.ids_path}"
            )
        
        return task_ids

    def load_tasks_by_ids(
        self,
        target: str
    ) -> List[Dict[str, Any]]:
        """
        Load task information from JSON files based on task IDs from scenario.toml.

        This method:
        1. Loads scenario.toml to get task_ids_path and target
        2. Loads task IDs using load_task_ids()
        3. Searches through all JSON files in tasks_dir (group2)
        4. Returns matching task information

        Args:
            target: Target category key (e.g., "factory", "warehouse", "custom", "retail")

        Returns:
            List of task dictionaries matching the task IDs
        """
        # Convert to Path objects
        tasks_directory = Path(self.tasks_dir)

        # Check if tasks directory exists
        if not tasks_directory.exists():
            logger.error(f"Tasks directory not found: {self.tasks_dir}")
            raise FileNotFoundError(f"Tasks directory not found: {self.tasks_dir}")

        # Load task IDs using existing method
        task_ids = self.load_task_ids(target)

        # Extract just the numeric part of task IDs (e.g., "1.1.0001" from "fieldworkarena.1.1.0001")
        # This assumes the format is "prefix.X.X.XXXX"
        task_id_set = set()
        for task_id in task_ids:
            # Split by '.' and take the last 3 parts (e.g., "1.1.0001")
            parts = task_id.split('.')
            if len(parts) >= 3:
                numeric_id = '.'.join(parts[-3:])
                task_id_set.add(numeric_id)
            else:
                # If format is unexpected, use the full task_id
                task_id_set.add(task_id)

        # Load all JSON files from tasks directory
        matching_tasks = []
        json_files = sorted(tasks_directory.glob('*.json'))

        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    tasks_data = json.load(f)

                # Ensure tasks_data is a list
                if not isinstance(tasks_data, list):
                    continue

                # Check each task in the file
                for task in tasks_data:
                    if isinstance(task, dict) and 'id' in task:
                        # Check if task id matches any of our target task IDs
                        if task['id'] in task_id_set:
                            matching_tasks.append(task)

            except json.JSONDecodeError as e:
                # Skip files that can't be parsed as JSON
                logger.warning(f"Warning: Failed to parse JSON file {json_file}: {e}")
                continue
            except Exception as e:
                # Skip files with other errors
                logger.warning(f"Warning: Error processing file {json_file}: {e}")
                continue

        return matching_tasks

    def extract_tasks(self, target: str) -> List[Dict[str, Any]]:
        """
        Extract tasks from JSON files based on task IDs.

        Args:
            target: Target category key (e.g., "factory", "warehouse").

        Returns:
            List of task dictionaries matching the task IDs.
        """
        tasks = self.load_tasks_by_ids(target)

        # extract only necessary fields from each task
        extracted_tasks = []

        for task in tasks:
            extracted_task = {
                'id': task.get('id'),
                'input_data': task.get('input_data'),
                'query': None,
                'answer': None,
                'output_format': task.get('output_format'),
                'eval_func': task.get('eval_func')
            }

            # Extract query and answer from conversations
            conversations = task.get('conversations', [])
            for conversation in conversations:
                if conversation.get('from') == 'human':
                    extracted_task['query'] = conversation.get('value')
                elif conversation.get('from') == 'gpt':
                    extracted_task['answer'] = conversation.get('value')

            extracted_tasks.append(extracted_task)

        return extracted_tasks


def build_goal(task: Dict[str, Any]) -> str:
    """
    Build a task query string from task data.
    
    Args:
        task: Task dictionary containing query, input_data, and output_format
        
    Returns:
        Formatted task query string
    """
    query = task['query']
    input_data = task['input_data']
    output_format = task['output_format']

    goal = '# Question\n' + query + '\n\n'

    if type(input_data) == str:
        # V2 task is stored as a single string with space-separated file names
        file_names = input_data.split()
        goal = goal + "# Input Data\n"
        for file_name in file_names:
            goal = goal + f"{file_name.strip()}\n"
    if type(input_data) == list:
        # V1 task is stored as a list of data paths
        goal = goal + "# Input Data\n"
        for data_path in input_data:
            goal = goal + f"{data_path}\n"
    
    goal = goal + f"\n# Output Format\n{output_format}\n"
    
    return goal
