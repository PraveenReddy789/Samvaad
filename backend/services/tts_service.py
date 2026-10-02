import os
import re
import uuid
import base64
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional

import edge_tts

from backend.config import TTS_AUDIO_DIR


# ============================================================
# AUDIO DIRECTORY
# ============================================================

audio_dir_path = Path(TTS_AUDIO_DIR)
audio_dir_path.mkdir(parents=True, exist_ok=True)


# ============================================================
# VOICES
# ============================================================

# English - India
FEMALE_AGENT_VOICE = "en-IN-NeerjaNeural"
MALE_AGENT_VOICE = "en-IN-PrabhatNeural"

# Telugu - India
TELUGU_FEMALE_AGENT_VOICE = "te-IN-ShrutiNeural"
TELUGU_MALE_AGENT_VOICE = "te-IN-MohanNeural"

# Hindi - India
HINDI_FEMALE_AGENT_VOICE = "hi-IN-SwaraNeural"
HINDI_MALE_AGENT_VOICE = "hi-IN-MadhurNeural"

# Tamil - India
TAMIL_FEMALE_AGENT_VOICE = "ta-IN-PallaviNeural"
TAMIL_MALE_AGENT_VOICE = "ta-IN-ValluvarNeural"

# Malayalam - India
MALAYALAM_FEMALE_AGENT_VOICE = "ml-IN-SobhanaNeural"
MALAYALAM_MALE_AGENT_VOICE = "ml-IN-MidhunNeural"


# ============================================================
# FEMALE CUSTOMER NAMES
# ============================================================

FEMALE_NAMES_SET = {
    "sneha",
    "priya",
    "ananya",
    "pooja",
    "deepa",
    "neha",
    "kavita",
    "divya",
    "shreya",
    "sunita",
    "rekha",
    "anita",
    "radha",
    "meena",
    "aarti",
    "swati",
    "jyoti",
    "nisha",
    "simran",
    "tanvi",
    "rashmi",
}


# ============================================================
# MALE NAME EXCEPTIONS
# ============================================================

MALE_NAME_EXCEPTIONS = {
    "arjun",
    "rahul",
    "vikram",
    "amit",
    "rohit",
    "ravi",
}


# ============================================================
# LANGUAGE-BASED VOICE SELECTION
# ============================================================

def get_voice_for_customer(
    customer_name: str,
    language: str = "en",
) -> str:
    """
    Select agent voice based on customer language and gender.

    Rules:

    English:
        Female customer -> Male agent voice
        Male customer   -> Female agent voice

    Telugu:
        Female customer -> Male Telugu agent voice
        Male customer   -> Female Telugu agent voice

    Supported languages:
        en -> English
        te -> Telugu
    """

    language = (language or "en").lower().strip()

    # --------------------------------------------------------
    # Detect customer gender from name
    # --------------------------------------------------------

    first_name = (
        customer_name.strip().split()[0].lower()
        if customer_name
        else ""
    )

    is_female = False

    if first_name in FEMALE_NAMES_SET:
        is_female = True

    elif first_name.endswith(("a", "i", "ee")):

        # Exceptions for male names
        if first_name not in MALE_NAME_EXCEPTIONS:
            is_female = True

    # --------------------------------------------------------
    # Language Voice Dispatch (Pan-Indian)
    # --------------------------------------------------------

    if language in ("te", "te-in", "telugu"):
        return TELUGU_MALE_AGENT_VOICE if is_female else TELUGU_FEMALE_AGENT_VOICE

    if language in ("hi", "hi-in", "hindi"):
        return HINDI_MALE_AGENT_VOICE if is_female else HINDI_FEMALE_AGENT_VOICE

    if language in ("ta", "ta-in", "tamil"):
        return TAMIL_MALE_AGENT_VOICE if is_female else TAMIL_FEMALE_AGENT_VOICE

    if language in ("ml", "ml-in", "malayalam"):
        return MALAYALAM_MALE_AGENT_VOICE if is_female else MALAYALAM_FEMALE_AGENT_VOICE

    # Default: English
    if is_female:
        return MALE_AGENT_VOICE

    return FEMALE_AGENT_VOICE


# ============================================================
# CLEAN TEXT
# ============================================================

