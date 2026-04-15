"""
Sync HubSpot CRM data into ChromaDB RAG index via MCP.

Connects to the HubSpot MCP server, fetches contacts, companies, deals,
notes, and activities, formats them as searchable text documents, and
indexes them into ChromaDB alongside playbooks and other knowledge.

Usage:
    python scripts/sync_hubspot_to_rag.py

Prerequisites:
    - HUBSPOT_ACCESS_TOKEN in .env (HubSpot Private App token)
    - npm install @hubspot/mcp-server (already in project)
    - ChromaDB and HuggingFace embeddings installed (already in requirements.txt)

What it does:
    1. Starts the HubSpot MCP server as a subprocess
    2. Calls MCP tools to fetch: companies, contacts, deals, notes
    3. Formats each record as a readable text document
    4. Indexes into ChromaDB with type="crm_company", "crm_contact", "crm_deal", etc.
    5. These are then searchable via tools/rag.py alongside playbooks

After running this, the RAG index will contain real CRM data that the
/research, /deal, /draft-email, and /pipeline commands can pull from
for richer, more contextual responses.
"""

import os
import sys
import json
import asyncio

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from langchain_mcp_adapters.client import MultiServerMCPClient
from tools.rag import index_document, get_collection_stats, clear_crm_records


# --- MCP Server Config ---

HUBSPOT_MCP_CONFIG = {
    "hubspot": {
        "command": "npx",
        "args": ["@hubspot/mcp-server"],
        "env": {
            "HUBSPOT_ACCESS_TOKEN": os.environ.get("HUBSPOT_ACCESS_TOKEN", ""),
        },
        "transport": "stdio",
    }
}


# --- Formatting Functions ---
# Each function takes raw MCP tool output and formats it as readable text
# suitable for RAG chunking and semantic search.

def format_company(company: dict) -> str:
    """Format a HubSpot company record as searchable text."""
    props = company.get("properties", company)
    lines = [
        f"Company: {props.get('name', 'Unknown')}",
        f"Domain: {props.get('domain', 'N/A')}",
        f"Industry: {props.get('industry', 'N/A')}",
        f"Description: {props.get('description', 'N/A')}",
        f"City: {props.get('city', 'N/A')}",
        f"State: {props.get('state', 'N/A')}",
        f"Country: {props.get('country', 'N/A')}",
        f"Number of Employees: {props.get('numberofemployees', 'N/A')}",
        f"Annual Revenue: {props.get('annualrevenue', 'N/A')}",
        f"Lifecycle Stage: {props.get('lifecyclestage', 'N/A')}",
        f"HubSpot Owner: {props.get('hubspot_owner_id', 'N/A')}",
        f"Created: {props.get('createdate', 'N/A')}",
        f"Last Modified: {props.get('hs_lastmodifieddate', 'N/A')}",
    ]
    # Add any notes or description content
    if props.get("notes_last_updated"):
        lines.append(f"Notes Last Updated: {props['notes_last_updated']}")
    return "\n".join(lines)


def format_contact(contact: dict) -> str:
    """Format a HubSpot contact record as searchable text."""
    props = contact.get("properties", contact)
    name = f"{props.get('firstname', '')} {props.get('lastname', '')}".strip()
    lines = [
        f"Contact: {name or 'Unknown'}",
        f"Email: {props.get('email', 'N/A')}",
        f"Phone: {props.get('phone', 'N/A')}",
        f"Job Title: {props.get('jobtitle', 'N/A')}",
        f"Company: {props.get('company', 'N/A')}",
        f"Lifecycle Stage: {props.get('lifecyclestage', 'N/A')}",
        f"Lead Status: {props.get('hs_lead_status', 'N/A')}",
        f"Last Activity: {props.get('notes_last_updated', 'N/A')}",
        f"Created: {props.get('createdate', 'N/A')}",
    ]
    return "\n".join(lines)


def format_deal(deal: dict) -> str:
    """Format a HubSpot deal record as searchable text."""
    props = deal.get("properties", deal)
    lines = [
        f"Deal: {props.get('dealname', 'Unknown')}",
        f"Amount: ${props.get('amount', 'N/A')}",
        f"Stage: {props.get('dealstage', 'N/A')}",
        f"Pipeline: {props.get('pipeline', 'N/A')}",
        f"Close Date: {props.get('closedate', 'N/A')}",
        f"Deal Type: {props.get('dealtype', 'N/A')}",
        f"Owner: {props.get('hubspot_owner_id', 'N/A')}",
        f"Created: {props.get('createdate', 'N/A')}",
        f"Last Modified: {props.get('hs_lastmodifieddate', 'N/A')}",
    ]
    # Add associated company if available
    if props.get("associations"):
        lines.append(f"Associated Company: {props['associations']}")
    return "\n".join(lines)


