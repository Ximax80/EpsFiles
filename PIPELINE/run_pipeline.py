"""
PIPELINE: House Oversight Committee Document Processing

This pipeline processes three types of inputs:
1. NATIVES/ - Excel spreadsheets: Analyze structure, extract relationships, build connection maps
2. IMAGES/ - Images: OCR/extract text, describe pictures, output complex JSON
3. TEXT/ - Text conversations: Extract content, understand context, assemble into stories/letters

Usage:
    python run_pipeline.py --process natives
    python run_pipeline.py --process images
    python run_pipeline.py --process text
    python run_pipeline.py --process all
"""
from __future__ import annotations

import os
import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Import processing modules
# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from process_natives import process_natives
from process_images import process_images
from process_text import process_text


def _guess_default_base_dir(script_dir: Path) -> Path:
    """Return the most likely project root that contains TEXT/ etc."""
    candidates = [
        script_dir,
        script_dir / "PIPELINE",
        script_dir / "pipeline",
        script_dir.parent / "PIPELINE",
        script_dir.parent / "pipeline",
    ]
    for candidate in candidates:
        if candidate.exists() and any((candidate / subdir).exists() for subdir in ("TEXT", "IMAGES", "NATIVES")):
            return candidate
    return script_dir


def main() -> None:
    # Load .env from script directory or parent directory
    script_dir = Path(__file__).parent.absolute()
    # Try script directory first (where .env actually is)
    env_path = script_dir / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
    else:
        # Fallback to parent directory
        load_dotenv(dotenv_path=script_dir.parent / ".env")
        # Also try default location
        load_dotenv()
    
    ap = argparse.ArgumentParser(
        description="House Oversight Pipeline: Process NATIVES, IMAGES, and TEXT directories"
    )
    ap.add_argument(
        "--process",
        choices=["natives", "images", "text", "all"],
        default="all",
        help="Which processing stage to run (default: all)"
    )
    # Default base_dir to the detected project root, even if this script lives in /batch7
    script_dir = Path(__file__).parent.absolute()
    default_base_dir = _guess_default_base_dir(script_dir)
    
    ap.add_argument(
        "--base-dir",
        default=str(default_base_dir),
        help=f"Base directory containing NATIVES/, IMAGES/, TEXT/ (default: {default_base_dir})"
    )
    ap.add_argument(
        "--natives-dir",
        help="NATIVES directory (default: <base-dir>/NATIVES)"
    )
    ap.add_argument(
        "--images-dir",
        help="IMAGES directory (default: <base-dir>/IMAGES)"
    )
    ap.add_argument(
        "--text-dir",
        help="TEXT directory (default: <base-dir>/TEXT)"
    )
    ap.add_argument(
        "--source",
        help="Source folder containing NATIVES, IMAGES, TEXT"
    )
    ap.add_argument(
        "--batch",
        help="Batch folder name (e.g., DecemberBatch) in the workspace root"
    )
    ap.add_argument(
        "--output-dir",
        default="PIPELINE/output",
        help="Output directory for all results (default: PIPELINE/output)"
    )
    ap.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip files that already have outputs"
    )
    ap.add_argument(
        "--limit",
        type=int,
        help="Limit number of files to process in each category"
    )
    args = ap.parse_args()

    base_dir = Path(args.base_dir)
    if args.batch:
        workspace_root = script_dir.parent
        batch_dir = workspace_root / args.batch
        if batch_dir.exists():
            base_dir = batch_dir
            print(f"Using batch directory: {base_dir}")
        else:
            print(f"Error: Batch directory not found: {batch_dir}", file=sys.stderr)
            sys.exit(1)
    elif args.source:
        source_path = Path(args.source)
        if source_path.exists():
            base_dir = source_path
        elif (Path(args.base_dir) / args.source).exists():
            base_dir = Path(args.base_dir) / args.source
    
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Set up directory paths
    natives_dir = Path(args.natives_dir) if args.natives_dir else base_dir / "NATIVES"
    images_dir = Path(args.images_dir) if args.images_dir else base_dir / "IMAGES"
    text_dir = Path(args.text_dir) if args.text_dir else base_dir / "TEXT"

    # Check API key
    if not os.environ.get("GEMINI_API_KEY"):
        print("Error: GEMINI_API_KEY not set (set it or add it to .env)", file=sys.stderr)
        sys.exit(1)

    process_natives_flag = args.process in ("natives", "all")
    process_images_flag = args.process in ("images", "all")
    process_text_flag = args.process in ("text", "all")

    if process_natives_flag:
        print("=" * 80)
        print("PROCESSING NATIVES (Excel Spreadsheets)")
        print("=" * 80)
        if natives_dir.exists():
            process_natives(natives_dir, output_dir / "natives_analysis", args.skip_existing)
        else:
            print(f"NATIVES directory not found: {natives_dir}")

    if process_images_flag:
        print("\n" + "=" * 80)
        print("PROCESSING IMAGES")
        print("=" * 80)
        if images_dir.exists():
            process_images(images_dir, output_dir / "images_analysis", args.skip_existing, args.limit)
        else:
            print(f"IMAGES directory not found: {images_dir}")

    if process_text_flag:
        print("\n" + "=" * 80)
        print("PROCESSING TEXT")
        print("=" * 80)
        if text_dir.exists():
            process_text(text_dir, output_dir / "text_analysis", args.skip_existing)
        else:
            print(f"TEXT directory not found: {text_dir}")

    print("\n" + "=" * 80)
    print("PIPELINE COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()

