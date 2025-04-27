import re
import time
from typing import List, Any, Optional
import google.generativeai as genai

_INLINE_DOLLARS = re.compile(r"(?<!\\)\\$([^$]+?)\\$")       # $...$  → \\( ... \\)
_DOUBLE_LBRACE  = re.compile(r"\\{\\{")                     # {{     → \\\{
_DOUBLE_RBRACE  = re.compile(r"\\}\\}")                     # }}     → \\\}

# sanitize_input

def sanitize_input(text: str) -> str:
    return ' '.join(text.strip().split())

# clean_code_string

def clean_code_string(code: str) -> str:
    if code.startswith('```'):
        lines = code.splitlines()[1:]
        if lines and lines[-1].strip() == '```':
            lines = lines[:-1]
        return '\n'.join(lines).strip()
    return code

# fix_inline_latex

def fix_inline_latex(code: str) -> str:
    code = _INLINE_DOLLARS.sub(lambda m: f"\\({m.group(1).strip()}\\)", code)
    code = _DOUBLE_LBRACE.sub(r"\\{", code)
    code = _DOUBLE_RBRACE.sub(r"\\}", code)
    return code

# estimate_scene_time

def estimate_scene_time(code: str) -> float:
    WAIT_RE = re.compile(r"\\.wait\\(\\s*([0-9.]+)\\s*\\)")
    PLAY_RE = re.compile(r"\.play\(") # Corrected regex to match '.play('
    waits = [float(x) for x in WAIT_RE.findall(code)]
    plays = len(PLAY_RE.findall(code))
    return sum(waits) + plays * 2.0

def upload_to_gemini(path: str, mime_type: Optional[str] = None) -> Any:
    """Uploads the given file to Gemini and returns the file object."""
    return genai.upload_file(path, mime_type=mime_type)

def wait_for_files_active(files: List[Any]) -> None:
    """Blocks until all uploaded files are processed and active in Gemini."""
    for file in files:
        f = genai.get_file(file.name)
        while f.state.name == "PROCESSING":
            time.sleep(10)
            f = genai.get_file(file.name)
        if f.state.name != "ACTIVE":
            raise Exception(f"File {f.name} failed to process")
