import os
import re
import requests
from dotenv import load_dotenv
from pathlib import Path
from typing import Dict, Any, Optional
from app.config import Config
load_dotenv(override=True)
DISCIPLINE_TEMPLATES = {
    "web development": {
        "Professional": "Design, engineering, and deployment of a responsive web application including frontend interface development, backend REST API integration, performance optimization, and cross-browser QA testing.",
        "Simple": "Full-stack web application development and website implementation.",
        "Detailed": "End-to-end full-stack web engineering: UI component architecture in responsive HTML5/CSS3/JS, backend business logic implementation, database schema design, automated endpoint validation, staging deployment, and production cutover support."
    },
    "ui/ux": {
        "Professional": "Comprehensive UI/UX design deliverables including user research synthesis, wireframing, high-fidelity Figma design systems, interactive click-through prototypes, and design asset handoff.",
        "Simple": "UI/UX wireframing, visual design mockups, and interactive prototype delivery.",
        "Detailed": "End-to-end digital product design: user journey mapping, design token architecture, high-fidelity responsive interface layouts, interactive component states, typography/color specifications, and engineering design handoff."
    },
    "mobile app": {
        "Professional": "Native/cross-platform mobile application development including user interface implementation, API synchronization, local state caching, and app store release preparation.",
        "Simple": "Mobile application development, bug fixes, and feature integration.",
        "Detailed": "Mobile software development lifecycle: architecture setup, navigation and reactive state management, asynchronous backend integration, push notification handling, device compatibility testing, and build packaging."
    },
    "seo": {
        "Professional": "Search Engine Optimization audit and implementation covering technical SEO improvements, metadata restructuring, structured schema markup, and keyword search visibility optimization.",
        "Simple": "SEO technical audit, on-page optimization, and performance reporting.",
        "Detailed": "Comprehensive search engine optimization: core web vitals speed optimization, canonical & indexation audit, structured data schema deployment, on-page content alignment, and baseline ranking reporting."
    },
    "content": {
        "Professional": "Strategic content writing and technical copywriting including research, target persona alignment, SEO keyword integration, proofreading, and final editorial delivery.",
        "Simple": "Professional copywriting, blog articles, and documentation content.",
        "Detailed": "Content strategy and multi-format editorial copywriting: topic research, outline creation, draft composition with targeted industry terminology, meta descriptions, revision cycles, and publication formatting."
    },
    "consulting": {
        "Professional": "Strategic technical advisory, software architecture review, technology stack assessment, and executive recommendations for engineering execution.",
        "Simple": "Technical consulting, system design advisory, and roadmap planning sessions.",
        "Detailed": "In-depth engineering advisory and strategic roadmap planning: current-state architecture analysis, bottleneck identification, technology selection matrix, feasibility evaluation, and actionable milestone documentation."
    },
    "data science": {
        "Professional": "Data pipeline engineering, exploratory statistical analysis, feature modeling, and automated visualization reporting for business intelligence.",
        "Simple": "Data analysis, predictive modeling, and business insights dashboard creation.",
        "Detailed": "Full-lifecycle data science & AI development: data ingestion, cleaning and preprocessing, feature engineering, statistical algorithm evaluation, hyperparameter tuning, model artifact export, and performance evaluation documentation."
    }
}


def get_fallback_description(service_name: str,
                             tone: str = "Professional") -> str:
    """Provides high-quality fallback text based on keyword matching."""
    service_lower = service_name.lower().strip()
    tone_key = tone.capitalize()if tone.capitalize() in (
        "Professional", "Simple", "Detailed")else "Professional"
    for key, tone_dict in DISCIPLINE_TEMPLATES.items():
        if key in service_lower or any(
                word in service_lower for word in key.split()):
            return tone_dict.get(tone_key, tone_dict["Professional"])
    if tone_key == "Simple":
        return f"Professional {service_name} services and project deliverables."
    elif tone_key == "Detailed":
        return f"Comprehensive execution of {service_name}: requirements analysis, iterative development, quality assurance testing, documentation, and stakeholder review."
    else:
        return f"Professional execution and delivery of {service_name} in accordance with agreed project specifications, deliverables, and quality standards."


def generate_invoice_description(
    service_name: str,
    context: str = "",
    tone: str = "Professional"
) -> Dict[str, Any]:
    """
    Generates a concise, polished freelance line-item description.
    Uses LLM API if key is configured, otherwise uses deterministic fallback engine.
    """
    if not service_name or not service_name.strip():
        return {
            "success": False,
            "description": "",
            "message": "Please enter a service name to generate a description."
        }
    api_key = os.getenv("AI_API_KEY") or Config.AI_API_KEY
    ai_provider = os.getenv("AI_PROVIDER") or Config.AI_PROVIDER
    ai_model = os.getenv("AI_MODEL") or Config.AI_MODEL
    if not api_key:
        fallback_desc = get_fallback_description(service_name, tone)
        return {
            "success": True,
            "description": fallback_desc,
            "source": "template_engine",
            "message": "Generated using built-in professional template engine (AI API key not configured)."
        }
    prompt = (
        f"You are a professional freelance billing assistant.Generate a single clear, realistic, and polished "
        f"invoice line-item description for the service: '{service_name}'.\n"
        f"Context/Notes: '{context}'.\n"
        f"Tone: {tone}.\n"
        f"Rules: Return ONLY the description text.Do NOT generate prices, hours, currencies, or formatting headers.Keep it between 15 to 45 words."
    )
    try:
        is_groq = ai_provider == "groq" or (
            api_key and api_key.startswith("gsk_"))
        if is_groq:
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"}
            groq_model = ai_model if ai_model else "groq/compound-mini"
            payload = {
                "model": groq_model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 120,
                "temperature": 0.3
            }
            resp = requests.post(
                url, json=payload, headers=headers, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                text = data["choices"][0]["message"]["content"].strip()
                text = re.sub(
                    r"<think>.*?</think>",
                    "",
                    text,
                    flags=re.DOTALL).strip()
                text = text.replace(
                    "\u2011", "-").replace("\u2013", "-").replace("\u2014", "-")
                text = text.replace(
                    "\u2018",
                    "'").replace(
                    "\u2019",
                    "'").replace(
                    "\u201c",
                    '"').replace(
                    "\u201d",
                    '"')
                return {
                    "success": True,
                    "description": text,
                    "source": "groq_ai",
                    "message": "Generated with Groq AI Assistant."
                }
        elif Config.AI_PROVIDER == "gemini":
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{Config.AI_MODEL}:generateContent?key={api_key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.3, "maxOutputTokens": 100}
            }
            resp = requests.post(url, json=payload, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                return {
                    "success": True,
                    "description": text,
                    "source": "gemini_ai",
                    "message": "Generated with AI Assistant."
                }
        elif Config.AI_PROVIDER == "openai":
            url = "https://api.openai.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"}
            payload = {
                "model": "gpt-3.5-turbo",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 100,
                "temperature": 0.3
            }
            resp = requests.post(
                url, json=payload, headers=headers, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                text = data["choices"][0]["message"]["content"].strip()
                return {
                    "success": True,
                    "description": text,
                    "source": "openai",
                    "message": "Generated with AI Assistant."
                }
    except Exception as e:
        print(f"AI Generation Request Error: {e}")
    fallback_desc = get_fallback_description(service_name, tone)
    return {
        "success": True,
        "description": fallback_desc,
        "source": "template_engine_fallback",
        "message": "AI service was unreachable; generated description using professional fallback engine."
    }
