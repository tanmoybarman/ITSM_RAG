#!/bin/bash

# Install system dependencies
if [ -f "packages.txt" ]; then
    echo "Installing system packages..."
    apt-get update && apt-get install -y $(cat packages.txt)
fi

# Install Python dependencies
if [ -f "requirements.txt" ]; then
    echo "Installing Python dependencies..."
    pip install --upgrade pip
    pip install -r requirements.txt
fi

# Ensure NLTK data is downloaded
echo "Downloading NLTK data..."
python -c "import nltk; nltk.download('punkt', download_dir='/app/nltk_data'); nltk.download('stopwords', download_dir='/app/nltk_data')"

echo "Setup complete!"
