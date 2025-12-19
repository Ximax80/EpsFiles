"""
Auto-commit webhook for Document Processing pipeline.

This script runs every 5 minutes (via scheduler) and:
1. Checks for git changes in the repository
2. Analyzes new/modified outputs to generate descriptive commit messages
3. Commits changes with verbose, time-stamped messages
4. Pushes to remote repository

Usage:
    python auto_commit_webhook.py [--dry-run] [--interval 30]
"""
from __future__ import annotations

import os
import sys
import json
import subprocess
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def run_git_command(cmd: List[str], cwd: Optional[Path] = None) -> Tuple[str, int]:
    """Run a git command and return stdout and return code."""
    try:
        result = subprocess.run(
            ["git"] + cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False
        )
        return result.stdout.strip(), result.returncode
    except Exception as e:
        print(f"Error running git command: {e}", file=sys.stderr)
        return "", 1


def get_git_status(base_dir: Path) -> Dict[str, List[str]]:
    """Get git status and categorize changes."""
    changes = {
        "modified": [],
        "added": [],
        "deleted": [],
        "untracked": []
    }
    
    # Get modified and added files
    stdout, code = run_git_command(["status", "--porcelain"], cwd=base_dir)
    if code != 0:
        return changes
    
    for line in stdout.split("\n"):
        if not line.strip():
            continue
        status = line[:2]
        filename = line[3:].strip()
        
        if status.startswith("M"):
            changes["modified"].append(filename)
        elif status.startswith("A"):
            changes["added"].append(filename)
        elif status.startswith("D"):
            changes["deleted"].append(filename)
        elif status.startswith("??"):
            changes["untracked"].append(filename)
    
    return changes


def analyze_natives_output(file_path: Path) -> Dict[str, Any]:
    """Analyze a natives analysis JSON file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        summary = {
            "file": file_path.name,
            "worksheets": len(data.get("structure", {}).get("worksheets", [])),
            "entities": {
                "people": len(data.get("entities", {}).get("people", [])),
                "organizations": len(data.get("entities", {}).get("organizations", [])),
                "locations": len(data.get("entities", {}).get("locations", [])),
                "dates": len(data.get("entities", {}).get("dates", []))
            },
            "relationships": len(data.get("relationships", [])),
            "document_type": data.get("context", {}).get("document_type", "unknown")
        }
        return summary
    except Exception as e:
        return {"file": file_path.name, "error": str(e)}


def analyze_image_output(file_path: Path) -> Dict[str, Any]:
    """Analyze an image analysis JSON file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        structured = data.get("structured_data", {})
        people_list = structured.get("people", [])
        
        # Extract key entities for summary
        key_entities = []
        for person in people_list:
            person_lower = str(person).lower()
            # Basic filtering or ranking could go here, but keeping it general
            key_entities.append(person)
        
        summary = {
            "file": file_path.name,
            "document_type": data.get("image_analysis", {}).get("type", "unknown"),
            "has_text": bool(data.get("text_extraction", {}).get("full_text")),
            "entities": {
                "people": len(people_list),
                "people_list": people_list[:10],  # First 10 people
                "organizations": len(structured.get("organizations", [])),
                "dates": len(structured.get("dates", []))
            },
            "document_numbers": len(structured.get("document_numbers", [])),
            "has_signatures": len(structured.get("signatures", [])) > 0,
            "quality": data.get("image_analysis", {}).get("quality", "unknown"),
            "key_entities": key_entities[:10],
            "full_text_preview": (data.get("text_extraction", {}).get("full_text", "") or "")[:200]  # First 200 chars
        }
        return summary
    except Exception as e:
        return {"file": file_path.name, "error": str(e)}


