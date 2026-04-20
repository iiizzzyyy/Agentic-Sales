#!/usr/bin/env python3
"""
Generate synthetic demo data for SalesCoach AI.

Creates a complete, coherent demo environment encoding the Sarah Chen/DataFlow Inc narrative.

Usage:
    python scripts/generate_demo_data.py --mode json              # JSON files only
    python scripts/generate_demo_data.py --mode hubspot --token XXX  # Push to HubSpot
    python scripts/generate_demo_data.py --mode both --dry-run    # Both modes, dry run
    python scripts/generate_demo_data.py --verify                 # Verify data integrity
"""

import os
import sys
import json
import random
import argparse
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

# ============================================================================
# NARRATIVE CONFIGURATION
# ============================================================================

@dataclass
class DemoNarrativeConfig:
    """Encodes the complete demo story as configuration."""

    # Flagship company: DataFlow Inc
    flagship_company: Dict = field(default_factory=lambda: {
        "name": "DataFlow Inc",
        "domain": "dataflow.io",
        "industry": "Data Infrastructure",
        "employees": "100-250",
        "city": "San Jose",
        "state": "CA",
        "revenue": "20000000",
        "description": "Real-time data pipeline solutions for enterprise customers. Building the next generation of streaming data infrastructure."
    })

    # Flagship contacts with roles
    flagship_contacts: List[Dict] = field(default_factory=lambda: [
        {"firstname": "Priya", "lastname": "Sharma", "email": "priya.sharma@dataflow.io", "jobtitle": "VP of Engineering", "role": "champion", "phone": "+1-408-555-2341"},
        {"firstname": "Marcus", "lastname": "Chen", "email": "marcus.chen@dataflow.io", "jobtitle": "CTO", "role": "technical_champion", "phone": "+1-408-555-2342"},
        {"firstname": "Jennifer", "lastname": "Liu", "email": "jennifer.liu@dataflow.io", "jobtitle": "CFO", "role": "economic_buyer", "phone": "+1-408-555-2343"},
        {"firstname": "Raj", "lastname": "Gupta", "email": "raj.gupta@dataflow.io", "jobtitle": "CRO", "role": "influencer", "phone": "+1-408-555-2344"},
    ])

    # Flagship deal details
    flagship_deal: Dict = field(default_factory=lambda: {
        "name": "DataFlow Inc — Enterprise Platform License",
        "amount": "180000",
        "stage": "negotiation",
        "close_date": "2026-04-30",
        "competitor": "CompetitorBeta",
        "timeline_driver": "Q2 Sales Kickoff April 20"
    })

    # Hero rep: Sarah Chen
    hero_rep: Dict = field(default_factory=lambda: {
        "firstname": "Sarah",
        "lastname": "Chen",
        "email": "sarah.chen@ourcompany.com",
        "role": "Senior Account Executive",
        "performance": "strong",
        "flagship_deal": "dataflow_inc"
    })

    # Manager: Marcus Rodriguez
    manager: Dict = field(default_factory=lambda: {
        "firstname": "Marcus",
        "lastname": "Rodriguez",
        "email": "marcus.rodriguez@ourcompany.com",
        "role": "Sales Manager",
        "team_size": 8
    })

    # 6 additional reps with varying performance
    supporting_reps: List[Dict] = field(default_factory=lambda: [
        {"firstname": "Jordan", "lastname": "Mitchell", "email": "jordan.mitchell@ourcompany.com", "role": "Account Executive", "performance": "strong", "specialty": "enterprise"},
        {"firstname": "Alex", "lastname": "Rivera", "email": "alex.rivera@ourcompany.com", "role": "Account Executive", "performance": "struggling", "needs_coaching": True},
        {"firstname": "Taylor", "lastname": "Nguyen", "email": "taylor.nguyen@ourcompany.com", "role": "Account Executive", "performance": "average", "tenure": "6_months"},
        {"firstname": "Casey", "lastname": "Brooks", "email": "casey.brooks@ourcompany.com", "role": "Account Executive", "performance": "strong", "specialty": "mid_market"},
        {"firstname": "Morgan", "lastname": "Taylor", "email": "morgan.taylor@ourcompany.com", "role": "Account Executive", "performance": "average", "tenure": "1_year"},
        {"firstname": "Nina", "lastname": "Patel", "email": "nina.patel@ourcompany.com", "role": "Sales Development Rep", "performance": "new_hire", "ramp_status": "active"},
    ])

    # Supporting companies (7 more to make 8 total)
    supporting_companies: List[Dict] = field(default_factory=lambda: [
        {"name": "NovaTech Solutions", "domain": "novatech.io", "industry": "Enterprise Software", "employees": "250-500", "city": "Austin", "state": "TX", "revenue": "15000000"},
        {"name": "CloudBridge Systems", "domain": "cloudbridge.com", "industry": "Cloud Infrastructure", "employees": "500-1000", "city": "Seattle", "state": "WA", "revenue": "45000000"},
        {"name": "Apex Manufacturing", "domain": "apexmfg.com", "industry": "Manufacturing", "employees": "1000-5000", "city": "Detroit", "state": "MI", "revenue": "120000000"},
        {"name": "Velocity Retail", "domain": "velocityretail.com", "industry": "Retail Tech", "employees": "100-250", "city": "Chicago", "state": "IL", "revenue": "25000000"},
        {"name": "Meridian Healthcare", "domain": "meridianhc.com", "industry": "Healthcare Tech", "employees": "500-1000", "city": "Boston", "state": "MA", "revenue": "65000000"},
        {"name": "QuantumLeap AI", "domain": "quantumleap.ai", "industry": "AI/ML", "employees": "50-100", "city": "Palo Alto", "state": "CA", "revenue": "8000000"},
        {"name": "Greenfield Analytics", "domain": "greenfieldanalytics.com", "industry": "Data Analytics", "employees": "50-100", "city": "Denver", "state": "CO", "revenue": "5000000"},
    ])

    # Training history for Sarah Chen (showing improvement)
    sarah_training_history: List[Dict] = field(default_factory=lambda: [
        {"scenario": "negotiation", "score": 6.5, "date": "2026-01-15", "turns": 6, "feedback": "Needs work on handling price objections"},
        {"scenario": "negotiation", "score": 7.2, "date": "2026-02-01", "turns": 6, "feedback": "Better value framing, still conceding too quickly"},
        {"scenario": "negotiation", "score": 7.8, "date": "2026-02-15", "turns": 8, "feedback": "Strong trade-offs, using silence effectively"},
        {"scenario": "negotiation", "score": 8.4, "date": "2026-03-01", "turns": 8, "feedback": "Excellent negotiation discipline, anchoring well"},
    ])


# ============================================================================
# ID REGISTRY
# ============================================================================

