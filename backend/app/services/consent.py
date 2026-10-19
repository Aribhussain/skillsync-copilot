"""Plain-language consent notices (DPDP Act 2023 style). The notice hash is stored
with each consent so we can prove exactly which text the worker agreed to."""

from __future__ import annotations

from app.core.security import sha256_hex

NOTICE_VERSION = "2026-10"

PURPOSES = ("rpl_assessment", "evidence_capture", "voice_processing")

NOTICES: dict[str, dict] = {
    "en": {
        "title": "Your consent for skill assessment (RPL)",
        "items": [
            {
                "purpose": "rpl_assessment",
                "text": "We will use your work story and assessment scores only to check your skills "
                "for an NSQF certificate (Recognition of Prior Learning).",
            },
            {
                "purpose": "evidence_capture",
                "text": "The assessor will take three photos: your work setup, your finished work, and you "
                "holding a code slate. Photos are signed, encrypted and used only as assessment evidence. "
                "We do not create or store face templates.",
            },
            {
                "purpose": "voice_processing",
                "text": "If you speak instead of typing, your voice is turned into text. Only the text is "
                "kept, not the recording.",
            },
        ],
        "rights": "You can withdraw consent at any time. You can ask to see, correct or delete your data. "
        "Your data is never sold or used for advertising.",
    },
    "hi": {
        "title": "कौशल मूल्यांकन (RPL) के लिए आपकी सहमति",
        "items": [
            {
                "purpose": "rpl_assessment",
                "text": "आपकी काम की कहानी और मूल्यांकन के अंक केवल NSQF प्रमाणपत्र (पूर्व शिक्षा की मान्यता) "
                "के लिए आपके कौशल की जाँच में उपयोग होंगे।",
            },
            {
                "purpose": "evidence_capture",
                "text": "मूल्यांकनकर्ता तीन फ़ोटो लेंगे: आपका काम का सेटअप, आपका तैयार काम, और कोड वाली स्लेट "
                "पकड़े हुए आप। फ़ोटो पर डिजिटल हस्ताक्षर होंगे, वे एन्क्रिप्ट रहेंगी और केवल सबूत के रूप में "
                "उपयोग होंगी। हम चेहरे का कोई टेम्पलेट नहीं बनाते या रखते।",
            },
            {
                "purpose": "voice_processing",
                "text": "अगर आप बोलकर बताते हैं, तो आपकी आवाज़ को लिखित शब्दों में बदला जाएगा। केवल लिखा हुआ "
                "टेक्स्ट रखा जाएगा, रिकॉर्डिंग नहीं।",
            },
        ],
        "rights": "आप कभी भी सहमति वापस ले सकते हैं। आप अपना डेटा देखने, सुधारने या हटाने के लिए कह सकते हैं। "
        "आपका डेटा कभी बेचा नहीं जाएगा और विज्ञापन के लिए उपयोग नहीं होगा।",
    },
}


def get_notice(lang: str) -> dict:
    lang = lang if lang in NOTICES else "en"
    notice = NOTICES[lang]
    return {
        "version": NOTICE_VERSION,
        "language": lang,
        **notice,
        "sha256": notice_hash(lang),
    }


def notice_hash(lang: str) -> str:
    from app.core.security import canonical_json

    return sha256_hex(canonical_json({"version": NOTICE_VERSION, **NOTICES[lang]}))