def format_note(note: dict) -> str:
    """Format a HubSpot note/engagement as searchable text."""
    props = note.get("properties", note)
    lines = [
        f"Note/Activity",
        f"Type: {props.get('hs_engagement_type', props.get('type', 'N/A'))}",
        f"Body: {props.get('hs_body_preview', props.get('body', 'N/A'))}",
        f"Created: {props.get('hs_createdate', props.get('createdate', 'N/A'))}",
        f"Last Modified: {props.get('hs_lastmodifieddate', 'N/A')}",
    ]
    return "\n".join(lines)


# --- MCP Tool Callers ---
# These functions call HubSpot MCP tools and handle the response parsing.

async def batch_read_objects(tools: list, object_type: str, ids: list, properties: list) -> list:
    """
    Use hubspot-batch-read-objects to fetch full properties for a list of IDs.
    Returns list of enriched records.
    """
    tool = None
    for t in tools:
        if t.name == "hubspot-batch-read-objects":
            tool = t
            break

    if not tool or not ids:
        return []

    try:
        # HubSpot batch read expects 'inputs' array with id objects
        inputs = [{"id": str(id)} for id in ids[:100]]
        result = await tool.ainvoke({
            "objectType": object_type,
            "inputs": inputs,
            "properties": properties,
        })
        records, _ = parse_mcp_result_with_paging(result)
        return records
    except Exception as e:
        print(f"    Warning: batch-read failed: {e}")
        return []


async def fetch_and_index(tools: list, tool_name: str, format_fn, doc_type: str,
                          call_args: dict = None, paginate: bool = True) -> int:
    """
    Call an MCP tool, format the results, and index into ChromaDB.
    Supports pagination for large datasets.
    Uses batch-read to enrich records with full properties.

    Args:
        tools: List of MCP tools
        tool_name: Name of the MCP tool to invoke (e.g., "search_companies")
        format_fn: Function to format each record as text
        doc_type: ChromaDB metadata type tag (e.g., "crm_company")
        call_args: Arguments to pass to the MCP tool
        paginate: Whether to paginate through all results

    Returns:
        Number of records indexed
    """
    # Find the tool by name
    tool = None
    for t in tools:
        if t.name == tool_name:
            tool = t
            break

    if not tool:
        print(f"  Tool '{tool_name}' not found. Available tools: {[t.name for t in tools]}")
        return 0

    # Extract properties and objectType for batch-read enrichment
    properties = call_args.get("properties", []) if call_args else []
    object_type = call_args.get("objectType", "") if call_args else ""

    total_indexed = 0
    after = None  # Pagination cursor
    page = 1
    max_pages = 20  # Safety limit to prevent infinite loops

    while page <= max_pages:
        try:
            # Build call args with pagination (exclude properties - search doesn't use them)
            args = {k: v for k, v in (call_args or {}).items() if k != "properties"}
            if after:
                args["after"] = after

            # Invoke the MCP tool to get IDs
            result = await tool.ainvoke(args)

            # Parse the result — MCP tools return content in various formats
            records, next_after = parse_mcp_result_with_paging(result)

            if not records:
                break

            # Enrich records with batch-read if we have properties to fetch
            if properties and object_type:
                record_ids = [r.get("id") for r in records if r.get("id")]
                if record_ids:
                    enriched = await batch_read_objects(tools, object_type, record_ids, properties)
                    if enriched:
                        # Build lookup by ID (handle both string and int IDs)
                        enriched_by_id = {str(r.get("id")): r for r in enriched if r.get("id")}
                        # Merge enriched data into records
                        merged_count = 0
                        for record in records:
                            rid = str(record.get("id")) if record.get("id") else None
                            if rid and rid in enriched_by_id:
                                enriched_props = enriched_by_id[rid].get("properties", {})
                                if "properties" not in record:
                                    record["properties"] = {}
                                record["properties"].update(enriched_props)
                                merged_count += 1
                        if page == 1 and merged_count > 0:
                            # Debug: show sample enriched record on first page
                            sample = records[0].get("properties", {})
                            print(f"    [Enriched {merged_count} records, sample industry: {sample.get('industry', 'missing')}]")

            indexed = 0
            for record in records:
                text = format_fn(record)
                if not text or len(text.strip()) < 20:
                    continue

                # Build metadata
                props = record.get("properties", record)
                record_id = record.get("id", props.get("hs_object_id", f"unknown_{indexed}"))
                name = (props.get("name") or props.get("dealname") or
                        f"{props.get('firstname', '')} {props.get('lastname', '')}".strip() or
                        f"record_{record_id}")

                metadata = {
                    "source": f"hubspot_{doc_type}_{record_id}",
                    "type": doc_type,
                    "name": name,
                    "hubspot_id": str(record_id),
                }

                # Add company name for cross-referencing
                if props.get("company"):
                    metadata["company"] = props["company"]
                elif props.get("name") and doc_type == "crm_company":
                    metadata["company"] = props["name"]
                elif doc_type == "crm_deal" and props.get("dealname"):
                    # Extract company name from deal name (format: "Company - Deal Type")
                    deal_name = props.get("dealname", "")
                    if " - " in deal_name:
                        metadata["company"] = deal_name.split(" - ")[0].strip()

                index_document(text, metadata)
                indexed += 1

            total_indexed += indexed
            print(f"    Page {page}: {indexed} records (total: {total_indexed})")

            # Check for more pages
            if not paginate or not next_after:
                break

            after = next_after
            page += 1

        except Exception as e:
            print(f"  Error calling {tool_name}: {e}")
            break

    return total_indexed


