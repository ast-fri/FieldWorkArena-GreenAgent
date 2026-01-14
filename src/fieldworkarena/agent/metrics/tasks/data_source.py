# data_source.py

import base64
import io
import mimetypes
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Union

from a2a.types import FileWithBytes
from huggingface_hub import HfApi, hf_hub_download
from huggingface_hub.utils import HfHubHTTPError
from PIL import Image

from fieldworkarena.log.fwa_logger import getLogger
logger = getLogger(__name__)


class DataSource(ABC):
    """
    Abstract class for benchmark data sources.
    """

    @abstractmethod
    def validate_access(self) -> bool:
        """
        Validate the benchmark data access.
        """
        raise NotImplementedError

    @abstractmethod
    def _load_base64(self, path: str) -> str:
        """
        Retrieve data from the specified path and return it as a Base64-encoded string.
        """
        raise NotImplementedError
    
    @abstractmethod
    def load_file_payload(self, file_name: str) -> dict:
        """
        Retrieve the data from the specified path and return it as a file payload dictionary for A2A FilePart.
        """
        raise NotImplementedError


class BenchmarkDataSource(DataSource):
    """
    Implementation of DataSource using Hugging Face Dataset Hub.
    """

    def __init__(
        self,
        access_token: str,
        repo_id: str = "Fujitsu/FieldWorkArena_Dataset",
        repo_type: str = "dataset",
        cache_dir: str | None = None,
        force_download: bool = False,
    ):
        self.repo_id = repo_id
        self.access_token = access_token.strip() if access_token else ""
        self.repo_type = repo_type
        self.cache_dir = cache_dir
        self.force_download = force_download

    def validate_access(self) -> None:
        """
        Validate the benchmark data access in Hugging Face by checking access token.
        """
        api = HfApi(token=self.access_token)
        try:
            logger.info(f"Validating access to repository: {self.repo_id}")
            api.repo_info(
                repo_id=self.repo_id,
                repo_type=self.repo_type,
            )
            logger.info("Access validation successful")
        except HfHubHTTPError as e:
            status_code = e.response.status_code if e.response else "N/A"
            error_msg = f"Access validation failed: Invalid access token or insufficient permissions. Status code: {status_code}"
            logger.error(error_msg)
            raise ValueError(error_msg) from e

    def _load_base64(self, file_path: Path) -> str:
        """
        Retrieve the data from the specified path and return it as a Base64-encoded string.
        For image files, converts to JPEG format and handles transparency channels.

        Args:
            file_path (Path): Path to the data file.
        Returns:
            str: Base64-encoded string of the file content.
        """
        if file_path.suffix.lower() in ['.jpg']:
            image = Image.open(file_path)
            if image.mode in ("RGBA", "LA"):
                image = image.convert("RGB")
            
            with io.BytesIO() as buffer:
                image.save(buffer, format="JPEG")
                encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
        else:
            with file_path.open("rb") as f:
                encoded = base64.b64encode(f.read()).decode("utf-8")

        return encoded

    def _download(self, file_name: str) -> Path:
        """
        Retrieve remote data locally (considering cache).
        If force_download is True, always download from remote even if cache exists.
        """
        try:
            logger.info(f"Downloading file: {file_name} (force_download={self.force_download})")
            
            local_path = hf_hub_download(
                repo_id=self.repo_id,
                filename=file_name,
                repo_type=self.repo_type,
                token=self.access_token,
                cache_dir=self.cache_dir,
                force_download=self.force_download,
                local_files_only=False,
            )
            logger.info(f"Successfully downloaded/retrieved: {file_name}")
            return Path(local_path)
        except HfHubHTTPError as e:
            status_code = e.response.status_code if e.response else "N/A"
            logger.error(f"HTTP error downloading '{file_name}': status_code={status_code}, error={e}")

            if status_code in (401, 403):
                error_msg = f"Invalid access token or insufficient permissions for file '{file_name}'. Status code: {status_code}"
                logger.error(error_msg)
                raise ValueError(error_msg) from e
            elif status_code == 404:
                error_msg = f"File '{file_name}' not found in the repository '{self.repo_id}'."
                logger.error(error_msg)
                raise FileNotFoundError(error_msg) from e
            else:
                error_msg = f"Failed to download file '{file_name}': HTTP {status_code} - {e}"
                logger.error(error_msg)
                raise RuntimeError(error_msg) from e
        except Exception as e:
            error_msg = f"An unexpected error occurred while downloading file '{file_name}': {type(e).__name__} - {e}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    def _get_media_type(self, file_path: Path) -> str:
        """
        Get the media type based on the file extension.
        
        Args:
            file_path (Path): Path to the data file.
        """
        media_type, _ = mimetypes.guess_type(file_path.name)
        if media_type is None:
            raise ValueError(f"Unsupported file type: {file_path.suffix}")
        return media_type
    
    def _load_single_file(self, file_name: str) -> FileWithBytes:
        """
        Load a single file and return as FileWithBytes.
        
        Args:
            file_name: Name of the data file in the repository.
            
        Returns:
            FileWithBytes: File payload with mediaType, name, and Base64-encoded data.
        """
        # Determine subdirectory based on file extension
        file_path_obj = Path(file_name)
        extension = file_path_obj.suffix.lower()
        
        if extension in ['.pdf', '.txt']:
            subdirectory = 'document'
        elif extension == '.mp4':
            subdirectory = 'movie'
        elif extension in ['.jpg']:
            subdirectory = 'image'
        else:
            error_msg = f"Unsupported file extension: {extension} for file '{file_name}'"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Construct repository path: data/{subdirectory}/{file_name}
        repo_path = f"data/{subdirectory}/{file_name}"
        
        try:
            logger.info(f"Loading file: {file_name} from path: {repo_path}")
            local_path = self._download(repo_path)
            base64_data = self._load_base64(local_path)
            media_type = self._get_media_type(local_path)

            logger.info(f"Successfully loaded file: {file_name}")
            return FileWithBytes(
                bytes=base64_data,
                mime_type=media_type,
                name=local_path.name,
            )
        except (ValueError, FileNotFoundError, RuntimeError) as e:
            logger.error(f"Error loading file '{file_name}': {e}")
            raise
        except Exception as e:
            error_msg = f"Unexpected error loading file '{file_name}': {type(e).__name__} - {e}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e 

    def load_file_payload(self, input_data: Union[str, list[str]]) -> list[FileWithBytes]:
        """
        Retrieve file payloads from input data. Supports both V1 (list) and V2 (space-separated string) formats.

        Allowed file extensions: .txt, .pdf, .jpg, .mp4

        Args:
            input_data: Either a list of filenames (V1 format) or space-separated string (V2 format).

        Returns:
            list[FileWithBytes]: List of file payloads with mediaType, name, and Base64-encoded data.
        """
        # Normalize input to list of filenames
        if isinstance(input_data, list):
            file_names = input_data
        else:
            file_names = input_data.split()
        
        logger.info(f"Loading {len(file_names)} file(s): {file_names}")
        
        # Load all files
        try:
            files = [self._load_single_file(fname) for fname in file_names]
            logger.info(f"Successfully loaded all {len(files)} file(s)")
            return files
        except (ValueError, FileNotFoundError, RuntimeError) as e:
            logger.error(f"Error loading file payloads: {e}")
            raise
        except Exception as e:
            error_msg = f"Unexpected error loading file payloads: {type(e).__name__} - {e}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e    