"""Keyword-based and optional LLM judging for story winner."""
import random
import re
from typing import List, Tuple, Optional

from config import JUDGE_PROVIDER, OPENAI_API_KEY

# Preference -> list of keywords (lowercase) for counting in full story text
PreferenceKeywords = {
    "dark": ["dark", "death", "shadow", "blood", "fear", "horror", "night", "evil", "doom", "curse", "grim", "hopeless"],
    "romantic": ["love", "heart", "kiss", "romance", "passion", "together", "forever", "soulmate", "embrace", "devotion"],
    "melodramatic": ["tears", "tragedy", "fate", "destiny", "never", "always", "cry", "anguish", "drama", "sorrow", "betrayal"],
    "suspenseful": ["mystery", "secret", "danger", "hidden", "suddenly", "unknown", "tension", "cliff", "reveal", "suspense"],
    "comedic": ["laugh", "joke", "funny", "silly", "humor", "comedy", "absurd", "wit", "chuckle", "hilarious"],
}


def _sentence_count(text: str) -> int:
    """Count sentences: ., !, ? or Chinese equivalents (。！？)."""
    if not text or not str(text).strip():
        return 0
    # Split on sentence-ending punctuation (Latin + Chinese)
    parts = re.split(r"[.!?。！？]+", str(text).strip())
    return len([p for p in parts if p.strip()])


def count_sentences(text: str) -> int:
    """Public helper for validation: 2-3 sentences required per turn."""
    return _sentence_count(text)


def _keyword_score(full_text: str, preference: str) -> int:
    pref = preference.lower().strip()
    keywords = PreferenceKeywords.get(pref, [])
    if not keywords:
        return 0
    lower = full_text.lower()
    return sum(lower.count(k) for k in keywords)


def _keyword_judge(
    full_story: str,
    participants: List[Tuple[int, str, int]],  # (agent_id, preference, turns_used)
    last_speaker_agent_id: Optional[int],
) -> Tuple[int, str]:
    """
    Returns (winner_agent_id, method_used).
    Tie-break: 1) higher turns_used, 2) last speaker, 3) random.
    """
    if not participants:
        return (None, "keyword")
    scores = [(agent_id, _keyword_score(full_story, pref), turns_used) for agent_id, pref, turns_used in participants]
    max_score = max(s[1] for s in scores)
    candidates = [s for s in scores if s[1] == max_score]
    if len(candidates) == 1:
        return (candidates[0][0], "keyword")
    # Tie: higher turns_used wins
    max_turns = max(c[2] for c in candidates)
    candidates = [c for c in candidates if c[2] == max_turns]
    if len(candidates) == 1:
        return (candidates[0][0], "keyword")
    # Tie: last speaker wins
    if last_speaker_agent_id and any(c[0] == last_speaker_agent_id for c in candidates):
        return (last_speaker_agent_id, "keyword")
    # Random
    return (random.choice(candidates)[0], "keyword")


def _llm_judge(
    full_story: str,
    participants: List[Tuple[int, str, str, int]],  # (agent_id, name, preference, turns_used)
) -> Tuple[Optional[int], str, Optional[str]]:
    """Returns (winner_agent_id, "llm", reason). Uses OpenAI if available."""
    if not OPENAI_API_KEY or JUDGE_PROVIDER != "openai":
        return (None, "keyword", None)
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        parts_desc = "\n".join(
            f"- Agent '{name}' (id={aid}): preference='{pref}', turns_used={turns}"
            for aid, name, pref, turns in participants
        )
        prompt = f"""You are a judge for a collaborative story. Score each agent 0-10 on how well the story aligns with their declared preference. Only output a JSON object with keys being agent id (as integer) and value being {{"score": 0-10, "reason": "short reason"}}. Example: {{"1": {{"score": 7, "reason": "..."}}, "2": {{"score": 4, "reason": "..."}}}}. No other text.

Story:
{full_story}

Participants:
{parts_desc}
"""
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        content = (resp.choices[0].message.content or "").strip()
        # Parse JSON from content (allow markdown code block)
        import json
        if "```" in content:
            content = content.split("```")[1].replace("json", "").strip()
        data = json.loads(content)
        best_id, best_score, reason = None, -1, None
        for k, v in data.items():
            try:
                aid = int(k)
                score = int(v.get("score", 0))
                if score > best_score:
                    best_score = score
                    best_id = aid
                    reason = v.get("reason", "")
            except (ValueError, TypeError):
                continue
        return (best_id, "llm", reason)
    except Exception:
        return (None, "keyword", None)


def judge_story(
    full_story: str,
    participants: List[Tuple[int, str, str, int]],  # (agent_id, name, preference, turns_used)
    last_speaker_agent_id: Optional[int],
    use_llm: bool = False,
) -> Tuple[Optional[int], str]:
    """
    Returns (winner_agent_id, judge_method).
    If use_llm and JUDGE_PROVIDER=openai and OPENAI_API_KEY set, use LLM; else keyword.
    """
    if use_llm and JUDGE_PROVIDER == "openai" and OPENAI_API_KEY:
        winner, method, _ = _llm_judge(full_story, participants)
        if winner is not None:
            return (winner, method)
    # Fallback to keyword
    parts = [(aid, pref, turns) for aid, name, pref, turns in participants]
    winner, _ = _keyword_judge(full_story, parts, last_speaker_agent_id)
    return (winner, "keyword")
