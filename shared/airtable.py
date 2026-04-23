"""
Airtable integration for GEO prospect discovery.
Auto-creates records in Airtable base after each discovery run.
"""

import json
import os
from typing import Optional

import httpx

AIRTABLE_TOKEN = os.environ.get("AIRTABLE_TOKEN", "")
AIRTABLE_BASE_ID = os.environ.get("AIRTABLE_BASE_ID", "")
AIRTABLE_TABLE_NAME = os.environ.get("AIRTABLE_TABLE_NAME", "GEO Prospects")

AIRTABLE_API_URL = "https://api.airtable.com/v0"


class AirtableClient:
    """Client for Airtable API operations."""
    
    def __init__(self, token: Optional[str] = None, base_id: Optional[str] = None):
        self.token = token or AIRTABLE_TOKEN
        self.base_id = base_id or AIRTABLE_BASE_ID
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
    
    def is_configured(self) -> bool:
        """Check if Airtable is properly configured."""
        return bool(self.token and self.base_id)
    
    def create_record(self, table_name: str, fields: dict) -> dict:
        """Create a single record in Airtable."""
        url = f"{AIRTABLE_API_URL}/{self.base_id}/{table_name}"
        
        payload = {"fields": fields}
        
        resp = httpx.post(
            url,
            headers=self.headers,
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()
    
    def create_records(self, table_name: str, records: list[dict]) -> dict:
        """Create multiple records in Airtable (batch, max 10 per call)."""
        url = f"{AIRTABLE_API_URL}/{self.base_id}/{table_name}"
        
        results = {"records": [], "errors": []}
        
        # Process in batches of 10
        for i in range(0, len(records), 10):
            batch = records[i:i + 10]
            payload = {"records": [{"fields": r} for r in batch]}
            
            resp = httpx.post(
                url,
                headers=self.headers,
                json=payload,
                timeout=30,
            )
            
            if resp.status_code == 200:
                data = resp.json()
                results["records"].extend(data.get("records", []))
            else:
                results["errors"].append({
                    "batch": i // 10,
                    "status": resp.status_code,
                    "error": resp.text,
                })
        
        return results
    
    def list_bases(self) -> list[dict]:
        """List available Airtable bases (for finding base ID)."""
        url = "https://api.airtable.com/v0/meta/bases"
        
        resp = httpx.get(
            url,
            headers=self.headers,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("bases", [])
    
    def list_tables(self, base_id: Optional[str] = None) -> list[dict]:
        """List tables in a base."""
        base = base_id or self.base_id
        url = f"https://api.airtable.com/v0/meta/bases/{base}/tables"
        
        resp = httpx.get(
            url,
            headers=self.headers,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("tables", [])


def prospect_to_airtable_fields(prospect: dict) -> dict:
    """Convert a prospect dict to Airtable field format."""
    geo_score = prospect.get("geo_score", {})
    contacts = prospect.get("contacts", {})
    geo_analysis = prospect.get("geo_analysis", {})
    
    # Map to existing Airtable fields
    emails = contacts.get("emails", [])
    fields = {
        "company_name": prospect.get("company_name", ""),
        "website": prospect.get("website", ""),
        "geo_score": geo_score.get("normalized", 0),
        "priority": prospect.get("priority", ""),
        "contacts.emails": emails[0] if emails else "",
        "geo_analysis.gaps": "\n".join(geo_analysis.get("gaps", [])) if geo_analysis.get("gaps") else "",
    }
    
    return fields


def export_prospects_to_airtable(
    prospects: list[dict],
    table_name: Optional[str] = None,
    verbose: bool = True,
) -> dict:
    """
    Export prospects to Airtable.
    
    Args:
        prospects: List of prospect dicts (from CRMFormatter)
        table_name: Airtable table name (default from env)
        verbose: Print progress
        
    Returns:
        Result dict with created records and any errors
    """
    client = AirtableClient()
    table = table_name or AIRTABLE_TABLE_NAME
    
    if not client.is_configured():
        if verbose:
            print("⚠️ Airtable not configured. Set AIRTABLE_TOKEN and AIRTABLE_BASE_ID in .env")
        return {"error": "Airtable not configured", "records": []}
    
    # Convert prospects to Airtable fields
    records = [prospect_to_airtable_fields(p) for p in prospects]
    
    if verbose:
        print(f"\n📤 Exporting {len(records)} prospects to Airtable...")
    
    try:
        result = client.create_records(table, records)
        
        created = len(result.get("records", []))
        errors = len(result.get("errors", []))
        
        if verbose:
            print(f"  ✓ Created {created} records")
            if errors:
                print(f"  ✗ {errors} errors")
        
        return result
        
    except Exception as e:
        if verbose:
            print(f"  ✗ Airtable export failed: {e}")
        return {"error": str(e), "records": []}


# CLI helper
if __name__ == "__main__":
    import sys
    
    client = AirtableClient()
    
    if not client.is_configured():
        print("Error: AIRTABLE_TOKEN and AIRTABLE_BASE_ID must be set in .env")
        sys.exit(1)
    
    # List bases
    print("Available Airtable bases:")
    for base in client.list_bases():
        print(f"  {base['id']}: {base['name']}")
    
    # If base_id is set, list tables
    if client.base_id:
        print(f"\nTables in base {client.base_id}:")
        for table in client.list_tables():
            print(f"  {table['id']}: {table['name']}")