class IDRegistry:
    """Central registry for all generated IDs to ensure referential integrity."""

    def __init__(self):
        self.companies: Dict[str, str] = {}  # name -> id
        self.contacts: Dict[str, str] = {}   # email -> id
        self.deals: Dict[str, str] = {}      # deal_key -> id
        self.meetings: Dict[str, str] = {}   # meeting_key -> id
        self.owners: Dict[str, str] = {}     # email -> id

    def register_company(self, name: str, company_id: str) -> str:
        self.companies[name] = company_id
        return company_id

    def get_company_id(self, name: str) -> Optional[str]:
        return self.companies.get(name)

    def register_contact(self, email: str, contact_id: str) -> str:
        self.contacts[email] = contact_id
        return contact_id

    def get_contact_id(self, email: str) -> Optional[str]:
        return self.contacts.get(email)

    def register_deal(self, deal_key: str, deal_id: str) -> str:
        self.deals[deal_key] = deal_id
        return deal_id

    def get_deal_id(self, deal_key: str) -> Optional[str]:
        return self.deals.get(deal_key)

    def register_meeting(self, meeting_key: str, meeting_id: str) -> str:
        self.meetings[meeting_key] = meeting_id
        return meeting_id

    def get_meeting_id(self, meeting_key: str) -> Optional[str]:
        return self.meetings.get(meeting_key)

    def register_owner(self, email: str, owner_id: str) -> str:
        self.owners[email] = owner_id
        return owner_id

    def get_owner_id(self, email: str) -> Optional[str]:
        return self.owners.get(email)

    def validate(self) -> List[str]:
        """Return list of validation errors."""
        errors = []
        # All companies should be registered
        if not self.companies:
            errors.append("No companies registered")
        return errors


# ============================================================================
# BASE GENERATOR
# ============================================================================

class BaseGenerator:
    """Shared utilities for all generators."""

    INDUSTRY_MAP = {
        "enterprise software": "COMPUTER_SOFTWARE",
        "data analytics": "INFORMATION_TECHNOLOGY_AND_SERVICES",
        "healthcare tech": "HOSPITAL_HEALTH_CARE",
        "manufacturing": "MACHINERY",
        "cloud infrastructure": "INFORMATION_TECHNOLOGY_AND_SERVICES",
        "supply chain": "LOGISTICS_AND_SUPPLY_CHAIN",
        "financial services": "FINANCIAL_SERVICES",
        "retail tech": "RETAIL",
        "clean energy": "RENEWABLES_ENVIRONMENT",
        "edtech": "E_LEARNING",
        "data infrastructure": "INFORMATION_TECHNOLOGY_AND_SERVICES",
        "ai/ml": "INFORMATION_TECHNOLOGY_AND_SERVICES",
    }

    EMPLOYEE_COUNT_MAP = {
        "1-10": "5",
        "10-50": "30",
        "50-100": "75",
        "100-250": "175",
        "250-500": "375",
        "500-1000": "750",
        "1000-5000": "3000",
        "5000+": "7500",
    }

    STAGE_MAP = {
        "discovery": "appointmentscheduled",
        "qualification": "qualifiedtobuy",
        "demo_scheduled": "presentationscheduled",
        "demoscheduled": "presentationscheduled",
        "proposal_sent": "decisionmakerboughtin",
        "proposalsent": "decisionmakerboughtin",
        "negotiation": "contractsent",
        "closed_won": "closedwon",
        "closedwon": "closedwon",
        "closed_lost": "closedlost",
        "closedlost": "closedlost",
    }

    @staticmethod
    def slugify(name: str) -> str:
        """Convert name to slug."""
        return name.lower().replace(" ", "_").replace(".", "").replace(",", "")

    @staticmethod
    def generate_id(prefix: str, name: str) -> str:
        """Generate a HubSpot-style ID."""
        slug = BaseGenerator.slugify(name)
        return f"{prefix}_{slug}"

    @staticmethod
    def generate_timestamp(base: datetime, offset_days: int) -> str:
        """Generate ISO timestamp."""
        dt = base + timedelta(days=offset_days)
        return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")

    @staticmethod
    def generate_contact_id() -> str:
        """Generate random contact ID like contact_907662."""
        return f"contact_{random.randint(100000, 999999)}"

    @staticmethod
    def generate_deal_id() -> str:
        """Generate random deal ID like deal_992410."""
        return f"deal_{random.randint(100000, 999999)}"


# ============================================================================
# ENTITY GENERATORS
# ============================================================================

class CompanyGenerator(BaseGenerator):
    """Generate company records."""

    def __init__(self, registry: IDRegistry, config: DemoNarrativeConfig):
        self.registry = registry
        self.config = config
        self.companies = []

    def generate_all(self) -> List[Dict]:
        """Generate all companies."""
        # Flagship company
        self._generate_company(self.config.flagship_company, "dataflow_inc")

        # Supporting companies
        for i, company_data in enumerate(self.config.supporting_companies):
            company_id = f"company_{i+1}_{self.slugify(company_data['name'])}"
            self._generate_company(company_data, company_id)

        return self.companies

    def _generate_company(self, data: Dict, company_id: str) -> Dict:
        """Generate a single company."""
        now = datetime.now()
        created = now - timedelta(days=random.randint(90, 365))

        company = {
            "id": company_id,
            "properties": {
                "name": data["name"],
                "domain": data["domain"],
                "industry": data["industry"],
                "numberofemployees": data["employees"],
                "city": data["city"],
                "state": data["state"],
                "annualrevenue": data["revenue"],
                "description": data.get("description", f"{data['name']} is a {data['industry']} company headquartered in {data['city']}, {data['state']}."),
                "createdate": self.generate_timestamp(created, 0),
                "lastmodifieddate": self.generate_timestamp(now, 0),
            }
        }

        self.registry.register_company(data["name"], company_id)
        self.companies.append(company)
        return company


