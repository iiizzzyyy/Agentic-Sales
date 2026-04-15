"""
Index sales knowledge base into ChromaDB.
Indexes playbooks, call transcripts, and meeting notes with metadata type tags.

Usage: python scripts/index_playbooks.py
"""
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from pypdf import PdfReader
from tools.rag import index_document, clear_collection

# Directories to index into ChromaDB — each with a document type tag
INDEX_DIRS = [
    ("data/playbooks/", "playbook"),                         # Sales knowledge base (8 files)
    ("data/mock_crm/call_transcripts/", "call_transcript"),  # Past calls for Coach reference
    ("data/mock_crm/meeting_notes/", "meeting_note"),        # Meeting context for prep
]


def index_directory(directory: str, doc_type: str, recursive: bool = True) -> int:
    """Index all documents in a directory with a given type tag.

    Args:
        directory: Path to directory to index
        doc_type: Document type tag (e.g., 'playbook', 'coaching_script')
        recursive: If True, also index subdirectories
    """
    import glob as glob_module

    if not os.path.exists(directory):
        print(f"  Directory not found: {directory}")
        return 0

    # Get all files, optionally including subdirectories
    if recursive:
        pattern = os.path.join(directory, "**", "*")
        all_files = glob_module.glob(pattern, recursive=True)
        files = [f for f in all_files if os.path.isfile(f) and not os.path.basename(f).startswith('.')]
    else:
        files = [os.path.join(directory, f) for f in os.listdir(directory)
                 if not f.startswith('.') and os.path.isfile(os.path.join(directory, f))]

    if not files:
        print(f"  No files found in {directory}")
        return 0

    indexed_count = 0

    for filepath in files:
        filename = os.path.basename(filepath)

        # Skip manifest files
        if filename.endswith('.json'):
            continue

        # Read file based on extension
        if filename.endswith(".pdf"):
            try:
                reader = PdfReader(filepath)
                text = "\n".join(page.extract_text() or "" for page in reader.pages)
            except Exception as e:
                print(f"  Error reading PDF {filename}: {e}")
                continue
        elif filename.endswith((".txt", ".md")):
            with open(filepath, encoding="utf-8") as f:
                text = f.read()
        else:
            continue  # Skip unsupported files silently

        if not text.strip():
            print(f"  Skipping empty file: {filename}")
            continue

        # Determine doc_type — coaching scripts from transcripts get special type
        effective_doc_type = doc_type
        if "coaching_from_transcripts" in filepath:
            effective_doc_type = "coaching_script"

        # Extract additional metadata from filename
        metadata = {
            "source": filename,
            "type": effective_doc_type,
            "path": filepath,
        }

        # Add source info for coaching scripts
        if effective_doc_type == "coaching_script":
            metadata["source_type"] = "transcript_analysis"

        # Extract company name from call transcripts and meeting notes
        if effective_doc_type in ("call_transcript", "meeting_note"):
            # Filenames like: discovery_call_novatech_2026-02-18.md
            # or: prep_novatech_demo_2026-02-22.md
            parts = filename.replace(".md", "").split("_")
            # Try to find company name (usually after call type or prep/recap)
            for i, part in enumerate(parts):
                if part in ("call", "demo", "prep", "recap", "qbr"):
                    if i + 1 < len(parts):
                        metadata["company"] = parts[i + 1].title()
                        break

        print(f"  Indexing: {filename} ({len(text):,} chars) [type={effective_doc_type}]")
        index_document(text, metadata)
        indexed_count += 1

    return indexed_count


def main():
    print("=" * 60)
    print("ChromaDB Knowledge Base Indexer")
    print("=" * 60)

    # Clear existing collection for fresh index
    print("\nClearing existing ChromaDB collection...")
    clear_collection()

    total_indexed = 0

    for directory, doc_type in INDEX_DIRS:
        print(f"\nIndexing {doc_type}s from {directory}...")
        count = index_directory(directory, doc_type)
        total_indexed += count
        print(f"  → Indexed {count} {doc_type}(s)")

    print("\n" + "=" * 60)
    print(f"Done! Total documents indexed: {total_indexed}")
    print("=" * 60)

    # Print summary by type
    print("\nSummary:")
    for directory, doc_type in INDEX_DIRS:
        if os.path.exists(directory):
            count = len([f for f in os.listdir(directory)
                        if f.endswith(('.md', '.txt', '.pdf')) and not f.startswith('.')])
            print(f"  - {doc_type}: {count} files from {directory}")

    # Optional: sync HubSpot CRM data into RAG
    print("\n--- HubSpot CRM Sync ---")
    try:
        import asyncio
        from scripts.sync_hubspot_to_rag import sync_hubspot_to_rag
        asyncio.run(sync_hubspot_to_rag())
    except Exception as e:
        print(f"CRM sync skipped: {e}")
        print("To sync CRM data separately, run: python scripts/sync_hubspot_to_rag.py")


if __name__ == "__main__":
    main()
