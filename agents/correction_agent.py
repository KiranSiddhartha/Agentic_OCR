 
# agents/correction_agent.py
# WITH NOISE REMOVAL: Removes garbled text like "-aennen ar aeraan"
import re
from utils.dictionary import OCR_FIXES

def correct_lines(lines):
    """
    Correction with NOISE REMOVAL.
    Removes garbled text and OCR artifacts.
    """
    if not lines:
        return []
    
    corrected = []
    
    for line in lines:
        if not line or not line.strip():
            continue
        
        # Stage 1: Remove garbled text (repeating nonsense patterns)
        line = remove_garbled_text(line)
        
        # Stage 2: Dictionary fixes
        line = apply_dictionary_fixes(line)
        
        # Stage 3: Character corrections
        line = fix_obvious_chars(line)
        
        # Stage 4: Spacing cleanup
        line = re.sub(r'\s+', ' ', line).strip()
        
        # Stage 5: Validate line quality
        if is_valid_line(line):
            corrected.append(line)
    
    return corrected


def remove_garbled_text(text):
    """
    Remove garbled OCR noise like "-aennen ar aeraan aen aaennaen".
    Detects repeating patterns of consonants/noise.
    """
    if not text:
        return ""
    
    # Pattern 1: Repeating "aen", "nnn", "aar" patterns (garbled text)
    text = re.sub(r'[-\s]*([a-z]{2,3})\s+\1\s+\1', '', text, flags=re.IGNORECASE)
    
    # Pattern 2: Lines with excessive consonant clusters (no vowels)
    words = text.split()
    cleaned_words = []
    
    for word in words:
        # Check if word is mostly consonants (garbled)
        if len(word) > 5:
            vowel_count = sum(1 for c in word.lower() if c in 'aeiou')
            vowel_ratio = vowel_count / len(word)
            
            # If < 20% vowels, likely garbled
            if vowel_ratio < 0.2:
                continue  # Skip this word
        
        cleaned_words.append(word)
    
    text = ' '.join(cleaned_words)
    
    # Pattern 3: Remove lines that are just repeating chars
    text = re.sub(r'\b([a-z])\1{3,}\b', '', text, flags=re.IGNORECASE)
    
    # Pattern 4: Remove standalone dashes/hyphens clusters
    text = re.sub(r'[-]{2,}', '', text)
    
    return text


def apply_dictionary_fixes(text):
    """Apply dictionary corrections."""
    for error, fix in OCR_FIXES.items():
        # Whole word replacement
        pattern = r'\b' + re.escape(error) + r'\b'
        text = re.sub(pattern, fix, text, flags=re.IGNORECASE)
    
    return text


def fix_obvious_chars(text):
    """Fix obvious character confusions."""
    # Numbers: O/0, l/1
    text = re.sub(r'(?<=\d)O(?=\d)', '0', text)
    text = re.sub(r'(?<=\d)l(?=\d)', '1', text)
    
    # Words: 0/o, 1/I
    text = re.sub(r'(?<=[a-z])0(?=[a-z])', 'o', text)
    text = re.sub(r'(?<=[A-Z])1(?=[A-Z])', 'I', text)
    
    return text


def is_valid_line(text):
    """
    Validate if line should be kept.
    Removes noise lines.
    """
    if not text or len(text.strip()) < 2:
        return False
    
    # Check character composition
    alphanumeric = sum(c.isalnum() for c in text)
    total = len(text)
    
    # Must be at least 30% alphanumeric
    if alphanumeric < total * 0.3:
        return False
    
    # Check for excessive punctuation (noise)
    punct_count = sum(1 for c in text if c in '.,;:-_|/')
    if punct_count > len(text) * 0.5:
        return False
    
    # Check for repeating noise patterns
    if re.search(r'(.{2,})\1{3,}', text):
        return False
    
    return True

 