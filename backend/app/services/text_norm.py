"""Text normalisation shared by the server mapper and (mirrored in TypeScript) mapper-lite.

Rules (keep in sync with frontend/src/lib/mapper/tokenize.ts):
1. Unicode NFC, lowercase.
2. Danda (।, ॥) and every character that is not a word character or in the
   Devanagari block (U+0900–U+097F) becomes a space. Devanagari matras are kept,
   which a plain ``\\W`` split would break.
3. Split on whitespace and drop stopwords (English, Hinglish, Hindi).
4. Light English stemming: strip a trailing "s" from Latin tokens longer than 3
   characters that don't end in "ss".
"""

from __future__ import annotations

import re
import unicodedata

_SPLIT = re.compile(r"[^\wऀ-ॿ]+")
_LATIN = re.compile(r"^[a-z0-9]+$")

STOPWORDS_EN = set(
    (
        "a about after again all also am an and any are as at be been before but by can could did "
        "do does down etc experience for from had has have here how i in including into is it its "
        "job just last me more most mostly my necessary no not of on only or our out over own "
        "required same so some such than that the then there these this those to under up very was "
        "we were what when where which who will with work worked working would year years yes you "
    ).split()
)
STOPWORDS_HINGLISH = set(
    (
        "aata aati abhi apna apni aur bahut bhi chahiye deta deti do dono ek hai hain hoon hota "
        "hoti hu hum hun jo ka kaam kam kar karta karte karti ke khud ki kiya ko kuch leta leti "
        "liye mai main me mein mera mere meri na nahi par pe pichle roz saal sab sal se teen tha "
        "the thi thoda to wala wale wali wo woh ye yeh "
    ).split()
)
STOPWORDS_HI = set(
    (
        "अनुभव अपना आता आती एक और कर करता करती करते का काम किया की कुछ के को खुद चाहिए जो तो था थी "
        "थोड़ा देता दो नहीं पर बहुत बाद भी मुझे में मेरा मेरी मैं यह या लिए लेता वह वाला वाली सब "
        "साल से हम ही हूँ हूं है हैं हो हों होता "
    ).split()
)
STOPWORDS = STOPWORDS_EN | STOPWORDS_HINGLISH | STOPWORDS_HI


def stem(token: str) -> str:
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss") and _LATIN.match(token):
        return token[:-1]
    return token


def raw_tokens(text: str) -> list[str]:
    text = unicodedata.normalize("NFC", text).lower().replace("।", " ").replace("॥", " ").replace("_", " ")
    return [t for t in _SPLIT.sub(" ", text).split() if t]


def tokenize(text: str, drop_stopwords: bool = True) -> list[str]:
    toks = raw_tokens(text)
    if drop_stopwords:
        toks = [t for t in toks if t not in STOPWORDS]
    return [stem(t) for t in toks]


def phrase_tokens(text: str) -> list[str]:
    """Tokens for lexicon phrase matching: stopwords are kept so phrases such as
    'argon ka kaam' match exactly, but stemming is applied."""
    return [stem(t) for t in raw_tokens(text)]


DEVANAGARI_RANGE = (0x0900, 0x097F)
