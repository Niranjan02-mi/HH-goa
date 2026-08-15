"""
Language utilities for text-based auto-detection and normalization.
"""
from typing import TypedDict
import re

class LanguageInfo(TypedDict):
    code: str
    name: str
    script: str

_LANG_MAP = {
    "as": {"code": "as", "name": "Assamese", "script": "Bengali/Assamese"},
    "bn": {"code": "bn", "name": "Bengali", "script": "Bengali"},
    "gu": {"code": "gu", "name": "Gujarati", "script": "Gujarati"},
    "hi": {"code": "hi", "name": "Hindi", "script": "Devanagari"},
    "kn": {"code": "kn", "name": "Kannada", "script": "Kannada"},
    "ml": {"code": "ml", "name": "Malayalam", "script": "Malayalam"},
    "mr": {"code": "mr", "name": "Marathi", "script": "Devanagari"},
    "ne": {"code": "ne", "name": "Nepali", "script": "Devanagari"},
    "or": {"code": "or", "name": "Odia", "script": "Odia"},
    "pa": {"code": "pa", "name": "Punjabi", "script": "Gurmukhi"},
    "ta": {"code": "ta", "name": "Tamil", "script": "Tamil"},
    "te": {"code": "te", "name": "Telugu", "script": "Telugu"},
    "ur": {"code": "ur", "name": "Urdu", "script": "Arabic"},
    "en": {"code": "en", "name": "English", "script": "Latin"},
}

def normalize_language_code(code: str) -> str:
    """Normalize regional codes like hi-IN to hi."""
    if not code:
        return "en"
    code = code.lower().strip()
    if "-" in code:
        code = code.split("-")[0]
    return code if code in _LANG_MAP else "en"

def language_name(code: str) -> str:
    code = normalize_language_code(code)
    return _LANG_MAP[code]["name"]

def script_name(code: str) -> str:
    code = normalize_language_code(code)
    return _LANG_MAP[code]["script"]

def detect_language(text: str) -> LanguageInfo:
    """
    Very basic heuristic language detection based on Unicode block.
    """
    if not text:
        return _LANG_MAP["en"]

    text = text.strip()
    
    # Check for Devanagari block (\u0900-\u097F)
    if re.search(r'[\u0900-\u097F]', text):
        return _LANG_MAP["hi"]
    
    # Bengali (\u0980-\u09FF)
    if re.search(r'[\u0980-\u09FF]', text):
        return _LANG_MAP["bn"]
        
    # Gujarati (\u0A80-\u0AFF)
    if re.search(r'[\u0A80-\u0AFF]', text):
        return _LANG_MAP["gu"]
        
    # Gurmukhi/Punjabi (\u0A00-\u0A7F)
    if re.search(r'[\u0A00-\u0A7F]', text):
        return _LANG_MAP["pa"]
        
    # Oriya/Odia (\u0B00-\u0B7F)
    if re.search(r'[\u0B00-\u0B7F]', text):
        return _LANG_MAP["or"]
        
    # Tamil (\u0B80-\u0BFF)
    if re.search(r'[\u0B80-\u0BFF]', text):
        return _LANG_MAP["ta"]
        
    # Telugu (\u0C00-\u0C7F)
    if re.search(r'[\u0C00-\u0C7F]', text):
        return _LANG_MAP["te"]
        
    # Kannada (\u0C80-\u0CFF)
    if re.search(r'[\u0C80-\u0CFF]', text):
        return _LANG_MAP["kn"]
        
    # Malayalam (\u0D00-\u0D7F)
    if re.search(r'[\u0D00-\u0D7F]', text):
        return _LANG_MAP["ml"]
        
    # Arabic/Urdu (\u0600-\u06FF)
    if re.search(r'[\u0600-\u06FF]', text):
        return _LANG_MAP["ur"]

    # Default to English
    return _LANG_MAP["en"]
