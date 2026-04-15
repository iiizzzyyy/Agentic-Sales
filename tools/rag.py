"""ChromaDB RAG - index and search sales playbooks, call transcripts, meeting notes."""

import chromadb
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Initialize ChromaDB with persistent storage
CHROMA_PATH = "./chroma_db"
COLLECTION_NAME = "sales_knowledge"

client = chromadb.PersistentClient(path=CHROMA_PATH)
collection = client.get_or_create_collection(COLLECTION_NAME)

# Initialize embeddings (local HuggingFace - no API key needed)
embeddings = None


def get_embeddings():
    """Lazy initialization of embeddings client."""
    global embeddings
    if embeddings is None:
        embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    return embeddings


def clear_collection():
    """Delete and recreate the collection for fresh indexing."""
    global collection
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass  # Collection might not exist
    collection = client.get_or_create_collection(COLLECTION_NAME)
    print(f"Collection '{COLLECTION_NAME}' cleared.")


def clear_crm_records():
    """Delete only CRM records from the collection, keeping playbooks intact."""
    global collection
    crm_types = ["crm_company", "crm_contact", "crm_deal", "crm_note"]
    total_deleted = 0
    for crm_type in crm_types:
        try:
            # Get all IDs matching this type
            results = collection.get(where={"type": crm_type})
            if results and results.get("ids"):
                ids_to_delete = results["ids"]
                if ids_to_delete:
                    collection.delete(ids=ids_to_delete)
                    total_deleted += len(ids_to_delete)
        except Exception as e:
            print(f"  Warning: Could not clear {crm_type}: {e}")
    print(f"  Cleared {total_deleted} CRM records from RAG index.")


def index_document(text: str, metadata: dict):
    """Add a document to the RAG index."""
    emb = get_embeddings()
    if not emb:
        raise ValueError("Embeddings not initialized")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=75
    )
    chunks = splitter.split_text(text)

    for i, chunk in enumerate(chunks):
        embedding = emb.embed_query(chunk)
        collection.add(
            documents=[chunk],
            embeddings=[embedding],
            metadatas=[{**metadata, "chunk_index": i}],
            ids=[f"{metadata.get('source', 'doc')}_{i}"]
        )


def search(query: str, n_results: int = 5, doc_type: str = None) -> str:
    """Search the RAG index. Return formatted context string.

    Args:
        query: Search query
        n_results: Number of results to return
        doc_type: Optional filter by document type ('playbook', 'call_transcript', 'meeting_note')
    """
    emb = get_embeddings()
    if not emb:
        return "RAG not available (embeddings not initialized)"

    query_embedding = emb.embed_query(query)

    # Build where clause for type filtering
    where = {"type": doc_type} if doc_type else None

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        where=where
    )

    if not results["documents"] or not results["documents"][0]:
        return "No relevant content found."

    # Combine chunks into context string with source attribution
    formatted_results = []
    for i, (doc, meta) in enumerate(zip(results["documents"][0], results["metadatas"][0])):
        source = meta.get("source", "unknown")
        doc_type_label = meta.get("type", "document")
        formatted_results.append(f"[{doc_type_label}: {source}]\n{doc}")

    return "\n\n---\n\n".join(formatted_results)


def search_playbooks(query: str, n_results: int = 5) -> str:
    """Search only playbook documents."""
    return search(query, n_results, doc_type="playbook")


def search_call_transcripts(query: str, n_results: int = 3) -> str:
    """Search only call transcript documents."""
    return search(query, n_results, doc_type="call_transcript")


def search_meeting_notes(query: str, n_results: int = 3) -> str:
    """Search only meeting note documents."""
    return search(query, n_results, doc_type="meeting_note")


def search_crm_companies(query: str, n_results: int = 5) -> str:
    """Search CRM company records synced from HubSpot."""
    return search(query, n_results, doc_type="crm_company")


def search_crm_contacts(query: str, n_results: int = 5) -> str:
    """Search CRM contact records synced from HubSpot."""
    return search(query, n_results, doc_type="crm_contact")


def search_crm_deals(query: str, n_results: int = 5) -> str:
    """Search CRM deal records synced from HubSpot."""
    return search(query, n_results, doc_type="crm_deal")