def parse_mcp_result_with_paging(result) -> tuple:
    """
    Parse MCP tool result into a list of records and pagination cursor.
    Returns (records, next_cursor)
    """
    records = []
    next_after = None

    # Handle list of MCP content blocks: [{'type': 'text', 'text': '{"results": [...]}'}]
    if isinstance(result, list):
        if len(result) > 0 and isinstance(result[0], dict) and 'type' in result[0] and 'text' in result[0]:
            text_content = result[0].get('text', '')
            try:
                parsed = json.loads(text_content)
                if isinstance(parsed, dict):
                    records = parsed.get("results", [])
                    # Check for HubSpot pagination
                    paging = parsed.get("paging", {})
                    next_link = paging.get("next", {})
                    next_after = next_link.get("after")
                elif isinstance(parsed, list):
                    records = parsed
            except json.JSONDecodeError:
                pass
        else:
            records = result

    return records, next_after


def parse_mcp_result(result) -> list:
    """
    Parse MCP tool result into a list of records.
    MCP tools can return data in different formats depending on the server.
    """
    # Handle list of MCP content blocks: [{'type': 'text', 'text': '{"results": [...]}'}]
    if isinstance(result, list):
        # Check if it's a list of MCP content blocks
        if len(result) > 0 and isinstance(result[0], dict) and 'type' in result[0] and 'text' in result[0]:
            # Extract text content and parse as JSON
            text_content = result[0].get('text', '')
            try:
                parsed = json.loads(text_content)
                if isinstance(parsed, dict) and "results" in parsed:
                    return parsed["results"]
                if isinstance(parsed, list):
                    return parsed
                return [parsed]
            except json.JSONDecodeError:
                return []
        # Otherwise treat as list of records
        return result

    # If it's a string, try to parse as JSON
    if isinstance(result, str):
        try:
            parsed = json.loads(result)
            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, dict):
                # HubSpot often wraps results in {"results": [...]}
                if "results" in parsed:
                    return parsed["results"]
                return [parsed]
        except json.JSONDecodeError:
            return []

    # If it's a dict with results key
    if isinstance(result, dict):
        if "results" in result:
            return result["results"]
        return [result]

    # LangChain tool results might be wrapped
    if hasattr(result, "content"):
        return parse_mcp_result(result.content)

    return []


# --- Main Sync Logic ---

