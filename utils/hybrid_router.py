"""
Hybrid AI Router
================
Classifies user input into one of three modes:
  - RAG     → answer strictly from retrieved document context
  - CODE    → structured code assistant response
  - HYBRID  → combine retrieved context + code generation

Used by the /api/hybrid-chat endpoint in app.py.
"""

import re
from typing import Optional, Dict, Any
from openai import OpenAI


# ---------------------------------------------------------------------------
# Mode keywords
# ---------------------------------------------------------------------------

_CODE_KEYWORDS = [
    "fix", "bug", "error", "exception", "traceback", "debug",
    "optimize", "refactor", "explain this code", "generate", "create api",
    "build", "implement", "write a function", "write code", "write a script",
    "snippet", "class", "def ", "import ", "syntax", "compile",
    "sql", "query", "endpoint", "flask", "fastapi", "django", "node",
    "javascript", "python", "typescript", "java", "c++", "rust", "go", "php", "ruby", "c#", "swift", "kotlin", "sql", "html", "css",
    "math", "algorithm", "data structure", "how to"
]

_DATA_SCIENCE_KEYWORDS = [
    "data science", "machine learning", "sklearn", "pandas", "numpy", "matplotlib", "seaborn", 
    "keras", "tensorflow", "pytorch", "model", "training", "evaluation", "eda", "regression", 
    "classification", "neural network", "deep learning", "predict", "dataset"
]

_STUDY_KEYWORDS = [
    "concept", "explain", "study", "what is", "tutorial", "learn", "how it works", 
    "theoretical", "academic", "definition", "fundamentals"
]

_CAREER_KEYWORDS = [
    "career", "resume", "interview", "freelancing", "job", "roadmap", "salary", 
    "upwork", "fiverr", "client", "portfolio", "linkedin"
]

_IMAGE_GEN_KEYWORDS = [
    "generate image", "create image", "draw", "visualize", "dall-e", "stable diffusion", "prompt for image",
    "midjourney", "art style", "lighting"
]

_REPORT_KEYWORDS = [
    "report", "document", "abstract", "methodology", "conclusion", "formal", "academic report",
    "case study", "analysis document"
]

_RAG_KEYWORDS = [
    "document", "pdf", "uploaded", "knowledge base", "according to", "based on the", 
    "in the document", "from the file", "summarize the", "what is mentioned", "cite"
]


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------

def detect_mode(user_input: str, has_context: bool) -> str:
    """Return 'RAG', 'CODE', 'DS', 'STUDY', 'CAREER', 'IMAGE', or 'REPORT'."""
    lower = user_input.lower()
    words = set(re.findall(r'\b\w+\b', lower))

    # Score based on word presence
    report_score = sum(1 for kw in _REPORT_KEYWORDS if kw in lower)
    image_score = sum(1 for kw in _IMAGE_GEN_KEYWORDS if any(sub in lower for sub in kw.split()))
    code_score = sum(1 for kw in _CODE_KEYWORDS if kw in lower or kw.strip() in words)
    ds_score = sum(1 for kw in _DATA_SCIENCE_KEYWORDS if kw in lower)
    career_score = sum(1 for kw in _CAREER_KEYWORDS if kw in lower)
    study_score = sum(1 for kw in _STUDY_KEYWORDS if kw in lower)
    rag_score = sum(1 for kw in _RAG_KEYWORDS if kw in lower) + (2 if has_context else 0)

    # Ranking (Priority)
    if image_score >= 1: return "IMAGE"
    if report_score >= 1: return "REPORT"
    if career_score >= 1: return "CAREER"
    if ds_score >= 1: return "DS"
    if code_score >= 1 and (rag_score >= 3 or (has_context and rag_score >= 1)): return "HYBRID"
    if code_score >= 1: return "CODE"
    if rag_score >= 1 or has_context: return "RAG"
    if study_score >= 1: return "STUDY"
    
    return "CODE" if not has_context else "RAG"


# ---------------------------------------------------------------------------
# System prompts per mode
# ---------------------------------------------------------------------------