class ContactGenerator(BaseGenerator):
    """Generate contact records."""

    def __init__(self, registry: IDRegistry, config: DemoNarrativeConfig):
        self.registry = registry
        self.config = config
        self.contacts = []

    def generate_all(self) -> List[Dict]:
        """Generate all contacts."""
        # Flagship contacts
        for contact_data in self.config.flagship_contacts:
            self._generate_contact(contact_data, "DataFlow Inc")

        # Supporting contacts (2-3 per company)
        supporting_contacts = [
            {"name": "Wei Ahmed", "title": "Head of Operations", "email": "wei.ahmed@novatech.io", "company": "NovaTech Solutions"},
            {"name": "Alex Kowalski", "title": "VP Engineering", "email": "alex.kowalski@novatech.io", "company": "NovaTech Solutions"},
            {"name": "Lisa Park", "title": "VP Sales Enablement", "email": "lisa.park@cloudbridge.com", "company": "CloudBridge Systems"},
            {"name": "Tom Baker", "title": "VP Procurement", "email": "tom.baker@apexmfg.com", "company": "Apex Manufacturing"},
            {"name": "Jordan Lee", "title": "CTO", "email": "jordan.lee@velocityretail.com", "company": "Velocity Retail"},
            {"name": "Sam Wilson", "title": "Head of Product", "email": "sam.wilson@meridianhc.com", "company": "Meridian Healthcare"},
            {"name": "Derek Thompson", "title": "VP Sales", "email": "derek.thompson@quantumleap.ai", "company": "QuantumLeap AI"},
            {"name": "Nina Patel", "title": "CEO", "email": "nina.patel@quantumleap.ai", "company": "QuantumLeap AI"},
            {"name": "Casey Brooks", "title": "Data Director", "email": "casey.brooks@greenfieldanalytics.com", "company": "Greenfield Analytics"},
        ]

        for contact_data in supporting_contacts:
            self._generate_contact(contact_data, contact_data["company"])

        return self.contacts

    def _generate_contact(self, data: Dict, company_name: str) -> Dict:
        """Generate a single contact."""
        company_id = self.registry.get_company_id(company_name)
        if not company_id:
            print(f"  Warning: Company {company_name} not found for contact {data.get('email')}")
            return {}

        now = datetime.now()

        # Parse name
        if "firstname" in data:
            firstname, lastname = data["firstname"], data["lastname"]
        else:
            parts = data["name"].split()
            firstname, lastname = parts[0], parts[-1]

        contact_id = self.generate_contact_id()

        contact = {
            "id": contact_id,
            "properties": {
                "firstname": firstname,
                "lastname": lastname,
                "email": data["email"],
                "jobtitle": data.get("title", data.get("jobtitle", "Decision Maker")),
                "phone": data.get("phone", f"+1-555-{random.randint(100,999)}-{random.randint(1000,9999)}"),
                "company": company_name,
                "lifecyclestage": self._determine_lifecycle(data),
                "lastmodifieddate": self.generate_timestamp(now, 0),
            },
            "associations": {
                "company_id": company_id
            }
        }

        self.registry.register_contact(data["email"], contact_id)
        self.contacts.append(contact)
        return contact

    def _determine_lifecycle(self, data: Dict) -> str:
        """Determine lifecycle stage based on role."""
        role = data.get("role", "")
        if role == "economic_buyer":
            return "opportunity"
        elif role == "champion":
            return "salesqualifiedlead"
        elif role == "technical_champion":
            return "salesqualifiedlead"
        else:
            return random.choice(["lead", "marketingqualifiedlead", "salesqualifiedlead", "opportunity"])


class OwnerGenerator(BaseGenerator):
    """Generate internal sales rep (owner) records."""

    def __init__(self, registry: IDRegistry, config: DemoNarrativeConfig):
        self.registry = registry
        self.config = config
        self.owners = []

    def generate_all(self) -> List[Dict]:
        """Generate all owners."""
        # Hero rep
        self._generate_owner(self.config.hero_rep, "owner_100")

        # Manager
        self._generate_owner(self.config.manager, "owner_101")

        # Supporting reps
        for i, rep_data in enumerate(self.config.supporting_reps):
            owner_id = f"owner_{102 + i}"
            self._generate_owner(rep_data, owner_id)

        return self.owners

    def _generate_owner(self, data: Dict, owner_id: str) -> Dict:
        """Generate a single owner."""
        owner = {
            "id": owner_id,
            "email": data["email"],
            "firstName": data["firstname"],
            "lastName": data["lastname"],
            "role": data["role"],
            "performance": data.get("performance", "average"),
        }

        # Add performance-specific fields
        if data.get("needs_coaching"):
            owner["coaching_status"] = "active"
        if data.get("specialty"):
            owner["specialty"] = data["specialty"]
        if data.get("ramp_status"):
            owner["ramp_status"] = data["ramp_status"]

        self.registry.register_owner(data["email"], owner_id)
        self.owners.append(owner)
        return owner


