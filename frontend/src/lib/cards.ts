/** Icon cards for low-literacy users. Each card adds a phrase the lexicon understands. */
export interface IconCard {
  id: string
  icon: string
  en: string
  hi: string
  text: string
  group: 'trade' | 'process' | 'tool'
}

export const ICON_CARDS: IconCard[] = [
  { id: 'welding', icon: '🔥', en: 'Welding', hi: 'वेल्डिंग', text: 'welding', group: 'trade' },
  { id: 'co2', icon: '🟦', en: 'CO2 / MIG', hi: 'सीओ2 / मिग', text: 'co2 welding', group: 'process' },
  { id: 'argon', icon: '🟪', en: 'Argon / TIG', hi: 'आर्गन / टिग', text: 'argon tig welding', group: 'process' },
  { id: 'stick', icon: '🪄', en: 'Electrode / stick', hi: 'इलेक्ट्रोड', text: 'electrode stick welding', group: 'process' },
  { id: 'flux', icon: '🧵', en: 'Flux-core wire', hi: 'फ्लक्स वायर', text: 'flux core wire', group: 'process' },
  { id: 'grinder', icon: '⚙️', en: 'Grinding / finishing', hi: 'ग्राइंडिंग / फिनिशिंग', text: 'grinding finishing', group: 'tool' },
  { id: 'pipe', icon: '🔩', en: 'Pipe joints', hi: 'पाइप जोड़', text: 'pipe joint', group: 'process' },
  { id: 'plate', icon: '⬛', en: 'Plate joints', hi: 'प्लेट जोड़', text: 'plate joint', group: 'process' },
  { id: 'gascut', icon: '✂️', en: 'Gas cutting', hi: 'गैस कटिंग', text: 'gas cutting', group: 'tool' },
  { id: 'ppe', icon: '⛑️', en: 'Helmet & gloves', hi: 'हेलमेट और दस्ताने', text: 'helmet gloves safety', group: 'tool' },
  { id: 'drawing', icon: '📐', en: 'Reading drawings', hi: 'नक्शा पढ़ना', text: 'drawing weld symbols', group: 'tool' },
  { id: 'site', icon: '🏗️', en: 'Construction site', hi: 'बिल्डिंग साइट', text: 'construction site column beam', group: 'trade' },
  { id: 'stud', icon: '📌', en: 'Stud welding', hi: 'स्टड वेल्डिंग', text: 'stud welding', group: 'trade' },
  { id: 'fabrication', icon: '🚪', en: 'Gates & grills', hi: 'गेट और ग्रिल', text: 'fabrication gate grill', group: 'trade' },
  { id: 'electrician', icon: '💡', en: 'Electrician', hi: 'बिजली का काम', text: 'bijli wiring', group: 'trade' },
  { id: 'plumber', icon: '🚰', en: 'Plumber', hi: 'प्लंबर', text: 'plumber nal pipe fitting', group: 'trade' },
  { id: 'sewing', icon: '🧷', en: 'Sewing', hi: 'सिलाई', text: 'silai stitching', group: 'trade' },
  { id: 'beauty', icon: '💇', en: 'Beauty parlour', hi: 'ब्यूटी पार्लर', text: 'parlour facial', group: 'trade' },
  { id: 'bike', icon: '🏍️', en: 'Bike mechanic', hi: 'बाइक मैकेनिक', text: 'bike servicing', group: 'trade' },
  { id: 'mason', icon: '🧱', en: 'Mason', hi: 'राजमिस्त्री', text: 'raj mistri chinai plaster', group: 'trade' },
]

export function cardText(ids: string[]): string[] {
  return ids.map((id) => ICON_CARDS.find((c) => c.id === id)?.text).filter((t): t is string => !!t)
}
