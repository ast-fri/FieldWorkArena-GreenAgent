## ⚠️ Important Notice

**Task Availability Limitation**: Due to A2A FileWithBytes constraints for hosting large benchmark data, the AgentBeats environment has limited task availability. Additional tasks will be enabled as A2A updates are released. See [Task Configuration](#task-configuration) for details on available task counts per category.

**For Full Task Set**: If you want to try the complete version with all tasks, please visit [FieldWorkArena](https://github.com/FujitsuResearch/FieldWorkArena/).
# FieldWorkArena

> This repository is for GreenAgent submission to the AgentX - AgentBeats Competition. See below for more details.
> - Competition(https://rdi.berkeley.edu/agentx-agentbeats)
> - AgentBeats developer platform(https://agentbeats.dev/)

## Overview

The introduction of AI agents is being considered to address the challenges faced by many workplaces, such as the aging of the population, lack of human resources, and delays in decision-making. In order to improve the functionality of AI agents, we have developed and provided a benchmark suite to evaluate AI agents by extending the evaluation method of web operations to field operations.

FieldWorkArena is a groundbreaking benchmark suite for evaluating AI agents. By using data and tasks from Fujitsu's actual factories and warehouses, we quantitatively evaluate how effectively AI agents work in the field. This clarifies the challenges of AI adoption and ensures evidence when applied in the field.

See below for more details. \
https://en-documents.research.global.fujitsu.com/fieldworkarena/

## Project Structure
```
src/
└─ fieldworkarena/
   ├─ run_scenario.py         # run agents and start assessment
   ├─ agent/
      ├─ client.py            # CLI client to start assessment
      ├─ metrics/             # Utils for metrics of FWA
      └─ fwa_green_agent.py   # A2A GreenAgent server
   └─ core/
      ├─ green_executor.py    # base A2A green agent executor
      ├─ models.py            # pydantic models for green agent IO
      ├─ purple_client.py     # A2A client tool to communicate with PurpleAgent
      └─ client_utils.py      # A2A messaging helpers
   
scenarios/
└─ fwa/                        # implementation of the FWA
   ├─ purple_agent/            # put your Agent to solve FWA task
   ├─ all_task_ids.toml        # config of which task should be input in the scenario
   └─ scenario.toml            # config for evaluation in the FWA environment

benchmark/
├─ tasks/                      # Task detailed file
└─ all_task_ids.toml           # Task Definition file 
```

## Prerequisites

### Request Access to Hugging Face Dataset

This project requires access to the FieldWorkArena dataset hosted on Hugging Face. To request access:

1. Go to https://en-documents.research.global.fujitsu.com/fieldworkarena/ .
2. Click link on `Evaluation dataset` and apply from Forms page,
3. Confirm the download URL in email sent from FieldWorkArena. (It may take a few business days.)
   - If you do not receive a response within one week, please reapply using the Form from step 2.
4. Wait for approval from the dataset maintainers
5. Once approved, generate an access token:
   - Go to your Hugging Face Settings → Access Tokens
   - Create a new token with `read` permissions
   - Copy the token and set it in your `.env` file as `HF_TOKEN`

**Note:** You must have an approved access token before running the benchmark tasks. Please note that access permission handling procedures may be subject to change. 

## Getting Started
1. Clone (or fork) the repo:
```
git clone https://github.com/ast-fri/FieldWorkArena-GreenAgent.git
cd FieldWorkArena-GreenAgent
```

2. Set environment variables
```
cp sample.env .env
```

3. Edit your scenario scenarios/fwa/scenario.toml [How to edit](#scenariotoml)

4. Edit task Configuration if needed benchmark/all_task_ids.toml [How to edit](#all_task_idstoml)

## Quick Start (Running Locally)
```
uv sync
uv run fwa-run scenarios/fwa/scenario.toml
```
This command will:
- Start the agent servers, which include GreenAgent and PurpleAgent, using the commands specified in scenario.toml
- Construct an `assessment_request` message containing the participant's role-endpoint mapping and the assessment config
- Send the `assessment_request` to the green agent and print streamed responses

**Note:** Use `--show-logs` to see agent outputs during the assessment, and `--serve-only` to start agents without running the assessment.

To run this example manually, start the agent servers in separate terminals, and then in another terminal run the A2A client on the scenario.toml file to initiate the assessment.

## Running with Docker

### Running Complete Assessment (Recommended)

Build both Green Agent and Test Purple Agent images, then run the complete scenario:

```bash
bash docker_build.sh
bash docker_run_scenario.sh
```

This will:
- Start both Green Agent and Test Purple Agent containers with environment variables from `.env` file
- Wait for agents to initialize (40 seconds)
- Execute the assessment scenario
- Display logs and clean up containers

### Running Green Agent Server Only

To run only the Green Agent server for development or testing:

```bash
docker build -t fwa_green_agent .
docker run -p 9009:9009 --env-file .env fwa_green_agent
```

**Note:** This only starts the GreenAgent server and does not execute the assessment using test_agent.

## Scenario Configuration

### all_task_ids.toml

The `all_task_ids.toml` file defines which tasks should be executed in your scenario. It contains four categories:

- **`factory`**: Factory tasks (predefined, do not modify)
- **`warehouse`**: Warehouse tasks (predefined, do not modify)
- **`retail`**: Retail tasks (predefined, do not modify)
- **`custom`**: Custom task selection (modify this to pick specific tasks)

**⚠️ Important Note on Task Availability:**
Due to the use of A2A FileWithBytes for hosting benchmark data from GreenAgent, the AgentBeats environment currently has limitations on handling large-capacity benchmark data. The available task counts are:
- **factory**: 79 tasks available (out of 176 total tasks)
- **warehouse**: 162 tasks available (out of 264 total tasks)
- **retail**: 5 tasks available (out of 446 total tasks)

Additional tasks will be enabled as A2A updates are released. For the complete version with all tasks, please visit [FieldWorkArena](https://github.com/FujitsuResearch/FieldWorkArena/).

#### How to Use

1. **Run all predefined tasks**: In `scenario.toml`, set `target = "all"` to execute all tasks from `factory`, `warehouse`, and `retail` categories (excludes `custom`).

2. **Run specific category**: Set `target = "factory"`, `target = "warehouse"`, or `target = "retail"` to run tasks from a single category.

3. **Run custom task selection**: 
   - Set `target = "custom"` in `scenario.toml`
   - Copy task IDs from `factory`, `warehouse`, or `retail` categories and paste them into the `custom` array
   - For development use only
   
   Example:
   ```toml
   custom = [
     "fieldworkarena.1.1.0001",
     "fieldworkarena.2.1.0005",
     "fieldworkarena.3.1.0010"
   ]
   ```

**Note**: Do not modify the `factory`, `warehouse`, or `retail` categories. Use `custom` for custom task selections only.

### scenario.toml

The `scenario.toml` file configures the evaluation environment, including agent endpoints and assessment settings.

#### Structure

```toml
[green_agent]
endpoint = "http://127.0.0.1:9009"
cmd = "fwa-server --host 127.0.0.1 --port 9009"

[[participants]]
role = "agent"
endpoint = "http://127.0.0.1:9019"
cmd = "python scenarios/fwa/purple_agent/test_agent.py  --host 127.0.0.1 --port 9019"


[config]
target = "factory"
```

#### Configuration Sections

**`[green_agent]`**: Green Agent (orchestrator) configuration
- `endpoint`: URL where the Green Agent server will be accessible
- `cmd`: Command to start the Green Agent server

**`[[participants]]`**: Purple Agent (task executor) configuration
- `role`: Role identifier for the agent (must be "agent")
- `endpoint`: URL where the Purple Agent server will be accessible
- `cmd`: Command to start the Purple Agent server
- You can define multiple participants by adding more `[[participants]]` sections

**`[config]`**: Assessment configuration
- `target`: Target category to run (`"factory"`, `"warehouse"`, `"retail"`, `"custom"`, or `"all"`)

## Testing

This project uses `pytest` for testing. For detailed information about running tests, environment variable configuration, and security best practices, please see [tests/README.md](tests/README.md).

