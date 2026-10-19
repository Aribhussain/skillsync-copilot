<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'

import { fetchPlan, type PlanResponse } from '../../lib/assessor'
import { analyseImage, type QcResult } from '../../lib/imageQc'
import {
  canvasToBlob,
  drawPersonSample,
  drawProcessSample,
  imageToCanvas,
  loadImage,
  type ProductSample,
  productSamples,
} from '../../lib/sampleCapture'

type Shot = 'process' | 'product' | 'person'
type Source = 'camera' | 'upload' | 'simulated'

interface Capture {
  blob: Blob
  url: string
  qc: QcResult
  source: Source
  accepted: boolean
}

const SHOTS: Shot[] = ['process', 'product', 'person']
const { t } = useI18n()
const route = useRoute()
const id = Number(route.params.id)

const plan = ref<PlanResponse | null>(null)
const step = ref(0)
const captures = ref<Partial<Record<Shot, Capture>>>({})
const samples = ref<ProductSample[]>([])
const sampleIdx = ref(0)
const error = ref('')
const busy = ref(false)
const video = ref<HTMLVideoElement | null>(null)
const stream = ref<MediaStream | null>(null)
const cameraAvailable = typeof navigator !== 'undefined' && !!navigator.mediaDevices?.getUserMedia

const shot = computed<Shot>(() => SHOTS[step.value] ?? 'person')
const current = computed(() => captures.value[shot.value])
const code = computed(() => plan.value?.assessment.challenge_code ?? '')
const done = computed(() => SHOTS.every((s) => captures.value[s]?.accepted))

onMounted(async () => {
  try {
    plan.value = (await fetchPlan(id)).data
    samples.value = await productSamples()
    sampleIdx.value = id % Math.max(1, samples.value.length)
  } catch (e) {
    error.value = String(e)
  }
})
onBeforeUnmount(stopCamera)

async function startCamera() {
  error.value = ''
  try {
    stream.value = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' }, audio: false })
    if (video.value) {
      video.value.srcObject = stream.value
      await video.value.play()
    }
  } catch (e) {
    error.value = t('capture.cameraError', { msg: (e as Error).message })
  }
}

function stopCamera() {
  stream.value?.getTracks().forEach((tr) => tr.stop())
  stream.value = null
}

async function useCanvas(c: HTMLCanvasElement, source: Source) {
  busy.value = true
  try {
    const qc = await analyseImage(c)
    const blob = await canvasToBlob(c)
    const prev = captures.value[shot.value]
    if (prev) URL.revokeObjectURL(prev.url)
    captures.value = { ...captures.value, [shot.value]: { blob, url: URL.createObjectURL(blob), qc, source, accepted: false } }
  } finally {
    busy.value = false
  }
}

async function snap() {
  const v = video.value
  if (!v || !v.videoWidth) return
  const c = document.createElement('canvas')
  c.width = v.videoWidth
  c.height = v.videoHeight
  c.getContext('2d')!.drawImage(v, 0, 0)
  stopCamera()
  await useCanvas(c, 'camera')
}

async function onFile(ev: Event) {
  const file = (ev.target as HTMLInputElement).files?.[0]
  if (!file) return
  const bmp = await createImageBitmap(file)
  await useCanvas(await imageToCanvas(bmp), 'upload')
}

async function simulate() {
  const key = `${id}`
  if (shot.value === 'process') await useCanvas(drawProcessSample(key), 'simulated')
  else if (shot.value === 'person') await useCanvas(drawPersonSample(key, code.value || '------'), 'simulated')
  else {
    const s = samples.value[sampleIdx.value]
    if (s) await useCanvas(await imageToCanvas(await loadImage(s.file)), 'simulated')
  }
}

function accept() {
  const c = captures.value[shot.value]
  if (!c) return
  captures.value = { ...captures.value, [shot.value]: { ...c, accepted: true } }
  if (step.value < SHOTS.length - 1) step.value++
}

function retake() {
  const c = captures.value[shot.value]
  if (c) URL.revokeObjectURL(c.url)
  const next = { ...captures.value }
  delete next[shot.value]
  captures.value = next
}
</script>

