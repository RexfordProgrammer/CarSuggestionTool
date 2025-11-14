from typing import List 
import os
from pydantic_models import FullToolSpec, SystemPrompt

def build_system_prompt(specs: List[FullToolSpec], turn: int, max_turns: int) -> SystemPrompt:
    """
    Construct system prompt with tool listings from Pydantic FullToolSpec objects 
    and optional appended rules. Adds urgent final-turn directive when appropriate.
    """
    lines = []
    
    # 1. Build tool list
    for s in specs:
        ts = s.toolSpec
        lines.append(f"- {ts.name}: {ts.description}")
        
    allowed_block = "\n".join(lines) or "- (no tools available)"

    # 2. Load appendix (unchanged)
    appendix_text = ""
    appendix_path = os.path.join(os.path.dirname(__file__), "prompt_append.txt")
    if os.path.exists(appendix_path):
        with open(appendix_path, "r", encoding="utf-8") as f:
            appendix_text = f.read().strip()

    # 3. Base prompt
    base_prompt = (
        "Available tools:\n"
        f"{allowed_block}\n\n"
        "When responding:\n"
        "- Only emit valid `toolUse` blocks when invoking tools.\n"
        "- Never describe tool calls in plain text.\n"
        "- Do NOT include tool JSON in user-visible replies.\n"
        "- Be conversational and concise.\n"
    )

    # 4. Add appendix if exists
    if appendix_text:
        base_prompt += "\n\nADDITIONAL RULES:\n" + appendix_text + "\n"

    # 5. FINAL TURN OVERRIDE: Force immediate final answer
    if turn == max_turns - 1:
        base_prompt += (
            "\n\nTHIS IS YOUR FINAL TURN.\n"
            "You MUST give a direct, complete final answer now.\n"
            "DO NOT call any more tools.\n"
            "DO NOT say you're thinking or planning.\n"
            "Respond immediately with the answer."
        )
    else:
        base_prompt += (
            "\n\nUse tools immediately if needed.\n"
            "Do not overthink or delay action."
        )

    return SystemPrompt(text=str(base_prompt))