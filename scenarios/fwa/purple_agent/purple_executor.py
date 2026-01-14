from collections.abc import AsyncGenerator
import base64
import io
import tempfile
import os
import cv2
import numpy as np
from PIL import Image
from pypdf import PdfReader

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import (
    FileWithBytes,
    FileWithUri,
    Part,
    InvalidParamsError,
    Task,
    TextPart,
    FilePart,
    UnsupportedOperationError,
)
from a2a.utils import (
    new_task,
)
from a2a.utils.errors import ServerError

from google.adk.agents import RunConfig
from google.adk.artifacts import InMemoryArtifactService
from google.adk.events import Event
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from pydantic import ConfigDict


from fieldworkarena.log.fwa_logger import getLogger
logger = getLogger(__name__)


class A2ARunConfig(RunConfig):
    """Custom override of ADK RunConfig to smuggle extra data through the event loop."""

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )
    current_task_updater: TaskUpdater

class PurpleExecutor(AgentExecutor):

    def __init__(self, agent):
        self.agent = agent
        self.runner = Runner(
            app_name=agent.name,
            agent=agent,
            artifact_service=InMemoryArtifactService(),
            session_service=InMemorySessionService(),
            memory_service=InMemoryMemoryService(),
        )

    def _run_agent(
        self,
        session_id,
        new_message: types.Content,
        task_updater: TaskUpdater,
    ) -> AsyncGenerator[Event]:
        return self.runner.run_async(
            session_id=session_id,
            user_id='self',
            new_message=new_message,
            run_config=A2ARunConfig(
                current_task_updater=task_updater,
            ),
        )
    
    async def _process_request(
        self,
        new_message: types.Content,
        session_id: str,
        task_updater: TaskUpdater,
    ):
        session = await self._upsert_session(
            session_id=session_id
        )

        # Run the runner and process events
        response_text = ""
        async for event in self._run_agent(
            session_id=session_id,
            new_message=new_message,
            task_updater=task_updater,
        ):
            if event.is_final_response() and event.content and event.content.parts:
                for part in event.content.parts:
                    if hasattr(part, "text") and part.text:
                        response_text += part.text + "\n"
                    elif hasattr(part, "function_call"):
                        pass

            await task_updater.add_artifact(
                [Part(root=TextPart(text=response_text))],
            )
            await task_updater.complete()

            break
            
    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        # Create or get existing task
        if context.current_task:
            task = context.current_task
        elif context.message:
            task = new_task(context.message)
        else:
            raise ServerError(error=InvalidParamsError(message="No message provided"))
        
        if not context.message:
            raise ServerError(error=InvalidParamsError(message="No message provided"))
        
        updater = TaskUpdater(event_queue, task.id, task.context_id)
        if context.call_context:
            user_id = context.call_context.user.user_name
        else:
            user_id = "fwa_user"
        
        await updater.start_work()
        logger.info("====================================================")
        logger.info(f"[Agent] Processing task {task.id} for user {user_id}")
        logger.info("====================================================")
        await self._process_request(
            types.UserContent(
                parts=convert_a2a_parts_to_agent_input(context.message.parts)
            ),
            task.context_id,
            updater,
        )

    async def _upsert_session(self, session_id: str):
        """Get or create a session"""
        return await self.runner.session_service.get_session(
            app_name=self.runner.app_name, user_id='self', session_id=session_id
        ) or await self.runner.session_service.create_session(
            app_name=self.runner.app_name, user_id='self', session_id=session_id
        )

    async def cancel(
        self, request: RequestContext, event_queue: EventQueue
    ) -> Task | None:
        raise ServerError(error=UnsupportedOperationError())

def convert_a2a_parts_to_agent_input(parts: list[Part]) -> list[types.Part]:
    """Convert a list of A2A Part types into a list of Agent Input"""
    result = []
    for part in parts:
        converted = convert_a2a_part_to_agent_input(part)
        # convert_a2a_part_to_agent_input may return a list for video files
        if isinstance(converted, list):
            result.extend(converted)
        else:
            result.append(converted)
    return result
    