<template>
  <div class="mx-auto grid max-w-3xl gap-4" data-testid="capture-view">
    <section class="card">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <h1 class="text-2xl font-bold">{{ t('capture.title') }}</h1>
        <RouterLink :to="`/assessor/assessment/${id}`" class="chip bg-navy-100 px-3 py-2">{{ t('common.back') }}</RouterLink>
      </div>
      <p class="text-sm text-navy-700">{{ plan?.assessment.candidate }} · {{ plan?.qp.title }}</p>
      <ol class="mt-3 grid grid-cols-3 gap-2">
        <li
          v-for="(s, i) in SHOTS"
          :key="s"
          class="rounded-xl border-2 p-2 text-center text-sm font-semibold"
          :class="captures[s]?.accepted ? 'border-green-india-600 bg-green-india-100' : i === step ? 'border-navy-900' : 'border-navy-100'"
          :data-testid="`step-${s}`"
          :data-done="!!captures[s]?.accepted"
          @click="step = i"
        >
          {{ i + 1 }}. {{ t(`capture.shot.${s}`) }}
        </li>
      </ol>
    </section>

    <section v-if="!done" class="card">
      <h2 class="text-lg font-bold">{{ t(`capture.shot.${shot}`) }}</h2>
      <p class="mb-3 text-sm">{{ t(`capture.guide.${shot}`) }}</p>
      <div v-if="shot === 'person'" class="mb-3 rounded-xl border-2 border-dashed border-navy-900 p-3 text-center">
        <div class="text-xs font-semibold">{{ t('assessor.challengeCode') }}</div>
        <div class="font-mono text-3xl font-bold tracking-widest" data-testid="capture-challenge-code">{{ code || '—' }}</div>
        <p v-if="!code" class="text-xs text-saffron-600">{{ t('capture.startFirst') }}</p>
      </div>

      <div v-if="stream" class="relative overflow-hidden rounded-xl bg-black">
        <video ref="video" class="w-full" playsinline muted />
        <div class="pointer-events-none absolute inset-[15%] rounded-lg border-4 border-dashed border-white/70" />
        <button class="btn-saffron absolute bottom-3 left-1/2 -translate-x-1/2" @click="snap">📸 {{ t('capture.snap') }}</button>
      </div>

      <div v-if="current" class="grid gap-3">
        <img :src="current.url" alt="" class="max-h-80 w-full rounded-xl object-contain bg-navy-50" data-testid="capture-preview" />
        <div
          class="rounded-xl p-3 text-sm"
          :class="current.qc.ok ? 'bg-green-india-100 text-green-india-700' : 'bg-saffron-100'"
          data-testid="qc-result"
          :data-ok="current.qc.ok"
        >
          <b>{{ current.qc.ok ? t('capture.qcOk') : t('capture.qcIssues') }}</b>
          <ul v-if="!current.qc.ok" class="mt-1 list-disc pl-5">
            <li v-for="issue in current.qc.issues" :key="issue" :data-testid="`qc-issue-${issue}`">{{ t(`capture.qc.${issue}`) }}</li>
          </ul>
          <div class="mt-1 text-xs opacity-75">
            blur {{ current.qc.metrics.laplacianVar.toFixed(1) }} · light {{ current.qc.metrics.brightness.toFixed(0) }} ·
            centre {{ (current.qc.metrics.centreEdgeShare * 100).toFixed(0) }}% · {{ current.qc.metrics.width }}×{{ current.qc.metrics.height }}
            <span v-if="current.source === 'simulated'"> · {{ t('capture.simulatedTag') }}</span>
          </div>
        </div>
        <div class="flex flex-wrap gap-2">
          <button class="btn-ghost flex-1" @click="retake">{{ t('capture.retake') }}</button>
          <button class="btn-green flex-1" data-testid="accept-shot" @click="accept">
            {{ current.qc.ok ? t('capture.accept') : t('capture.acceptAnyway') }}
          </button>
        </div>
      </div>

      <div v-else-if="!stream" class="grid gap-2 sm:grid-cols-3">
        <button v-if="cameraAvailable" class="btn-primary" @click="startCamera">📷 {{ t('capture.camera') }}</button>
        <label class="btn-ghost cursor-pointer">
          ⬆ {{ t('capture.upload') }}
          <input type="file" accept="image/*" capture="environment" class="hidden" data-testid="file-input" @change="onFile" />
        </label>
        <button class="btn-saffron" :disabled="busy" data-testid="simulate-shot" @click="simulate">🧪 {{ t('capture.simulate') }}</button>
        <div v-if="shot === 'product' && samples.length" class="sm:col-span-3">
          <p class="mb-1 text-xs text-navy-700">{{ t('capture.pickSample') }}</p>
          <div class="flex gap-2 overflow-x-auto pb-1">
            <button
              v-for="(s, i) in samples"
              :key="s.file"
              class="shrink-0 rounded-lg border-2"
              :class="i === sampleIdx ? 'border-saffron-500' : 'border-transparent'"
              :data-testid="`sample-${i}`"
              @click="sampleIdx = i"
            >
              <img :src="s.file" alt="" class="h-16 w-16 rounded-md object-cover" />
            </button>
          </div>
        </div>
      </div>
    </section>

    <section v-else class="card" data-testid="capture-review">
      <h2 class="text-lg font-bold">{{ t('capture.review') }}</h2>
      <div class="mt-2 grid grid-cols-3 gap-2">
        <figure v-for="s in SHOTS" :key="s">
          <img :src="captures[s]!.url" alt="" class="aspect-square w-full rounded-lg object-cover" />
          <figcaption class="mt-1 text-xs font-semibold">
            {{ t(`capture.shot.${s}`) }} {{ captures[s]!.qc.ok ? '✓' : '⚠' }}
          </figcaption>
        </figure>
      </div>
    </section>

    <p v-if="error" class="rounded-lg bg-saffron-100 p-2 text-sm" role="alert">{{ error }}</p>
  </div>
</template>
