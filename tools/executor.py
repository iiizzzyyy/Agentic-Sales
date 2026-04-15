"""Direct executor for Hive Mind orchestration.

Executes single tool calls for DIRECT path tasks with typed output.
"""

from typing import Any
from graphs.contracts import TaskInput, TaskOutput, TaskStatus, ResearchBrief, DealStatus, EmailDraft, PipelineDigest


class DirectExecutor:
    """Executor for direct (single tool call) tasks."""

    def __init__(self, mcp_tools: list | None = None):
        """Initialize executor with optional MCP tools.

        Args:
            mcp_tools: List of MCP tools from MCP setup
        """
        self.mcp_tools = mcp_tools or []
        self._tool_registry = {}
        self._register_direct_tools()

    def _register_direct_tools(self):
        """Register direct tools (non-MCP)."""
        # Web search (Tavily)
        try:
            from tools.web_search import search_company_news
            self._tool_registry["search_company_news"] = search_company_news
        except ImportError:
            pass

        # RAG search
        try:
            from tools.rag import search as rag_search, search_crm, search_crm_deals, search_crm_contacts
            self._tool_registry["rag_search"] = rag_search
            self._tool_registry["search_crm"] = search_crm
            self._tool_registry["search_crm_deals"] = search_crm_deals
            self._tool_registry["search_crm_contacts"] = search_crm_contacts
        except ImportError:
            pass

        # Mock CRM (fallback)
        try:
            from tools import mock_crm
            self._tool_registry["mock_crm_get_company"] = mock_crm.get_company
            self._tool_registry["mock_crm_get_deal"] = mock_crm.get_deal
            self._tool_registry["mock_crm_get_all_open_deals"] = mock_crm.get_all_open_deals
            self._tool_registry["mock_crm_get_contacts"] = mock_crm.get_contacts
        except ImportError:
            pass

    def get_available_tools(self) -> list[str]:
        """Get list of available tool names."""
        mcp_names = [t.name for t in self.mcp_tools] if self.mcp_tools else []
        direct_names = list(self._tool_registry.keys())
        return mcp_names + direct_names

    def execute_tool_call(self, tool_name: str, tool_input: dict[str, Any]) -> Any:
        """Execute a single tool call.

        Args:
            tool_name: Name of tool to execute
            tool_input: Tool input arguments

        Returns:
            Raw tool output

        Raises:
            ValueError: If tool not found
        """
        # Try MCP tools first
        for mcp_tool in self.mcp_tools:
            if mcp_tool.name == tool_name:
                return mcp_tool.invoke(tool_input)

        # Try direct tools
        if tool_name in self._tool_registry:
            tool_func = self._tool_registry[tool_name]
            return tool_func(**tool_input)

        raise ValueError(f"Tool not found: {tool_name}")

    def execute_single_task(self, task_input: TaskInput) -> TaskOutput:
        """Execute a single task.

        Args:
            task_input: Task input contract

        Returns:
            Task output contract
        """
        try:
            # Parse the goal to determine what tool to call
            goal = task_input.goal.lower()
            artifacts = {}

            # Determine tool based on goal and file_scope
            if "research" in goal or "company" in goal:
                # Research brief
                company_name = self._extract_company_name(task_input.goal)
                result = self._execute_research(company_name, task_input.file_scope)
                artifacts["research_brief"] = result

            elif "deal" in goal:
                # Deal status
                deal_name = self._extract_deal_name(task_input.goal)
                result = self._execute_deal_lookup(deal_name, task_input.file_scope)
                artifacts["deal_status"] = result

            elif "email" in goal or "draft" in goal:
                # Email draft
                result = self._execute_email_draft(task_input.goal, task_input.constraints)
                artifacts["email_draft"] = result

            elif "pipeline" in goal:
                # Pipeline digest
                result = self._execute_pipeline_digest(task_input.file_scope)
                artifacts["pipeline_digest"] = result

            else:
                # Generic tool execution
                if task_input.file_scope:
                    tool_name = task_input.file_scope[0]
                    raw_output = self.execute_tool_call(tool_name, task_input.constraints)
                    artifacts["raw_output"] = raw_output
                else:
                    return TaskOutput(
                        status="failed",
                        error=f"Could not determine tool from goal: {task_input.goal}"
                    )

            return TaskOutput(
                status="success",
                artifacts=artifacts,
                handoff_notes=f"Executed DIRECT task: {task_input.goal}"
            )

        except Exception as e:
            return TaskOutput(
                status="failed",
                error=str(e),
                handoff_notes=f"Failed to execute: {task_input.goal}"
            )

    def _extract_company_name(self, goal: str) -> str:
        """Extract company name from goal string."""
        # Simple extraction - look for capitalized words after common prefixes
        prefixes = ["research", "company", "about", "for"]
        for prefix in prefixes:
            if prefix in goal.lower():
                parts = goal.split(prefix, 1)
                if len(parts) > 1:
                    return parts[1].strip().split(" ")[0].strip()
        # Fallback: return last capitalized phrase
        return goal.split(" ")[-1].strip()

    def _extract_deal_name(self, goal: str) -> str:
        """Extract deal name from goal string."""
        # Simple extraction
        if "deal" in goal.lower():
            parts = goal.split("deal", 1)
            if len(parts) > 1:
                return parts[1].strip().lstrip("about ").strip()
        return goal

    def _execute_research(self, company_name: str, file_scope: list[str]) -> ResearchBrief:
        """Execute research task."""
        overview = ""
        recent_news = []
        icp_fit = ""
        talking_points = []
        competitors = []
        recommended_approach = ""
        sources = []

        # Web search
        if "web" in file_scope or "tavily" in file_scope:
            try:
                from tools.web_search import search_company_news
                news_results = search_company_news(company_name)
                if news_results:
                    recent_news = news_results.split("\n")[:5]
                    sources.append("web_search")
            except Exception:
                pass

        # RAG search
        if "rag" in file_scope or "chroma" in file_scope:
            try:
                from tools.rag import search as rag_search
                rag_results = rag_search(f"sales approach {company_name} ICP")
                if rag_results:
                    icp_fit = rag_results
                    talking_points = rag_results.split("\n")[:3]
                    sources.append("rag")
            except Exception:
                pass

        # CRM search
        if "crm" in file_scope or "hubspot" in file_scope:
            try:
                from tools.rag import search_crm
                crm_results = search_crm(company_name)
                if crm_results:
                    overview = crm_results
                    sources.append("crm")
            except Exception:
                pass

        # Mock CRM fallback
        if not overview and not recent_news:
            try:
                from tools import mock_crm
                company_data = mock_crm.get_company(company_name)
                if company_data:
                    overview = company_data.get("description", "")
                    sources.append("mock_crm")
            except Exception:
                pass

        return ResearchBrief(
            company_name=company_name,
            overview=overview or f"Research results for {company_name}",
            recent_news=recent_news,
            icp_fit=icp_fit,
            talking_points=talking_points or ["Review company website", "Check recent news", "Identify key stakeholders"],
            competitors=competitors,
            recommended_approach=recommended_approach or "Start with discovery questions about current challenges",
            sources=sources
        )

    def _execute_deal_lookup(self, deal_name: str, file_scope: list[str]) -> DealStatus:
        """Execute deal status lookup."""
        # Try CRM search
        if "crm" in file_scope or "hubspot" in file_scope:
            try:
                from tools.rag import search_crm_deals
                deal_results = search_crm_deals(deal_name)
                if deal_results:
                    # Parse deal info from RAG results
                    return DealStatus(
                        deal_name=deal_name,
                        company_name=deal_name,
                        amount=None,
                        stage="unknown",
                        close_date=None,
                        owner="unknown",
                        health="yellow",
                        next_steps=["Follow up in CRM"],
                        risks=[],
                        recent_activity=[deal_results[:200] if deal_results else "No recent activity"]
                    )
            except Exception:
                pass

        # Mock CRM fallback
        try:
            from tools import mock_crm
            deal = mock_crm.get_deal(deal_name)
            if deal:
                return DealStatus(
                    deal_name=deal.get("deal_name", deal_name),
                    company_name=deal.get("company_name", ""),
                    amount=deal.get("amount"),
                    stage=deal.get("stage", "unknown"),
                    close_date=deal.get("close_date"),
                    owner=deal.get("owner", "unknown"),
                    health="green" if deal.get("stage") in ["closed won", "verbal commit"] else "yellow",
                    next_steps=deal.get("next_steps", []),
                    risks=deal.get("risks", []),
                    recent_activity=deal.get("recent_activity", [])
                )
        except Exception:
            pass

        # Default fallback
        return DealStatus(
            deal_name=deal_name,
            company_name=deal_name,
            amount=None,
            stage="unknown",
            close_date=None,
            owner="unknown",
            health="yellow",
            next_steps=["Look up deal in CRM"],
            risks=["No data found"],
            recent_activity=[]
        )

    def _execute_email_draft(self, goal: str, constraints: dict) -> EmailDraft:
        """Execute email draft task."""
        # Extract recipient info from constraints or goal
        to_name = constraints.get("to_name", "there")
        to_email = constraints.get("to_email", "")
        purpose = constraints.get("purpose", "follow-up")

        # Generate simple draft
        subject = f"Following up on our conversation"
        body = f"""Hi {to_name},

I wanted to follow up on our recent discussion.

[Brief summary of discussion]

Next steps:
- [Action item 1]
- [Action item 2]

Let me know if you have any questions.

Best regards,
[Your name]"""

        return EmailDraft(
            to_name=to_name,
            to_email=to_email,
            subject=subject,
            body=body,
            tone=constraints.get("tone", "professional"),
            purpose=purpose
        )

    def _execute_pipeline_digest(self, file_scope: list[str]) -> PipelineDigest:
        """Execute pipeline digest task."""
        # Try mock CRM
        try:
            from tools import mock_crm
            deals = mock_crm.get_all_open_deals()

            total_deals = len(deals)
            total_value = sum(d.get("amount", 0) for d in deals if d.get("amount"))

            by_stage = {}
            for deal in deals:
                stage = deal.get("stage", "unknown")
                if stage not in by_stage:
                    by_stage[stage] = {"count": 0, "value": 0}
                by_stage[stage]["count"] += 1
                by_stage[stage]["value"] += deal.get("amount", 0)

            return PipelineDigest(
                total_deals=total_deals,
                total_value=total_value,
                by_stage=by_stage,
                at_risk_deals=[d for d in deals if d.get("health") == "red"][:5],
                won_this_period=[d for d in deals if d.get("stage") == "closed won"][:5],
                recommendations=["Review at-risk deals", "Focus on closing end-of-period deals"]
            )
        except Exception as e:
            return PipelineDigest(
                total_deals=0,
                total_value=0,
                by_stage={},
                at_risk_deals=[],
                won_this_period=[],
                recommendations=["Connect to CRM for pipeline data"]
            )


# ─────────────────────────────────────────────────────────────────────────────
# Convenience function
# ─────────────────────────────────────────────────────────────────────────────

_executor_instance: DirectExecutor | None = None


def get_executor(mcp_tools: list | None = None) -> DirectExecutor:
    """Get or create executor instance."""
    global _executor_instance
    if _executor_instance is None:
        _executor_instance = DirectExecutor(mcp_tools)
    return _executor_instance


def execute_direct_task(task_input: TaskInput, mcp_tools: list | None = None) -> TaskOutput:
    """Convenience function to execute a direct task."""
    executor = get_executor(mcp_tools)
    return executor.execute_single_task(task_input)
