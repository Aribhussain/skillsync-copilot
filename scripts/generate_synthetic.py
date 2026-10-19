"""Reproducible SYNTHETIC data generator (seeded).

Writes to data/synthetic/:
  workers.json             60 synthetic worker profiles with Hindi / Hinglish / English
                           "kaam ki kahani" narratives and a ground-truth QP
  weld_images/*.jpg        procedurally drawn weld coupons (good / porosity / undercut /
                           spatter / incomplete), 256x256
  weld_labels.csv          ground truth: file, defect, severity, quality_level (0-3)

Everything here is SYNTHETIC DEMO DATA, not real workers or real welds.

Usage:  python scripts/generate_synthetic.py [--seed 26242] [--images-per-class 60]
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "synthetic"

WELDING = "QG-4.5-AU-01811-2024-V1-ASDC"

# --------------------------------------------------------------------------- narratives
# Per QP: facts in three registers. A narrative = opener + 2-4 facts + optional noise.
FACTS: dict[str, dict[str, list[str]]] = {
    WELDING: {
        "en": [
            "I do CO2 welding on mild steel plates",
            "I also do argon TIG welding on stainless steel sheet",
            "I weld with electrode stick welding on pipes",
            "I make butt and fillet joints on plate and pipe",
            "after welding I do grinding and finishing with wire brush",
            "I can see porosity and spatter and correct it",
            "I set the current and voltage on the machine myself",
            "I always wear helmet, gloves and apron",
            "I read the drawing and weld symbols before starting",
            "I have used flux core wire welding also",
            "I do root pass and capping on plate joints",
            "I check the weld for defects like undercut",
        ],
        "hinglish": [
            "CO2 welding karta hoon MS plate pe",
            "argon ka kaam bhi aata hai, TIG se stainless sheet jodta hoon",
            "electrode wali welding pipe pe karta hoon",
            "plate aur pipe joint banata hoon, butt aur kona joint",
            "grinding karke finishing deta hoon",
            "chhed aur chhinte aa jaye to theek karta hoon",
            "machine pe current aur voltage setting khud karta hoon",
            "helmet, dastane aur apron pehen ke kaam karta hoon",
            "drawing dekh ke welding karta hoon",
            "flux wire se bhi welding ki hai",
            "root aur capping dono karta hoon",
            "slag hatana aur wire brush karna roz ka kaam hai",
        ],
        "hi": [
            "मैं सीओ2 वेल्डिंग करता हूँ",
            "आर्गन वेल्डिंग से स्टेनलेस की चादर जोड़ता हूँ",
            "इलेक्ट्रोड से पाइप पर वेल्डिंग करता हूँ",
            "प्लेट और पाइप के जोड़ बनाता हूँ",
            "वेल्डिंग के बाद ग्राइंडर से घिसाई और फिनिशिंग करता हूँ",
            "वेल्डिंग में छेद या छींटे हों तो ठीक करता हूँ",
            "मशीन का करंट खुद सेट करता हूँ",
            "हेलमेट, चश्मा और दस्ताने पहनता हूँ",
            "नक्शा देखकर काम करता हूँ",
            "टिग वेल्डिंग भी आती है",
        ],
    },
    "DEMO-CON-WELDER-L4": {
        "en": [
            "I weld columns and beams on building construction sites",
            "I weld sariya rebar joints at site",
            "I work on scaffolding at height with a safety belt",
            "I use electrode arc welding for structure work",
            "I tack the beams before full welding",
            "site welding of structural steel is my main work",
        ],
        "hinglish": [
            "building site pe column aur beam ki welding karta hoon",
            "sariya jodne ka kaam site pe karta hoon",
            "paad pe chadh ke uchai par welding karta hoon, safety belt lagata hoon",
            "structure ka kaam electrode se karta hoon",
            "construction site pe loha jodta hoon",
        ],
        "hi": [
            "बिल्डिंग साइट पर कॉलम और बीम की वेल्डिंग करता हूँ",
            "सरिया जोड़ने का काम करता हूँ",
            "पाड़ पर चढ़कर ऊँचाई पर काम करता हूँ",
            "स्ट्रक्चर का काम इलेक्ट्रोड से करता हूँ",
        ],
    },
    "DEMO-AU-STUD-WELD-L3": {
        "en": [
            "I operate a stud gun to weld studs on sheet metal",
            "I weld shear studs on steel deck sheet",
            "I set the stud gun timer and lift",
            "I do bend test on studs to check the weld",
            "stud welding on car body panels is my job",
        ],
        "hinglish": [
            "stud gun se stud welding karta hoon",
            "deck sheet pe shear stud lagata hoon",
            "stud ka bend test karke check karta hoon",
            "car body pe stud aur nut welding karta hoon",
        ],
        "hi": ["स्टड गन से स्टड वेल्डिंग करता हूँ", "डेक शीट पर स्टड लगाता हूँ", "स्टड का बेंड टेस्ट करता हूँ"],
    },
    "DEMO-CG-SR-WELDER-PIPE-L5": {
        "en": [
            "I am a 6G qualified pipe welder",
            "my welds pass radiography x-ray test",
            "I do TIG root and electrode filling on boiler pipes",
            "I worked on IBR boiler and refinery pipelines",
            "I follow the WPS for preheat and interpass temperature",
            "pipe welding in all positions for pressure piping",
        ],
        "hinglish": [
            "6G pipe welding karta hoon",
            "meri welding ka x-ray test pass hota hai",
            "boiler pipe pe TIG root aur electrode se filling karta hoon",
            "refinery pipeline aur IBR ka kaam kiya hai",
            "WPS ke hisaab se kaam karta hoon",
        ],
        "hi": ["6G पाइप वेल्डिंग करता हूँ", "बॉयलर और पाइपलाइन पर काम किया है", "रेडियोग्राफी टेस्ट पास होता है"],
    },
    "DEMO-CG-FITTER-FAB-L4": {
        "en": [
            "I do marking and cutting of angle and channel",
            "I make gates, grills and frames in a fabrication shop",
            "I use gas cutter for cutting plates",
            "I fit up and tack weld frames square",
            "I drill holes as per the drawing",
            "I do fit-up of fabrication assemblies",
        ],
        "hinglish": [
            "fabrication shop mein gate, grill aur shutter banata hoon",
            "angle channel ki marking aur cutting karta hoon",
            "gas cutter se plate kaatta hoon",
            "frame ki fitting karke tack lagata hoon",
            "fitter ka kaam karta hoon",
        ],
        "hi": ["फैब्रिकेशन में गेट और ग्रिल बनाता हूँ", "फिटर का काम करता हूँ", "एंगल की मार्किंग और कटिंग करता हूँ"],
    },
    "DEMO-EL-DOMESTIC-L3": {
        "en": [
            "I do house wiring and fix switch boards",
            "I install MCB distribution boards",
            "I do earthing for houses",
            "I repair fans and fix lights",
            "I find short circuit faults",
        ],
        "hinglish": [
            "ghar ki wiring karta hoon",
            "MCB board lagata hoon",
            "earthing ka kaam karta hoon",
            "pankha aur light fitting karta hoon",
            "bijli ka kaam aata hai",
        ],
        "hi": ["घर की वायरिंग करता हूँ", "बिजली का काम करता हूँ", "पंखा और स्विच लगाता हूँ", "अर्थिंग करता हूँ"],
    },
    "DEMO-PL-GENERAL-L3": {
        "en": [
            "I fit PVC and CPVC pipes in houses",
            "I repair leakage in taps and pipes",
            "I install toilet and wash basin",
            "I fit water tank connections",
            "I do GI pipe threading",
        ],
        "hinglish": [
            "nal aur tonti ki fitting karta hoon",
            "pvc pipe fitting ka kaam karta hoon",
            "leakage theek karta hoon",
            "tanki ka connection karta hoon",
            "toilet aur sink lagata hoon",
        ],
        "hi": ["नल और टोंटी लगाता हूँ", "प्लंबर का काम करता हूँ", "पाइप की लीकेज ठीक करता हूँ", "टंकी का कनेक्शन करता हूँ"],
    },
    "DEMO-AMH-SMO-L4": {
        "en": [
            "I stitch shirts and kurtas on industrial sewing machines",
            "I operate overlock and single needle machines",
            "I stitch collars and cuffs",
            "I work on a garment production line",
        ],
        "hinglish": [
            "silai ka kaam karti hoon",
            "overlock machine chalati hoon",
            "kapde ki stitching karti hoon",
            "factory mein kurta aur shirt silti hoon",
        ],
        "hi": ["सिलाई का काम करती हूँ", "ओवरलॉक मशीन चलाती हूँ", "कपड़े की सिलाई करती हूँ", "दर्जी का काम आता है"],
    },
    "DEMO-BWS-ABT-L3": {
        "en": [
            "I do facial, threading and waxing in a beauty parlour",
            "I do manicure and pedicure",
            "I keep tools sterilised",
            "I do bridal makeup",
        ],
        "hinglish": [
            "parlour mein facial aur threading karti hoon",
            "waxing aur bleach karti hoon",
            "makeup bhi karti hoon",
        ],
        "hi": ["पार्लर में फेशियल और थ्रेडिंग करती हूँ", "वैक्सिंग करती हूँ", "मेकअप करती हूँ"],
    },
    "DEMO-AU-2W-TECH-L4": {
        "en": [
            "I service motorcycles and scooters",
            "I change engine oil and clean the carburettor",
            "I adjust brakes and clutch",
            "I repair bike chain and spark plug problems",
        ],
        "hinglish": [
            "bike aur scooter ki servicing karta hoon",
            "engine oil badalta hoon, carburettor saaf karta hoon",
            "brake aur clutch theek karta hoon",
            "gaadi ka engine ka kaam aata hai",
        ],
        "hi": ["बाइक और स्कूटर की सर्विसिंग करता हूँ", "इंजन और ब्रेक ठीक करता हूँ", "कार्बोरेटर साफ़ करता हूँ"],
    },
    "DEMO-CON-MASON-L3": {
        "en": [
            "I build brick walls with cement mortar",
            "I do plastering of walls",
            "I check level and plumb of walls",
            "I lay tiles on floors",
        ],
        "hinglish": [
            "eent ki chinai karta hoon",
            "deewar pe plaster karta hoon",
            "sahul aur level se deewar seedhi rakhta hoon",
            "raj mistri ka kaam karta hoon",
        ],
        "hi": ["ईंट की चिनाई करता हूँ", "दीवार पर प्लास्टर करता हूँ", "राजमिस्त्री का काम करता हूँ", "टाइल लगाता हूँ"],
    },
}

OPENERS = {
    "en": [
        "I have worked for {y} years in a {place}.",
        "For the last {y} years I am working in a {place}.",
        "My experience is {y} years, mostly in a {place}.",
    ],
    "hinglish": [
        "Main {y} saal se {place} mein kaam karta hoon.",
        "{y} saal ka experience hai, {place} mein.",
        "Pichle {y} saal se {place} mein hoon.",
    ],
    "hi": ["मैं {y} साल से {place} में काम करता हूँ।", "मुझे {y} साल का अनुभव है।"],
}
PLACES = {
    "en": ["fabrication shop", "small workshop", "factory", "local shop"],
    "hinglish": ["fabrication shop", "workshop", "factory", "dukaan"],
    "hi": ["वर्कशॉप", "फैक्ट्री", "दुकान"],
}
NOISE = {
    "en": ["I learned from my ustad.", "I want a certificate for a better job.", "I did not go to ITI."],
    "hinglish": ["Ustad se seekha hai.", "Certificate chahiye achhi naukri ke liye.", "ITI nahi kiya."],
    "hi": ["उस्ताद से सीखा है।", "अच्छी नौकरी के लिए सर्टिफिकेट चाहिए।"],
}
# Realistic overlap: some non-welders mention a bit of welding and vice versa.
CROSS_NOISE = {
    "DEMO-CG-FITTER-FAB-L4": {
        "en": "Sometimes I also do a little welding.",
        "hinglish": "Thoda welding bhi kar leta hoon.",
        "hi": "थोड़ी वेल्डिंग भी कर लेता हूँ।",
    },
    "DEMO-AU-2W-TECH-L4": {
        "en": "I can do small welding repairs on bike frames.",
        "hinglish": "Bike frame pe chhoti welding bhi kar leta hoon.",
        "hi": "छोटी वेल्डिंग भी कर लेता हूँ।",
    },
    "DEMO-PL-GENERAL-L3": {
        "en": "I also cut pipes with a grinder.",
        "hinglish": "Grinder se pipe bhi kaatta hoon.",
        "hi": "ग्राइंडर से पाइप काटता हूँ।",
    },
}
NAMES = [
    "Ramesh",
    "Suresh",
    "Mahesh",
    "Rajesh",
    "Imran",
    "Salim",
    "Arjun",
    "Vijay",
    "Sunil",
    "Anil",
    "Ravi",
    "Mohan",
    "Sohan",
    "Deepak",
    "Manoj",
    "Pooja",
    "Sunita",
    "Rekha",
    "Meena",
    "Anita",
    "Farhan",
    "Gurpreet",
    "Harish",
    "Kiran",
    "Lakshmi",
    "Naveen",
    "Om Prakash",
    "Prakash",
    "Raju",
    "Shabnam",
]
SURNAMES = [
    "Kumar",
    "Singh",
    "Yadav",
    "Ansari",
    "Sharma",
    "Devi",
    "Khan",
    "Patel",
    "Gupta",
    "Verma",
    "Das",
    "Nair",
]


def make_narrative(rng: random.Random, qp_id: str, lang: str) -> str:
    facts = FACTS[qp_id][lang]
    k = min(len(facts), rng.randint(2, 4))
    chosen = rng.sample(facts, k)
    parts = [rng.choice(OPENERS[lang]).format(y=rng.randint(2, 15), place=rng.choice(PLACES[lang]))]
    end = "।" if lang == "hi" else "."
    parts += [c[0].upper() + c[1:] + end if lang != "hi" else c + end for c in chosen]
    if qp_id in CROSS_NOISE and rng.random() < 0.6:
        parts.append(CROSS_NOISE[qp_id][lang])
    if rng.random() < 0.5:
        parts.append(rng.choice(NOISE[lang]))
    return " ".join(parts)


def generate_workers(rng: random.Random, n: int = 60) -> list[dict]:
    qps = list(FACTS)
    # welding (the demo QP) gets 10, the 10 other QPs get 5 each = 60
    plan = [WELDING] * 10 + [q for q in qps if q != WELDING for _ in range(5)]
    assert len(plan) == n, len(plan)
    rng.shuffle(plan)
    langs = ["hinglish", "hi", "en"]
    workers = []
    for i, qp_id in enumerate(plan, start=1):
        lang = langs[i % 3]
        workers.append(
            {
                "id": f"SYN-W{i:03d}",
                "name": f"{rng.choice(NAMES)} {rng.choice(SURNAMES)} (synthetic)",
                "language": lang,
                "input_mode": rng.choice(["voice", "voice", "typed", "cards"]),
                "years_experience": rng.randint(2, 15),
                "narrative": make_narrative(rng, qp_id, lang),
                "ground_truth_qp": qp_id,
                "synthetic": True,
            }
        )
    return workers


# --------------------------------------------------------------------------- weld images
SIZE = 256
DEFECTS = ["good", "porosity", "undercut", "spatter", "incomplete"]


def _plate(rng: np.random.Generator) -> np.ndarray:
    base = rng.integers(105, 150)
    img = np.full((SIZE, SIZE), base, np.float32)
    streaks = rng.normal(0, 9, (SIZE, 1)).astype(np.float32)
    img += cv2.GaussianBlur(np.repeat(streaks, SIZE, axis=1), (1, 9), 0)
    img += rng.normal(0, 4, (SIZE, SIZE)).astype(np.float32)
    gx = np.linspace(-1, 1, SIZE, dtype=np.float32)
    img += (rng.uniform(-18, 18) * gx)[None, :]
    return img


def _bead_path(rng: np.random.Generator):
    y0 = SIZE / 2 + rng.uniform(-20, 20)
    amp, freq, phase = rng.uniform(0, 4), rng.uniform(0.01, 0.03), rng.uniform(0, 6.28)
    xs = np.arange(14, SIZE - 14)
    ys = y0 + amp * np.sin(freq * xs + phase)
    return xs, ys


def draw_weld(rng: np.random.Generator, defect: str, severity: int) -> np.ndarray:
    img = _plate(rng)
    xs, ys = _bead_path(rng)
    width = rng.uniform(22, 30)
    widths = np.full(len(xs), width)
    widths += rng.normal(0, 0.6 if defect != "incomplete" else 2.5, len(xs)).cumsum() * 0.05
    widths = np.clip(widths, 12, 38)

    present = np.ones(len(xs), bool)
    if defect == "incomplete":
        n_gaps = {1: 1, 2: 2, 3: 4}[severity]
        for _ in range(n_gaps):
            start = rng.integers(10, len(xs) - 40)
            present[start : start + rng.integers(12, 26 if severity < 3 else 40)] = False

    # heat-affected zone (darker halo)
    hz = np.zeros_like(img)
    for x, y, w, p in zip(xs, ys, widths, present, strict=True):
        if p:
            cv2.circle(hz, (int(x), int(y)), int(w * 0.95), 1.0, -1)
    img -= cv2.GaussianBlur(hz, (0, 0), 6) * 22

    # bead body with ripples (overlapping ellipses = solidified weld pool)
    spacing = rng.uniform(5.0, 7.0)
    bright = rng.uniform(175, 205)
    x = float(xs[0])
    while x < xs[-1]:
        i = int(x - xs[0])
        if present[i]:
            y, w = ys[i], widths[i]
            # fill first, then the darker leading-edge arc; the next pool covers the
            # back half of this arc, leaving the characteristic chevron ripples
            cv2.ellipse(img, (int(x), int(y)), (int(w * 0.30), int(w / 2) - 1), 0, -90, 90, bright, -1)
            cv2.ellipse(img, (int(x), int(y)), (int(w * 0.30), int(w / 2) - 1), 0, -90, 90, bright - 60, 2)
        x += spacing
    # toes of the bead
    for x, y, w, p in zip(xs, ys, widths, present, strict=True):
        if p:
            img[int(y - w / 2), int(x)] -= 25
            img[min(SIZE - 1, int(y + w / 2)), int(x)] -= 25

    if defect == "porosity":
        n = {1: rng.integers(3, 6), 2: rng.integers(9, 16)}[severity]
        for _ in range(n):
            i = rng.integers(5, len(xs) - 5)
            cy = ys[i] + rng.uniform(-widths[i] * 0.3, widths[i] * 0.3)
            r = rng.uniform(1.5, 2.6 if severity == 1 else 4.0)
            cv2.circle(img, (int(xs[i]), int(cy)), int(round(r)), float(rng.uniform(25, 55)), -1)
    elif defect == "undercut":
        frac = {1: 0.35, 2: 0.8}[severity]
        start = rng.integers(0, int(len(xs) * (1 - frac)) + 1)
        side = rng.choice([-1, 1])
        for i in range(start, start + int(len(xs) * frac)):
            if i < len(xs):
                yy = int(ys[i] + side * (widths[i] / 2 + 2))
                cv2.circle(img, (int(xs[i]), yy), 2 if severity == 1 else 3, 45.0, -1)
    elif defect == "spatter":
        n = {1: rng.integers(15, 30), 2: rng.integers(45, 80)}[severity]
        for _ in range(n):
            i = rng.integers(0, len(xs))
            off = rng.choice([-1, 1]) * rng.uniform(widths[i] * 0.7, widths[i] * 2.5)
            col = float(rng.choice([rng.uniform(200, 240), rng.uniform(40, 70)]))
            cv2.circle(
                img, (int(xs[i] + rng.normal(0, 4)), int(ys[i] + off)), int(rng.integers(1, 4)), col, -1
            )

    img = cv2.GaussianBlur(img, (3, 3), 0)
    img = np.clip(img, 0, 255).astype(np.uint8)
    angle = rng.uniform(-15, 15)
    m = cv2.getRotationMatrix2D((SIZE / 2, SIZE / 2), angle, 1.0)
    img = cv2.warpAffine(img, m, (SIZE, SIZE), borderMode=cv2.BORDER_REFLECT)
    # slight colour tint (steel + heat tint), stored as BGR
    tint = np.array([rng.uniform(0.95, 1.05), 1.0, rng.uniform(0.92, 1.02)], np.float32)
    color = np.clip(cv2.cvtColor(img, cv2.COLOR_GRAY2BGR).astype(np.float32) * tint, 0, 255).astype(np.uint8)
    return color


def quality_level(defect: str, severity: int) -> int:
    return 3 if defect == "good" else max(0, 3 - severity)


def generate_images(seed: int, per_class: int, out_dir: Path) -> list[dict]:
    rng = np.random.default_rng(seed)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for defect in DEFECTS:
        for k in range(per_class):
            if defect == "good":
                severity = 0
            elif defect == "incomplete":
                severity = int(rng.choice([1, 2, 3]))
            else:
                severity = int(rng.choice([1, 2]))
            img = draw_weld(rng, defect, severity)
            name = f"weld_{defect}_{k:03d}.jpg"
            cv2.imwrite(str(out_dir / name), img, [cv2.IMWRITE_JPEG_QUALITY, 90])
            rows.append(
                {
                    "file": name,
                    "defect": defect,
                    "severity": severity,
                    "quality_level": quality_level(defect, severity),
                    "synthetic": True,
                }
            )
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", type=int, default=26242)
    ap.add_argument("--images-per-class", type=int, default=60)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    workers = generate_workers(random.Random(args.seed))
    (args.out / "workers.json").write_text(
        json.dumps({"synthetic": True, "seed": args.seed, "workers": workers}, ensure_ascii=False, indent=1)
        + "\n",
        encoding="utf-8",
    )
    rows = generate_images(args.seed, args.images_per_class, args.out / "weld_images")
    with (args.out / "weld_labels.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"SYNTHETIC: {len(workers)} workers, {len(rows)} weld images -> {args.out}")


if __name__ == "__main__":
    main()
