from typing import Dict, Any, List 
import os


def build_system_prompt(specs: List[Dict[str, Any]]) -> str:
    """Construct system prompt with tool listings and optional appended rules."""
    lines = []
    for s in specs:
        ts = s.get("toolSpec", s)
        lines.append(f"- {ts.get('name')}: {ts.get('description')}")
    allowed_block = "\n".join(lines) or "- (no tools available)"

    appendix_text = ""
    appendix_path = os.path.join(os.path.dirname(__file__), "prompt_append.txt")
    if os.path.exists(appendix_path):
        with open(appendix_path, "r", encoding="utf-8") as f:
            appendix_text = f.read().strip()

    base_prompt = (
        "Available tools:\n"
        f"{allowed_block}\n\n"
        "When responding:\n"
        "- Only emit valid `toolUse` blocks when invoking tools.\n"
        "- Never describe tool calls in plain text.\n"
        "- Do NOT include tool JSON in user-visible replies.\n"
        "- Be conversational and concise.\n"
    )
    if appendix_text:
        base_prompt += "\n\nADDITIONAL RULES:\n" + appendix_text + "\n"
    return base_prompt