# English Phrases Video Generator

This project generates educational videos with English conversation phrases, including audio narration and subtitles.

## Setup

### Automatic Setup (requires sudo)
Run the setup script to install all dependencies:
```bash
bash setup.sh
```

### Manual Setup

1. **Install system packages** (requires sudo):
   ```bash
   sudo pacman -S --needed python python-pip ffmpeg imagemagick ttf-liberation
   ```

2. **Create and activate virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install Python packages**:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **Fix ImageMagick policy** (if needed):
   ```bash
   sudo sed -i 's/rights="none" pattern="@\*"/rights="read|write" pattern="@*"/g' /etc/ImageMagick-7/policy.xml
   ```

## Usage

### Option 1: Using the wrapper script (recommended)
```bash
./run.sh
```

### Option 2: Manual activation
1. **Activate the virtual environment**:
   ```bash
   source venv/bin/activate
   ```

2. **Run the generator**:
   ```bash
   python generate.py
   ```

The script will:
- Generate audio for all phrases using Microsoft Edge TTS
- Create a video with subtitles
- Output files: `english_phrases_video.mp4` and `english_phrases_audio.mp3`

## Output Directory

By default, videos are saved to the `output/` folder. You can change this by editing the `OUTPUT_DIR` variable in `generate.py`:

```python
OUTPUT_DIR = "output"  # Change this to any folder name inside the project directory
```

For example:
- `OUTPUT_DIR = "output"` → saves to `output/english_phrases_video.mp4`
- `OUTPUT_DIR = "videos"` → saves to `videos/english_phrases_video.mp4`
- `OUTPUT_DIR = "my_videos/final"` → saves to `my_videos/final/english_phrases_video.mp4`
- `OUTPUT_DIR = None` → saves to the project root directory

The output directory will be created automatically if it doesn't exist.

## Requirements

- Python 3.x
- ffmpeg
- ImageMagick
- Liberation Sans font (ttf-liberation)

## Python Packages

See `requirements.txt` for the complete list. Main packages:
- edge-tts: Text-to-speech
- pydub: Audio manipulation
- moviepy: Video editing
- Pillow: Image processing