async def sync_hubspot_to_rag():
    """
    Main sync function: connects to HubSpot MCP, fetches all CRM data,
    and indexes it into ChromaDB.
    """
    print("=" * 60)
    print("HubSpot → ChromaDB RAG Sync")
    print("=" * 60)

    # Verify environment
    if not os.environ.get("HUBSPOT_ACCESS_TOKEN"):
        print("\nERROR: HUBSPOT_ACCESS_TOKEN not found in .env")
        print("Get a Private App token from:")
        print("  HubSpot → Settings → Integrations → Private Apps → Create")
        print("Required scopes: crm.objects.contacts.read, crm.objects.companies.read,")
        print("  crm.objects.deals.read, crm.objects.notes.read")
        sys.exit(1)

    # Clear existing CRM records before syncing (keeps playbooks intact)
    print("\nClearing old CRM records from RAG index...")
    clear_crm_records()

    print("\nConnecting to HubSpot MCP server...")

    # Create client (new API - no context manager)
    client = MultiServerMCPClient(HUBSPOT_MCP_CONFIG)
    try:
        tools = await client.get_tools()
        tool_names = [t.name for t in tools]
        print(f"Connected! Available tools: {tool_names}")

        total_indexed = 0

        # The HubSpot MCP server uses hubspot-search-objects for all object types
        # We pass objectType parameter to specify what to search

        # --- Fetch Companies ---
        print("\n--- Syncing Companies ---")
        company_properties = [
            "name", "domain", "industry", "description", "city", "state", "country",
            "numberofemployees", "annualrevenue", "lifecyclestage", "hubspot_owner_id",
            "createdate", "hs_lastmodifieddate", "phone", "website", "address", "zip",
            "notes_last_updated", "hs_lead_status", "type"
        ]
        if "hubspot-search-objects" in tool_names:
            count = await fetch_and_index(
                tools, "hubspot-search-objects", format_company, "crm_company",
                {"objectType": "companies", "searchTerm": "", "limit": 100, "properties": company_properties}
            )
            print(f"  → Indexed {count} companies")
            total_indexed += count
        elif "hubspot-list-objects" in tool_names:
            count = await fetch_and_index(
                tools, "hubspot-list-objects", format_company, "crm_company",
                {"objectType": "companies", "limit": 100, "properties": company_properties}
            )
            print(f"  → Indexed {count} companies")
            total_indexed += count
        else:
            print("  No company search tool found — skipping")

        # --- Fetch Contacts ---
        print("\n--- Syncing Contacts ---")
        contact_properties = [
            "firstname", "lastname", "email", "phone", "jobtitle", "company",
            "lifecyclestage", "hs_lead_status", "createdate", "notes_last_updated",
            "mobilephone", "address", "city", "state", "zip", "country",
            "hubspot_owner_id", "hs_lastmodifieddate"
        ]
        if "hubspot-search-objects" in tool_names:
            count = await fetch_and_index(
                tools, "hubspot-search-objects", format_contact, "crm_contact",
                {"objectType": "contacts", "searchTerm": "", "limit": 100, "properties": contact_properties}
            )
            print(f"  → Indexed {count} contacts")
            total_indexed += count
        elif "hubspot-list-objects" in tool_names:
            count = await fetch_and_index(
                tools, "hubspot-list-objects", format_contact, "crm_contact",
                {"objectType": "contacts", "limit": 100, "properties": contact_properties}
            )
            print(f"  → Indexed {count} contacts")
            total_indexed += count
        else:
            print("  No contact search tool found — skipping")

        # --- Fetch Deals ---
        print("\n--- Syncing Deals ---")
        deal_properties = [
            "dealname", "amount", "dealstage", "pipeline", "closedate", "dealtype",
            "hubspot_owner_id", "createdate", "hs_lastmodifieddate", "description",
            "hs_priority", "hs_deal_stage_probability", "notes_last_updated"
        ]
        if "hubspot-search-objects" in tool_names:
            count = await fetch_and_index(
                tools, "hubspot-search-objects", format_deal, "crm_deal",
                {"objectType": "deals", "searchTerm": "", "limit": 100, "properties": deal_properties}
            )
            print(f"  → Indexed {count} deals")
            total_indexed += count
        elif "hubspot-list-objects" in tool_names:
            count = await fetch_and_index(
                tools, "hubspot-list-objects", format_deal, "crm_deal",
                {"objectType": "deals", "limit": 100, "properties": deal_properties}
            )
            print(f"  → Indexed {count} deals")
            total_indexed += count
        else:
            print("  No deal search tool found — skipping")

        # --- Fetch Notes/Engagements ---
        print("\n--- Syncing Notes ---")
        if "hubspot-list-objects" in tool_names:
            count = await fetch_and_index(
                tools, "hubspot-list-objects", format_note, "crm_note",
                {"objectType": "notes", "limit": 100}
            )
            print(f"  → Indexed {count} notes")
            total_indexed += count
        else:
            print("  No note search tool found — skipping")

    finally:
        # Clean up client if needed
        pass

    # Print final stats
    stats = get_collection_stats()
    print("\n" + "=" * 60)
    print(f"Sync complete! Indexed {total_indexed} CRM records")
    print(f"Total ChromaDB chunks: {stats['total_chunks']}")
    print("=" * 60)

    print("\nCRM data is now searchable via RAG. Example queries:")
    print('  rag.search("NovaTech deal status")')
    print('  rag.search("VP Engineering contacts")')
    print('  rag.search("deals closing this month", doc_type="crm_deal")')


if __name__ == "__main__":
    asyncio.run(sync_hubspot_to_rag())
