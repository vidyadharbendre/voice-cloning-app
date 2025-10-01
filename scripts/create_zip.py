# ================================
# FILE: scripts/create_zip.py
# ================================

#!/usr/bin/env python3
"""
Script to create a deployable ZIP package of the voice cloning application
"""

import os
import zipfile
import shutil
from pathlib import Path

def create_deployment_zip():
    """Create a ZIP file with all necessary files for deployment"""
    
    # Define the project root
    project_root = Path(__file__).parent.parent
    zip_filename = "voice_cloning_app_mvp.zip"
    
    # Files and directories to include
    include_patterns = [
        "app/",
        "tests/",
        "docker/",
        "scripts/",
        "notebooks/",
        "docs/",
        "requirements.txt",
        "run.py",
        "README.md",
        ".env.example"
    ]
    
    # Files to exclude
    exclude_patterns = [
        "__pycache__",
        ".pyc",
        ".git",
        ".pytest_cache",
        "venv",
        "env",
        ".env",
        "uploads/",
        "outputs/",
        "logs/",
        ".DS_Store",
        "*.log"
    ]
    
    print(f"Creating deployment ZIP: {zip_filename}")
    
    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for pattern in include_patterns:
            path = project_root / pattern
            
            if path.is_file():
                # Add individual file
                zipf.write(path, pattern)
                print(f"Added file: {pattern}")
            elif path.is_dir():
                # Add directory recursively
                for root, dirs, files in os.walk(path):
                    # Filter out excluded directories
                    dirs[:] = [d for d in dirs if not any(exc in d for exc in exclude_patterns)]
                    
                    for file in files:
                        # Filter out excluded files
                        if any(exc in file for exc in exclude_patterns):
                            continue
                        
                        file_path = Path(root) / file
                        arcname = file_path.relative_to(project_root)
                        zipf.write(file_path, arcname)
                        print(f"Added: {arcname}")
    
    print(f"\n✅ Deployment ZIP created successfully: {zip_filename}")
    print(f"📦 ZIP size: {os.path.getsize(zip_filename) / 1024 / 1024:.2f} MB")
    
    # Create extraction instructions
    instructions = """