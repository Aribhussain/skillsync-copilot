<script setup lang="ts">
import { BarChart, HeatmapChart, LineChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent, VisualMapComponent } from 'echarts/components'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { computed, onMounted, ref } from 'vue'
import VChart from 'vue-echarts'
import { useI18n } from 'vue-i18n'

import StudiesPanel from '../components/StudiesPanel.vue'
import { type CalibrationSummary, fetchAuditVerify, fetchSummary, seedGolden } from '../lib/calibration'

use([CanvasRenderer, LineChart, BarChart, HeatmapChart, GridComponent, TooltipComponent, LegendComponent, VisualMapComponent])

// Palette validated with the dataviz validator (light surface): categorical slots 1-2,
// diverging blue <-> red with a neutral grey midpoint. Text stays in text tokens.
const C = {
  s1: '#2a78d6', // blind (unassisted)
  s2: '#eb6834', // final (assisted)
  divNeg: '#2a78d6', // severe
  divMid: '#f0efec',
  divPos: '#e34948', // lenient
  text: '#0b0b0b',
  muted: '#52514e',
  grid: '#e3e9f7',
}

const { t } = useI18n()
const data = ref<CalibrationSummary | null>(null)
const audit = ref<{ valid: boolean; entries: number } | null>(null)
const error = ref('')
const seeding = ref(false)
const showTable = ref(false)

async function load() {
  error.value = ''
  try {
    ;[data.value, audit.value] = await Promise.all([fetchSummary(), fetchAuditVerify()])
  } catch (e) {
    error.value = String(e)
  }
}
onMounted(load)

async function seed() {
  seeding.value = true
  try {
    await seedGolden(4)
    await load()
  } finally {
    seeding.value = false
  }
}

const fmt = (x: number | null | undefined, d = 2) => (x === null || x === undefined ? '—' : x.toFixed(d))
const axisText = { color: C.muted, fontSize: 11 }

const trendOption = computed(() => {
  const tr = data.value?.trend ?? []
  return {
    animationDuration: 300,
    tooltip: { trigger: 'axis' },
    legend: { data: [t('qa.blind'), t('qa.final')], textStyle: { color: C.text }, top: 0 },
    grid: { left: 40, right: 16, top: 32, bottom: 28 },
    xAxis: { type: 'category', data: tr.map((x) => x.week), axisLabel: axisText, axisLine: { lineStyle: { color: C.grid } } },
    yAxis: { type: 'value', min: -0.2, max: 1, axisLabel: axisText, splitLine: { lineStyle: { color: C.grid } } },
    series: [
      { name: t('qa.blind'), type: 'line', data: tr.map((x) => x.alpha_blind), lineStyle: { width: 2, color: C.s1 }, itemStyle: { color: C.s1 }, symbolSize: 10, showSymbol: true, connectNulls: true },
      { name: t('qa.final'), type: 'line', data: tr.map((x) => x.alpha_final), lineStyle: { width: 2, color: C.s2 }, itemStyle: { color: C.s2 }, symbolSize: 10, showSymbol: true, connectNulls: true },
    ],
  }
})

const heatOption = computed(() => {
  const h = data.value?.heatmap
  const cells: [number, number, number | null][] = []
  h?.values.forEach((row, yi) => row.forEach((v, xi) => cells.push([xi, yi, v])))
  return {
    tooltip: {
      formatter: (p: { value: [number, number, number | null] }) =>
        `${h?.assessors[p.value[1]]} · ${h?.nos[p.value[0]]}<br/>${t('qa.meanDeviation')}: ${p.value[2] === null ? '—' : (p.value[2] > 0 ? '+' : '') + p.value[2]}`,
    },
    grid: { left: 80, right: 16, top: 8, bottom: 64 },
    xAxis: { type: 'category', data: h?.nos.map((n) => n.replace('ASC/', '')) ?? [], axisLabel: axisText, splitArea: { show: false } },
    yAxis: { type: 'category', data: h?.assessors ?? [], axisLabel: axisText },
    visualMap: {
      min: -2,
      max: 2,
      calculable: false,
      orient: 'horizontal',
      left: 'center',
      bottom: 0,
      itemHeight: 120,
      text: [t('qa.lenient'), t('qa.severe')],
      textStyle: { color: C.muted },
      inRange: { color: [C.divNeg, C.divMid, C.divPos] },
    },
    series: [
      {
        type: 'heatmap',
        data: cells,
        label: { show: true, color: C.text, formatter: (p: { value: [number, number, number | null] }) => (p.value[2] === null ? '' : String(p.value[2])) },
        itemStyle: { borderColor: '#ffffff', borderWidth: 2, borderRadius: 4 },
      },
    ],
  }
})

function barOption(labels: string[], values: number[], max?: number) {
  return {
    animationDuration: 300,
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 140, right: 48, top: 8, bottom: 24 },
    xAxis: { type: 'value', max, axisLabel: axisText, splitLine: { lineStyle: { color: C.grid } } },
    yAxis: { type: 'category', data: labels, axisLabel: { ...axisText, width: 130, overflow: 'truncate' } },
    series: [{ type: 'bar', data: values, barWidth: 14, itemStyle: { color: C.s1, borderRadius: [0, 4, 4, 0] }, label: { show: true, position: 'right', color: C.text } }],
  }
}
const centreOption = computed(() => {
  const c = data.value?.centres ?? {}
  return barOption(Object.keys(c), Object.values(c), 100)
})
const reasonOption = computed(() => {
  const r = data.value?.reason_codes ?? {}
  return barOption(Object.keys(r).map((k) => t(`scoring.reason.${k}`)), Object.values(r))
})
</script>

