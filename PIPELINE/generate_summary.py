#!/usr/bin/env python3
"""
Generate a STRATEGIC high-level summary aggregating ALL processed documents.

This script:
1. Reads ALL JSON files across all datasets
2. Aggregates: named individuals, explosive findings, patterns, connections
3. Sends aggregated data to Gemini for strategic analysis
4. Updates README.md with comprehensive summary
"""
from __future__ import annotations

import os
import sys
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Set
from collections import defaultdict
from dotenv import load_dotenv

from google import genai
from google.genai import types


PROMPT_STRATEGIC_SUMMARY = """You are analyzing House Oversight Committee documents related to high-profile investigations. You have been given aggregated data from ALL processed documents.

Create a STRATEGIC, HIGH-LEVEL summary that journalists and investigators can use. Focus on:

1. NAMED INDIVIDUALS: List ALL people explicitly named or identified across all documents
2. MOST EXPLOSIVE FINDINGS: The top 5-10 most significant revelations (ranked by newsworthiness)
3. DOCUMENT SCOPE: What types of evidence, date ranges, sources
4. PATTERNS & CONNECTIONS: Relationships, recurring themes, timeline patterns
5. LEGAL/FINANCIAL IMPLICATIONS: Potential violations, financial dealings, legal significance

FORMAT - Start directly with sections (NO preamble):

### Named Individuals Identified
[List all named people with brief context for each]

### Most Explosive Findings
[Ranked list of 5-10 most significant revelations with document references]

### Document Analysis
- Total documents processed: [number]
- Date range: [if identifiable]
- Document types: [photos, financial records, communications, etc.]

### Key Patterns & Connections
[Identify relationships, recurring locations, timeline connections]

### Legal & Financial Significance
[Potential implications, violations, financial dealings]

Be specific, factual, and concise. Total length: 400-600 words. This is for investigative journalists - prioritize newsworthiness and verifiable facts."""


def load_api_key(base_dir: Path) -> str:
    """Load GEMINI_API_KEY from .env file."""
    script_dir = Path(__file__).parent.absolute()
    
    env_paths = [
        script_dir / ".env",
        base_dir / ".env",
        script_dir.parent / ".env"
    ]
    
    for env_path in env_paths:
        if env_path.exists():
            load_dotenv(dotenv_path=env_path, override=False)
            break
    else:
        load_dotenv()
    
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        print("Error: GEMINI_API_KEY not found in .env file", file=sys.stderr)
        print(f"Checked: {env_paths}", file=sys.stderr)
        sys.exit(1)
    
    return api_key


def aggregate_all_json_files(base_dir: Path) -> Dict[str, Any]:
    """
    Read ALL JSON files and aggregate key information:
    - All named entities
    - Document metadata
    - Key findings from each file
    - Dates, locations, organizations
    """
    aggregated = {
        "named_individuals": set(),
        "organizations": set(),
        "locations": set(),
        "dates": set(),
        "document_types": defaultdict(int),
        "total_documents": 0,
        "explosive_findings": [],
        "file_samples": []  # Keep samples for context
    }
    
    # Find all JSON files (except in PIPELINE and .git)
    all_json = []
    for json_file in base_dir.rglob("*.json"):
        if "PIPELINE" not in json_file.parts and ".git" not in json_file.parts:
            all_json.append(json_file)
    
    print(f"Found {len(all_json)} JSON files to aggregate", file=sys.stderr)
    
    # Process all JSON files
    for json_file in all_json:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            aggregated["total_documents"] += 1
            
            # Extract entities if present
            if isinstance(data, dict):
                # Check for structured_data section (our JSON format)
                structured = data.get("structured_data", {})
                
                # Extract people
                if "people" in structured and structured["people"]:
                    if isinstance(structured["people"], list):
                        aggregated["named_individuals"].update(structured["people"])
                
                # Extract organizations
                if "organizations" in structured and structured["organizations"]:
                    if isinstance(structured["organizations"], list):
                        aggregated["organizations"].update(structured["organizations"])
                
                # Extract locations
                if "locations" in structured and structured["locations"]:
                    if isinstance(structured["locations"], list):
                        aggregated["locations"].update(structured["locations"])
                
                # Extract dates
                if "dates" in structured and structured["dates"]:
                    if isinstance(structured["dates"], list):
                        aggregated["dates"].update(structured["dates"])
                
                # Also check document_metadata for additional context
                metadata = data.get("document_metadata", {})
                if "date" in metadata and metadata["date"]:
                    aggregated["dates"].add(str(metadata["date"]))
                
                # Capture explosive notes/context
                if "notes" in data and data["notes"]:
                    aggregated["explosive_findings"].append({
                        "file": json_file.name,
                        "note": data["notes"]
                    })
                
                # Document type
                if "document_type" in data:
                    aggregated["document_types"][data["document_type"]] += 1
                elif "_extraction" in json_file.name:
                    aggregated["document_types"]["text_extraction"] += 1
                else:
                    aggregated["document_types"]["image_analysis"] += 1
                
                # Keep sample files for context (last 20 processed)
                if len(aggregated["file_samples"]) < 20:
                    aggregated["file_samples"].append({
                        "file": json_file.name,
                        "data": data
                    })
                    
        except Exception as e:
            print(f"Warning: Could not process {json_file.name}: {e}", file=sys.stderr)
    
    # Convert sets to sorted lists
    aggregated["named_individuals"] = sorted(list(aggregated["named_individuals"]))
    aggregated["organizations"] = sorted(list(aggregated["organizations"]))
    aggregated["locations"] = sorted(list(aggregated["locations"]))
    aggregated["dates"] = sorted(list(aggregated["dates"]))
    
    return aggregated