_MASTER_CORE = """You are an advanced AI Smart Assistant created by Ganesh.
CORE BEHAVIOR:
- Always give clear, structured, and practical answers.
- Explain concepts in simple terms first, then advanced.
- If user is a beginner, simplify aggressively.
- If user is advanced, provide deep technical detail.
- **IMPORTANT**: If a request is unclear, vague, or missing critical details, STOP and ask the user clarifying questions before proceeding."""

_RAG_SYSTEM = _MASTER_CORE + """
RAG MODE (Knowledge Retrieval):
- Your priority is to answer using the context below.
- If the question is about the document but the info is missing → say "Not found in documents."
- For general greetings or short non-document queries, respond politely and helpfully.
{context}"""

_CODE_SYSTEM = _MASTER_CORE + """
CODING MODE:
When given a task:
- If the coding task is missing the language, environment, or specific goal, ask for clarification.
- For DEBUGGING: If the user didn't provide the error message or the full code, ask for it.
- 🔍 Problem: brief overview.
- ✅ Code: Complete working code with comments.
- 💡 Explanation: reasoning."""

_DS_SYSTEM = _MASTER_CORE + """
DATA SCIENCE MODE:
- Ask about the nature of the data (size, features, target) if it's not clear.
- Provide ML workflow: EDA → Model → Evaluation."""

_IMAGE_SYSTEM = _MASTER_CORE + """
IMAGE PROMPT MODE:
- If the image idea is brief (e.g., "draw a dog"), ask the user for details like style (cyberpunk, oil painting, minimalist), lighting, and mood.
- Once clarified, convert the idea into a highly detailed, descriptive prompt.
- **CRITICAL**: Your response must contain ONLY the final prompt. Do not include any conversational filler like "Sure", "Here is your prompt", or "I have created..."."""

_REPORT_SYSTEM = _MASTER_CORE + """
REPORT / DOCUMENT MODE:
- Use formal academic tone.
- Format: Title, Abstract, Introduction, Methodology, Results, Conclusion."""

_CAREER_SYSTEM = _MASTER_CORE + """
CAREER & FREELANCING MODE:
- Provide actionable steps, roadmap, and suggested tools/platforms (Upwork, Fiverr).
- Focus on real-world execution."""

_HYBRID_SYSTEM = _MASTER_CORE + """
HYBRID MODE (Document context + Expertise):
- Use document info {context} AND your advanced reasoning.
- Follow the structured Code/DS formats if relevant."""


# ---------------------------------------------------------------------------
# HybridRouter class
# ---------------------------------------------------------------------------

class HybridRouter:
    def __init__(self, client: OpenAI, model: str = "google/gemini-2.0-flash-001"):
        self.client = client
        self.model = model

    def route(
        self,
        user_input: str,
        text_context: str = "",
        chat_history: Optional[list] = None,
    ) -> Dict[str, Any]:
        """
        Main entry point. Returns:
        {
          "mode": "RAG" | "CODE" | "HYBRID",
          "answer": str,
          "model": str,
        }
        """
        has_context = bool(text_context and text_context.strip())
        mode = detect_mode(user_input, has_context)

        system_prompt = self._build_system(mode, text_context)
        messages = [{"role": "system", "content": system_prompt}]

        # Inject recent history (last 6 turns for context continuity)
        if chat_history:
            for turn in chat_history[-6:]:
                messages.append({"role": turn["role"], "content": turn["content"]})

        messages.append({"role": "user", "content": user_input})

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.15,
            )
            answer = response.choices[0].message.content
        except Exception as e:
            answer = f"❌ LLM Error: {str(e)}"

        return {
            "mode": mode,
            "answer": answer,
            "model": self.model,
        }

    # ------------------------------------------------------------------
    def _build_system(self, mode: str, context: str) -> str:
        ctx = context.strip() if context else "[No document context available]"
        if mode == "RAG": return _RAG_SYSTEM.format(context=ctx)
        if mode == "CODE": return _CODE_SYSTEM
        if mode == "DS": return _DS_SYSTEM
        if mode == "IMAGE": return _IMAGE_SYSTEM
        if mode == "REPORT": return _REPORT_SYSTEM
        if mode == "CAREER": return _CAREER_SYSTEM
        if mode == "HYBRID": return _HYBRID_SYSTEM.format(context=ctx)
        return _MASTER_CORE + "\nGeneral Assistant mode."