def analyze_text_output(file_path: Path) -> Dict[str, Any]:
    """Analyze a text extraction or story assembly JSON file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if "letters" in data:
            # Story assembly format
            summary = {
                "file": file_path.name,
                "type": "story_assembly",
                "letters_count": len(data.get("letters", [])),
                "unassigned_pages": len(data.get("unassigned_pages", []))
            }
        else:
            # Text extraction format
            summary = {
                "file": file_path.name,
                "type": "text_extraction",
                "document_type": data.get("metadata", {}).get("document_type", "unknown"),
                "entities": {
                    "people": len(data.get("entities", {}).get("people", [])),
                    "organizations": len(data.get("entities", {}).get("organizations", [])),
                    "dates": len(data.get("entities", {}).get("dates", []))
                },
                "themes": len(data.get("themes", []))
            }
        return summary
    except Exception as e:
        return {"file": file_path.name, "error": str(e)}


def analyze_letter_directory(letter_dir: Path) -> Dict[str, Any]:
    """Analyze a letter/story directory."""
    summary = {
        "letter_id": letter_dir.name,
        "has_meta": False,
        "has_text": False,
        "has_translation": False,
        "translation_text": "",
        "source_files_count": 0
    }
    
    meta_file = letter_dir / "meta.json"
    if meta_file.exists():
        summary["has_meta"] = True
        try:
            with open(meta_file, 'r', encoding='utf-8') as f:
                meta = json.load(f)
                source_files = meta.get("source_files", [])
                summary["source_files_count"] = len(source_files) if isinstance(source_files, list) else 0
        except:
            pass
    
    if (letter_dir / "text.txt").exists() or (letter_dir / "de.txt").exists():
        summary["has_text"] = True
    
    en_path = letter_dir / "en.txt"
    if en_path.exists():
        summary["has_translation"] = True
        try:
            with open(en_path, 'r', encoding='utf-8') as f:
                summary["translation_text"] = f.read().strip()
        except:
            pass
    
    return summary


def generate_visual_summary(text: str, output_path: Path, api_key: str) -> bool:
    """Generate a visual summary of the text using Nano Banana (Gemini 3 Pro Image)."""
    if not text or not api_key:
        return False
    
    try:
        client = genai.Client(api_key=api_key)
        prompt = (
            "Create a professional, high-fidelity visual summary of the following document content.\n"
            "The image should be an editorial illustration capturing the key themes, people, and atmosphere.\n"
            "Style: Modern investigative journalism, sleek, slightly dramatic but realistic.\n"
            "Include subtle textual elements for key names or dates if appropriate.\n"
            "CONTENT:\n" + text[:2000]
        )
        
        print(f"Generating visual summary for latest translation...")
        response = client.models.generate_image(
            model='gemini-3-pro-image-preview',
            prompt=prompt,
            config=types.GenerateImageConfig(
                number_of_images=1,
                include_rai_reasoning=True,
                output_mime_type='image/png'
            )
        )
        
        if response.generated_images:
            image_data = response.generated_images[0].image_bytes
            with open(output_path, 'wb') as f:
                f.write(image_data)
            print(f"Visual summary saved to {output_path}")
            return True
    except Exception as e:
        print(f"Error generating visual summary: {e}", file=sys.stderr)
    return False


def generate_commit_message(changes: Dict[str, List[str]], base_dir: Path, visual_summary_path: Optional[Path] = None) -> str:
    """Generate a verbose commit message describing the latest findings."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Collect all findings across files
    all_people = []
    processing_status = []
    
    message_parts = [
        f"Pipeline Update: {timestamp}",
        "",
        "=== LATEST FINDINGS ===",
        ""
    ]
    
    # Analyze natives outputs
    natives_files = [f for f in changes["added"] + changes["modified"] 
                     if "natives_analysis" in f and f.endswith("_analysis.json")]
    if natives_files:
        message_parts.append("NATIVES PROCESSING:")
        natives_summaries = []
        for file in natives_files[:5]:  # Limit to 5 most recent
            file_path = base_dir / file
            if file_path.exists():
                summary = analyze_natives_output(file_path)
                if "error" not in summary:
                    natives_summaries.append(
                        f"  • {summary['file']}: {summary['worksheets']} worksheets, "
                        f"{summary['entities']['people']} people, "
                        f"{summary['relationships']} relationships"
                    )
        if natives_summaries:
            message_parts.extend(natives_summaries)
        else:
            message_parts.append(f"  • {len(natives_files)} new/modified analysis file(s)")
        message_parts.append("")
    
    # Analyze image outputs
    image_json_files = [f for f in changes["added"] + changes["modified"] 
                       if f.endswith(".json") and "/IMAGES/" in f.replace("\\", "/")]
    if image_json_files:
        processing_status.append(f"Analyzing {len(image_json_files)} image(s)")
        message_parts.append("IMAGES PROCESSING:")
        message_parts.append(f"Processing {len(image_json_files)} new image analysis file(s)...")
        message_parts.append("")
        
        # Collect key findings
        notable_docs = []
        
        for file in image_json_files[:20]:  # Check up to 20 most recent
            file_path = base_dir / file
            if file_path.exists():
                summary = analyze_image_output(file_path)
                if "error" not in summary:
                    # Collect all people
                    people_list = summary.get("entities", {}).get("people_list", [])
                    for person in people_list:
                        if person not in all_people:
                            all_people.append(person)
                    
                    # Note notable documents
                    notable_docs.append({
                        "file": summary['file'],
                        "type": summary.get("document_type", "unknown"),
                        "people_count": summary.get("entities", {}).get("people", 0),
                        "has_signatures": summary.get("has_signatures", False)
                    })
        
        # Summary of notable documents
        if notable_docs:
            message_parts.append("NOTABLE DOCUMENTS:")
            for doc in notable_docs[:5]:
                flags = []
                if doc["has_signatures"]:
                    flags.append("SIGNED")
                flag_str = f" [{', '.join(flags)}]" if flags else ""
                message_parts.append(f"  • {doc['file']}: {doc['type']}, {doc['people_count']} people{flag_str}")
            message_parts.append("")
        
        # Overall stats
        message_parts.append(f"Total people identified across all images: {len(all_people)}")
        message_parts.append("")
    
    # Analyze text outputs
    text_extraction_files = [f for f in changes["added"] + changes["modified"] 
                            if "text_extractions.json" in f or "stories_assembly.json" in f]
    if text_extraction_files:
        message_parts.append("TEXT PROCESSING:")
        for file in text_extraction_files:
            file_path = base_dir / file
            if file_path.exists():
                summary = analyze_text_output(file_path)
                if "error" not in summary:
                    if summary.get("type") == "story_assembly":
                        message_parts.append(
                            f"  • Story assembly: {summary['letters_count']} letters/stories assembled, "
                            f"{summary['unassigned_pages']} unassigned pages"
                        )
                    else:
                        message_parts.append(
                            f"  • Text extraction: {summary['document_type']}, "
                            f"{summary['entities']['people']} people, "
                            f"{len(summary.get('themes', []))} themes"
                        )
        message_parts.append("")
    
    # Analyze letter directories
    letter_dirs = [f for f in changes["added"] + changes["untracked"] 
                  if "/letters/" in f.replace("\\", "/") and 
                  (f.endswith("/meta.json") or f.endswith("/text.txt") or f.endswith("/en.txt"))]
    if letter_dirs:
        # Group by letter directory
        letter_ids = set()
        for file in letter_dirs:
            parts = file.replace("\\", "/").split("/letters/")
            if len(parts) > 1:
                letter_id = parts[1].split("/")[0]
                letter_ids.add(letter_id)
        
        if letter_ids:
            message_parts.append("LETTERS/STORIES:")
            for letter_id in sorted(list(letter_ids))[:10]:  # Limit to 10
                letter_path = base_dir / "output" / "text_analysis" / "letters" / letter_id
                if letter_path.exists():
                    summary = analyze_letter_directory(letter_path)
                    status_parts = []
                    if summary["has_text"]:
                        status_parts.append("text")
                    if summary["has_translation"]:
                        status_parts.append("translated")
                    if summary["source_files_count"] > 0:
                        status_parts.append(f"{summary['source_files_count']} sources")
                    message_parts.append(f"  • {letter_id}: {', '.join(status_parts) if status_parts else 'new'}")
            message_parts.append("")
    
    # Summary statistics
    message_parts.append("=== SUMMARY ===")
    if processing_status:
        message_parts.append("Current Status:")
        for status in processing_status:
            message_parts.append(f"  • {status}")
        message_parts.append("")
    
    message_parts.append(f"Modified files: {len(changes['modified'])}")
    message_parts.append(f"New files: {len(changes['added'])}")
    message_parts.append(f"Untracked files: {len(changes['untracked'])}")
    if changes["deleted"]:
        message_parts.append(f"Deleted files: {len(changes['deleted'])}")
    message_parts.append("")
    
    # Add catchier closing
    message_parts.append("---")
    message_parts.append("Investigation continues as new documents are analyzed and connections revealed.")
    message_parts.append("")
    
    if visual_summary_path:
        message_parts.append("VISUAL SUMMARY:")
        message_parts.append(f"  • Nano Banana generated a new visual summary of the latest evidence: {visual_summary_path.name}")
        message_parts.append("")
    
    message_parts.append(f"Auto-committed at {timestamp}")
    message_parts.append("Processing continues through the night...")
    
    return "\n".join(message_parts)


