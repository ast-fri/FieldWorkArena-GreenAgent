"""
Tests for data_source.py
"""

import base64
import io
import os
import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, mock_open
from PIL import Image

from a2a.types import FileWithBytes
from huggingface_hub.utils import HfHubHTTPError
from fieldworkarena.agent.metrics.tasks.data_source import BenchmarkDataSource


class TestBenchmarkDataSource:
    """Test cases for BenchmarkDataSource class"""
    
    @pytest.fixture
    def mock_access_token(self):
        """Fixture for mock access token (for unit tests)"""
        return "test_token_123"
    
    @pytest.fixture
    def real_access_token(self):
        """Fixture for real access token from environment variable (for integration tests)"""
        token = os.getenv("FWA_TEST_TOKEN")
        if not token:
            pytest.skip("FWA_TEST_TOKEN environment variable not set")
        return token
    
    @pytest.fixture
    def data_source(self, mock_access_token):
        """Fixture for BenchmarkDataSource instance with mock token"""
        return BenchmarkDataSource(
            access_token=mock_access_token,
            repo_id="test/repo",
            cache_dir="/tmp/test_cache"
        )
    
    @pytest.fixture
    def data_source_force_download(self, mock_access_token):
        """Fixture for BenchmarkDataSource with force_download=True"""
        return BenchmarkDataSource(
            access_token=mock_access_token,
            repo_id="test/repo",
            force_download=True
        )
    
    @pytest.fixture
    def real_data_source(self, real_access_token):
        """Fixture for BenchmarkDataSource with real token (for integration tests)"""
        return BenchmarkDataSource(
            access_token=real_access_token,
            repo_id="Fujitsu/FieldWorkArena_Dataset",
            repo_type="dataset"
        )
    
    def test_init(self, mock_access_token):
        """Test initialization of BenchmarkDataSource"""
        ds = BenchmarkDataSource(
            access_token=mock_access_token,
            repo_id="custom/repo",
            repo_type="dataset",
            cache_dir="/custom/cache",
            force_download=True
        )
        
        assert ds.access_token == mock_access_token
        assert ds.repo_id == "custom/repo"
        assert ds.repo_type == "dataset"
        assert ds.cache_dir == "/custom/cache"
        assert ds.force_download is True
    
    def test_init_defaults(self, mock_access_token):
        """Test initialization with default values"""
        ds = BenchmarkDataSource(access_token=mock_access_token)
        
        assert ds.repo_id == "Fujitsu/FieldWorkArena_Dataset"
        assert ds.repo_type == "dataset"
        assert ds.cache_dir is None
        assert ds.force_download is False
    
    @pytest.mark.integration
    def test_validate_access_success_integration(self, real_data_source):
        """Test successful access validation with real token (integration test)"""
        # Should not raise any exception
        real_data_source.validate_access()
    
    @patch('fieldworkarena.agent.metrics.tasks.data_source.HfApi')
    def test_validate_access_success(self, mock_hf_api, data_source):
        """Test successful access validation with mock (unit test)"""
        mock_api_instance = Mock()
        mock_hf_api.return_value = mock_api_instance
        
        # Should not raise any exception
        data_source.validate_access()
        
        mock_hf_api.assert_called_once_with(token=data_source.access_token)
        mock_api_instance.repo_info.assert_called_once_with(
            repo_id=data_source.repo_id,
            repo_type=data_source.repo_type
        )
    
    @patch('fieldworkarena.agent.metrics.tasks.data_source.HfApi')
    def test_validate_access_401_error(self, mock_hf_api, data_source):
        """Test access validation with 401 error"""
        mock_api_instance = Mock()
        mock_hf_api.return_value = mock_api_instance
        
        # Create mock HTTP error with 401 status
        mock_response = Mock()
        mock_response.status_code = 401
        mock_error = HfHubHTTPError(message="Unauthorized", response=mock_response)
        mock_api_instance.repo_info.side_effect = mock_error
        
        with pytest.raises(ValueError) as exc_info:
            data_source.validate_access()
        
        assert "Invalid access token" in str(exc_info.value)
        assert "401" in str(exc_info.value)
    
    @patch('fieldworkarena.agent.metrics.tasks.data_source.HfApi')
    def test_validate_access_403_error(self, mock_hf_api, data_source):
        """Test access validation with 403 error"""
        mock_api_instance = Mock()
        mock_hf_api.return_value = mock_api_instance
        
        # Create mock HTTP error with 403 status
        mock_response = Mock()
        mock_response.status_code = 403
        mock_error = HfHubHTTPError(message="Forbidden", response=mock_response)
        mock_api_instance.repo_info.side_effect = mock_error
        
        with pytest.raises(ValueError) as exc_info:
            data_source.validate_access()
        
        assert "Invalid access token" in str(exc_info.value)
        assert "403" in str(exc_info.value)
    
    def test_load_base64_text_file(self, data_source, tmp_path):
        """Test loading text file and converting to base64"""
        # Create a test text file
        test_file = tmp_path / "test.txt"
        test_content = "Hello, World!"
        test_file.write_text(test_content)
        
        result = data_source._load_base64(test_file)
        
        # Verify base64 encoding
        decoded = base64.b64decode(result).decode('utf-8')
        assert decoded == test_content
    
    def test_load_base64_jpg_image(self, data_source, tmp_path):
        """Test loading JPG image and converting to base64"""
        # Create a test JPEG image
        test_file = tmp_path / "test.jpg"
        img = Image.new('RGB', (100, 100), color='red')
        img.save(test_file, format='JPEG')
        
        result = data_source._load_base64(test_file)
        
        # Verify it's valid base64
        decoded_bytes = base64.b64decode(result)
        assert len(decoded_bytes) > 0
        
        # Verify it's a valid JPEG image
        decoded_img = Image.open(io.BytesIO(decoded_bytes))
        assert decoded_img.format == 'JPEG'
        assert decoded_img.size == (100, 100)
    
    def test_load_base64_rgba_image(self, data_source, tmp_path):
        """Test loading RGBA image (should convert to RGB)"""
        # Create a test PNG image with RGBA mode (JPEG doesn't support RGBA)
        test_file = tmp_path / "test_rgba.jpg"
        img = Image.new('RGBA', (100, 100), color=(255, 0, 0, 128))
        # Save as PNG first, then rename to .jpg to test the conversion logic
        temp_png = tmp_path / "temp.png"
        img.save(temp_png, format='PNG')
        temp_png.rename(test_file)
        
        result = data_source._load_base64(test_file)
        
        # Verify it's valid base64 and converted to RGB
        decoded_bytes = base64.b64decode(result)
        decoded_img = Image.open(io.BytesIO(decoded_bytes))
        assert decoded_img.mode == 'RGB'
        assert decoded_img.format == 'JPEG'
    
    @patch('fieldworkarena.agent.metrics.tasks.data_source.hf_hub_download')
    def test_download_success(self, mock_hf_hub_download, data_source):
        """Test successful file download"""
        mock_hf_hub_download.return_value = "/tmp/downloaded_file.txt"
        
        result = data_source._download("data/document/test.txt")
        
        assert result == Path("/tmp/downloaded_file.txt")
        mock_hf_hub_download.assert_called_once_with(
            repo_id=data_source.repo_id,
            filename="data/document/test.txt",
            repo_type=data_source.repo_type,
            token=data_source.access_token,
            cache_dir=data_source.cache_dir,
            force_download=False,
            local_files_only=False,
        )
    
    @patch('fieldworkarena.agent.metrics.tasks.data_source.hf_hub_download')
    def test_download_with_force_download(self, mock_hf_hub_download, data_source_force_download):
        """Test download with force_download=True"""
        mock_hf_hub_download.return_value = "/tmp/downloaded_file.txt"
        
        result = data_source_force_download._download("data/document/test.txt")
        
        assert result == Path("/tmp/downloaded_file.txt")
        mock_hf_hub_download.assert_called_once_with(
            repo_id=data_source_force_download.repo_id,
            filename="data/document/test.txt",
            repo_type=data_source_force_download.repo_type,
            token=data_source_force_download.access_token,
            cache_dir=data_source_force_download.cache_dir,
            force_download=True,
            local_files_only=False,
        )
    
    @patch('fieldworkarena.agent.metrics.tasks.data_source.hf_hub_download')
    def test_download_401_error(self, mock_hf_hub_download, data_source):
        """Test download with 401 error"""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_error = HfHubHTTPError(message="Unauthorized", response=mock_response)
        mock_hf_hub_download.side_effect = mock_error
        
        with pytest.raises(ValueError) as exc_info:
            data_source._download("data/document/test.txt")
        
        assert "Invalid access token" in str(exc_info.value)
        assert "401" in str(exc_info.value)
    
    @patch('fieldworkarena.agent.metrics.tasks.data_source.hf_hub_download')
    def test_download_403_error(self, mock_hf_hub_download, data_source):
        """Test download with 403 error"""
        mock_response = Mock()
        mock_response.status_code = 403
        mock_error = HfHubHTTPError(message="Forbidden", response=mock_response)
        mock_hf_hub_download.side_effect = mock_error
        
        with pytest.raises(ValueError) as exc_info:
            data_source._download("data/document/test.txt")
        
        assert "Invalid access token" in str(exc_info.value)
        assert "403" in str(exc_info.value)
    
    @patch('fieldworkarena.agent.metrics.tasks.data_source.hf_hub_download')
    def test_download_404_error(self, mock_hf_hub_download, data_source):
        """Test download with 404 error"""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_error = HfHubHTTPError(message="Not Found", response=mock_response)
        mock_hf_hub_download.side_effect = mock_error
        
        with pytest.raises(FileNotFoundError) as exc_info:
            data_source._download("data/document/test.txt")
        
        assert "not found" in str(exc_info.value).lower()
        assert "test.txt" in str(exc_info.value)
    
    @patch('fieldworkarena.agent.metrics.tasks.data_source.hf_hub_download')
    def test_download_500_error(self, mock_hf_hub_download, data_source):
        """Test download with 500 error"""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_error = HfHubHTTPError(message="Internal Server Error", response=mock_response)
        mock_hf_hub_download.side_effect = mock_error
        
        with pytest.raises(RuntimeError) as exc_info:
            data_source._download("data/document/test.txt")
        
        assert "Failed to download" in str(exc_info.value)
        assert "500" in str(exc_info.value)
    
    @patch('fieldworkarena.agent.metrics.tasks.data_source.hf_hub_download')
    def test_download_unexpected_error(self, mock_hf_hub_download, data_source):
        """Test download with unexpected error"""
        mock_hf_hub_download.side_effect = ConnectionError("Network error")
        
        with pytest.raises(RuntimeError) as exc_info:
            data_source._download("data/document/test.txt")
        
        assert "unexpected error" in str(exc_info.value).lower()
        assert "ConnectionError" in str(exc_info.value)
    
    def test_get_media_type_txt(self, data_source):
        """Test getting media type for text file"""
        test_path = Path("test.txt")
        result = data_source._get_media_type(test_path)
        assert result == "text/plain"
    
    def test_get_media_type_pdf(self, data_source):
        """Test getting media type for PDF file"""
        test_path = Path("test.pdf")
        result = data_source._get_media_type(test_path)
        assert result == "application/pdf"
    
    def test_get_media_type_jpg(self, data_source):
        """Test getting media type for JPEG file"""
        test_path = Path("test.jpg")
        result = data_source._get_media_type(test_path)
        assert result == "image/jpeg"
    
    def test_get_media_type_mp4(self, data_source):
        """Test getting media type for MP4 file"""
        test_path = Path("test.mp4")
        result = data_source._get_media_type(test_path)
        assert result == "video/mp4"
    
    def test_get_media_type_unsupported(self, data_source):
        """Test getting media type for file type that returns None from mimetypes"""
        # Test with a truly unknown extension that mimetypes won't recognize
        # Note: Some systems may have registered MIME types for various extensions
        # We need to use a very unusual extension or mock the behavior
        with patch('fieldworkarena.agent.metrics.tasks.data_source.mimetypes.guess_type') as mock_guess:
            mock_guess.return_value = (None, None)
            test_path = Path("test.unknownext")
            
            with pytest.raises(ValueError) as exc_info:
                data_source._get_media_type(test_path)
            
            assert "Unsupported file type" in str(exc_info.value)
    
    @patch.object(BenchmarkDataSource, '_download')
    @patch.object(BenchmarkDataSource, '_load_base64')
    @patch.object(BenchmarkDataSource, '_get_media_type')
    def test_load_single_file_txt(self, mock_get_media_type, mock_load_base64, 
                                   mock_download, data_source):
        """Test loading a single text file"""
        mock_download.return_value = Path("/tmp/test.txt")
        mock_load_base64.return_value = "base64encodedcontent"
        mock_get_media_type.return_value = "text/plain"
        
        result = data_source._load_single_file("test.txt")
        
        assert isinstance(result, FileWithBytes)
        assert result.bytes == "base64encodedcontent"
        assert result.mime_type == "text/plain"
        assert result.name == "test.txt"
        
        mock_download.assert_called_once_with("data/document/test.txt")
    
    @patch.object(BenchmarkDataSource, '_download')
    @patch.object(BenchmarkDataSource, '_load_base64')
    @patch.object(BenchmarkDataSource, '_get_media_type')
    def test_load_single_file_pdf(self, mock_get_media_type, mock_load_base64, 
                                   mock_download, data_source):
        """Test loading a single PDF file"""
        mock_download.return_value = Path("/tmp/test.pdf")
        mock_load_base64.return_value = "base64encodedcontent"
        mock_get_media_type.return_value = "application/pdf"
        
        result = data_source._load_single_file("test.pdf")
        
        assert result.mime_type == "application/pdf"
        mock_download.assert_called_once_with("data/document/test.pdf")
    
    @patch.object(BenchmarkDataSource, '_download')
    @patch.object(BenchmarkDataSource, '_load_base64')
    @patch.object(BenchmarkDataSource, '_get_media_type')
    def test_load_single_file_jpg(self, mock_get_media_type, mock_load_base64, 
                                   mock_download, data_source):
        """Test loading a single JPEG file"""
        mock_download.return_value = Path("/tmp/test.jpg")
        mock_load_base64.return_value = "base64encodedcontent"
        mock_get_media_type.return_value = "image/jpeg"
        
        result = data_source._load_single_file("test.jpg")
        
        assert result.mime_type == "image/jpeg"
        mock_download.assert_called_once_with("data/image/test.jpg")
    
    @patch.object(BenchmarkDataSource, '_download')
    @patch.object(BenchmarkDataSource, '_load_base64')
    @patch.object(BenchmarkDataSource, '_get_media_type')
    def test_load_single_file_mp4(self, mock_get_media_type, mock_load_base64, 
                                   mock_download, data_source):
        """Test loading a single MP4 file"""
        mock_download.return_value = Path("/tmp/test.mp4")
        mock_load_base64.return_value = "base64encodedcontent"
        mock_get_media_type.return_value = "video/mp4"
        
        result = data_source._load_single_file("test.mp4")
        
        assert result.mime_type == "video/mp4"
        mock_download.assert_called_once_with("data/movie/test.mp4")
    
    def test_load_single_file_unsupported_extension(self, data_source):
        """Test loading file with unsupported extension"""
        with pytest.raises(ValueError) as exc_info:
            data_source._load_single_file("test.xyz")
        
        assert "Unsupported file extension" in str(exc_info.value)
        assert ".xyz" in str(exc_info.value)
    
    @patch.object(BenchmarkDataSource, '_download')
    def test_load_single_file_download_error(self, mock_download, data_source):
        """Test loading file when download fails"""
        mock_download.side_effect = FileNotFoundError("File not found")
        
        with pytest.raises(FileNotFoundError):
            data_source._load_single_file("test.txt")
    
    @patch.object(BenchmarkDataSource, '_load_single_file')
    def test_load_file_payload_list_format(self, mock_load_single_file, data_source):
        """Test load_file_payload with list format (V1)"""
        mock_file1 = FileWithBytes(bytes="base64_1", mime_type="text/plain", name="file1.txt")
        mock_file2 = FileWithBytes(bytes="base64_2", mime_type="application/pdf", name="file2.pdf")
        mock_load_single_file.side_effect = [mock_file1, mock_file2]
        
        result = data_source.load_file_payload(["file1.txt", "file2.pdf"])
        
        assert len(result) == 2
        assert result[0] == mock_file1
        assert result[1] == mock_file2
        assert mock_load_single_file.call_count == 2
    
    @patch.object(BenchmarkDataSource, '_load_single_file')
    def test_load_file_payload_string_format(self, mock_load_single_file, data_source):
        """Test load_file_payload with space-separated string format (V2)"""
        mock_file1 = FileWithBytes(bytes="base64_1", mime_type="text/plain", name="file1.txt")
        mock_file2 = FileWithBytes(bytes="base64_2", mime_type="application/pdf", name="file2.pdf")
        mock_load_single_file.side_effect = [mock_file1, mock_file2]
        
        result = data_source.load_file_payload("file1.txt file2.pdf")
        
        assert len(result) == 2
        assert result[0] == mock_file1
        assert result[1] == mock_file2
        assert mock_load_single_file.call_count == 2
    
    @patch.object(BenchmarkDataSource, '_load_single_file')
    def test_load_file_payload_single_file(self, mock_load_single_file, data_source):
        """Test load_file_payload with single file"""
        mock_file = FileWithBytes(bytes="base64", mime_type="text/plain", name="file.txt")
        mock_load_single_file.return_value = mock_file
        
        result = data_source.load_file_payload(["file.txt"])
        
        assert len(result) == 1
        assert result[0] == mock_file
    
    @patch.object(BenchmarkDataSource, '_load_single_file')
    def test_load_file_payload_error_handling(self, mock_load_single_file, data_source):
        """Test load_file_payload error handling"""
        mock_load_single_file.side_effect = ValueError("File load error")
        
        with pytest.raises(ValueError) as exc_info:
            data_source.load_file_payload(["file.txt"])
        
        assert "File load error" in str(exc_info.value)
    
    @patch.object(BenchmarkDataSource, '_load_single_file')
    def test_load_file_payload_empty_list(self, mock_load_single_file, data_source):
        """Test load_file_payload with empty list"""
        result = data_source.load_file_payload([])
        
        assert len(result) == 0
        mock_load_single_file.assert_not_called()
    
    @patch.object(BenchmarkDataSource, '_load_single_file')
    def test_load_file_payload_empty_string(self, mock_load_single_file, data_source):
        """Test load_file_payload with empty string"""
        result = data_source.load_file_payload("")
        
        assert len(result) == 0
        mock_load_single_file.assert_not_called()



