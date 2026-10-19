<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t, locale } = useI18n()

// Where the tool supports vs replaces judgement (also in docs/SOLUTION.md).
const rows = [
  { d: ['QP suggestion', 'QP सुझाव'], ai: ['Ranks top-3', 'शीर्ष-3 क्रम देता है'], f: ['Worker + assessor confirm', 'कामगार + मूल्यांकनकर्ता पुष्टि करते हैं'] },
  { d: ['Evidence plan', 'सबूत योजना'], ai: ['Rules engine (critical PCs locked)', 'नियम इंजन (महत्वपूर्ण PC लॉक)'], f: ['System rule', 'सिस्टम नियम'] },
  { d: ['Evidence authenticity', 'सबूत की प्रामाणिकता'], ai: ['Flags anomalies', 'गड़बड़ी चिह्नित करता है'], f: ['Assessor reviews', 'मूल्यांकनकर्ता जाँचते हैं'] },
  { d: ['PC scores', 'PC अंक'], ai: ['Second opinion, shown after blind score', 'दूसरी राय, ब्लाइंड अंक के बाद दिखती है'], f: ['Assessor', 'मूल्यांकनकर्ता'] },
  { d: ['Full / Partial / Fail', 'पूर्ण / आंशिक / अनुत्तीर्ण'], ai: ['Recommends only', 'केवल सिफ़ारिश'], f: ['Assessor only', 'केवल मूल्यांकनकर्ता'] },
  { d: ['Certificate', 'प्रमाणपत्र'], ai: ['None', 'कोई नहीं'], f: ['Awarding body', 'प्रमाणन संस्था'] },
]
const i = () => (locale.value === 'hi' ? 1 : 0)
</script>

<template>
  <section class="card">
    <h1 class="text-2xl font-bold">{{ t('about.title') }}</h1>
    <p class="mb-4 text-navy-700">{{ t('about.lead') }}</p>
    <div class="overflow-x-auto">
      <table class="w-full min-w-[480px] text-left text-sm" data-testid="support-replace-table">
        <thead>
          <tr class="border-b-2 border-navy-900">
            <th class="py-2 pr-2">{{ t('about.decision') }}</th>
            <th class="py-2 pr-2">{{ t('about.aiRole') }}</th>
            <th class="py-2">{{ t('about.finalSay') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in rows" :key="r.d[0]" class="border-b border-navy-100">
            <td class="py-2 pr-2 font-semibold">{{ r.d[i()] }}</td>
            <td class="py-2 pr-2">{{ r.ai[i()] }}</td>
            <td class="py-2 font-semibold text-green-india-700">{{ r.f[i()] }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
