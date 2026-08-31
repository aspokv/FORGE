from pathlib import Path

path = Path("backend/server.py")
text = path.read_text(encoding="utf-8-sig")

anchor = '''    client = google_genai.Client(api_key=key)\n    parts = [FORGE_MUSCLE_PROMPT]\n'''
replacement = '''    # Vision model is configurable so a provider retirement does not require another\n    # emergency code change. The default tracks Google's current stable multimodal Flash.\n    model = os.environ.get("GEMINI_VISION_MODEL", "gemini-3.7-flash").strip() or "gemini-3.7-flash"\n    client = google_genai.Client(api_key=key)\n    parts = [FORGE_MUSCLE_PROMPT]\n'''

if text.count(anchor) != 1:
    raise SystemExit(f"Expected exactly one analyze_physique anchor, found {text.count(anchor)}")
if text.count('model="gemini-2.0-flash"') != 1:
    raise SystemExit("Expected exactly one retired Gemini model call")
if text.count('result["model"] = "gemini-2.0-flash"') != 1:
    raise SystemExit("Expected exactly one retired Gemini result label")

text = text.replace(anchor, replacement, 1)
text = text.replace('model="gemini-2.0-flash"', 'model=model', 1)
text = text.replace('result["model"] = "gemini-2.0-flash"', 'result["model"] = model', 1)

path.write_text(text, encoding="utf-8")
print("Vision model patch applied: GEMINI_VISION_MODEL -> gemini-3.7-flash default")