def clean_text_for_speech(text: str) -> str:
    """
    Removes markdown symbols, citations, and unnecessary
    formatting before sending text to TTS.
    """

    if not text:
        return ""

    # Remove markdown formatting
    cleaned = re.sub(
        r"[\\\*#\_>\`]",
        "",
        text
    )

    # Remove citation brackets such as:
    # [Policy v2]
    # [Source]
    # [1]
    cleaned = re.sub(
        r"\[[^\]]*\]",
        "",
        cleaned
    )

    # Normalize whitespace
    cleaned = re.sub(
        r"\s+",
        " ",
        cleaned
    ).strip()

    return cleaned


# ============================================================
# GENERATE SPEECH
# ============================================================

async def generate_speech_audio(
    text: str,
    voice: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate speech using Microsoft Edge TTS.

    Returns:

        success
        filename
        audio_url
        audio_base64
        voice
        voice_gender
        cleaned_text
    """

    # --------------------------------------------------------
    # Clean input
    # --------------------------------------------------------

    cleaned = clean_text_for_speech(text)

    if not cleaned:

        return {
            "success": False,
            "error": "No text provided",
        }

    # --------------------------------------------------------
    # Select voice
    # --------------------------------------------------------

    selected_voice = voice or FEMALE_AGENT_VOICE

    # If text is in Telugu script, automatically enforce Telugu neural voice
    if re.search(r"[\u0C00-\u0C7F]", cleaned) and not selected_voice.startswith("te-IN"):
        if "Prabhat" in selected_voice or "Mohan" in selected_voice:
            selected_voice = TELUGU_MALE_AGENT_VOICE
        else:
            selected_voice = TELUGU_FEMALE_AGENT_VOICE

    # --------------------------------------------------------
    # Create deterministic hash
    #
    # Same text + same voice = same audio file
    #
    # This prevents generating the same audio repeatedly.
    # --------------------------------------------------------

    text_hash = hashlib.md5(
        f"{cleaned}_{selected_voice}".encode("utf-8")
    ).hexdigest()[:12]

    filename = f"speech_{text_hash}.mp3"

    filepath = audio_dir_path / filename

    # --------------------------------------------------------
    # Generate audio only if it doesn't already exist
    # --------------------------------------------------------

    if not filepath.exists():

        try:

            communicate = edge_tts.Communicate(
                cleaned,
                selected_voice
            )

            await communicate.save(
                str(filepath)
            )

        except Exception as e:

            print(
                f"[TTS Error] {e}"
            )

            return {
                "success": False,
                "error": str(e),
                "cleaned_text": cleaned,
            }

    # --------------------------------------------------------
    # Convert audio to Base64
    # --------------------------------------------------------

    try:

        with open(
            filepath,
            "rb"
        ) as f:

            audio_bytes = f.read()

            b64_audio = base64.b64encode(
                audio_bytes
            ).decode("utf-8")

    except Exception as e:

        print(
            f"[TTS Read Error] {e}"
        )

        b64_audio = None

    # --------------------------------------------------------
    # Determine language
    # --------------------------------------------------------

    if selected_voice.startswith("te-IN"):

        language = "Telugu"

    elif selected_voice.startswith("en-IN"):

        language = "English"

    else:

        language = "Unknown"

    # --------------------------------------------------------
    # Determine voice gender
    # --------------------------------------------------------

    if "Prabhat" in selected_voice:

        voice_gender = "Male (Prabhat)"

    elif "Neerja" in selected_voice:

        voice_gender = "Female (Neerja)"

    elif "Mohan" in selected_voice:

        voice_gender = "Male (Mohan)"

    elif "Shruti" in selected_voice:

        voice_gender = "Female (Shruti)"

    else:

        voice_gender = "Unknown"

    # --------------------------------------------------------
    # Return response
    # --------------------------------------------------------

    return {

        "success": True,

        "filename": filename,

        "audio_url": f"/api/audio/{filename}",

        "audio_base64": (
            f"data:audio/mp3;base64,{b64_audio}"
            if b64_audio
            else None
        ),

        "voice": selected_voice,

        "voice_gender": voice_gender,

        "language": language,

        "cleaned_text": cleaned,
    }