<template>
  <div class="grid gap-4" data-testid="qa-dashboard">
    <section class="card">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <h1 class="text-2xl font-bold">{{ t('home.qaTitle') }}</h1>
        <div class="flex flex-wrap items-center gap-2">
          <span
            v-if="audit"
            class="chip"
            :class="audit.valid ? 'bg-green-india-100 text-green-india-700' : 'bg-red-100 text-red-800'"
            data-testid="audit-badge"
            :data-valid="audit.valid"
          >
            {{ audit.valid ? '✓ ' + t('qa.auditOk', { n: audit.entries }) : '✗ ' + t('qa.auditBroken') }}
          </span>
          <button class="btn-ghost min-h-10" :disabled="seeding" data-testid="seed-golden" @click="seed">{{ t('qa.seed') }}</button>
        </div>
      </div>
      <p class="mt-1 text-xs text-navy-700">{{ data?.synthetic_note }} {{ t('qa.explainer') }}</p>
    </section>

    <p v-if="error" class="rounded-lg bg-saffron-100 p-2 text-sm" role="alert">{{ error }}</p>

    <template v-if="data">
      <section class="grid grid-cols-2 gap-3 md:grid-cols-4">
        <div class="card" data-testid="kpi-alpha-blind">
          <div class="text-xs text-navy-700">{{ t('qa.alphaBlind') }}</div>
          <div class="text-3xl font-bold">{{ fmt(data.alpha_blind) }}</div>
        </div>
        <div class="card">
          <div class="text-xs text-navy-700">{{ t('qa.alphaFinal') }}</div>
          <div class="text-3xl font-bold">{{ fmt(data.alpha_final) }}</div>
        </div>
        <div class="card">
          <div class="text-xs text-navy-700">{{ t('qa.alphaDecision') }}</div>
          <div class="text-3xl font-bold">{{ fmt(data.alpha_decision) }}</div>
        </div>
        <div class="card">
          <div class="text-xs text-navy-700">{{ t('qa.aiAgreement') }}</div>
          <div class="text-3xl font-bold">{{ data.ai_agreement_within_1 === null ? '—' : Math.round(data.ai_agreement_within_1 * 100) + '%' }}</div>
        </div>
      </section>
      <p class="-mt-2 text-xs text-navy-700">{{ t('qa.units', { units: data.units, scores: data.scores }) }}</p>

      <p v-if="!data.scores" class="card text-sm" data-testid="qa-empty">{{ t('qa.empty') }}</p>

      <div v-else class="grid gap-4 lg:grid-cols-2">
        <section class="card">
          <h2 class="font-bold">{{ t('qa.trend') }}</h2>
          <div class="chart-box h-64"><VChart :option="trendOption" autoresize /></div>
        </section>
        <section class="card" data-testid="heatmap">
          <h2 class="font-bold">{{ t('qa.heatmap') }}</h2>
          <div class="chart-box h-72"><VChart :option="heatOption" autoresize /></div>
        </section>
        <section class="card">
          <h2 class="font-bold">{{ t('qa.centres') }}</h2>
          <div class="chart-box h-48"><VChart :option="centreOption" autoresize /></div>
        </section>
        <section class="card">
          <h2 class="font-bold">{{ t('qa.reasons') }}</h2>
          <div v-if="Object.keys(data.reason_codes).length" class="chart-box h-48"><VChart :option="reasonOption" autoresize /></div>
          <p v-else class="text-sm text-navy-700">{{ t('qa.noReasons') }}</p>
        </section>
      </div>

      <section class="card" data-testid="assessor-indices">
        <div class="flex items-center justify-between">
          <h2 class="font-bold">{{ t('qa.indexTitle') }}</h2>
          <button class="chip bg-navy-100 px-3 py-1.5" @click="showTable = !showTable">{{ t('qa.perPcTable') }}</button>
        </div>
        <div class="overflow-x-auto">
          <table class="mt-2 w-full min-w-[480px] text-left text-sm">
            <thead>
              <tr class="border-b-2 border-navy-900">
                <th class="py-1">{{ t('qa.assessor') }}</th>
                <th>{{ t('qa.centre') }}</th>
                <th>{{ t('qa.index') }}</th>
                <th>{{ t('qa.bias') }}</th>
                <th>{{ t('qa.drift') }}</th>
                <th>n</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(v, name) in data.assessors" :key="name" class="border-b border-navy-100">
                <td class="py-1 font-semibold">{{ name }}</td>
                <td>{{ v.centre }}</td>
                <td>{{ v.index ?? '—' }}</td>
                <td>{{ v.bias === null ? '—' : (v.bias > 0 ? '+' : '') + v.bias }}</td>
                <td>{{ fmt(v.drift, 3) }}</td>
                <td>{{ v.n }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-if="showTable" class="mt-3 overflow-x-auto">
          <table class="w-full min-w-[320px] text-left text-sm">
            <thead><tr class="border-b-2 border-navy-900"><th class="py-1">PC</th><th>α ({{ t('qa.blind') }})</th></tr></thead>
            <tbody>
              <tr v-for="(a, pc) in data.alpha_per_pc" :key="pc" class="border-b border-navy-100">
                <td class="py-1 font-mono">{{ pc }}</td>
                <td>{{ fmt(a) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p class="mt-2 text-xs text-navy-700">{{ t('qa.privacy') }}</p>
      </section>
    </template>

    <StudiesPanel />
  </div>
</template>

<style scoped>
/* vue-echarts sizes itself to 100% of its parent, so the parent carries the height */
.chart-box {
  position: relative;
}
.chart-box > :deep(*) {
  position: absolute;
  inset: 0;
}
</style>