def search_contacts_by_company(company_name: str, n_results: int = 5) -> str:
    """Search contacts filtered by company name.

    Uses fuzzy matching to handle spelling variations (e.g., Kaffekassan vs Kaffekassen).
    """
    emb = get_embeddings()
    if not emb:
        return "RAG not available"

    # Get all contacts and filter by fuzzy company name match
    results = collection.get(
        where={"type": "crm_contact"},
        limit=200
    )

    if not results.get("documents"):
        return f"No contacts found for {company_name}"

    # Fuzzy match: check if company names share a common prefix (first 6+ chars)
    search_prefix = company_name.lower()[:6] if len(company_name) >= 6 else company_name.lower()

    filtered_docs = []
    filtered_metas = []
    for doc, meta in zip(results["documents"], results["metadatas"]):
        meta_company = meta.get("company", "").lower()
        # Match if: exact match, contains, or shares prefix
        if (company_name.lower() == meta_company or
            company_name.lower() in meta_company or
            meta_company.startswith(search_prefix) or
            (len(meta_company) >= 6 and meta_company[:6] == search_prefix)):
            filtered_docs.append(doc)
            filtered_metas.append(meta)

    if not filtered_docs:
        return f"No contacts found for {company_name}"

    formatted = []
    for doc, meta in zip(filtered_docs[:n_results], filtered_metas[:n_results]):
        source = meta.get("source", "unknown")
        formatted.append(f"[crm_contact: {source}]\n{doc}")

    return "\n\n---\n\n".join(formatted)


def search_deals_by_company(company_name: str, n_results: int = 5) -> str:
    """Search deals for a company using fuzzy matching.

    Handles spelling variations (e.g., Kaffekassan vs Kaffekassen).
    """
    emb = get_embeddings()
    if not emb:
        return "RAG not available"

    # Get all deals and filter by fuzzy company name match
    results = collection.get(
        where={"type": "crm_deal"},
        limit=200
    )

    if not results.get("documents"):
        return f"No deals found for {company_name}"

    # Fuzzy match: check company metadata and document text
    search_prefix = company_name.lower()[:6] if len(company_name) >= 6 else company_name.lower()

    filtered_docs = []
    filtered_metas = []
    for doc, meta in zip(results["documents"], results["metadatas"]):
        meta_company = meta.get("company", "").lower()
        doc_lower = doc.lower()

        # Match if: metadata matches, or document text contains similar company name
        matches = (
            company_name.lower() == meta_company or
            company_name.lower() in meta_company or
            meta_company.startswith(search_prefix) or
            search_prefix in doc_lower or
            (len(meta_company) >= 6 and meta_company[:6] == search_prefix)
        )

        if matches:
            filtered_docs.append(doc)
            filtered_metas.append(meta)

    if not filtered_docs:
        return f"No deals found for {company_name}"

    formatted = []
    for doc, meta in zip(filtered_docs[:n_results], filtered_metas[:n_results]):
        source = meta.get("source", "unknown")
        formatted.append(f"[crm_deal: {source}]\n{doc}")

    return "\n\n---\n\n".join(formatted)


def search_crm(query: str, n_results: int = 5) -> str:
    """Search ALL CRM data (companies, contacts, deals, notes) from HubSpot."""
    # Search across all CRM types and merge results
    crm_types = ["crm_company", "crm_contact", "crm_deal", "crm_note"]
    all_results = []

    emb = get_embeddings()
    if not emb:
        return "RAG not available (embeddings not initialized)"

    query_embedding = emb.embed_query(query)

    for crm_type in crm_types:
        try:
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=2,  # Get top 2 from each type
                where={"type": crm_type}
            )
            if results["documents"] and results["documents"][0]:
                for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
                    source = meta.get("source", "unknown")
                    all_results.append(f"[{crm_type}: {source}]\n{doc}")
        except Exception:
            continue

    if not all_results:
        return "No CRM data found. Run: python scripts/sync_hubspot_to_rag.py"

    return "\n\n---\n\n".join(all_results[:n_results])


def get_collection_stats() -> dict:
    """Get statistics about the indexed collection."""
    count = collection.count()
    return {
        "total_chunks": count,
        "collection_name": COLLECTION_NAME,
        "path": CHROMA_PATH,
    }
