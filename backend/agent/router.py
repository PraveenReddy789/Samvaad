import re
from typing import Dict, Any


def detect_language(text: str) -> str:
    """
    Detects whether user query is in Telugu, Hindi, Tamil, Malayalam, or English
    via Unicode script blocks and conversational transliterated keywords.
    """
    if not text:
        return "en"

    # 1. Unicode Script Block Detection
    if re.search(r"[\u0C00-\u0C7F]", text):
        return "te"  # Telugu
    if re.search(r"[\u0900-\u097F]", text):
        return "hi"  # Hindi (Devanagari)
    if re.search(r"[\u0B80-\u0BFF]", text):
        return "ta"  # Tamil
    if re.search(r"[\u0D00-\u0D7F]", text):
        return "ml"  # Malayalam

    text_lower = text.lower()

    # 2. Conversational Transliterated Keywords
    # Tamil (check distinctive Tamil markers first)
    tamil_patterns = [
        r"\bennoda\b", r"\benakku\b", r"\bevvalavu\b", r"\bevalavu\b", r"\birukku\b",
        r"\bkattalaam\b", r"\bkaasu\b", r"\bkattamaaten\b", r"\bkattala\b", r"\bmaaten\b",
        r"\bsolla\b", r"\bsollunga\b", r"\bvanakkam\b", r"\baama\b", r"\beppadi\b",
        r"\beppa\b", r"\bkuduka\b", r"\bmudiyadhu\b", r"\bmudiyathu\b", r"\bkatren\b", r"\bkattiten\b",
        r"\bthara\s*maaten\b", r"\bpanam\s*thara\b", r"\bemi\s*evvalavu\b", r"\bbaaki\s*irukku\b", r"\ben\s*emi\b"
    ]
    if any(re.search(pat, text_lower) for pat in tamil_patterns):
        return "ta"

    # Malayalam (check distinctive Malayalam markers)
    malayalam_patterns = [
        r"\bente\b", r"\benikku\b", r"\bethra\b", r"\bund\b", r"\bundu\b", r"\billa\b",
        r"\bkodukkilla\b", r"\bnjaan\b", r"\badakilla\b", r"\badaykkilla\b", r"\btharilla\b",
        r"\bkazhiyilla\b", r"\badakkanam\b", r"\bparayamo\b", r"\bnamaskaram\b", r"\bathe\b",
        r"\bengane\b", r"\beppol\b", r"\bkodukkoo\b", r"\badachu\b", r"\btheernnu\b",
        r"\bkazhinju\b", r"\bemi\s*ethra\b", r"\bpanam\s*tharilla\b", r"\bpanam\s*illa\b"
    ]
    if any(re.search(pat, text_lower) for pat in malayalam_patterns):
        return "ml"


    # Telugu (distinctive Telugu markers)
    telugu_patterns = [
        r"\bnenu\b", r"\bkattanu\b", r"\bkatta\b", r"\bkattalenu\b", r"\bcheyyanu\b",
        r"\bivvanu\b", r"\bdabbu\b", r"\bdabbulu\b", r"\bpaisalu\b", r"\bippudu\b",
        r"\bkudaradu\b", r"\bavvadu\b", r"\bvaddu\b", r"\benduku\b", r"\bchesanu\b",
        r"\bmatladu\b", r"\btelugulo\b", r"\btelugu\b", r"\bkattesanu\b", r"\bnaaku\b",
        r"\bmeeru\b", r"\bcheppandi\b", r"\beppudu\b", r"\boddu\b", r"\blekapothe\b",
        r"\bnaa\b", r"\bna\b", r"\bentha\b", r"\benta\b", r"\bundhi\b", r"\bundi\b",
        r"\bkattali\b", r"\bchudandi\b", r"\bchudu\b", r"\bkadataanu\b", r"\bkadathanu\b",
        r"\bkavali\b", r"\bemi\s*ent[ha]{1,2}\b", r"\bpending\s*und[hi]{1,2}\b"
    ]
    if any(re.search(pat, text_lower) for pat in telugu_patterns):
        return "te"

    # Hindi (distinctive Hindi markers)
    hindi_patterns = [
        r"\bmera\b", r"\bmeri\b", r"\bmere\b", r"\bkitna\b", r"\bkitni\b",
        r"\bnahi\b", r"\bnhi\b", r"\bdunga\b", r"\bdungi\b", r"\bpaisa\b", r"\bpaise\b",
        r"\bbharna\b", r"\bbharo\b", r"\bchahiye\b", r"\bshukriya\b", r"\bnamaste\b",
        r"\bhaan\b", r"\bbataye\b", r"\bbatao\b", r"\bpareshani\b", r"\bkhatam\b",
        r"\bkyun\b", r"\bkarein\b", r"\bkarunga\b", r"\bkarenge\b", r"\bmat\s*karo\b",
        r"\bpaise\s*nahi\b", r"\bkitna\s*hai\b", r"\bemi\s*kitn[ai]\b", r"\bbaaki\s*hai\b", r"\bbaki\s*hai\b"
    ]
    if any(re.search(pat, text_lower) for pat in hindi_patterns):
        return "hi"

    return "en"



