/**
 * Pluggable speech-to-text adapters.
 *  - WebSpeechAdapter: browser Web Speech API (hi-IN / en-IN). Not every browser ships it;
 *    Brave and Firefox, for example, usually don't. `available()` reports that honestly.
 *  - Typed input and icon cards are always available as fallbacks (in the UI).
 *  - The Bhashini adapter is a server-side scaffold (see backend/app/api/speech.py).
 */

// TypeScript's DOM lib has the event types but not the recogniser itself.
interface SpeechRecognitionLike extends EventTarget {
  lang: string
  continuous: boolean
  interimResults: boolean
  start(): void
  stop(): void
  onresult: ((ev: SpeechRecognitionEvent) => void) | null
  onerror: ((ev: SpeechRecognitionErrorEvent) => void) | null
  onend: (() => void) | null
}
type SpeechRecognitionCtor = new () => SpeechRecognitionLike

export type SpeechLang = 'hi-IN' | 'en-IN'

export interface SpeechCallbacks {
  onText: (finalText: string, interim: string) => void
  onError: (code: string) => void
  onEnd: () => void
}

export interface SpeechAdapter {
  readonly id: string
  available(): boolean
  start(lang: SpeechLang, cb: SpeechCallbacks): void
  stop(): void
}

function recogniserCtor(): SpeechRecognitionCtor | undefined {
  const w = window as unknown as { SpeechRecognition?: SpeechRecognitionCtor; webkitSpeechRecognition?: SpeechRecognitionCtor }
  return w.SpeechRecognition ?? w.webkitSpeechRecognition
}

export class WebSpeechAdapter implements SpeechAdapter {
  readonly id = 'web-speech'
  private rec: SpeechRecognitionLike | null = null

  available(): boolean {
    return typeof window !== 'undefined' && !!recogniserCtor()
  }

  start(lang: SpeechLang, cb: SpeechCallbacks): void {
    const Ctor = recogniserCtor()
    if (!Ctor) {
      cb.onError('not-supported')
      return
    }
    const rec = new Ctor()
    rec.lang = lang
    rec.continuous = true
    rec.interimResults = true
    let finalText = ''
    rec.onresult = (ev) => {
      let interim = ''
      for (let i = ev.resultIndex; i < ev.results.length; i++) {
        const res = ev.results[i]
        if (res.isFinal) finalText += `${res[0].transcript} `
        else interim += res[0].transcript
      }
      cb.onText(finalText.trim(), interim)
    }
    rec.onerror = (ev) => cb.onError(ev.error)
    rec.onend = () => {
      this.rec = null
      cb.onEnd()
    }
    this.rec = rec
    rec.start()
  }

  stop(): void {
    this.rec?.stop()
  }
}

export const speech: SpeechAdapter = new WebSpeechAdapter()
