# Purple Agent Implementation Guide

## Overview

This directory contains an example implementation of a Purple Agent for FieldWorkArena. The Purple Agent is responsible for processing tasks and interacting with the GreenAgent through the [Agent2Agent (A2A) Protocol](https://a2a-protocol.org/latest/).

## Architecture

FieldWorkArena is designed to send multimodal inputs through the A2A protocol, including:
- Video files (`.mp4`)
- Image files (`.jpg`, `.png`)
- PDF documents (`.pdf`)
- Text files (`.txt`)

## Required Functionality

### Input Conversion

Your Purple Agent implementation **must** include functionality to convert A2A `FileWithByte` objects into inputs that your agent can process. 

The framework provides a reference implementation in `convert_a2a_part_to_agent_input`, which demonstrates how to:
- Extract files from A2A message parts
- Handle different file formats
- Convert binary data into agent-compatible inputs

### Key Components

1. **Multimodal Input Processing**: Your agent must be capable of handling various input formats sent via the A2A protocol
2. **File Conversion Logic**: Implement conversion functions similar to `convert_a2a_part_to_agent_input` to transform A2A file objects into your agent's expected input format
3. **A2A Protocol Compliance**: Ensure proper communication with the GreenAgent following the A2A specification

## Implementation Tips

- Study the `convert_a2a_part_to_agent_input` function to understand the expected file handling pattern
- Consider implementing specialized handlers for different file types (video, image, document, text)
- For video files, you may need to implement frame extraction utilities
- For image files, ensure proper format conversion and preprocessing

## Getting Started

1. Review the example implementation in `test_agent.py`
2. Implement your own agent logic while maintaining A2A compatibility
3. Test with the provided benchmark tasks to ensure proper functionality