def convert_a2a_part_to_agent_input(part: Part) -> types.Part | list[types.Part]:
    """Convert a single A2A Part type into an Agent Input
    Args:
        part (Part): The A2A Part to convert, which can be TextPart and FilePart in FWA benchmark.
    
    Returns:
        types.Part | list[types.Part]: For images/PDFs, returns single types.Part.
                                       For videos, returns list of types.Part (text + frames).
                                       For text, returns types.Part with text.
    """
    unwrapped_part = part.root
    if isinstance(unwrapped_part, TextPart):
        logger.info(f"🎯Task Goal:\n{unwrapped_part.text}")
        return types.Part(text=unwrapped_part.text)
    if isinstance(unwrapped_part, FilePart):
        if isinstance(unwrapped_part.file, FileWithUri):
            # FWA don't use FileWithUri, but just in case
            raise ValueError(f"Unsupported file type: {type(unwrapped_part.file)}")
        if isinstance(unwrapped_part.file, FileWithBytes):
            file_data = unwrapped_part.file.bytes
            mime_type = unwrapped_part.file.mime_type
            file_name = unwrapped_part.file.name
            logger.info(f"📃Input Data:\n{file_name}, size: {len(file_data)} bytes, mime_type: {mime_type}")
            
            # Handle video files - extract frames
            if mime_type and mime_type.startswith('video/') or (file_name and file_name.endswith('.mp4')):
                try:
                    logger.info(f"Processing video file: {file_name}")
                    frames_parts = process_video_to_parts(file_data, str(file_name))
                    logger.info(f"Extracted {len(frames_parts)} parts from video (including text descriptions)")
                    return frames_parts
                except Exception as e:
                    logger.error(f"Error processing video: {e}")
                    raise ValueError(f"Error processing video {file_name}: {e}")
            
            # Handle image files - decode and re-encode to ensure correct format
            if mime_type and mime_type.startswith('image/'):
                try:
                    # If file_data is bytes, use directly; if string, assume it's base64
                    if isinstance(file_data, str):
                        # Assume base64 encoded
                        if file_data.startswith('data:'):
                            file_data = file_data.split(',', 1)[1]
                        file_data = file_data.replace(' ', '').replace('\n', '').replace('\r', '')
                        decoded_bytes = base64.b64decode(file_data)
                    elif isinstance(file_data, bytes):
                        decoded_bytes = file_data
                    else:
                        raise ValueError(f"Unsupported file data type: {type(file_data)}")
                    
                    # Open, validate and re-encode as JPEG
                    image = Image.open(io.BytesIO(decoded_bytes))
                    logger.info(f"Successfully opened image: mode={image.mode}, size={image.size}")
                    
                    # Convert to RGB if needed
                    if image.mode in ("RGBA", "LA", "P"):
                        image = image.convert("RGB")
                        logger.info(f"Converted image mode to RGB")
                    
                    # Re-encode as JPEG
                    with io.BytesIO() as buffer:
                        image.save(buffer, format="JPEG")
                        jpeg_bytes = buffer.getvalue()
                    
                    logger.info(f"Re-encoded image as JPEG, size: {len(jpeg_bytes)} bytes")
                    
                    # Return with inline_data using the validated JPEG bytes
                    return types.Part(
                        inline_data=types.Blob(
                            display_name=file_name,
                            data=jpeg_bytes,
                            mime_type='image/jpeg',
                        )
                    )
                except Exception as e:
                    logger.error(f"Error processing image: {e}")
                    raise ValueError(f"Error processing image {file_name}: {e}")
            
            # Handle PDF files - extract text
            if mime_type and mime_type == 'application/pdf' or (file_name and file_name.endswith('.pdf')):
                try:
                    logger.info(f"Processing PDF file: {file_name}")
                    text_content = extract_pdf_text(file_data, str(file_name))
                    logger.info(f"Extracted {len(text_content)} characters from PDF")
                    
                    # Return as text part
                    return types.Part(text=f"Content of {file_name}:\n\n{text_content}")
                except Exception as e:
                    logger.error(f"Error processing PDF: {e}")
                    raise ValueError(f"Error processing PDF {file_name}: {e}")
            
            # Handle text files
            if mime_type and mime_type.startswith('text/') or (file_name and file_name.endswith('.txt')):
                try:
                    if isinstance(file_data, bytes):
                        text_content = file_data.decode('utf-8')
                    elif isinstance(file_data, str):
                        # Assume base64 encoded
                        if file_data.startswith('data:'):
                            file_data = file_data.split(',', 1)[1]
                        decoded_bytes = base64.b64decode(file_data)
                        text_content = decoded_bytes.decode('utf-8')
                    else:
                        raise ValueError(f"Unsupported file data type: {type(file_data)}")
                    
                    logger.info(f"Extracted {len(text_content)} characters from text file")
                    return types.Part(text=f"Content of {file_name}:\n\n{text_content}")
                except Exception as e:
                    logger.error(f"Error processing text file: {e}")
                    raise ValueError(f"Error processing text file {file_name}: {e}")
            
            # For other file types - return as inline_data
            if isinstance(file_data, str):
                file_data = file_data.encode('utf-8')
            
            return types.Part(
                inline_data=types.Blob(
                    display_name=file_name,
                    data=file_data,
                    mime_type=mime_type,
                )
            )
        raise ValueError(f"Unsupported file type: {type(unwrapped_part.file)}")
    raise ValueError(f"Unsupported part type: {type(unwrapped_part)}")