class DealGenerator(BaseGenerator):
    """Generate deal records with activities."""

    def __init__(self, registry: IDRegistry, config: DemoNarrativeConfig):
        self.registry = registry
        self.config = config
        self.deals = []

    def generate_all(self) -> List[Dict]:
        """Generate all deals."""
        # Flagship deal
        self._generate_flagship_deal()

        # Supporting deals
        self._generate_supporting_deals()

        return self.deals

    def _generate_flagship_deal(self) -> Dict:
        """Generate the DataFlow Inc flagship deal."""
        now = datetime.now()
        company_id = self.registry.get_company_id("DataFlow Inc")

        # Find Sarah Chen's owner ID
        sarah_owner_id = self.registry.get_owner_id("sarah.chen@ourcompany.com")
        if not sarah_owner_id:
            sarah_owner_id = "owner_100"

        # Find primary contact
        primary_contact_id = self.registry.get_contact_id("priya.sharma@dataflow.io")

        deal_id = self.generate_deal_id()
        deal_key = "dataflow_flagship"

        deal = {
            "id": deal_id,
            "properties": {
                "dealname": self.config.flagship_deal["name"],
                "amount": self.config.flagship_deal["amount"],
                "dealstage": self.config.flagship_deal["stage"],
                "dealstage_label": "Negotiation",
                "pipeline": "default",
                "closedate": self.config.flagship_deal["close_date"],
                "createdate": self.generate_timestamp(now - timedelta(days=120), 0),
                "hs_lastmodifieddate": self.generate_timestamp(now, 0),
                "hubspot_owner_id": sarah_owner_id,
                "description": f"Enterprise platform license deal. Displacing {self.config.flagship_deal['competitor']}. Timeline driver: {self.config.flagship_deal['timeline_driver']}",
            },
            "associations": {
                "company": company_id,
                "contact": primary_contact_id,
            },
            "activities": self._generate_flagship_activities(now)
        }

        self.registry.register_deal(deal_key, deal_id)
        self.deals.append(deal)
        return deal

    def _generate_flagship_activities(self, now: datetime) -> List[Dict]:
        """Generate activities for the flagship deal."""
        competitor = self.config.flagship_deal["competitor"]

        return [
            {
                "type": "NOTE",
                "body": f"Final negotiation prep complete. {competitor} still in play but we have strong champion support. CFO Jennifer Liu is the key decision maker - focused on ROI and implementation timeline.",
                "timestamp": self.generate_timestamp(now - timedelta(days=2), 0),
            },
            {
                "type": "CALL",
                "body": f"Spoke with Priya (champion). She confirmed {competitor} is pushing hard on price but our technical differentiation is resonating. CTO Marcus Chen is our technical champion. Setting up CFO call for next week.",
                "timestamp": self.generate_timestamp(now - timedelta(days=5), 0),
            },
            {
                "type": "EMAIL",
                "body": f"Sent proposal revision with revised pricing tier. Addressed {competitor} comparison directly - our TCO is 30% lower over 3 years.",
                "timestamp": self.generate_timestamp(now - timedelta(days=7), 0),
            },
            {
                "type": "NOTE",
                "body": f"Technical deep dive completed. Security review passed. Integration architecture approved. {competitor}'s main advantage is brand recognition but our solution is more flexible.",
                "timestamp": self.generate_timestamp(now - timedelta(days=14), 0),
            },
            {
                "type": "MEETING",
                "body": "Discovery call with full team. Priya confirmed budget is approved ($200K capex). Decision timeline: end of April. Competitor {competitor} demo'd last week - feedback was 'good but not as adaptable'.",
                "timestamp": self.generate_timestamp(now - timedelta(days=30), 0),
            },
            {
                "type": "NOTE",
                "body": "Initial outreach. Priya reached out after seeing our content on AI coaching. First meeting scheduled for next week.",
                "timestamp": self.generate_timestamp(now - timedelta(days=45), 0),
            },
        ]

    def _generate_supporting_deals(self):
        """Generate supporting deals for other companies."""
        now = datetime.now()

        supporting_deals = [
            {"company": "NovaTech Solutions", "name": "Annual Platform License", "amount": "48000", "stage": "discovery", "owner": "sarah.chen@ourcompany.com", "close": "2026-05-15"},
            {"company": "CloudBridge Systems", "name": "Enterprise Training Program", "amount": "85000", "stage": "demo_scheduled", "owner": "jordan.mitchell@ourcompany.com", "close": "2026-05-30"},
            {"company": "Apex Manufacturing", "name": "Sales Enablement Platform", "amount": "180000", "stage": "closed_won", "owner": "casey.brooks@ourcompany.com", "close": "2026-03-15"},
            {"company": "Velocity Retail", "name": "Coaching Platform License", "amount": "62000", "stage": "proposal_sent", "owner": "taylor.nguyen@ourcompany.com", "close": "2026-04-30"},
            {"company": "Meridian Healthcare", "name": "Compliance Training Suite", "amount": "145000", "stage": "negotiation", "owner": "jordan.mitchell@ourcompany.com", "close": "2026-05-15"},
            {"company": "QuantumLeap AI", "name": "Startup Package", "amount": "36000", "stage": "qualification", "owner": "alex.rivera@ourcompany.com", "close": "2026-06-30"},
            {"company": "Greenfield Analytics", "name": "Analytics Training", "amount": "42000", "stage": "closed_lost", "owner": "morgan.taylor@ourcompany.com", "close": "2026-03-01", "lost_reason": "Went with CompetitorAlpha"},
        ]

        for deal_data in supporting_deals:
            self._generate_deal(deal_data, now)

    def _generate_deal(self, data: Dict, now: datetime) -> Dict:
        """Generate a single deal."""
        company_id = self.registry.get_company_id(data["company"])
        owner_id = self.registry.get_owner_id(data["owner"])

        if not company_id:
            print(f"  Warning: Company {data['company']} not found")
            return {}

        # Get a contact from this company
        contact_id = None
        for email, cid in self.registry.contacts.items():
            if data["company"].lower() in email.lower():
                contact_id = cid
                break

        deal_id = self.generate_deal_id()
        deal_key = self.slugify(data["company"])

        stage_label = data["stage"].replace("_", " ").title()

        deal = {
            "id": deal_id,
            "properties": {
                "dealname": f"{data['company']} — {data['name']}",
                "amount": data["amount"],
                "dealstage": data["stage"],
                "dealstage_label": stage_label,
                "pipeline": "default",
                "closedate": data["close"],
                "createdate": self.generate_timestamp(now - timedelta(days=random.randint(60, 180)), 0),
                "hs_lastmodifieddate": self.generate_timestamp(now, 0),
                "hubspot_owner_id": owner_id or "owner_100",
                "description": f"Active deal with {data['company']}.",
            },
            "associations": {
                "company": company_id,
                "contact": contact_id,
            },
            "activities": self._generate_generic_activities(now, data)
        }

        self.registry.register_deal(deal_key, deal_id)
        self.deals.append(deal)
        return deal

    def _generate_generic_activities(self, now: datetime, deal_data: Dict) -> List[Dict]:
        """Generate generic activities for a deal."""
        stage = deal_data["stage"]

        activities = []

        if stage in ["closed_won", "closed_lost"]:
            activities.append({
                "type": "NOTE",
                "body": f"Deal {stage.replace('_', ' ')}. " + (deal_data.get("lost_reason", "Contract signed and executed.") if stage == "closed_lost" else "Customer onboarded successfully."),
                "timestamp": self.generate_timestamp(now - timedelta(days=10), 0),
            })

        activities.extend([
            {
                "type": "NOTE",
                "body": "Follow-up scheduled. Prospect engaged but evaluating options.",
                "timestamp": self.generate_timestamp(now - timedelta(days=20), 0),
            },
            {
                "type": "EMAIL",
                "body": "Sent product overview and case studies.",
                "timestamp": self.generate_timestamp(now - timedelta(days=30), 0),
            },
            {
                "type": "NOTE",
                "body": "Initial discovery call completed. Budget confirmed, timeline is Q2.",
                "timestamp": self.generate_timestamp(now - timedelta(days=45), 0),
            },
        ])

        return activities


# ============================================================================
# CONTENT GENERATORS
# ============================================================================

