#!/bin/bash
# Wrapper script to run join_video_files.py with proper environment setup

cd "$(dirname "$0")"

# Activate virtual environment
source venv/bin/activate

# Ensure Python can find packages (fix for Python 3.14 venv issue)
export PYTHONPATH="$VIRTUAL_ENV/lib/python3.14/site-packages:$PYTHONPATH"

# Run the script
python join_video_files.py "$@"