def generate_strategic_summary(aggregated_data: Dict[str, Any], api_key: str) -> str:
    """Send aggregated data to Gemini for strategic analysis."""
    
    if aggregated_data["total_documents"] == 0:
        return "No documents have been processed yet. Summary will appear as processing begins."
    
    # Prepare strategic analysis prompt with aggregated data
    prompt = f"""{PROMPT_STRATEGIC_SUMMARY}

AGGREGATED DATA FROM ALL PROCESSED DOCUMENTS:

Total Documents Analyzed: {aggregated_data['total_documents']}

Named Individuals Found: {len(aggregated_data['named_individuals'])}
{json.dumps(aggregated_data['named_individuals'][:50], indent=2) if aggregated_data['named_individuals'] else '[]'}

Organizations Found: {len(aggregated_data['organizations'])}
{json.dumps(aggregated_data['organizations'][:30], indent=2) if aggregated_data['organizations'] else '[]'}

Locations Identified: {len(aggregated_data['locations'])}
{json.dumps(aggregated_data['locations'][:30], indent=2) if aggregated_data['locations'] else '[]'}

Document Types:
{json.dumps(dict(aggregated_data['document_types']), indent=2)}

Sample Document Data (for context):
{json.dumps(aggregated_data['file_samples'][:10], indent=2, ensure_ascii=False)}

Now create the strategic summary as specified above. Focus on newsworthiness, named individuals, and explosive findings."""

    try:
        client = genai.Client(api_key=api_key)
        
        print(f"Sending aggregated data from {aggregated_data['total_documents']} documents to Gemini...", file=sys.stderr)
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=[types.Content(
                role="user",
                parts=[types.Part.from_text(text=prompt)]
            )]
        )
        
        summary = response.text.strip()
        
        # Clean up markdown artifacts
        if summary.startswith("```markdown"):
            summary = summary.replace("```markdown", "").replace("```", "").strip()
        elif summary.startswith("```"):
            summary = summary.replace("```", "").strip()
        
        print(f"Received strategic summary ({len(summary)} chars)", file=sys.stderr)
        return summary
        
    except Exception as e:
        print(f"Error calling Gemini API: {e}", file=sys.stderr)
        return f"""### Processing Status

- Total documents analyzed: {aggregated_data['total_documents']}
- Named individuals identified: {len(aggregated_data['named_individuals'])}
- Organizations found: {len(aggregated_data['organizations'])}
- Document types: {', '.join(aggregated_data['document_types'].keys())}

(Strategic analysis temporarily unavailable - processing continues)"""


def update_readme_with_summary(base_dir: Path) -> bool:
    """Update README.md with strategic summary."""
    readme_path = base_dir / "README.md"
    
    if not readme_path.exists():
        print(f"README.md not found at {readme_path}", file=sys.stderr)
        return False
    
    # Load API key
    try:
        api_key = load_api_key(base_dir)
    except SystemExit:
        return False
    
    # Aggregate ALL JSON files
    print("Aggregating all processed documents...", file=sys.stderr)
    aggregated_data = aggregate_all_json_files(base_dir)
    
    # Generate strategic summary
    summary_text = generate_strategic_summary(aggregated_data, api_key)
    
    # Read README
    try:
        with open(readme_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading README: {e}", file=sys.stderr)
        return False
    
    # Replace the summary section
    import re
    
    pattern = r'(### Latest Context Update\n\n)(.*?)(\n\n---)'
    
    updated_content = content
    if re.search(pattern, content, re.DOTALL):
        updated_content = re.sub(
            pattern,
            r'\1' + summary_text + r'\3',
            content,
            flags=re.DOTALL
        )
    else:
        # Add section if it doesn't exist
        status_line = "**Status:** Processing"
        if status_line in content:
            updated_content = content.replace(
                status_line,
                f"{status_line}\n\n### Latest Context Update\n\n{summary_text}\n\n---"
            )
        else:
            updated_content = content + f"\n\n### Latest Context Update\n\n{summary_text}\n\n---\n"
    
    # Only write if changed
    if updated_content != content:
        try:
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write(updated_content)
            print(f"Updated README.md with strategic summary")
            return True
        except Exception as e:
            print(f"Error writing README: {e}", file=sys.stderr)
            return False
    
    return True


def main() -> None:
    script_dir = Path(__file__).parent.absolute()
    if script_dir.name == "PIPELINE":
        base_dir = script_dir.parent
    else:
        base_dir = script_dir
    
    update_readme_with_summary(base_dir)


if __name__ == "__main__":
    main()
