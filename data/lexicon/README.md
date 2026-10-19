# Trade-vernacular lexicon

`lexicon.json` maps shop-floor terms (Devanagari Hindi, Hinglish and English) to canonical NSQF terms.

Each entry has:

- `term`: what a worker actually says, e.g. "argon ka kaam", "आर्गन", "chhinte".
- `lang`: `hi` (Devanagari), `hinglish` (romanised Hindi) or `en`.
- `canonical`: the NSQF term shown to the user, e.g. "GTAW (141)".
- `category`: process, tool, defect, safety, material, joint, position, finishing, testing, trade or context.
- `expand`: terms appended to the query during retrieval. A test checks that every expansion term occurs in the QP corpus.
- `source`: `seed`, or `assessor` for additions confirmed through `POST /lexicon`.

The seed list was compiled by the team for this prototype and still needs validation by practising welders and ITI instructors.
