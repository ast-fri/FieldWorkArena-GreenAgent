import os
import pytest
from pathlib import Path
from fieldworkarena.agent.metrics.tasks.task_loader import TaskLoader, build_goal

# Get the fixtures directory path
FIXTURES_DIR = Path(__file__).parent.parent.parent.parent / "fixtures"
FIX_FWA_DIR = FIXTURES_DIR / "scenarios" / "fwa"
BENCHMARK_DIR = FIX_FWA_DIR / "benchmark"
TASK_IDS_PATH = str(BENCHMARK_DIR / "all_task_ids.toml")
TASKS_DIR = str(BENCHMARK_DIR / "tasks" / "group2")

def test_load_task_ids_factory():
    """Test loading factory task IDs"""
    loader = TaskLoader(tasks_dir=TASKS_DIR, ids_path=TASK_IDS_PATH)
    ids = loader.load_task_ids('factory')
    assert len(ids) == 3
    assert 'fieldworkarena.1.1.0001' in ids
    assert 'fieldworkarena.1.1.0023' in ids
    assert 'fieldworkarena.1.1.0031' in ids


def test_load_task_ids_warehouse():
    """Test loading warehouse task IDs"""
    loader = TaskLoader(tasks_dir=TASKS_DIR, ids_path=TASK_IDS_PATH)
    ids = loader.load_task_ids('warehouse')
    assert len(ids) == 3
    assert 'fieldworkarena.1.1.0033' in ids
    assert 'fieldworkarena.2.1.0001' in ids
    assert 'fieldworkarena.2.1.0002' in ids


def test_load_task_ids_retail():
    """Test loading retail task IDs"""
    loader = TaskLoader(tasks_dir=TASKS_DIR, ids_path=TASK_IDS_PATH)
    ids = loader.load_task_ids('retail')
    assert len(ids) == 2
    assert 'fieldworkarena.1.1.2001' in ids
    assert 'fieldworkarena.2.1.2108' in ids


def test_load_task_ids_all():
    """Test loading all task IDs (excluding custom)"""
    loader = TaskLoader(tasks_dir=TASKS_DIR, ids_path=TASK_IDS_PATH)
    ids = loader.load_task_ids('all')
    assert len(ids) == 8  # 3 factory + 3 warehouse + 2 retail
    
    # Check factory tasks are included
    assert 'fieldworkarena.1.1.0001' in ids
    assert 'fieldworkarena.1.1.0023' in ids
    assert 'fieldworkarena.1.1.0031' in ids
    
    # Check warehouse tasks are included
    assert 'fieldworkarena.1.1.0033' in ids
    assert 'fieldworkarena.2.1.0001' in ids
    assert 'fieldworkarena.2.1.0002' in ids
    
    # Check retail tasks are included
    assert 'fieldworkarena.1.1.2001' in ids
    assert 'fieldworkarena.2.1.2108' in ids


def test_load_task_ids_nonexistent():
    """Test loading non-existent target raises KeyError"""
    loader = TaskLoader(tasks_dir=TASKS_DIR, ids_path=TASK_IDS_PATH)
    with pytest.raises(KeyError):
        loader.load_task_ids('not_exist')


def test_extract_tasks_factory():
    """Test extracting factory tasks"""
    loader = TaskLoader(tasks_dir=TASKS_DIR, ids_path=TASK_IDS_PATH)
    result = loader.extract_tasks('factory')
    assert len(result) == 3
    
    # Check first task
    task = result[0]
    assert task['id'] == '1.1.0001'
    assert task['input_data'] == ['West5_G210_HANKUMI.mp4']
    assert task['query'] == 'In this video, please indicate the start and end times of the equipment assembly work cycle. This cycle is from when the worker starts working at the work desk to when the worker completes the work and leaves the work desk.'
    assert task['answer'] == 'The detected equipment assembly work cycle start and end times are from 00: 00:03:53 to 00:09:00.'
    assert task['output_format'] == 'text'
    assert task['eval_func'] == 'numerical_match'


def test_extract_tasks_warehouse():
    """Test extracting warehouse tasks"""
    loader = TaskLoader(tasks_dir=TASKS_DIR, ids_path=TASK_IDS_PATH)
    result = loader.extract_tasks('warehouse')
    assert len(result) == 3
    
    # Check first task
    task = result[0]
    assert task['id'] == '1.1.0033'
    assert task['input_data'] == ['Table_2_in_English.pdf']
    assert task['query'] == 'In this PDF file, please extract and complete the precaution for "Man-powered Transportation Work."'
    assert task['answer'] == 'The following are cautionary notes for manual transportation work.  ①Do not repeatedly hold or move, or repeat the intermediate step. ②To reduce or reduce movement from bottom to top and from top to bottom. ③Do not handle the product below 0cm above the floor or above the chest. ④Do not work while moving backwards. ⑤Don\'t swing long things around. ⑥When handling hazardous and hazardous materials, we shall strictly observe the precautions concerning these matters. ⑦Consider the weight of the baggage and handle the baggage that is too much for your own power more than others. ⑧Hands should be held for as little time as possible. ⑨Orient correctly (facing straight), lightly bend knees, lower back, straight back and hold firmly.'
    assert task['eval_func'] == 'fuzzy_match'