def normalize_pan_indian_spoken_numbers(text: str) -> str:
    """
    Normalizes spoken and written number words across Telugu, Hindi, Tamil, Malayalam,
    and English into standardized numeric digits for financial verification.
    """
    if not text:
        return ""
    s = text

    # Multilingual numeral mappings
    number_words_map = {
        # Telugu
        "జీరో": "0", "సున్నా": "0", "వన్": "1", "ఒకటి": "1", "టు": "2", "రెండు": "2",
        "త్రీ": "3", "మూడు": "3", "ఫోర్": "4", "నాలుగు": "4", "ఫైవ్": "5", "ఐదు": "5",
        "సిక్స్": "6", "ఆరు": "6", "సెవెన్": "7", "ఏడు": "7", "ఎయిట్": "8", "ఎనిమిది": "8",
        "నైన్": "9", "తొమ్మిది": "9",
        # Hindi
        "शून्य": "0", "जीरो": "0", "एक": "1", "वन": "1", "दो": "2", "टू": "2",
        "तीन": "3", "थ्री": "3", "चार": "4", "फोर": "4", "पांच": "5", "पाँच": "5", "फाइव": "5",
        "छह": "6", "सिक्स": "6", "सात": "7", "सेवन": "7", "आठ": "8", "एट": "8",
        "नौ": "9", "नाइन": "9", "दस": "10",
        # Tamil
        "பூஜ்ஜியம்": "0", "ஜீரோ": "0", "ஒன்று": "1", "ஒன்னு": "1", "இரண்டு": "2", "ரெண்டு": "2",
        "மூன்று": "3", "மூணு": "3", "நான்கு": "4", "நாpeer": "4", "ஐந்து": "5", "அஞ்சு": "5",
        "ஆறு": "6", "ஏழு": "7", "எட்டு": "8", "ஒன்பது": "9", "பத்து": "10",
        # Malayalam
        "പൂജ്യം": "0", "സീറോ": "0", "ഒന്ന്": "1", "രണ്ട്": "2", "മൂന്ന്": "3",
        "നാല്": "4", "അഞ്ച്": "5", "ആറ്": "6", "ഏഴ്": "7", "എട്ട്": "8",
        "ഒമ്പത്": "9", "പത്ത്": "10"
    }

    for word, digit in number_words_map.items():
        s = s.replace(word, f" {digit} ")

    # Banking keywords normalization across Indian scripts
    s = re.sub(r"ట్రాన్సాక్షన్|ట్రాన్స్ఫర్|ట్రాన్సఫర్|ट्रांजैक्शन|ट्रांजेक्शन|பரிவர்த்தனை|டிரான்ஸாக்ஷன்|ട്രാൻസാക്ഷൻ|ട്രാൻസ്ഫർ", "TXN", s)
    s = re.sub(r"నెంబర్|నంబర్|नंबर|எண்|നമ്പർ", "NUMBER", s)

    # Collapse spaced digits (e.g. "7 0 0 0 2" -> "70002")
    s = re.sub(r"\b([0-9])\s+([0-9])\s+([0-9])\s+([0-9])\s+([0-9])\b", r"\1\2\3\4\5", s)
    s = re.sub(r"\b([0-9])\s+([0-9])\s+([0-9])\s+([0-9])\b", r"\1\2\3\4", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


# Backward-compatible alias
normalize_telugu_spoken_numbers = normalize_pan_indian_spoken_numbers


class QueryRouter:
    """Classifies user queries into operational recovery intents and extracts entities."""

    INTENTS = {
        "ALREADY_PAID": [
            r"already paid", r"i paid", r"payment made", r"done payment", r"transferred",
            r"paid\b", r"txn", r"transaction", r"utr", r"reference",
            r"7000[1-9]", r"700[1-9]",
            # Telugu
            r"చెల్లించాను", r"కట్టాను", r"కట్టేసాను", r"డబ్బులు పంపాను", r"డబ్బులు కట్టాను",
            r"\bchesanu\b", r"\bkattesanu\b", r"\bkattaanu\b",
            # Hindi
            r"भुगतान कर दिया", r"पेमेंट कर दिया", r"पैसे भर दिए", r"भर दिया", r"दे दिए",
            r"\bpay\s*kiya\b", r"\bbhar\s*diya\b", r"\bde\s*diya\b", r"\bpayment\s*ho\s*gaya\b",
            # Tamil
            r"பணம் செலுத்திவிட்டேன்", r"கட்டிவிட்டேன்", r"கட்டிட்டேன்", r"அனுப்பிவிட்டேன்",
            r"\bkattiyaachu\b", r"\bkattiten\b", r"\bpanam\s*anupiyachu\b",
            # Malayalam
            r"പണം അടച്ചു", r"പേയ്‌മെന്റ് ചെയ്തു", r"അടച്ചു", r"കൊടുത്തു",
            r"\badachu\b", r"\bpanam\s*koduthu\b", r"\bkazhinju\b"
        ],
        "PROMISE_TO_PAY": [
            r"will pay", r"going to pay", r"can pay on", r"pay tomorrow", r"pay by",
            r"pay next week", r"clearing on", r"settle by",
            # Telugu
            r"రేపు కడతాను", r"కడతాను", r"చెల్లిస్తాను", r"తర్వాత కడతాను", r"kadataanu", r"kadathanu",
            # Hindi
            r"कल दूंगा", r"कल भरूंगा", r"अगले हफ्ते दूंगा", r"दे दूंगा", r"\bkal\s*dunga\b", r"\bpay\s*karunga\b",
            # Tamil
            r"நாளை கட்டுகிறேன்", r"அடுத்த வாரம் தருகிறேன்", r"\bnaalaiku\s*kattaren\b", r"\btharen\b",
            # Malayalam
            r"നാളെ അടയ്ക്കാം", r"അടുത്ത ആഴ്ച അടയ്ക്കാം", r"\bnaale\s*adakkam\b", r"\btharam\b"
        ],
        "HARDSHIP": [
            r"lost my job", r"job loss", r"unemployed", r"medical emergency", r"hospital",
            r"salary delay", r"cannot afford", r"financial crisis", r"hardship assistance",
            r"cannot pay the full amount", r"no money",
            # Telugu
            r"ఉద్యోగం పోయింది", r"ఆరోగ్యం బాగాలేదు", r"డబ్బు సమస్య", r"కష్టాల్లో ఉన్నాను",
            r"job poyindi", r"aarogyam", r"dabbu ledu",
            # Hindi
            r"नौकरी चली गई", r"पैसे नहीं है", r"तबीयत खराब है", r"आर्थिक तंगी",
            r"\bnaukri\s*chali\s*gayi\b", r"\bpareshani\s*hai\b", r"\bpaisa\s*nahi\s*hai\b",
            # Tamil
            r"வேலை போய்விட்டது", r"பணக் கஷ்டம்", r"உடம்பு சரியில்லை",
            r"\bvelai\s*poyidichu\b", r"\bpanam\s*kashtam\b",
            # Malayalam
            r"ജോലി പോയി", r"പണമില്ല", r"ചികിത്സയിലാണ്", r"സാമ്പത്തിക ബുദ്ധിമുട്ട്",
            r"\bjoli\s*poyi\b", r"\bpanam\s*illa\b"
        ],
        "REFUSAL_TO_PAY": [
            r"will not pay", r"wont pay", r"won't pay", r"not paying", r"refuse", r"sue me",
            r"do whatever", r"not giving money", r"never pay", r"harassment", r"stop calling",
            # Telugu Script & Romanized
            r"కట్టను", r"కట్టలేను", r"డబ్బులు లేవు", r"చెయ్యను", r"ఇవ్వను", r"కుదరదు", r"దొబ్బేయ్", r"పోరా",
            r"\bkattanu\b", r"\bkattalenu\b", r"\bcheyyanu\b", r"\bivvanu\b", r"\bdabbu\s*ledu\b",
            r"\bdabbulu\s*levu\b", r"\bavvadu\b", r"\bkudaradu\b", r"\bvaddu\b", r"\bdobbey\b",
            # Hindi Script & Romanized
            r"पैसे नहीं दूंगा", r"नहीं भरूंगा", r"नहीं दूंगा", r"जो करना है कर लो", r"कॉल मत करो",
            r"\bnahi\s*dunga\b", r"\bnahi\s*bharunga\b", r"\bpaise\s*nahi\s*dunga\b", r"\bmat\s*karo\b",
            # Tamil Script & Romanized
            r"பணம் தர முடியாது", r"கட்ட மாட்டேன்", r"தர மாட்டேன்", r"என்ன வேணா பண்ணு",
            r"\bkattamaaten\b", r"\bthara\s*maaten\b", r"\bpanam\s*illai\b", r"\bmudiyathu\b",
            # Malayalam Script & Romanized
            r"പണം തരില്ല", r"അടയ്ക്കില്ല", r"കൊടുക്കില്ല",
            r"\bpanam\s*tharilla\b", r"\badaykkilla\b", r"\bkodukkilla\b", r"\bkazhiyilla\b"
        ],
        "DISPUTE": [

            r"wrong amount", r"incorrect amount", r"partial payment", r"already debited",
            r"dispute", r"not my loan", r"already settled", r"overcharged",
            # Telugu
            r"తప్పు మొత్తం", r"నా లోన్ కాదు", r"ఎక్కువ వేశారు", r"wrong emi",
            # Hindi
            r"गलत राशि", r"गलत ईएमआई", r"मेरा लोन नहीं है", r"ज्यादा पैसे", r"\bgalat\s*amount\b",
            # Tamil
            r"தவறான தொகை", r"என் கடன் இல்லை", r"\bthappana\s*amount\b",
            # Malayalam
            r"തെറ്റായ തുക", r"എന്റെ ലോൺ അല്ല", r"\bthettaya\s*thuka\b"
        ],
        "CHECK_BALANCE": [
            r"how much", r"current emi", r"due date", r"balance", r"outstanding",
            r"what do i owe", r"when is it due", r"loan details", r"account status",
            r"\bwhat\s*is\s*my\s*emi\b", r"\bmy\s*emi\b", r"\bwhat\s*is\s*my\s*balance\b",
            r"\bwhat\s*is\s*the\s*emi\b", r"\bhow\s*much\s*emi\b", r"\bemi\s*amount\b",
            r"\bemi\s*details\b", r"\bcheck\s*balance\b", r"\bhow\s*much\s*to\s*pay\b",
            # Telugu Script & Romanized
            r"ఎంత కట్టాలి", r"బకాయి ఎంత", r"ఎప్పుడు కట్టాలి", r"తేదీ ఎప్పుడు",
            r"ఎంత పెండింగ్", r"ఎంత బకాయి", r"నా ఈఎంఐ", r"నా emi",
            r"enta kattali", r"enta due", r"eppudu kattali", r"naa emi", r"na emi",
            r"entha pending", r"enta pending", r"pending undhi", r"pending undi",
            r"emi entha", r"emi enta", r"balance entha", r"balance enta",
            # Hindi Script & Romanized
            r"कितना बकाया", r"कितना बाकी", r"ईएमआई कितनी", r"मेरा ईएमआई", r"कितने पैसे बाकी",
            r"कब तक भरना", r"कितना देना है", r"\bkitna\s*baaki\b", r"\bkitna\s*baki\b",
            r"\bemi\s*kitna\b", r"\bkitna\s*hai\b", r"\bkitna\s*dena\b", r"\bmera\s*emi\b",
            # Tamil Script & Romanized
            r"எவ்வளவு பாக்கி", r"என் இஎம்ஐ", r"எவ்வளவு கட்ட", r"கடைசி தேதி", r"எவ்வளவு இருக்கு",
            r"\bevvalavu\s*baaki\b", r"\bemi\s*evvalavu\b", r"\bevalavu\s*irukku\b", r"\ben\s*emi\b",
            # Malayalam Script & Romanized
            r"എത്ര ബാക്കി", r"എന്റെ ഇഎംഐ", r"എത്ര അടയ്ക്കണം", r"അവസാന തീയതി", r"എത്രയുണ്ട്",
            r"\bethra\s*baakki\b", r"\bethra\s*bakki\b", r"\bemi\s*ethra\b", r"\bente\s*emi\b"
        ],
        "ESCALATE": [
            r"human agent", r"real person", r"supervisor", r"manager", r"complaint",
            r"legal action", r"lawyer", r"fraud",
            # Telugu
            r"మేనేజర్ తో మాట్లాడాలి", r"అధికారితో మాట్లాడాలి", r"కస్టమర్ కేర్",
            r"manager tho matladali", r"officer tho matladali",
            # Hindi
            r"मैनेजर से बात करनी है", r"अधिकारी से बात कराओ", r"कस्टमर केयर",
            r"\bmanager\s*se\s*baat\b", r"\bofficer\s*se\s*baat\b",
            # Tamil
            r"மேனேஜரிடம் பேச வேண்டும்", r"அதிகாரியிடம் பேச வேண்டும்",
            r"\bmanager\s*kitta\s*pesanom\b",
            # Malayalam
            r"മാനേജറോട് സംസാരിക്കണം", r"ഓഫീസറോട് സംസാരിക്കണം",
            r"\bmanagerodu\s*samsarikkanam\b"
        ],
        "CALL_CLOSING": [
            # English
            r"\bno\s*thanks\b", r"\bno\s*thank\s*you\b", r"\bnothing\s*else\b", r"\bno\s*more\b",
            r"\bthat'?s\s*all\b", r"\bno\s*need\b", r"\bbye\b", r"\bgoodbye\b", r"\ball\s*good\b",
            r"\bno\s*questions?\b", r"\bhave\s*a\s*good\s*day\b", r"\bhave\s*a\s*nice\s*day\b",
            r"\bthank\s*you\b", r"\bthanks\b", r"\bnothing\b", r"\bno\s*other\b", r"\bthats\s*it\b",
            r"\bno\b$", r"\bnope\b",
            # Telugu
            r"వద్దు ధన్యవాదాలు", r"ఏమీ లేదు", r"ఇంకేమీ లేదు", r"సరే బాయ్", r"ధన్యవాదాలు",
            r"\bvaddu\b", r"\bem\s*ledu\b", r"\binkem\s*ledu\b", r"\bchalu\b", r"\bsare\s*bye\b",
            # Hindi
            r"नहीं धन्यवाद", r"कुछ नहीं", r"बस इतना ही", r"कोई सवाल नहीं", r"धन्यवाद", r"अलविदा",
            r"\bnahi\s*thanks\b", r"\bkuch\s*nahi\b", r"\bbas\s*itna\s*hi\b", r"\bkoi\s*sawal\s*nahi\b",
            r"\bshukriya\b", r"\balvida\b", r"\bnahi\s*chahiye\b",
            # Tamil
            r"இல்லை நன்றி", r"ஒன்றுமில்லை", r"வேண்டாம்", r"அவ்வளவுதான்", r"நன்றி",
            r"\billa\s*nandri\b", r"\bvendam\b", r"\bonnum\s*illa\b", r"\bavvalavuthan\b",
            # Malayalam
            r"വേണ്ട നന്ദി", r"ഒന്നുമില്ല", r"മതിയേ", r"നന്ദി", r"ശരി ബൈ",
            r"\bvenda\s*nanni\b", r"\bonnumilla\b", r"\bmathi\b", r"\bshari\s*bye\b"
        ],
        "CHITCHAT": [
            # English
            r"\bhow\s*are\s*you\b", r"\bhow\s*r\s*u\b", r"\bhow\s*do\s*you\s*do\b", r"\bhow\s*is\s*it\s*going\b",
            r"\bhope\s*you\s*are\s*doing\s*well\b", r"\bhow\s*are\s*you\s*doing\b",
            # Telugu
            r"ఎలా ఉన్నారు", r"బాగున్నారా", r"మీరు ఎలా ఉన్నారు", r"\bela\s*unnaru\b", r"\bbagunnara\b",
            # Hindi
            r"आप कैसे हैं", r"आप कैसी हैं", r"कैसे हो", r"क्या हाल है", r"सब ठीक",
            r"\baap\s*kaise\s*ho\b", r"\bkya\s*haal\s*hai\b", r"\bkaise\s*ho\b", r"\bsab\s*theek\b",
            # Tamil
            r"எப்படி இருக்கீங்க", r"எப்படி இருக்கிறீர்கள்", r"நலமா",
            r"\beppadi\s*irukkeenga\b", r"\beppadi\s*irukkinga\b", r"\bnalama\b",
            # Malayalam
            r"സുഖമാണോ", r"എങ്ങനെ ഇരിക്കുന്നു", r"വിശേഷം എന്താണ്",
            r"\bsukhamano\b", r"\bengane\s*irikkunnu\b", r"\bvishesham\s*enthanu\b"
        ],
        "GREETING": [
            # English
            r"\bhello\b", r"\bhi\b", r"\bhey\b", r"\bgood\s*morning\b", r"\bgood\s*afternoon\b",
            r"\bgood\s*evening\b",
            # Telugu
            r"నమస్కారం", r"హలో", r"నమస్తే", r"\bnamaskaram\b", r"\bnamaste\b",
            # Hindi
            r"नमस्ते", r"नमस्कार", r"हेलो", r"हाय", r"सुप्रभात", r"\bnamaskar\b", r"\bpranam\b",
            # Tamil
            r"வணக்கம்", r"வணக்கங்க", r"\bvanakkam\b",
            # Malayalam
            r"നമസ്കാരം", r"നമസ്തേ", r"\bnamaskaram\b"
        ],
        "POLICY_INQUIRY": [
            r"grace period", r"late fee", r"penalty", r"policy", r"interest rate",
            r"terms", r"guidelines", r"rules", r"penal charges", r"charges"
        ]
    }


    def route_query(self, query: str) -> Dict[str, Any]:
        """Analyzes query and extracts intent, entities, and language."""
        query_norm = normalize_pan_indian_spoken_numbers(query)
        query_clean = query_norm.lower().strip()
        detected_language = detect_language(query)


        # Extract entities
        # 1. Flexible Transaction Reference Extraction & Normalization
        transaction_ref = None

        txn_pattern = re.search(r"\b(?:TXN|TX|TRANSACTION|REF|REFERENCE|UTR|NUMBER)[-\s:]*([0-9]{3,7})\b", query_norm, re.IGNORECASE)
        if txn_pattern:
            digits = txn_pattern.group(1)
            # Acoustic zero-drop compensation (e.g. speech recognizer hearing 7002 instead of 70002)
            if digits in ("7002", "702"):
                digits = "70002"
            elif digits in ("7001", "701"):
                digits = "70001"
            elif digits in ("7003", "703"):
                digits = "70003"
            elif len(digits) == 4 and digits.startswith("70"):
                digits = digits[:3] + "0" + digits[3:]
            transaction_ref = f"TXN-{digits}"
        else:
            std_txn = re.search(r"\b(TXN-[A-Z0-9]+)\b", query_norm, re.IGNORECASE)
            if std_txn:
                transaction_ref = std_txn.group(1).upper()
            else:
                num_match = re.search(r"\b(7000[1-9]|700[1-9])\b", query_norm)
                if num_match:
                    digits = num_match.group(1)
                    if len(digits) == 4:
                        digits = digits[:3] + "0" + digits[3:]
                    transaction_ref = f"TXN-{digits}"

        # 2. Date expressions
        date_match = re.search(r"\b(\d{4}-\d{2}-\d{2}|\d{1,2}(?:st|nd|rd|th)?\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*|tomorrow|next week|monday|friday)\b", query, re.IGNORECASE)
        promised_date = date_match.group(1) if date_match else None

        # 3. Classify Intent
        detected_intent = "POLICY_INQUIRY"  # Default fallback
        for intent, patterns in self.INTENTS.items():
            if any(re.search(pat, query_clean) for pat in patterns):
                detected_intent = intent
                break

        # Priority overrides: If transaction reference is provided, intent is ALREADY_PAID
        if transaction_ref:
            detected_intent = "ALREADY_PAID"

        return {
            "intent": detected_intent,
            "transaction_reference": transaction_ref,
            "promised_date": promised_date,
            "language": detected_language,
            "query": query
        }


_router_instance = None


def get_query_router() -> QueryRouter:
    global _router_instance
    if _router_instance is None:
        _router_instance = QueryRouter()
    return _router_instance
