"""
Language/i18n utilities for multi-language support.
"""

# Supported languages with display names
SUPPORTED_LANGUAGES = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "pt": "Portuguese",
    "ja": "Japanese",
    "zh": "Chinese (Simplified)",
    "ko": "Korean"
}

# UI strings for common elements
UI_STRINGS = {
    "en": {
        "my_day_header": "Your Day",
        "no_meetings": "No meetings scheduled for today. Great time to focus on outreach or training!",
        "start_training": "Start Training",
        "view_pipeline": "View Pipeline",
        "customer_meetings": "Customer Meetings",
        "internal": "Internal",
        "training": "Training",
        "prep": "Prep",
        "join": "Join",
        "team_dashboard_header": "Team Training Dashboard",
        "no_training_data": "No training data yet. Team members need to complete training sessions to appear here.",
        "total_sessions": "Total Sessions",
        "team_avg_score": "Team Avg Score",
        "active_reps": "Active Reps",
        "this_week": "This Week",
        "leaderboard": "Leaderboard (by avg score)",
        "assign_training": "Assign Training",
        "view_cohorts": "View Cohorts",
        "export_report": "Export Report",
        "cohorts_header": "Training Cohorts",
        "no_cohorts": "No cohorts created yet. Use `/create-cohort` to create one.",
        "view_progress": "View Progress",
        "create_new_cohort": "Create New Cohort",
        "participants": "Participants",
        "graduated": "Graduated",
        "avg_completion": "Avg Completion",
        "avg_score": "Avg Score",
        "market_insights_header": "Market Insights",
        "industry_trends": "Industry Trends",
        "competitor_watch": "Competitor Watch",
        "customer_signals": "Customer Signals",
        "market_stats": "Market Stats",
        "search_insights": "Search Insights",
        "view_all_competitors": "View All Competitors",
        "scenarios_header": "Scenario Library",
        "no_scenarios": "No saved scenarios yet. Use `/create-scenario` to create one.",
        "create_scenario": "Create Scenario",
        "launch": "Launch",
        "assign": "Assign",
        "assignments_header": "Your Assignments",
        "no_assignments": "No pending assignments. Check with your manager or practice on your own!",
        "start": "Start",
        "due": "Due",
        "completed": "Completed",
        "pending": "Pending"
    },
    "es": {
        "my_day_header": "Tu Dia",
        "no_meetings": "No hay reuniones programadas para hoy. Buen momento para contactar prospectos o entrenar!",
        "start_training": "Iniciar Entrenamiento",
        "view_pipeline": "Ver Pipeline",
        "customer_meetings": "Reuniones con Clientes",
        "internal": "Interno",
        "training": "Entrenamiento",
        "prep": "Preparar",
        "join": "Unirse",
        "team_dashboard_header": "Panel del Equipo",
        "total_sessions": "Sesiones Totales",
        "team_avg_score": "Promedio del Equipo",
        "active_reps": "Reps Activos",
        "leaderboard": "Clasificacion (por promedio)",
        "assign_training": "Asignar Entrenamiento",
        "scenarios_header": "Biblioteca de Escenarios",
        "create_scenario": "Crear Escenario",
        "launch": "Lanzar",
        "assign": "Asignar",
        "assignments_header": "Tus Asignaciones",
        "start": "Iniciar",
        "due": "Vence",
        "completed": "Completado",
        "pending": "Pendiente"
    },
    "fr": {
        "my_day_header": "Votre Journee",
        "no_meetings": "Aucune reunion prevue aujourd'hui. Bon moment pour la prospection ou la formation!",
        "start_training": "Commencer Formation",
        "view_pipeline": "Voir Pipeline",
        "customer_meetings": "Reunions Clients",
        "internal": "Interne",
        "training": "Formation",
        "prep": "Preparer",
        "join": "Rejoindre",
        "team_dashboard_header": "Tableau de Bord Equipe",
        "total_sessions": "Sessions Totales",
        "team_avg_score": "Moyenne Equipe",
        "leaderboard": "Classement (par moyenne)",
        "scenarios_header": "Bibliotheque de Scenarios",
        "create_scenario": "Creer Scenario",
        "launch": "Lancer",
        "assign": "Assigner"
    },
    "de": {
        "my_day_header": "Ihr Tag",
        "no_meetings": "Heute keine Meetings geplant. Gute Zeit fur Akquise oder Training!",
        "start_training": "Training Starten",
        "view_pipeline": "Pipeline Anzeigen",
        "customer_meetings": "Kundenmeetings",
        "internal": "Intern",
        "training": "Training",
        "team_dashboard_header": "Team-Dashboard",
        "total_sessions": "Gesamte Sitzungen",
        "team_avg_score": "Team-Durchschnitt",
        "leaderboard": "Rangliste (nach Durchschnitt)",
        "scenarios_header": "Szenario-Bibliothek",
        "create_scenario": "Szenario Erstellen"
    }
}

# LLM prompt language instructions
LLM_LANGUAGE_PROMPTS = {
    "en": "Respond in English.",
    "es": "Responde en espanol. Usa un tono profesional pero amigable.",
    "fr": "Reponds en francais. Utilise un ton professionnel mais amical.",
    "de": "Antworte auf Deutsch. Verwende einen professionellen aber freundlichen Ton.",
    "pt": "Responda em portugues. Use um tom profissional mas amigavel.",
    "ja": "日本語で応答してください。プロフェッショナルで親しみやすいトーンを使用してください。",
    "zh": "请用中文回复。使用专业但友好的语气。",
    "ko": "한국어로 응답해 주세요. 전문적이면서도 친근한 어조를 사용하세요."
}


def get_ui_string(key, language="en"):
    """
    Get a UI string in the specified language.

    Args:
        key: String key (e.g., 'my_day_header')
        language: Language code (e.g., 'en', 'es')

    Returns:
        Translated string, falls back to English if not found
    """
    lang_strings = UI_STRINGS.get(language, UI_STRINGS["en"])
    return lang_strings.get(key, UI_STRINGS["en"].get(key, key))


def get_llm_language_prompt(language="en"):
    """
    Get the language instruction to prepend to LLM prompts.

    Args:
        language: Language code

    Returns:
        Language instruction string for LLM
    """
    return LLM_LANGUAGE_PROMPTS.get(language, LLM_LANGUAGE_PROMPTS["en"])


def get_language_name(code):
    """
    Get the display name for a language code.

    Args:
        code: Language code (e.g., 'en')

    Returns:
        Display name (e.g., 'English')
    """
    return SUPPORTED_LANGUAGES.get(code, code)


def get_supported_languages():
    """
    Get list of supported languages for settings UI.

    Returns:
        List of dicts with code and name
    """
    return [{"code": code, "name": name} for code, name in SUPPORTED_LANGUAGES.items()]


def format_language_options_for_slack():
    """
    Format language options for Slack select menu.

    Returns:
        List of Slack option objects
    """
    return [
        {
            "text": {"type": "plain_text", "text": name},
            "value": code
        }
        for code, name in SUPPORTED_LANGUAGES.items()
    ]