class MeetingGenerator(BaseGenerator):
    """Generate meeting records."""

    def __init__(self, registry: IDRegistry, config: DemoNarrativeConfig):
        self.registry = registry
        self.config = config
        self.meetings = []

    def generate_all(self) -> List[Dict]:
        """Generate all meetings."""
        # DataFlow meetings
        self._generate_dataflow_meetings()

        # Supporting meetings
        self._generate_supporting_meetings()

        return self.meetings

    def _generate_dataflow_meetings(self):
        """Generate meetings for the DataFlow Inc deal."""
        now = datetime.now()
        deal_id = self.registry.get_deal_id("dataflow_flagship")
        company_id = self.registry.get_company_id("DataFlow Inc")

        contacts = [
            self.registry.get_contact_id("priya.sharma@dataflow.io"),
            self.registry.get_contact_id("marcus.chen@dataflow.io"),
            self.registry.get_contact_id("jennifer.liu@dataflow.io"),
        ]

        dataflow_meetings = [
            {"type": "discovery", "title": "DataFlow Inc — Discovery Call", "date": now - timedelta(days=60), "outcome": "completed"},
            {"type": "technical_review", "title": "DataFlow Inc — Technical Deep Dive", "date": now - timedelta(days=30), "outcome": "completed"},
            {"type": "economic_buyer", "title": "DataFlow Inc — CFO Alignment Call", "date": now - timedelta(days=10), "outcome": "completed"},
            {"type": "negotiation", "title": "DataFlow Inc — Final Negotiation", "date": now + timedelta(days=5), "outcome": "scheduled"},
        ]

        for i, meeting_data in enumerate(dataflow_meetings):
            self._generate_meeting(
                title=meeting_data["title"],
                meeting_type=meeting_data["type"],
                start_time=meeting_data["date"],
                outcome=meeting_data["outcome"],
                deal_id=deal_id,
                company_id=company_id,
                contact_ids=[c for c in contacts if c],
                summary=f"{meeting_data['type'].replace('_', ' ').title()} meeting with DataFlow Inc team."
            )

    def _generate_supporting_meetings(self):
        """Generate meetings for other deals."""
        now = datetime.now()

        for deal_key, deal_id in self.registry.deals.items():
            if deal_key == "dataflow_flagship":
                continue

            # 1-2 meetings per deal
            meeting_types = ["discovery", "demo", "proposal_review"]
            for mt in random.sample(meeting_types, k=random.randint(1, 2)):
                self._generate_meeting(
                    title=f"{deal_key.replace('_', ' ').title()} — {mt.replace('_', ' ').title()}",
                    meeting_type=mt,
                    start_time=now - timedelta(days=random.randint(5, 60)),
                    outcome=random.choice(["completed", "completed", "no_show"]),
                    deal_id=deal_id,
                    company_id=None,  # Would need company lookup
                    contact_ids=[],
                    summary=f"{mt.replace('_', ' ').title()} meeting."
                )

    def _generate_meeting(self, title: str, meeting_type: str, start_time: datetime,
                          outcome: str, deal_id: Optional[str], company_id: Optional[str],
                          contact_ids: List[str], summary: str) -> Dict:
        """Generate a single meeting."""
        meeting_id = f"meeting_{random.randint(10000, 99999)}"

        meeting = {
            "id": meeting_id,
            "properties": {
                "title": title,
                "start_time": start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "end_time": (start_time + timedelta(minutes=45)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "meeting_type": meeting_type,
                "outcome": outcome,
                "summary": summary,
            },
            "associations": {
                "deal_id": deal_id,
                "company_id": company_id,
                "contact_ids": contact_ids,
            }
        }

        self.meetings.append(meeting)
        return meeting


class EmailThreadGenerator(BaseGenerator):
    """Generate email thread records."""

    def __init__(self, registry: IDRegistry, config: DemoNarrativeConfig):
        self.registry = registry
        self.config = config
        self.emails = []

    def generate_all(self) -> List[Dict]:
        """Generate all email threads."""
        # DataFlow negotiation thread
        self._generate_dataflow_thread()

        # Supporting threads
        self._generate_supporting_threads()

        return self.emails

    def _generate_dataflow_thread(self):
        """Generate email thread for DataFlow negotiation."""
        deal_id = self.registry.get_deal_id("dataflow_flagship")
        company_id = self.registry.get_company_id("DataFlow Inc")

        contacts = [
            {"email": "jennifer.liu@dataflow.io", "name": "Jennifer Liu"},
            {"email": "sarah.chen@ourcompany.com", "name": "Sarah Chen"},
        ]

        now = datetime.now()

        thread = {
            "thread_id": "thread_dataflow_negotiation",
            "subject": "Re: DataFlow Inc — Updated Proposal and Pricing",
            "associations": {
                "deal_id": deal_id,
                "company_id": company_id,
                "contact_ids": [self.registry.get_contact_id(c["email"]) for c in contacts if self.registry.get_contact_id(c["email"])],
            },
            "participants": contacts,
            "messages": [
                {
                    "from": "sarah.chen@ourcompany.com",
                    "to": ["jennifer.liu@dataflow.io"],
                    "cc": ["priya.sharma@dataflow.io"],
                    "date": (now - timedelta(days=8)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "body": "Hi Jennifer,\n\nFollowing up on our call last week. Attached is the revised proposal with the pricing tier we discussed.\n\nKey highlights:\n- 30% lower TCO vs CompetitorBeta over 3 years\n- Implementation in 4 weeks, not 8\n- Dedicated success manager included\n\nLet me know if you have any questions.\n\nBest,\nSarah"
                },
                {
                    "from": "jennifer.liu@dataflow.io",
                    "to": ["sarah.chen@ourcompany.com"],
                    "cc": [],
                    "date": (now - timedelta(days=6)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "body": "Sarah,\n\nThanks for the revised proposal. A few questions:\n\n1. Can we get a 90-day payment term instead of 30?\n2. What's the exit clause if we're not satisfied?\n3. Can you include the advanced analytics module at no extra cost?\n\nI'd like to move forward but need to address these with our finance team.\n\nJennifer"
                },
                {
                    "from": "sarah.chen@ourcompany.com",
                    "to": ["jennifer.liu@dataflow.io"],
                    "cc": ["priya.sharma@dataflow.io"],
                    "date": (now - timedelta(days=4)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "body": "Jennifer,\n\nGreat questions:\n\n1. 90-day terms: Approved for enterprise contracts\n2. Exit clause: 60-day opt-out with full refund of unused portion\n3. Advanced analytics: I can include the first year at no cost\n\nDoes this address your concerns?\n\nSarah"
                },
                {
                    "from": "jennifer.liu@dataflow.io",
                    "to": ["sarah.chen@ourcompany.com"],
                    "cc": ["raj.gupta@dataflow.io"],
                    "date": (now - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "body": "Sarah,\n\nThis looks good. Let me review with Raj (our CRO) and we should be ready to move forward.\n\nCan we schedule a final call next week to review terms?\n\nJennifer"
                },
            ]
        }

        self.emails.append(thread)
        return thread

    def _generate_supporting_threads(self):
        """Generate supporting email threads."""
        # Add 2-3 more threads for other deals
        pass


class CallTranscriptGenerator(BaseGenerator):
    """Generate call transcript markdown files."""

    def __init__(self, registry: IDRegistry, config: DemoNarrativeConfig):
        self.registry = registry
        self.config = config
        self.transcripts = []

    def generate_all(self) -> List[Dict]:
        """Generate all call transcripts."""
        self._generate_dataflow_discovery()
        self._generate_dataflow_technical()

        return self.transcripts

    def _generate_dataflow_discovery(self):
        """Generate discovery call transcript for DataFlow."""
        now = datetime.now()

        transcript = {
            "filename": "discovery_call_dataflow_2026-02-15.md",
            "content": f"""# Discovery Call: DataFlow Inc

**Date:** {(now - timedelta(days=60)).strftime('%Y-%m-%d')}
**Attendees:** Priya Sharma (VP Eng, DataFlow), Sarah Chen (AE, Our Company)
**Duration:** 45 minutes

---

## Opening (0:00 - 5:00)

**Sarah:** Thanks for making time today, Priya. To make the best use of our time, I'd love to learn about what's happening on your end and see if there's a fit. Does that work?

**Priya:** Absolutely. We're looking for solutions to scale our sales coaching.

## Current State (5:00 - 20:00)

**Sarah:** Walk me through how you handle sales coaching today.

**Priya:** Right now it's very manual. Managers spend 2+ hours per week on coaching calls. The problem is inconsistency — every manager has their own approach.

**Sarah:** What does success look like?

**Priya:** Three things: (1) Consistent messaging across all reps, (2) Faster ramp time for new hires, (3) Better conversion rates from our coaching investments.

## Pain Exploration (20:00 - 35:00)

**Sarah:** What happens if nothing changes?

**Priya:** We continue with inconsistent coaching. Our Q2 goal is to improve win rates by 15% — without better coaching, that's at risk.

**Sarah:** Who else is involved in this decision?

**Priya:** Marcus Chen (CTO) will need to approve the technical side. Jennifer Liu (CFO) owns the budget. I'm the champion, but I need their buy-in.

## Next Steps (35:00 - 45:00)

**Sarah:** What's your timeline?

**Priya:** Looking to decide by end of April. We'd want to start onboarding in May.

**Sarah:** Perfect. Let me set up a technical deep dive with Marcus to address any integration questions.

---

## Rep Notes (Post-Call)

**MEDDIC Assessment:**
- **Metrics:** 2hrs/week per manager, 15% win rate improvement goal
- **Economic Buyer:** Jennifer Liu (CFO) — not yet met
- **Decision Criteria:** Consistency, ramp time, win rate improvement
- **Decision Process:** Priya champions, Marcus technical approval, Jennifer budget approval
- **Identify Pain:** Manual process, inconsistent coaching, Q2 at risk
- **Champion:** Priya Sharma — strong, confirmed budget and timeline

**Competitive Intel:** CompetitorBeta demo scheduled for next week. Priya said they want to "see both options."

**Next Steps:**
1. Technical deep dive with Marcus Chen (CTO)
2. Send ROI calculator to Priya
3. Schedule CFO alignment call
"""
        }

        self.transcripts.append(transcript)
        return transcript

    def _generate_dataflow_technical(self):
        """Generate technical deep dive transcript."""
        now = datetime.now()

        transcript = {
            "filename": "technical_review_dataflow_2026-03-15.md",
            "content": f"""# Technical Deep Dive: DataFlow Inc

**Date:** {(now - timedelta(days=30)).strftime('%Y-%m-%d')}
**Attendees:** Marcus Chen (CTO, DataFlow), Sarah Chen (AE, Our Company), Tech Specialist
**Duration:** 60 minutes

---

## Security Review (0:00 - 20:00)

**Marcus:** Our security team has a few requirements. SOC 2 Type II?

**Tech Specialist:** Yes, current SOC 2 Type II available under NDA. Also ISO 27001 certified.

**Marcus:** Data residency?

**Tech Specialist:** All data hosted in US-East region by default. Can do EU if needed.

**Marcus:** SSO integration?

**Tech Specialist:** SAML 2.0, Okta out of the box. Implementation is 2-4 hours.

## Integration Architecture (20:00 - 40:00)

**Marcus:** How do you integrate with HubSpot?

**Tech Specialist:** Bi-directional sync via HubSpot API. We read companies, contacts, deals. We can write back notes and activities.

**Marcus:** What about data export if we terminate?

**Tech Specialist:** Full data export in JSON/CSV format. Your data is yours — no lock-in.

## Technical Concerns (40:00 - 60:00)

**Marcus:** Two concerns: (1) API rate limits for sync, (2) Uptime SLA.

**Tech Specialist:** (1) We batch requests, stay well under limits. (2) 99.9% uptime SLA with credits for violations.

**Marcus:** Okay. I'm comfortable moving forward. Let me know what you need from me for the CFO pack.

---

## Rep Notes (Post-Call)

**Technical Outcome:** PASSED

**Open Items:**
- Send SOC 2 report under NDA
- Provide uptime SLA document for CFO review

**Champion Signal:** Marcus said "I'm comfortable moving forward" — strong technical approval.

**Next Steps:**
1. Send security docs to Marcus
2. Prepare CFO pack with SLA and ROI
3. Schedule Jennifer Liu (CFO) call
"""
        }

        self.transcripts.append(transcript)
        return transcript


class MeetingNotesGenerator(BaseGenerator):
    """Generate meeting notes markdown files."""

    def __init__(self, registry: IDRegistry, config: DemoNarrativeConfig):
        self.registry = registry
        self.config = config
        self.notes = []

    def generate_all(self) -> List[Dict]:
        """Generate all meeting notes."""
        self._generate_dataflow_prep()
        self._generate_dataflow_recap()

        return self.notes

    def _generate_dataflow_prep(self):
        """Generate prep doc for DataFlow negotiation."""
        now = datetime.now()

        note = {
            "filename": "prep_dataflow_negotiation_2026-04-25.md",
            "content": f"""# Meeting Prep: DataFlow Inc Final Negotiation

**Date:** {(now + timedelta(days=5)).strftime('%Y-%m-%d')}
**Attendees:** Jennifer Liu (CFO), Raj Gupta (CRO), Priya Sharma (VP Eng), Sarah Chen

---

## Objectives

1. Finalize pricing and payment terms
2. Review exit clause and SLA
3. Get verbal commitment to move forward

## Agenda

1. Review revised proposal (5 min)
2. Address remaining questions (15 min)
3. Next steps and timeline (10 min)

## Key Points to Emphasize

- 30% lower TCO vs CompetitorBeta
- 90-day payment terms approved
- Advanced analytics included Year 1
- Implementation in 4 weeks

## Anticipated Objections

**"CompetitorBeta is cheaper"**
→ Response: Our TCO analysis shows 30% savings over 3 years. Their base tier lacks advanced analytics and dedicated success manager.

**"We need more time to decide"**
→ Response: I understand. What additional information would help? The Q2 timeline driver you mentioned — what happens if we slip to Q3?

## Success Criteria

- Verbal commitment to proceed
- Clear understanding of any remaining blockers
- Scheduled contract review call

---

## Internal Notes

**Champion Check:** Priya confirmed budget ($200K capex) and timeline (end of April). She's coaching us internally — good sign.

**Competitor Intel:** CompetitorBeta demo'd last week. Feedback: "Good but not as adaptable."

**Red Flags:** None identified. All stakeholders engaged.
"""
        }

        self.notes.append(note)
        return note

    def _generate_dataflow_recap(self):
        """Generate recap doc for DataFlow discovery."""
        now = datetime.now()

        note = {
            "filename": "recap_dataflow_discovery_2026-02-15.md",
            "content": f"""# Meeting Recap: DataFlow Inc Discovery

**Date:** {(now - timedelta(days=60)).strftime('%Y-%m-%d')}
**Attendees:** Priya Sharma (VP Eng), Sarah Chen

---

## Summary

Strong discovery call. Priya confirmed:
- Current coaching is manual and inconsistent
- Managers spend 2+ hrs/week on coaching
- Q2 goal: 15% improvement in win rates
- Budget approved, timeline is end of April

## Pain Points

1. Inconsistent messaging across reps
2. Slow ramp time for new hires (3-4 months)
3. No visibility into coaching effectiveness

## Decision Process

- **Champion:** Priya Sharma (VP Eng)
- **Technical:** Marcus Chen (CTO) — needs approval
- **Economic:** Jennifer Liu (CFO) — owns budget
- **Timeline:** Decision by end of April
- **Competitors:** CompetitorBeta demo scheduled

## Action Items

- [ ] Sarah: Send ROI calculator to Priya
- [ ] Sarah: Schedule technical deep dive with Marcus
- [ ] Sarah: Prepare CFO pack for Jennifer
- [ ] Priya: Share current coaching process docs

---

## MEDDIC Score

| Criteria | Status | Notes |
|----------|--------|-------|
| Metrics | ✅ | 2hrs/week, 15% win rate goal |
| Economic Buyer | ⚠️ | Identified, not yet met |
| Decision Criteria | ✅ | Consistency, ramp time, win rate |
| Decision Process | ✅ | Clear 3-step approval |
| Identify Pain | ✅ | Manual, inconsistent, Q2 at risk |
| Champion | ✅ | Priya strong, coaching us |

**Overall:** Strong discovery. 7/10 MEDDIC score.
"""
        }

        self.notes.append(note)
        return note


# ============================================================================
# TRAINING SESSION GENERATOR
# ============================================================================

class TrainingSessionGenerator(BaseGenerator):
    """Generate training session records in SQLite."""

    def __init__(self, registry: IDRegistry, config: DemoNarrativeConfig):
        self.registry = registry
        self.config = config
        self.sessions = []

    def generate_all(self):
        """Generate all training sessions."""
        # Import db module for saving sessions
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        try:
            from db import save_training_session, save_dimension_scores
        except ImportError:
            print("  Warning: db.py not found, skipping SQLite training sessions")
            return

        # Sarah's training history (showing improvement)
        sarah_owner_id = self.registry.get_owner_id("sarah.chen@ourcompany.com")
        if sarah_owner_id:
            for session_data in self.config.sarah_training_history:
                self._save_session(sarah_owner_id, session_data, save_training_session, save_dimension_scores)

        # Other reps' training
        for rep_email in ["jordan.mitchell@ourcompany.com", "alex.rivera@ourcompany.com"]:
            owner_id = self.registry.get_owner_id(rep_email)
            if owner_id:
                # Generate 2-3 sessions per rep
                for i in range(random.randint(2, 4)):
                    session_data = {
                        "scenario": random.choice(["discovery", "negotiation", "objection", "competitive"]),
                        "score": round(random.uniform(6.0, 8.5), 1),
                        "date": (datetime.now() - timedelta(days=random.randint(10, 60))).strftime("%Y-%m-%d"),
                        "turns": random.randint(4, 8),
                    }
                    self._save_session(owner_id, session_data, save_training_session, save_dimension_scores)

    def _save_session(self, owner_id: str, session_data: Dict, save_fn, score_fn):
        """Save a single training session."""
        try:
            session_id = save_fn(
                user_id=owner_id,
                scenario_type=session_data["scenario"],
                overall_score=session_data["score"],
                turns=session_data["turns"],
                methodology="MEDDIC",
                company=random.choice(["DataFlow Inc", "NovaTech", "CloudBridge"]),
                persona="VP Engineering"
            )

            # Save dimension scores
            dimensions = ["opening", "needs_assessment", "objection_handling", "closing"]
            for dim in dimensions:
                score_fn(
                    session_id=session_id,
                    dimension=dim,
                    score=round(session_data["score"] + random.uniform(-0.5, 0.5), 1)
                )

            self.sessions.append(session_data)
        except Exception as e:
            print(f"  Warning: Could not save training session: {e}")


# ============================================================================
# OUTPUT MODES
# ============================================================================

class JSONWriter:
    """Write generated data to JSON files."""

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def write_all(self, companies: List, contacts: List, deals: List,
                  meetings: List, owners: List, emails: List,
                  transcripts: List, notes: List):
        """Write all data to JSON files."""
        print("\n--- Writing JSON Files ---")

        # Clear existing files first (overwrite mode)
        for f in ["companies.json", "contacts.json", "deals.json", "meetings.json", "owners.json"]:
            filepath = self.output_dir / f
            if filepath.exists():
                filepath.unlink()

        self._write_json("companies.json", companies)
        self._write_json("contacts.json", contacts)
        self._write_json("deals.json", deals)
        self._write_json("meetings.json", meetings)
        self._write_json("owners.json", owners)

        # Clear and write email threads to individual files
        email_dir = self.output_dir / "email_threads"
        if email_dir.exists():
            for f in email_dir.glob("*.json"):
                f.unlink()
        email_dir.mkdir(exist_ok=True)
        for email in emails:
            filename = f"{email['thread_id']}.json"
            self._write_json(f"email_threads/{filename}", email)

        # Clear and write transcripts to markdown files
        transcript_dir = self.output_dir / "call_transcripts"
        if transcript_dir.exists():
            for f in transcript_dir.glob("*.md"):
                f.unlink()
        transcript_dir.mkdir(exist_ok=True)
        for transcript in transcripts:
            self._write_markdown(f"call_transcripts/{transcript['filename']}", transcript['content'])

        # Clear and write meeting notes to markdown files
        notes_dir = self.output_dir / "meeting_notes"
        if notes_dir.exists():
            for f in notes_dir.glob("*.md"):
                f.unlink()
        notes_dir.mkdir(exist_ok=True)
        for note in notes:
            self._write_markdown(f"meeting_notes/{note['filename']}", note['content'])

        print(f"  Written to: {self.output_dir}")

    def _write_json(self, filename: str, data: Any):
        """Write JSON file."""
        filepath = self.output_dir / filename
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"  ✓ {filename}")

    def _write_markdown(self, filename: str, content: str):
        """Write markdown file."""
        filepath = self.output_dir / filename
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"  ✓ {filename}")


class HubSpotPusher:
    """Push generated data to HubSpot via API."""

    def __init__(self, api_token: str, dry_run: bool = False):
        from hubspot import HubSpot
        self.client = HubSpot(access_token=api_token)
        self.dry_run = dry_run
        self.synced_ids = {}

    def push_all(self, companies: List, contacts: List, deals: List,
                 meetings: List, emails: List):
        """Push all data to HubSpot."""
        print("\n--- Pushing to HubSpot ---")

        if self.dry_run:
            print("  [DRY RUN MODE]")

        # Push in order: companies -> contacts -> deals -> meetings -> emails
        company_map = self._push_companies(companies)
        contact_map = self._push_contacts(contacts, company_map)
        deal_map = self._push_deals(deals, company_map, contact_map)

        self.synced_ids = {
            "companies": company_map,
            "contacts": contact_map,
            "deals": deal_map,
        }

        return self.synced_ids

    def _push_companies(self, companies: List) -> Dict:
        """Push companies to HubSpot."""
        print(f"\n  Creating {len(companies)} companies...")
        mapping = {}

        for company in companies:
            if self.dry_run:
                mapping[company["id"]] = f"dry_run_{company['id']}"
                continue

            # TODO: Implement HubSpot API call
            # result = self.client.crm.companies.basic_api.create(...)
            # mapping[company["id"]] = result.id

        return mapping

    def _push_contacts(self, contacts: List, company_map: Dict) -> Dict:
        """Push contacts to HubSpot."""
        print(f"  Creating {len(contacts)} contacts...")
        mapping = {}

        for contact in contacts:
            if self.dry_run:
                mapping[contact["id"]] = f"dry_run_{contact['id']}"
                continue

            # TODO: Implement HubSpot API call

        return mapping

    def _push_deals(self, deals: List, company_map: Dict, contact_map: Dict) -> Dict:
        """Push deals to HubSpot."""
        print(f"  Creating {len(deals)} deals...")
        mapping = {}

        for deal in deals:
            if self.dry_run:
                mapping[deal["id"]] = f"dry_run_{deal['id']}"
                continue

            # TODO: Implement HubSpot API call

        return mapping

    def save_synced_ids(self, filepath: str):
        """Save synced IDs to file."""
        with open(filepath, 'w') as f:
            json.dump(self.synced_ids, f, indent=2)
        print(f"  Saved synced IDs to: {filepath}")


# ============================================================================
# VERIFICATION
# ============================================================================

def verify_data(registry: IDRegistry, companies: List, contacts: List,
                deals: List, meetings: List, owners: List = None) -> List[str]:
    """Verify data integrity."""
    print("\n--- Verifying Data Integrity ---")

    errors = []

    # Check company references
    company_ids = {c["id"] for c in companies}
    for contact in contacts:
        company_id = contact.get("associations", {}).get("company_id")
        if company_id and company_id not in company_ids:
            errors.append(f"Contact {contact['id']} references unknown company {company_id}")

    # Check deal references
    deal_ids = {d["id"] for d in deals}
    for meeting in meetings:
        deal_id = meeting.get("associations", {}).get("deal_id")
        if deal_id and deal_id not in deal_ids:
            errors.append(f"Meeting {meeting['id']} references unknown deal {deal_id}")

    # Check flagship deal
    flagship_found = False
    for deal in deals:
        if "DataFlow" in deal["properties"].get("dealname", ""):
            if deal["properties"].get("amount") == "180000":
                flagship_found = True
                print(f"  ✓ Flagship deal found: ${deal['properties']['amount']}")

    if not flagship_found:
        errors.append("Flagship DataFlow deal ($180K) not found")

    # Report
    if errors:
        print(f"  ✗ {len(errors)} errors found:")
        for error in errors:
            print(f"    - {error}")
    else:
        print("  ✓ All integrity checks passed")

    return errors


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Generate synthetic demo data for SalesCoach AI")
    parser.add_argument("--mode", choices=["json", "hubspot", "both"], default="json",
                        help="Output mode: json (files only), hubspot (API push), both")
    parser.add_argument("--token", help="HubSpot API token (required for hubspot mode)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without making changes")
    parser.add_argument("--verify", action="store_true", help="Verify data integrity and exit")
    parser.add_argument("--output-dir", default="data/mock_crm", help="Output directory for JSON files")

    args = parser.parse_args()

    # Initialize
    print("=" * 60)
    print("SalesCoach AI - Synthetic Demo Data Generator")
    print("=" * 60)

    config = DemoNarrativeConfig()
    registry = IDRegistry()

    # Generate all data
    print("\n--- Generating Demo Data ---")

    company_gen = CompanyGenerator(registry, config)
    companies = company_gen.generate_all()
    print(f"  Generated {len(companies)} companies")

    contact_gen = ContactGenerator(registry, config)
    contacts = contact_gen.generate_all()
    print(f"  Generated {len(contacts)} contacts")

    owner_gen = OwnerGenerator(registry, config)
    owners = owner_gen.generate_all()
    print(f"  Generated {len(owners)} owners")

    deal_gen = DealGenerator(registry, config)
    deals = deal_gen.generate_all()
    print(f"  Generated {len(deals)} deals")

    meeting_gen = MeetingGenerator(registry, config)
    meetings = meeting_gen.generate_all()
    print(f"  Generated {len(meetings)} meetings")

    email_gen = EmailThreadGenerator(registry, config)
    emails = email_gen.generate_all()
    print(f"  Generated {len(emails)} email threads")

    transcript_gen = CallTranscriptGenerator(registry, config)
    transcripts = transcript_gen.generate_all()
    print(f"  Generated {len(transcripts)} call transcripts")

    notes_gen = MeetingNotesGenerator(registry, config)
    notes = notes_gen.generate_all()
    print(f"  Generated {len(notes)} meeting notes")

    training_gen = TrainingSessionGenerator(registry, config)
    training_gen.generate_all()
    print(f"  Generated {len(training_gen.sessions)} training sessions")

    # Verify if requested
    if args.verify:
        errors = verify_data(registry, companies, contacts, deals, meetings, [])
        sys.exit(0 if not errors else 1)

    # Output
    if args.mode in ["json", "both"]:
        writer = JSONWriter(args.output_dir)
        writer.write_all(companies, contacts, deals, meetings, owners, emails, transcripts, notes)

    if args.mode in ["hubspot", "both"]:
        if not args.token:
            print("\n  ✗ HubSpot token required for hubspot mode")
            print("  Usage: --token YOUR_HUBSPOT_TOKEN")
            sys.exit(1)

        pusher = HubSpotPusher(args.token, dry_run=args.dry_run)
        synced_ids = pusher.push_all(companies, contacts, deals, meetings, emails)
        pusher.save_synced_ids("data/hubspot_synced_ids.json")

    print("\n" + "=" * 60)
    print("Generation complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
