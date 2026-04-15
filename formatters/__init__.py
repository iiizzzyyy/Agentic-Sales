"""Block Kit formatters for Slack responses."""
from formatters.helpers import timestamp, truncate, format_currency
from formatters.research import format_research_response, format_research_summary
from formatters.deal import format_deal_response, format_deal_picker
from formatters.coach import format_roleplay_start, format_roleplay_debrief
from formatters.email import format_email_draft, format_contact_picker, format_email_deal_picker
from formatters.pipeline import format_pipeline_response
from formatters.objection import format_objection_response
from formatters.ask import format_ask_response
from formatters.followup import format_followup_response
from formatters.competitor import format_competitor_response
from formatters.battlecard import format_battlecard_picker, format_battlecard_response
from formatters.alerts import format_alerts_digest, format_single_alert
from formatters.forecast import format_forecast_response
from formatters.win_loss import format_win_loss_response
from formatters.persona import format_persona_response
from formatters.handoff import format_handoff_response, format_handoff_summary
from formatters.email_sequence import format_email_sequence_response
from formatters.coach_live import format_coach_live_start, format_coach_live_tip, format_coach_live_summary
from formatters.demo_flow import format_demo_welcome, format_demo_step_intro, format_demo_step_nav, format_demo_complete, DEMO_STEPS
from formatters.training_history import format_training_history
from formatters.skill_gaps import format_skill_gaps
from formatters.crm_detect import format_crm_suggestion

__all__ = [
    "timestamp",
    "truncate",
    "format_currency",
    "format_research_response",
    "format_research_summary",
    "format_deal_response",
    "format_deal_picker",
    "format_roleplay_start",
    "format_roleplay_debrief",
    "format_email_draft",
    "format_contact_picker",
    "format_email_deal_picker",
    "format_pipeline_response",
    "format_objection_response",
    "format_ask_response",
    "format_followup_response",
    "format_competitor_response",
    "format_battlecard_picker",
    "format_battlecard_response",
    "format_alerts_digest",
    "format_single_alert",
    "format_forecast_response",
    "format_win_loss_response",
    "format_persona_response",
    "format_handoff_response",
    "format_handoff_summary",
    "format_email_sequence_response",
    "format_coach_live_start",
    "format_coach_live_tip",
    "format_coach_live_summary",
    "format_demo_welcome",
    "format_demo_step_intro",
    "format_demo_step_nav",
    "format_demo_complete",
    "DEMO_STEPS",
    "format_training_history",
    "format_skill_gaps",
    "format_crm_suggestion",
]
