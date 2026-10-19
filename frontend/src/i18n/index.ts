import { createI18n } from 'vue-i18n'

import en from './en.json'
import hi from './hi.json'

export type Locale = 'en' | 'hi'
const LOCALE_KEY = 'skillsync.locale'

function initialLocale(): Locale {
  const saved = localStorage.getItem(LOCALE_KEY)
  if (saved === 'en' || saved === 'hi') return saved
  return navigator.language?.toLowerCase().startsWith('hi') ? 'hi' : 'en'
}

export const i18n = createI18n({
  legacy: false,
  locale: initialLocale(),
  fallbackLocale: 'en',
  messages: { en, hi },
})

export function setLocale(locale: Locale): void {
  i18n.global.locale.value = locale
  localStorage.setItem(LOCALE_KEY, locale)
  document.documentElement.lang = locale
}
