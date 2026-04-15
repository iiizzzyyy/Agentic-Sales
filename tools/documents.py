"""
Document tools for retrieving battlecards, playbooks, and scripts.
"""
import os
import glob

DOCS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "documents")


def list_documents(doc_type=None):
    """
    List available documents.

    Args:
        doc_type: Optional filter - 'battlecards', 'playbooks', or 'scripts'

    Returns:
        List of dicts with name, type, and path
    """
    docs = []

    if doc_type:
        search_paths = [os.path.join(DOCS_PATH, doc_type, "*.md")]
    else:
        search_paths = [
            os.path.join(DOCS_PATH, "battlecards", "*.md"),
            os.path.join(DOCS_PATH, "playbooks", "*.md"),
            os.path.join(DOCS_PATH, "scripts", "*.md"),
        ]

    for pattern in search_paths:
        for filepath in glob.glob(pattern):
            doc_type_from_path = os.path.basename(os.path.dirname(filepath))
            filename = os.path.basename(filepath)
            name = filename.replace(".md", "").replace("_", " ").title()
            docs.append({
                "name": name,
                "type": doc_type_from_path,
                "filename": filename,
                "path": filepath
            })

    return docs


def get_document(filename):
    """
    Get document content by filename.

    Args:
        filename: The document filename (e.g., 'competitor_alpha.md')

    Returns:
        Dict with name, type, content or None if not found
    """
    # Search in all document directories
    for doc_type in ["battlecards", "playbooks", "scripts"]:
        filepath = os.path.join(DOCS_PATH, doc_type, filename)
        if os.path.exists(filepath):
            with open(filepath, "r") as f:
                content = f.read()
            name = filename.replace(".md", "").replace("_", " ").title()
            return {
                "name": name,
                "type": doc_type,
                "filename": filename,
                "content": content
            }

    return None


def search_documents(query):
    """
    Search documents for a query string.

    Args:
        query: Search string (case-insensitive)

    Returns:
        List of matching documents with snippet of matching content
    """
    query_lower = query.lower()
    results = []

    for doc in list_documents():
        filepath = doc["path"]
        with open(filepath, "r") as f:
            content = f.read()

        if query_lower in content.lower():
            # Find matching line for snippet
            lines = content.split("\n")
            snippet = ""
            for i, line in enumerate(lines):
                if query_lower in line.lower():
                    snippet = line.strip()[:200]
                    break

            results.append({
                "name": doc["name"],
                "type": doc["type"],
                "filename": doc["filename"],
                "snippet": snippet
            })

    return results


def get_battlecard(competitor_name):
    """
    Get battlecard for a specific competitor.

    Args:
        competitor_name: Competitor name (e.g., 'CompetitorAlpha')

    Returns:
        Dict with battlecard content or None
    """
    # Normalize name to filename format
    filename = competitor_name.lower().replace(" ", "_") + ".md"
    filepath = os.path.join(DOCS_PATH, "battlecards", filename)

    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            content = f.read()
        return {
            "competitor": competitor_name,
            "content": content
        }

    return None


def get_playbook(playbook_name):
    """
    Get a specific playbook.

    Args:
        playbook_name: Playbook name (e.g., 'discovery_methodology')

    Returns:
        Dict with playbook content or None
    """
    filename = playbook_name.lower().replace(" ", "_")
    if not filename.endswith(".md"):
        filename += ".md"

    filepath = os.path.join(DOCS_PATH, "playbooks", filename)

    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            content = f.read()
        return {
            "name": playbook_name,
            "content": content
        }

    return None