def test_extract_tasks_retail():
    """Test extracting retail tasks"""
    loader = TaskLoader(tasks_dir=TASKS_DIR, ids_path=TASK_IDS_PATH)
    result = loader.extract_tasks('retail')
    assert len(result) == 2
    
    task = result[0]
    assert task['id'] == '1.1.2001'
    assert task['input_data'] == 'Cam001-Coffee1.mp4  Coffee_Maker_Cleaning_Manual.txt'
    assert task['query'] == 'In this video, what is the start time and what is the end time of CoffeeMaker Cleaning. The start and end times must be output from the time of the movie itself. The procudeure is in "Coffee_Maker_Cleaning_Manual.txt". If the specified work is not found in the video, report as "No specified motion".'
    assert task['answer'] == 'The specified motion start and end times are from 00:00:10 to 00:02:36.'
    assert task['eval_func'] == 'numerical_match'


def test_extract_tasks_all():
    """Test extracting all tasks (excluding custom)"""
    loader = TaskLoader(tasks_dir=TASKS_DIR, ids_path=TASK_IDS_PATH)
    result = loader.extract_tasks('all')
    assert len(result) == 8  # 3 factory + 3 warehouse + 2 retail
    
    # Check all task IDs are present
    task_ids = [task['id'] for task in result]
    assert '1.1.0001' in task_ids
    assert '1.1.0023' in task_ids
    assert '1.1.0031' in task_ids
    assert '1.1.0033' in task_ids
    assert '2.1.0001' in task_ids
    assert '2.1.0002' in task_ids
    assert '1.1.2001' in task_ids
    assert '2.1.2108' in task_ids


def test_extract_tasks_with_multiple_input_data():
    """Test extracting tasks with multiple input_data"""
    loader = TaskLoader(tasks_dir=TASKS_DIR, ids_path=TASK_IDS_PATH)
    result = loader.extract_tasks('factory')
    
    # Find task with multiple input files
    task_with_multiple_inputs = [t for t in result if t['id'] == '1.1.0023'][0]
    assert len(task_with_multiple_inputs['input_data']) == 2
    assert 'West5_Checkmask_4_00h24m00s_00h34m34s.mp4' in task_with_multiple_inputs['input_data']
    assert '7_MaskCheck_RouterAssembly.txt' in task_with_multiple_inputs['input_data']


def test_build_goal_with_list_input_data():
    """Test building goal with list input_data (V1 format)"""
    task = {
        'query': 'What is the start time?',
        'input_data': ['test_video_1.mp4', 'data.txt'],
        'output_format': 'text'
    }
    
    result = build_goal(task)
    
    # Check the structure
    assert '# Question' in result
    assert 'What is the start time?' in result
    assert '# Input Data' in result
    assert 'test_video_1.mp4' in result
    assert 'data.txt' in result
    assert '# Output Format' in result
    assert 'text' in result


def test_build_goal_with_string_input_data():
    """Test building goal with string input_data (V2 format) - space-separated files"""
    task = {
        'query': 'How many items are there?',
        'input_data': 'warehouse_items.csv warehouse_log.txt',
        'output_format': 'number'
    }
    
    result = build_goal(task)
    
    # Check the structure
    assert '# Question' in result
    assert 'How many items are there?' in result
    assert '# Input Data' in result
    assert 'warehouse_items.csv' in result
    assert 'warehouse_log.txt' in result
    assert '# Output Format' in result
    assert 'number' in result


def test_build_goal_with_single_input():
    """Test building goal with single input_data in list"""
    task = {
        'query': 'What is the quality score?',
        'input_data': ['retail_video_1.mp4'],
        'output_format': 'text'
    }
    
    result = build_goal(task)
    
    assert '# Question' in result
    assert 'What is the quality score?' in result
    assert '# Input Data' in result
    assert 'retail_video_1.mp4' in result
    assert '# Output Format' in result
    assert 'text' in result


def test_build_goal_with_empty_input_data():
    """Test building goal with empty input_data list"""
    task = {
        'query': 'General question?',
        'input_data': [],
        'output_format': 'text'
    }
    
    result = build_goal(task)
    
    # Should still have the basic structure
    assert '# Question' in result
    assert 'General question?' in result
    assert '# Input Data' in result
    assert '# Output Format' in result
    assert 'text' in result


def test_build_goal_with_multiple_string_files():
    """Test building goal with multiple space-separated files in string format"""
    task = {
        'query': 'Analyze the coffee machine cleaning process',
        'input_data': 'Cam001-Coffee1.mp4  Coffee_Maker_Cleaning_Manual.txt',
        'output_format': 'text'
    }
    
    result = build_goal(task)
    
    assert '# Question' in result
    assert 'Analyze the coffee machine cleaning process' in result
    assert '# Input Data' in result
    assert 'Cam001-Coffee1.mp4' in result
    assert 'Coffee_Maker_Cleaning_Manual.txt' in result
    assert '# Output Format' in result
    assert 'text' in result
    # Both files should be on separate lines
    lines = result.split('\n')
    assert any('Cam001-Coffee1.mp4' in line for line in lines)
    assert any('Coffee_Maker_Cleaning_Manual.txt' in line for line in lines)

