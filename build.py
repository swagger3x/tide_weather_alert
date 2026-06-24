"""
Cross-platform Lambda deployment package builder.
Works on Windows, Mac, and Linux.

Usage:
    python build.py

Output:
    lambda_package.zip — ready to upload to AWS Lambda
"""

import os
import shutil
import subprocess
import sys
import zipfile


SRC_DIR = "src"
PACKAGE_DIR = "package"
OUTPUT_ZIP = "lambda_package.zip"
REQUIREMENTS = "requirements.txt"


def clean():
    print("Cleaning previous build...")
    if os.path.exists(PACKAGE_DIR):
        shutil.rmtree(PACKAGE_DIR)
    if os.path.exists(OUTPUT_ZIP):
        os.remove(OUTPUT_ZIP)


def install_dependencies():
    print("Installing dependencies into package/...")
    os.makedirs(PACKAGE_DIR, exist_ok=True)
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", REQUIREMENTS, "-t", PACKAGE_DIR],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print("ERROR installing dependencies:")
        print(result.stderr)
        sys.exit(1)
    print("Dependencies installed.")


def copy_source_files():
    print(f"Copying source files from {SRC_DIR}/...")
    if not os.path.exists(SRC_DIR):
        print(f"ERROR: {SRC_DIR}/ folder not found. Make sure your source files are in {SRC_DIR}/")
        sys.exit(1)

    for fname in os.listdir(SRC_DIR):
        src_path = os.path.join(SRC_DIR, fname)
        dst_path = os.path.join(PACKAGE_DIR, fname)
        if os.path.isfile(src_path):
            shutil.copy2(src_path, dst_path)
            print(f"  Copied: {fname}")


def create_zip():
    print(f"Creating {OUTPUT_ZIP}...")
    with zipfile.ZipFile(OUTPUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(PACKAGE_DIR):
            # skip __pycache__ folders
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for file in files:
                if file.endswith(".pyc"):
                    continue
                full_path = os.path.join(root, file)
                arcname = os.path.relpath(full_path, PACKAGE_DIR)
                zf.write(full_path, arcname)

    size_mb = os.path.getsize(OUTPUT_ZIP) / (1024 * 1024)
    print(f"Done — {OUTPUT_ZIP} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    print("=== Lambda Package Builder ===\n")
    clean()
    install_dependencies()
    copy_source_files()
    create_zip()
    print(f"\n✅ Ready to upload: {OUTPUT_ZIP}")
    print("   Go to AWS Lambda → your function → Upload from → .zip file")