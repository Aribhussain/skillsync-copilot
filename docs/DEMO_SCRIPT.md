# 5-minute demo script (judges)

**Goal:** show the whole RPL journey for one welder, from a spoken story to a verifiable certificate, including the moments where the AI *helps* and where the human *decides*.

## Before the judges arrive (2 minutes)

```bash
npm run lite            # API :8000 + PWA :5173
npm run seed            # optional: populated QA dashboard, extra workers, one issued credential
```

- **Browser:** Chrome or Edge on a laptop, or Chrome on an Android phone for real Hindi voice (`hi-IN`). Brave and Firefox have no Web Speech API, so type the story or use the icon cards there.
- **Two tabs:**
  - Tab A for the worker: `http://localhost:5173` (or `<laptop-ip>:5173` on the phone).
  - Tab B for the assessor.
- Keep DevTools → Network → **Offline** within reach (or the phone's airplane mode).
- Demo passwords are on the login screen: `worker123`, `assessor123`, `qa123`.

## The script

| Time | Do | Say |
|---|---|---|
| 0:00 | Tab A: log in as **worker1** (Ramesh Kumar). Tick the consent purposes. | "Consent is per purpose, in Hindi or English. The server stores a hash of the exact notice he agreed to, and it blocks photos without his consent." |
| 0:30 | Switch to **हिंदी**, tap the mic and say: *"Main 6 saal se fabrication shop mein kaam karta hoon, CO2 aur argon dono welding karta hoon, plate aur pipe joint banata hoon, grinding karke finishing deta hoon"*. (Or paste it, or tap the Welding / CO2 / Argon cards.) | "No forms. He tells his work story the way he would tell a friend: Hindi, Hinglish or icon cards." |
| 1:00 | Submit. Point at **#1 Welding**, its confidence, the "we understood" chips (*argon → GTAW 141*, *CO2 → GMAW 135*) and the pre-ticked PCs. Confirm. | "Shop-floor slang maps to NSQF terms through a 399-entry lexicon. The top-3 are explainable. The same engine runs **on the phone, offline**." |
| 1:30 | Tab B: log in as **assessor1** and open Ramesh's assessment from the queue (if it isn't there, it went to **assessor2** or **assessor3**). Point at the 🔒 critical PCs. | "Every PC gets an evidence route. Safety-critical PCs are locked to live observation, so a photo can't stand in for watching him weld." |
| 2:00 | Go **offline**. Start the assessment and open **Capture**: Process → Product (pick sample *porosity*) → Person with the **challenge code** on the slate. Seal. The outbox counter goes up. | "Three guided shots with on-device quality checks. Each one is hashed, signed with a key that never leaves the phone, and encrypted. The one-time code proves the photo was taken *now*, for *this* candidate." |
| 2:45 | Go **online**. The outbox drains to 0. | "The server verifies every signature before it accepts a photo." |
| 3:00 | Open **Scoring**. On *N3125 PC1* pick **3** and lock it. The AI says **1** (pores detected), and a **reason code is required**. Pick a reason and save. | "Blind-first: the assessor scores before the AI opinion exists for him, and the server enforces that. A big disagreement needs a reason. The AI is a second opinion, never the decision." |
| 3:30 | *(Optional)* Tab A as **worker2**: request Welding. Capture the same porosity sample again → the reused-photo flag appears. | "Exact and perceptual hashes catch recycled photos across candidates. It's a flag for the assessor, not an automatic rejection." |
| 3:45 | Score the remaining PCs (give GTAW PCs a 0) and open the **Profile**: **Partial**, with a GTAW bridge module. **Sign off** with the password. | "The recommendation is Partial; only the assessor can sign it off, after re-entering his password. Overriding needs a written justification." |
| 4:15 | Show the credential QR → open **/verify** on the phone. | "A W3C Verifiable Credential signed with Ed25519. Anyone can verify it without logging in, and any edit breaks the signature." |
| 4:35 | Log in as **qa1**: point at **α**, the assessor × NOS drift heat-map and the **audit chain verified** badge. | "Hidden golden packets measure agreement across assessors and centres. The lenient assessor stands out. Every action is in a tamper-evident ledger." |
| 5:00 | Close on the support-vs-replace table (README). | "We don't replace the assessor. We make every assessor score like the best one." |

## If something goes wrong

- **No mic or "voice unavailable":** the browser has no Web Speech API. Type or paste the story; the mapping is identical.
- **The assessment isn't in assessor1's queue:** assignment picks the least-loaded assessor, so log in as assessor2 or assessor3. After `npm run seed`, loads differ per assessor.
- **The AI says "AI analysis running…":** in Docker full mode the analysis runs on a worker. It appears within seconds, and the scorer polls by itself.
- **You need a clean slate:** stop the API, run `npm run seed -- --reset` (or `python scripts/seed_demo.py --reset`), and start again.

## Honest answers to likely questions

- **"Is the weld AI real?"** It's a demo model trained on **synthetic** weld images, labelled that way in the UI. The pipeline and the blind-first gate are real; the model would be retrained on real, consented evidence.
- **"Does it improve consistency?"** The simulated crossover study shows α 0.33 → 0.57, mostly from the rubric anchors. The live study mode is built so real assessors can measure it (OFF, then ON).
- **"Who issues the certificate?"** The awarding body. Our credential carries the assessor's signed-off decision, and the issuer is labelled as a prototype.