def process_video_to_parts(video_data: bytes | str, file_name: str, seconds_per_frame: int = 1) -> list[types.Part]:
    """Process video file and extract frames as Parts.
    Args:
        video_data: Video file bytes or base64 string
        file_name: Name of the video file
        seconds_per_frame: Interval in seconds between extracted frames
    
    Returns:
        list[types.Part]: List containing text part with instructions and image parts for frames
    """
    # Decode video if base64
    if isinstance(video_data, str):
        if video_data.startswith('data:'):
            video_data = video_data.split(',', 1)[1]
        video_data = base64.b64decode(video_data)
    
    # Save to temporary file
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
        temp_file.write(video_data)
        temp_video_path = temp_file.name
    
    try:
        # Extract frames
        frames, actual_seconds_per_frame = extract_video_frames(temp_video_path, seconds_per_frame)
        
        if not frames:
            raise ValueError("No frames extracted from video")
        
        # Create parts list
        parts = []
        
        # Add introductory text explaining the frames
        intro_text = (
            f"Video file: {file_name}\n"
            f"This video has been processed into {len(frames)} frames.\n"
            f"Each frame is sampled at approximately {actual_seconds_per_frame:.2f} second intervals.\n"
            f"The frames are provided below with their timestamps:\n"
            "You cannot see the video directly, so you MUST use these frames to analyze the video content."
        )
        parts.append(types.Part(text=intro_text))
        
        # Add each frame with timestamp
        for i, frame_data in enumerate(frames):
            timestamp = seconds_to_hhmmss(i * actual_seconds_per_frame)
            parts.append(types.Part(text=f"Frame at timestamp: {timestamp}"))
            parts.append(types.Part(
                inline_data=types.Blob(
                    display_name=f"{file_name}_frame_{i}",
                    data=frame_data,
                    mime_type='image/jpeg',
                )
            ))
        
        return parts
    finally:
        # Clean up temporary file
        try:
            os.unlink(temp_video_path)
        except:
            pass

def extract_video_frames(video_path: str, seconds_per_frame: int = 1, max_frames: int = 30) -> tuple[list[bytes], float]:
    """Extract frames from video file.
    Args:
        video_path: Path to video file
        seconds_per_frame: Desired interval between frames
        max_frames: Maximum number of frames to extract
    
    Returns:
        tuple: (list of JPEG frame bytes, actual seconds per frame)
    """
    frames = []
    
    video = cv2.VideoCapture(video_path)
    total_frames = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = video.get(cv2.CAP_PROP_FPS)
    
    frames_to_skip = int(fps * seconds_per_frame)
    curr_frame = 0
    
    # Adjust frames_to_skip if needed to not exceed max_frames
    if frames_to_skip < total_frames / (max_frames - 1):
        frames_to_skip = int(total_frames / (max_frames - 1))
    
    while curr_frame < total_frames and len(frames) < max_frames:
        video.set(cv2.CAP_PROP_POS_FRAMES, curr_frame)
        success, frame = video.read()
        if not success:
            break
        
        # Convert frame to JPEG bytes
        frame_bytes = frame_to_jpeg_bytes(frame)
        frames.append(frame_bytes)
        curr_frame += frames_to_skip
    
    actual_seconds_per_frame = frames_to_skip / fps if fps > 0 else seconds_per_frame
    video.release()
    
    return frames, actual_seconds_per_frame

def extract_pdf_text(pdf_data: bytes | str, file_name: str) -> str:
    """Extract text from PDF file.
    Args:
        pdf_data: PDF file bytes or base64 string
        file_name: Name of the PDF file
    
    Returns:
        str: Extracted text content
    """
    # Decode if base64
    if isinstance(pdf_data, str):
        if pdf_data.startswith('data:'):
            pdf_data = pdf_data.split(',', 1)[1]
        pdf_data = base64.b64decode(pdf_data)
    
    # Extract text using pypdf
    pdf_file = io.BytesIO(pdf_data)
    reader = PdfReader(pdf_file)
    
    text = ""
    for page_num, page in enumerate(reader.pages, 1):
        page_text = page.extract_text()
        if page_text:
            text += f"--- Page {page_num} ---\n{page_text}\n\n"
    
    return text.strip()

def frame_to_jpeg_bytes(frame: np.ndarray) -> bytes:
    """Convert video frame (numpy array) to JPEG bytes.
    Args:
        frame: Video frame as numpy array (BGR format from OpenCV)
    
    Returns:
        bytes: JPEG encoded image bytes
    """
    # Convert BGR to RGB
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    image = Image.fromarray(frame_rgb)
    
    # Convert to RGB if needed
    if image.mode in ("RGBA", "LA"):
        image = image.convert("RGB")
    
    # Encode as JPEG
    with io.BytesIO() as buffer:
        image.save(buffer, format="JPEG")
        return buffer.getvalue()

def seconds_to_hhmmss(seconds: float) -> str:
    """Convert seconds to HH:MM:SS format.
    Args:
        seconds: Time in seconds
    
    Returns:
        str: Formatted time string
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02}:{minutes:02}:{secs:02}"
