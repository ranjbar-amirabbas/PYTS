# Testing Guide

## Prerequisites

### FFmpeg Installation

The audio conversion functionality requires FFmpeg to be installed on your system.

#### macOS
```bash
brew install ffmpeg
```

#### Ubuntu/Debian
```bash
sudo apt-get update
sudo apt-get install ffmpeg
```

#### Windows
Download from https://ffmpeg.org/download.html or use chocolatey:
```bash
choco install ffmpeg
```

### Python Dependencies

Install Python dependencies:
```bash
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Running Tests

### Run all tests
```bash
source venv/bin/activate
python -m pytest tests/ -v
```

### Run specific test modules
```bash
# Test audio processor (format detection - no FFmpeg required)
python -m pytest tests/test_audio_processor.py::TestAudioProcessor -v

# Test audio conversion (requires FFmpeg)
python -m pytest tests/test_audio_processor.py::TestAudioConversion -v
```

### Run with coverage
```bash
python -m pytest tests/ --cov=app --cov-report=html
```

## Docker Testing

The Docker container includes FFmpeg, so all tests will work in the containerized environment:

```bash
docker-compose build
docker-compose run --rm api pytest tests/ -v
```

## Note on FFmpeg Tests

Tests in `TestAudioConversion` class require FFmpeg to be installed on the system. If FFmpeg is not available:
- Tests will fail with `FileNotFoundError: [Errno 2] No such file or directory: 'ffmpeg'`
- This is expected behavior - install FFmpeg to run these tests
- The Docker container will have FFmpeg pre-installed
