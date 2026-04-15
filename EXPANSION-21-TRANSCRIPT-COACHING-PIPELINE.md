# EXPANSION-21: Transcript-to-Coaching Pipeline

## Goal
Build a pipeline that ingests real sales call transcripts, analyzes them with an LLM,
extracts coaching insights, and generates reusable coaching scripts that get indexed
into the RAG store. This creates a continuous learning loop where every call makes
the coaching smarter.

## Architecture Overview

```
┌─────────────────┐     ┌─────────────────┐     ┌──────────────────┐
│  Call Transcript │────▶│  LLM Analyzer   │────▶│  Coaching Script  │
│  (markdown file) │     │  (extract       │     │  (structured .md) │
│                  │     │   insights)     │     │                   │
└─────────────────┘     └─────────────────┘     └──────────────────┘
                                                         │
                                                         ▼
                                                ┌──────────────────┐
                                                │  RAG Vector Store │
                                                │  (ChromaDB)       │
                                                └──────────────────┘
                                                         │
                                                         ▼
                                          ┌──────────────────────────┐
                                          │  Coaching Commands        │
                                          │  /coach, /coach-live, etc │
                                          └──────────────────────────┘
```

## Current State
- 5 call transcripts exist in `data/mock_crm/call_transcripts/`
- Transcripts are markdown files with timestamped dialogue
- These are already indexed into ChromaDB via `index_playbooks.py`
- BUT they are indexed as raw text — no coaching annotations or insights extracted
- The coach graph queries `rag_search("roleplay {scenario} objections sales")`
  which may or may not match raw transcript chunks

## What to Build

### Step 1: Create the Transcript Analyzer Script

Create `scripts/analyze_transcripts.py`

This script:
1. Reads all transcripts from `data/mock_crm/call_transcripts/`
2. Sends each to an LLM with a structured analysis prompt
3. Extracts coaching insights in a structured format
4. Writes coaching scripts to `data/playbooks/coaching_from_transcripts/`
5. The new coaching scripts get picked up by `index_playbooks.py` on next run