def commit_and_push(base_dir: Path, dry_run: bool = False) -> bool:
    """Check for changes, generate commit message, and push to remote."""
    # Check if we're in a git repository
    stdout, code = run_git_command(["rev-parse", "--git-dir"], cwd=base_dir)
    if code != 0:
        print("Not a git repository. Skipping commit.", file=sys.stderr)
        return False
    
    # Get current branch
    stdout, code = run_git_command(["branch", "--show-current"], cwd=base_dir)
    current_branch = stdout.strip() if code == 0 else "main"
    
    # Check for changes
    changes = get_git_status(base_dir)
    total_changes = sum(len(v) for v in changes.values())
    
    if total_changes == 0:
        print("No changes detected. Skipping commit.")
        return False
    
    print(f"Detected {total_changes} changes:")
    print(f"  Modified: {len(changes['modified'])}")
    print(f"  Added: {len(changes['added'])}")
    print(f"  Untracked: {len(changes['untracked'])}")
    print(f"  Deleted: {len(changes['deleted'])}")
    
    # Find latest assembled narrative for visual summary
    api_key = os.environ.get("GEMINI_API_KEY")
    latest_narrative_text = ""
    visual_summary_path = None
    
    # Check for new text.txt files in changes (assembled stories)
    narrative_files = [f for f in changes["added"] + changes["modified"] if f.endswith("text.txt")]
    if narrative_files:
        # Sort to get the most recent one
        latest_file = sorted(narrative_files)[-1]
        file_path = base_dir / latest_file
        if file_path.exists():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    latest_narrative_text = f.read().strip()
            except:
                pass
    
    if latest_narrative_text and api_key:
        summary_img_path = base_dir / "PIPELINE" / "latest_visual_summary.png"
        if generate_visual_summary(latest_narrative_text, summary_img_path, api_key):
            visual_summary_path = summary_img_path

    # Generate commit message
    commit_message = generate_commit_message(changes, base_dir, visual_summary_path)
    
    # Update README with latest summary BEFORE committing
    # Timestamp will be updated AFTER commit (so it shows the new commit time)
    print("Updating README with latest summary...")
    readme_updated = False
    try:
        import subprocess
        # Update summary from JSON files first (needs current files)
        summary_generator = base_dir / "PIPELINE" / "generate_summary.py"
        if not summary_generator.exists():
            summary_generator = base_dir / "generate_summary.py"
        if summary_generator.exists():
            result = subprocess.run([sys.executable, str(summary_generator)], cwd=base_dir, check=False, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"Summary updated: {result.stdout.strip()}")
                readme_updated = True
            else:
                print(f"Summary update error: {result.stderr}", file=sys.stderr)
    except Exception as e:
        print(f"Note: Could not update README summary: {e}", file=sys.stderr)
    
    if dry_run:
        print("\n=== DRY RUN - Would commit with message: ===")
        print(commit_message)
        if readme_updated:
            print("\n(README would be updated and included in this commit)")
        print("\n=== END DRY RUN ===")
        return True
    
    # Stage all changes (including README if it was updated)
    print("Staging changes...")
    stdout, code = run_git_command(["add", "-A"], cwd=base_dir)
    if code != 0:
        print(f"Error staging changes: {stdout}", file=sys.stderr)
        return False
    
    # Commit (includes README update if it happened)
    print("Committing changes...")
    stdout, code = run_git_command(
        ["commit", "-m", commit_message],
        cwd=base_dir
    )
    if code != 0:
        if "nothing to commit" in stdout.lower():
            print("No changes to commit (may have been committed already).")
            return True
        print(f"Error committing: {stdout}", file=sys.stderr)
        return False
    
    print(f"Committed successfully: {stdout[:100]}...")
    
    # Update timestamp with THIS commit's time (now that we have a new commit)
    print("Updating README timestamp with latest commit time...")
    try:
        import subprocess
        readme_updater = base_dir / "PIPELINE" / "update_status.py"
        if not readme_updater.exists():
            readme_updater = base_dir / "update_status.py"
        if readme_updater.exists():
            result = subprocess.run([sys.executable, str(readme_updater)], cwd=base_dir, check=False, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"Timestamp updated: {result.stdout.strip()}")
                # Check if README files have timestamp changes
                stdout_status, code_status = run_git_command(["status", "--porcelain", "README.md", "PIPELINE/README.md"], cwd=base_dir)
                if stdout_status.strip():
                    # Stage both README files
                    run_git_command(["add", "README.md", "PIPELINE/README.md"], cwd=base_dir)
                    timestamp_msg = f"Update README timestamp - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    stdout_commit, code_commit = run_git_command(["commit", "-m", timestamp_msg], cwd=base_dir)
                    if code_commit == 0:
                        print("Timestamp commit successful")
                    else:
                        print(f"Note: Timestamp commit had issues: {stdout_commit}", file=sys.stderr)
            else:
                print(f"Timestamp update error: {result.stderr}", file=sys.stderr)
    except Exception as e:
        print(f"Note: Could not update timestamp: {e}", file=sys.stderr)
    
    # Push to remote (all commits including README updates)
    print(f"Pushing to remote (branch: {current_branch})...")
    stdout, code = run_git_command(
        ["push", "origin", current_branch],
        cwd=base_dir
    )
    if code != 0:
        print(f"Error pushing: {stdout}", file=sys.stderr)
        print("Commit was successful, but push failed. You may need to push manually.")
        return False
    
    print("Pushed successfully!")
    
    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Auto-commit webhook for BATCH7 pipeline"
    )
    parser.add_argument(
        "--base-dir",
        type=str,
        default=None,
        help="Base directory (default: parent of script directory)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be committed without actually committing"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=5,
        help="Interval in minutes (default: 5)"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run once and exit (don't loop)"
    )
    
    args = parser.parse_args()
    
    # Determine base directory
    if args.base_dir:
        base_dir = Path(args.base_dir)
    else:
        script_dir = Path(__file__).parent.absolute()
        # Go up to project root (where .git should be)
        base_dir = script_dir.parent if script_dir.name == "PIPELINE" else script_dir
    
    if not base_dir.exists():
        print(f"Error: Base directory does not exist: {base_dir}", file=sys.stderr)
        sys.exit(1)
    
    print(f"Base directory: {base_dir}")
    print(f"Dry run: {args.dry_run}")
    
    if args.once:
        commit_and_push(base_dir, dry_run=args.dry_run)
    else:
        import time
        print(f"Starting webhook loop (checking every {args.interval} minutes)...")
        print("Press Ctrl+C to stop")
        
        try:
            while True:
                commit_and_push(base_dir, dry_run=args.dry_run)
                if not args.dry_run:
                    print(f"Waiting {args.interval} minutes until next check...")
                    time.sleep(args.interval * 60)
                else:
                    break
        except KeyboardInterrupt:
            print("\nStopped by user")


if __name__ == "__main__":
    main()