class TestBenchmarkDataSourceIntegration:
    """Integration tests for BenchmarkDataSource with real HuggingFace API"""
    
    @pytest.fixture
    def real_access_token(self):
        """Fixture for real access token from environment variable"""
        token = os.getenv("FWA_TEST_TOKEN")
        if not token:
            pytest.skip("FWA_TEST_TOKEN environment variable not set. See tests/README.md for setup instructions.")
        return token
    
    @pytest.fixture
    def real_data_source(self, real_access_token):
        """Fixture for BenchmarkDataSource with real token"""
        return BenchmarkDataSource(
            access_token=real_access_token,
            repo_id="Fujitsu/FieldWorkArena_Dataset",
            repo_type="dataset"
        )
    
    @pytest.mark.integration
    def test_validate_access_real(self, real_data_source):
        """Test access validation with real HuggingFace token"""
        # Should not raise any exception with valid token
        real_data_source.validate_access()
    
    @pytest.mark.integration
    def test_load_single_file_txt_real(self, real_data_source):
        """Test loading a real text file from HuggingFace"""
        # Assuming there's a test file available in the repository
        # Adjust filename based on actual test data
        try:
            result = real_data_source._load_single_file("6_ScrewTightening_PhoneAssembly.txt")
            
            assert isinstance(result, FileWithBytes)
            assert result.mime_type == "text/plain"
            assert result.name == "6_ScrewTightening_PhoneAssembly.txt"
            assert len(result.bytes) > 0
            
            # Verify base64 encoding
            decoded = base64.b64decode(result.bytes)
            assert len(decoded) > 0
        except FileNotFoundError:
            pytest.skip("Test file not found in repository")
    
    @pytest.mark.integration
    def test_load_file_payload_multiple_files_real(self, real_data_source):
        """Test loading multiple files with real HuggingFace API"""
        try:
            # Test with space-separated string format (V2)
            result = real_data_source.load_file_payload(
                "6_ScrewTightening_PhoneAssembly.txt"
            )
            
            assert len(result) >= 1
            assert all(isinstance(f, FileWithBytes) for f in result)
            assert all(len(f.bytes) > 0 for f in result)
        except FileNotFoundError:
            pytest.skip("Test files not found in repository")
    
    @pytest.mark.integration
    def test_download_nonexistent_file(self, real_data_source):
        """Test downloading a file that doesn't exist"""
        with pytest.raises(FileNotFoundError) as exc_info:
            real_data_source._download("data/document/nonexistent_file_xyz123.txt")
        
        assert "not found" in str(exc_info.value).lower()