```python
"""
Transcript-to-Coaching Pipeline
================================
Analyzes sales call transcripts and generates coaching scripts
that get indexed into the RAG store for coaching commands.

Usage:
    python scripts/analyze_transcripts.py                    # Analyze all transcripts
    python scripts/analyze_transcripts.py --file discovery_call_novatech_2026-02-18.md
    python scripts/analyze_transcripts.py --skip-existing    # Skip already analyzed

Prerequisites:
    - OPENROUTER_API_KEY env var set
    - Transcripts in data/mock_crm/call_transcripts/

After running:
    - Re-index: python scripts/index_playbooks.py
"""

import os
import sys
import json
import glob
import argparse
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm_factory import get_llm
from langchain_core.messages import SystemMessage, HumanMessage


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRANSCRIPTS_DIR = os.path.join(BASE_DIR, "data", "mock_crm", "call_transcripts")
OUTPUT_DIR = os.path.join(BASE_DIR, "data", "playbooks", "coaching_from_transcripts")
MANIFEST_FILE = os.path.join(OUTPUT_DIR, "analysis_manifest.json")

os.makedirs(OUTPUT_DIR, exist_ok=True)

ANALYSIS_PROMPT = """You are an expert sales coach analyzing a real sales call transcript.

TRANSCRIPT:
{transcript}

Analyze this call and generate a structured coaching script. Extract EVERY coachable moment.

Respond in EXACTLY this format (do NOT deviate):

CALL_SUMMARY:
[2-3 sentence summary of the call: who, what company, what stage, outcome]

CALL_TYPE: [discovery|demo|negotiation|cold_call|follow_up|renewal|upsell]
DIFFICULTY: [easy|medium|hard]
OVERALL_SCORE: [1-10]
REP_NAME: [name of the sales rep]
BUYER_NAME: [name of the buyer]
BUYER_TITLE: [title of the buyer]
COMPANY: [company name]

SKILLS_DEMONSTRATED:
- [Skill 1]: [specific example from the call with timestamp]
- [Skill 2]: [specific example from the call with timestamp]
- [Skill 3]: [specific example from the call with timestamp]

MISSED_OPPORTUNITIES:
- [Opportunity 1]: [what the rep should have done, with the buyer's statement that created the opening]
- [Opportunity 2]: [what the rep should have done]
- [Opportunity 3]: [what the rep should have done]

TECHNIQUE_USAGE:
- [Technique name, e.g., "SPIN Implication Question"]: [USED/MISSED] — [context]
- [Technique name]: [USED/MISSED] — [context]

BEST_MOMENT:
[Timestamp]: [Quote from the rep that was excellent] — [Why it was effective]

WORST_MOMENT:
[Timestamp]: [Quote from the rep or moment that was poor] — [What should have been said instead]

COACHING_SCRIPT:
[Write a 3-4 paragraph coaching narrative that could be used to train other reps.
Include: what made this call effective or ineffective, the key learning moments,
and specific techniques that were used or should have been used.
Write as if you are telling a coaching story: "In this call, the rep opened by...
Notice how they... A better approach would have been..."]

ROLEPLAY_SCENARIO:
[Based on this call, describe a roleplay scenario that would help a rep practice
the skills needed. Include the buyer persona, their hidden objections, and what
a successful roleplay looks like.]

TAGS: [comma-separated tags, e.g., discovery, SPIN, pricing_objection, CTO, mid_market]
"""


def load_manifest():
    """Load the analysis manifest (tracks which files have been analyzed)."""
    if os.path.exists(MANIFEST_FILE):
        with open(MANIFEST_FILE, "r") as f:
            return json.load(f)
    return {"analyzed": {}, "last_run": None}


def save_manifest(manifest):
    """Save the analysis manifest."""
    manifest["last_run"] = datetime.now().isoformat()
    with open(MANIFEST_FILE, "w") as f:
        json.dump(manifest, f, indent=2)


def analyze_transcript(transcript_path, llm):
    """Analyze a single transcript and return the coaching script."""
    with open(transcript_path, "r") as f:
        transcript = f.read()

    filename = os.path.basename(transcript_path)
    print(f"  Analyzing: {filename} ({len(transcript)} chars)...")

    response = llm.invoke([
        SystemMessage(content="You are an expert sales coach. Analyze transcripts precisely and extract actionable coaching insights."),
        HumanMessage(content=ANALYSIS_PROMPT.format(transcript=transcript)),
    ])

    return response.content


def format_coaching_script(analysis, source_file):
    """Format the LLM analysis into a markdown coaching script."""
    output = f"""# Coaching Script — Generated from: {source_file}
**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}
**Source:** data/mock_crm/call_transcripts/{source_file}

---

{analysis}

---
*This coaching script was auto-generated by the Transcript-to-Coaching Pipeline.
Source transcript: {source_file}*
"""
    return output


def main():
    parser = argparse.ArgumentParser(description="Analyze call transcripts for coaching insights")
    parser.add_argument("--file", help="Analyze a specific transcript file")
    parser.add_argument("--skip-existing", action="store_true", help="Skip already analyzed transcripts")
    parser.add_argument("--force", action="store_true", help="Re-analyze all transcripts")
    args = parser.parse_args()

    manifest = load_manifest()
    llm = get_llm()

    # Get transcript files
    if args.file:
        files = [os.path.join(TRANSCRIPTS_DIR, args.file)]
    else:
        files = sorted(glob.glob(os.path.join(TRANSCRIPTS_DIR, "*.md")))

    if not files:
        print("No transcript files found in", TRANSCRIPTS_DIR)
        return

    print(f"Found {len(files)} transcript(s) to analyze")

    analyzed_count = 0
    skipped_count = 0

    for filepath in files:
        filename = os.path.basename(filepath)

        # Skip if already analyzed (unless --force)
        if args.skip_existing and not args.force:
            if filename in manifest.get("analyzed", {}):
                print(f"  Skipping (already analyzed): {filename}")
                skipped_count += 1
                continue

        try:
            analysis = analyze_transcript(filepath, llm)

            # Generate output filename
            output_name = f"coaching_{filename}"
            output_path = os.path.join(OUTPUT_DIR, output_name)

            coaching_script = format_coaching_script(analysis, filename)

            with open(output_path, "w") as f:
                f.write(coaching_script)

            print(f"  ✓ Created: {output_name}")

            # Update manifest
            manifest["analyzed"][filename] = {
                "analyzed_at": datetime.now().isoformat(),
                "output_file": output_name,
                "transcript_size": os.path.getsize(filepath),
            }

            analyzed_count += 1

        except Exception as e:
            print(f"  ✗ Error analyzing {filename}: {e}")

    save_manifest(manifest)

    print(f"\nDone! Analyzed: {analyzed_count}, Skipped: {skipped_count}")
    print(f"Coaching scripts saved to: {OUTPUT_DIR}")
    print(f"\nNext step: Re-index the RAG store:")
    print(f"  python scripts/index_playbooks.py")


if __name__ == "__main__":
    main()
```

