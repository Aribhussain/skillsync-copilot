/**
 * Mirror of backend/app/services/text_norm.py. Keep the two in sync; the parity test
 * (mapperLite.spec.ts) fails if they drift.
 *  1. NFC, lowercase
 *  2. danda (।, ॥) and "_" -> space; every char that is not a letter, digit, "_" or in the
 *     Devanagari block becomes a space (Python's \w == Unicode letters/digits/underscore)
 *  3. split on whitespace, drop stopwords
 *  4. strip a trailing "s" from latin tokens longer than 3 chars not ending in "ss"
 */

// Devanagari block U+0900–U+097F, written as regex escapes (U+0900 is itself a combining
// mark, so it must not appear literally inside a character class).
const BS = String.fromCharCode(92) // backslash
const DEV_RANGE = `${BS}u0900-${BS}u097F`
// eslint-disable-next-line no-misleading-character-class -- intentional block range that includes matras; verified by the parity tests
const SPLIT = new RegExp(`[^${BS}p{L}${BS}p{N}_${DEV_RANGE}]+`, 'gu')
const LATIN = /^[a-z0-9]+$/

export function stem(token: string): string {
  if (token.length > 3 && token.endsWith('s') && !token.endsWith('ss') && LATIN.test(token)) {
    return token.slice(0, -1)
  }
  return token
}

export function rawTokens(text: string): string[] {
  const norm = text
    .normalize('NFC')
    .toLowerCase()
    .replaceAll('।', ' ')
    .replaceAll('॥', ' ')
    .replaceAll('_', ' ')
  return norm
    .replace(SPLIT, ' ')
    .split(/\s+/)
    .filter((t) => t.length > 0)
}

export function tokenize(text: string, stopwords: Set<string>): string[] {
  return rawTokens(text)
    .filter((t) => !stopwords.has(t))
    .map(stem)
}

export function phraseTokens(text: string): string[] {
  return rawTokens(text).map(stem)
}