### Step 2: Update `index_playbooks.py` to Include Coaching Scripts

The existing `index_playbooks.py` likely indexes `data/playbooks/*.md`. It needs to ALSO index
the subdirectory `data/playbooks/coaching_from_transcripts/*.md`.

Check the current indexing logic. If it uses `glob("data/playbooks/*.md")`, change it to:
```python
# BEFORE (if this pattern):
files = glob.glob("data/playbooks/*.md")

# AFTER:
files = glob.glob("data/playbooks/*.md") + glob.glob("data/playbooks/**/*.md", recursive=True)
```

If it already uses recursive globbing, no change needed.

When indexing coaching scripts, add metadata tags:
```python
# When indexing files from coaching_from_transcripts/:
metadata = {
    "doc_type": "coaching_script",
    "source": "transcript_analysis",
    "filename": filename,
}
```

### Step 3: Add a Slash Command to Trigger Analysis

Add `/analyze-transcript` command to `app.py` for on-demand analysis of new transcripts.

```python
@app.command("/analyze-transcript")
def handle_analyze_transcript(ack, say, command):
    """Analyze call transcripts and generate coaching scripts."""
    ack()
    channel_id = command["channel_id"]
    text = command["text"].strip()

    import subprocess
    import threading

    say("Analyzing call transcripts for coaching insights... This may take 1-2 minutes.", channel=channel_id)

    def run_analysis():
        try:
            cmd = ["python", "scripts/analyze_transcripts.py"]
            if text:
                cmd.extend(["--file", text])
            else:
                cmd.append("--skip-existing")

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            if result.returncode == 0:
                # Count generated files
                import glob
                scripts = glob.glob("data/playbooks/coaching_from_transcripts/coaching_*.md")

                say(
                    text=f"✓ Transcript analysis complete!\n"
                         f"Generated {len(scripts)} coaching script(s).\n"
                         f"Re-indexing RAG store...",
                    channel=channel_id,
                )

                # Re-index
                reindex = subprocess.run(
                    ["python", "scripts/index_playbooks.py"],
                    capture_output=True, text=True, timeout=120,
                )

                if reindex.returncode == 0:
                    say(
                        text="✓ RAG store re-indexed. New coaching insights are now available in:\n"
                             "• `/coach roleplay` — richer scenarios\n"
                             "• `/coach-live` — better coaching tips\n"
                             "• `/ask` — coaching Q&A",
                        channel=channel_id,
                    )
                else:
                    say(text=f"⚠️ Re-indexing had issues: {reindex.stderr[:500]}", channel=channel_id)
            else:
                say(text=f"⚠️ Analysis error: {result.stderr[:500]}", channel=channel_id)

        except subprocess.TimeoutExpired:
            say(text="⚠️ Analysis timed out after 5 minutes.", channel=channel_id)
        except Exception as e:
            say(text=f"⚠️ Error: {str(e)}", channel=channel_id)

    # Run in background thread so we don't block Slack
    thread = threading.Thread(target=run_analysis, daemon=True)
    thread.start()
```

### Step 4: Add Transcript Upload Support (Future — Wire Up Only)

For the POC, transcripts are pre-loaded files. But wire up the infrastructure for future
file upload support.

Add a helper function in `tools/transcript_utils.py`:

```python
"""Utilities for handling call transcript ingestion."""

import os
import re
from datetime import datetime

TRANSCRIPTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "mock_crm", "call_transcripts"
)


def save_transcript(content: str, company: str, call_type: str, date: str = None) -> str:
    """Save a new transcript file and return the filepath.

    Args:
        content: The transcript text (markdown format)
        company: Company name (e.g., "NovaTech")
        call_type: Type of call (e.g., "discovery", "negotiation")
        date: Date string (YYYY-MM-DD), defaults to today

    Returns:
        Path to the saved transcript file
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    # Sanitize company name for filename
    safe_company = re.sub(r'[^\w]', '_', company.lower())
    filename = f"{call_type}_call_{safe_company}_{date}.md"
    filepath = os.path.join(TRANSCRIPTS_DIR, filename)

    with open(filepath, "w") as f:
        f.write(content)

    return filepath


def list_unanalyzed_transcripts() -> list:
    """List transcripts that haven't been analyzed yet."""
    import json
    import glob

    manifest_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "playbooks", "coaching_from_transcripts", "analysis_manifest.json"
    )

    analyzed = set()
    if os.path.exists(manifest_path):
        with open(manifest_path, "r") as f:
            manifest = json.load(f)
            analyzed = set(manifest.get("analyzed", {}).keys())

    all_transcripts = glob.glob(os.path.join(TRANSCRIPTS_DIR, "*.md"))
    unanalyzed = [
        os.path.basename(f)
        for f in all_transcripts
        if os.path.basename(f) not in analyzed
    ]

    return unanalyzed
```

### Step 5: Anonymization Helper (For Real Transcripts)

When real transcripts are used in production, they should be anonymized before analysis.

Add to `tools/transcript_utils.py`:

```python
def anonymize_transcript(content: str, replacements: dict = None) -> str:
    """Anonymize a transcript by replacing sensitive information.

    Args:
        content: Raw transcript text
        replacements: Optional dict of {real_value: anonymized_value}

    Returns:
        Anonymized transcript text
    """
    import re

    # Default patterns to anonymize
    patterns = [
        # Email addresses
        (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]'),
        # Phone numbers
        (r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[PHONE]'),
        # Dollar amounts over $1000 (may be deal-specific)
        # Don't anonymize — these are useful for coaching context
        # SSN patterns
        (r'\b\d{3}-\d{2}-\d{4}\b', '[SSN]'),
    ]

    result = content
    for pattern, replacement in patterns:
        result = re.sub(pattern, replacement, result)

    # Apply custom replacements
    if replacements:
        for real, anon in replacements.items():
            result = result.replace(real, anon)

    return result
```

## Pipeline Flow (Production Vision)

For the POC, the flow is manual:
```
1. Transcripts pre-loaded in data/mock_crm/call_transcripts/
2. Run: python scripts/analyze_transcripts.py
3. Run: python scripts/index_playbooks.py
4. Coaching commands now use the new insights
```

For production, the flow would be:
```
1. Rep completes a sales call in Gong/Chorus/Zoom
2. Webhook triggers transcript export to the pipeline
3. Transcript is anonymized (strip PII)
4. LLM analyzes and generates coaching script
5. Manager reviews and approves (optional quality gate)
6. Approved scripts are indexed into RAG
7. Next coaching session uses insights from the latest calls
```

The `/analyze-transcript` command serves as the manual trigger for steps 3-6.

## Testing

1. Run `python scripts/analyze_transcripts.py` — should analyze all 5 existing transcripts
2. Check `data/playbooks/coaching_from_transcripts/` — should have 5 coaching script files
3. Check `analysis_manifest.json` — should list all 5 files as analyzed
4. Run `python scripts/analyze_transcripts.py --skip-existing` — should skip all 5
5. Run `python scripts/index_playbooks.py` — should index the new coaching scripts
6. `/coach roleplay discovery call` — should pull coaching insights from analyzed transcripts
7. `/ask What techniques did Jordan use in the NovaTech call?` — should find the coaching script
8. `/analyze-transcript` in Slack — should trigger the pipeline and report results
9. `/analyze-transcript discovery_call_novatech_2026-02-18.md` — should analyze just that one file

## DO NOT
- Do not modify existing transcripts — they are source data
- Do not run the analyzer automatically on app startup — it's expensive (LLM calls)
- Do not store the analysis LLM responses in ChromaDB directly — write markdown files
  first, then let the standard indexer handle embedding
- Do not delete the manifest file — it tracks which transcripts have been analyzed
- Do not bypass the anonymization step for real transcripts in production
- Do not make the analyzer a blocking operation in Slack — always use a background thread
