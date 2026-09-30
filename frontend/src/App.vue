<template>
  <v-app>
    <v-app-bar flat border="b">
      <v-container class="d-flex align-center">
        <v-icon size="30" class="mr-3">mdi-database-sync</v-icon>
        <v-app-bar-title>Movie Data Loader</v-app-bar-title>
        <v-spacer />
        <v-chip
          v-if="runId"
          size="small"
          variant="outlined"
        >
          Run ID: {{ runId }}
        </v-chip>
      </v-container>
    </v-app-bar>

    <v-main>
      <v-container class="py-8" max-width="1000">
        <v-row>
          <v-col cols="12">
            <v-card rounded="lg" elevation="2">
              <v-card-item>
                <v-card-title class="text-h5">
                  Bronze → Silver
                </v-card-title>
                <v-card-subtitle>
                  Ejecuta el Notebook de carga de películas mediante un Lakeflow Job.
                </v-card-subtitle>
              </v-card-item>

              <v-divider />

              <v-card-text>
                <v-alert
                  v-if="error"
                  type="error"
                  variant="tonal"
                  class="mb-5"
                >
                  {{ error }}
                </v-alert>

                <v-row>
                  <v-col cols="12" md="6">
                    <v-sheet border rounded="lg" class="pa-4">
                      <div class="text-caption text-medium-emphasis">
                        Origen
                      </div>
                      <div class="font-weight-medium mt-1">
                        ADLS Gen2 / Bronze
                      </div>
                      <div class="text-body-2 text-medium-emphasis">
                        movie.csv
                      </div>
                    </v-sheet>
                  </v-col>

                  <v-col cols="12" md="6">
                    <v-sheet border rounded="lg" class="pa-4">
                      <div class="text-caption text-medium-emphasis">
                        Destino
                      </div>
                      <div class="font-weight-medium mt-1">
                        demo_catalog.silver.movie
                      </div>
                      <div class="text-body-2 text-medium-emphasis">
                        Delta / Unity Catalog
                      </div>
                    </v-sheet>
                  </v-col>
                </v-row>

                <div class="d-flex align-center mt-6">
                  <v-btn
                    color="primary"
                    size="large"
                    prepend-icon="mdi-play"
                    :loading="starting"
                    :disabled="running"
                    @click="executeNotebook"
                  >
                    Ejecutar Notebook
                  </v-btn>

                  <v-btn
                    v-if="runId && running"
                    class="ml-3"
                    variant="outlined"
                    prepend-icon="mdi-refresh"
                    @click="refreshStatus"
                  >
                    Actualizar
                  </v-btn>
                </div>
              </v-card-text>
            </v-card>
          </v-col>

          <v-col cols="12">
            <v-card rounded="lg" elevation="2">
              <v-card-item>
                <v-card-title>Estado de ejecución</v-card-title>
              </v-card-item>

              <v-card-text>
                <div class="status-row">
                  <v-chip
                    :color="statusColor"
                    :prepend-icon="statusIcon"
                    size="large"
                    variant="tonal"
                  >
                    {{ statusLabel }}
                  </v-chip>
                </div>

                <v-progress-linear
                  v-if="running"
                  indeterminate
                  color="primary"
                  class="mt-5"
                  rounded
                />

                <v-list v-if="runId" class="mt-4" lines="two">
                  <v-list-item title="Run ID" :subtitle="String(runId)" />
                  <v-list-item
                    v-if="runPageUrl"
                    title="Ejecución en Databricks"
                    subtitle="Abrir detalle de la ejecución"
                  >
                    <template #append>
                      <v-btn
                        icon="mdi-open-in-new"
                        variant="text"
                        :href="runPageUrl"
                        target="_blank"
                      />
                    </template>
                  </v-list-item>
                  <v-list-item
                    v-if="message"
                    title="Mensaje"
                    :subtitle="message"
                  />
                </v-list>
              </v-card-text>
            </v-card>
          </v-col>

          <v-col cols="12" v-if="result">
            <v-card rounded="lg" elevation="2">
              <v-card-item>
                <v-card-title>Resultado de la carga</v-card-title>
              </v-card-item>

              <v-card-text>
                <v-row>
                  <v-col cols="12" md="4">
                    <v-sheet border rounded="lg" class="pa-4 text-center">
                      <div class="text-caption text-medium-emphasis">
                        Registros procesados
                      </div>
                      <div class="text-h4 font-weight-bold mt-2">
                        {{ result.records ?? '-' }}
                      </div>
                    </v-sheet>
                  </v-col>

                  <v-col cols="12" md="4">
                    <v-sheet border rounded="lg" class="pa-4 text-center">
                      <div class="text-caption text-medium-emphasis">
                        Tabla
                      </div>
                      <div class="text-body-1 font-weight-medium mt-2">
                        {{ result.table ?? 'demo_catalog.silver.movie' }}
                      </div>
                    </v-sheet>
                  </v-col>

                  <v-col cols="12" md="4">
                    <v-sheet border rounded="lg" class="pa-4 text-center">
                      <div class="text-caption text-medium-emphasis">
                        Estado
                      </div>
                      <div class="text-h6 font-weight-bold mt-2">
                        {{ result.status ?? 'SUCCESS' }}
                      </div>
                    </v-sheet>
                  </v-col>
                </v-row>

                <v-alert
                  v-if="result.message"
                  type="success"
                  variant="tonal"
                  class="mt-5"
                >
                  {{ result.message }}
                </v-alert>
              </v-card-text>
            </v-card>
          </v-col>
        </v-row>
      </v-container>
    </v-main>
  </v-app>
</template>

<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'

const runId = ref(null)
const starting = ref(false)
const running = ref(false)
const status = ref('IDLE')
const error = ref('')
const message = ref('')
const runPageUrl = ref('')
const result = ref(null)

let pollTimer = null

const statusLabel = computed(() => {
  const labels = {
    IDLE: 'Sin ejecución',
    PENDING: 'PENDING',
    QUEUED: 'QUEUED',
    RUNNING: 'RUNNING',
    TERMINATING: 'TERMINATING',
    SUCCESS: 'SUCCESS',
    FAILED: 'FAILED',
    CANCELED: 'CANCELED',
    TIMEDOUT: 'TIMEDOUT',
    INTERNAL_ERROR: 'INTERNAL_ERROR'
  }
  return labels[status.value] ?? status.value
})

const statusColor = computed(() => {
  if (status.value === 'SUCCESS') return 'success'
  if (['FAILED', 'CANCELED', 'TIMEDOUT', 'INTERNAL_ERROR'].includes(status.value)) return 'error'
  if (['RUNNING', 'PENDING', 'QUEUED', 'TERMINATING'].includes(status.value)) return 'primary'
  return 'grey'
})

const statusIcon = computed(() => {
  if (status.value === 'SUCCESS') return 'mdi-check-circle'
  if (['FAILED', 'CANCELED', 'TIMEDOUT', 'INTERNAL_ERROR'].includes(status.value)) return 'mdi-alert-circle'
  if (['RUNNING', 'PENDING', 'QUEUED', 'TERMINATING'].includes(status.value)) return 'mdi-progress-clock'
  return 'mdi-minus-circle-outline'
})

async function executeNotebook() {
  starting.value = true
  error.value = ''
  result.value = null
  message.value = ''
  runPageUrl.value = ''

  try {
    const response = await fetch('/api/jobs/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({})
    })

    const data = await response.json()

    if (!response.ok) {
      throw new Error(data.detail || 'No fue posible iniciar el Job.')
    }

    runId.value = data.run_id
    status.value = data.status || 'PENDING'
    running.value = true
    startPolling()
  } catch (e) {
    error.value = e.message
    status.value = 'FAILED'
  } finally {
    starting.value = false
  }
}

async function refreshStatus() {
  if (!runId.value) return

  try {
    const response = await fetch(`/api/runs/${runId.value}`)
    const data = await response.json()

    if (!response.ok) {
      throw new Error(data.detail || 'No fue posible consultar el estado.')
    }

    status.value = data.status
    message.value = data.message || ''
    runPageUrl.value = data.run_page_url || ''

    if (data.result) {
      result.value = data.result
    }

    if (data.terminal) {
      running.value = false
      stopPolling()

      if (data.status !== 'SUCCESS') {
        error.value = data.message || 'La ejecución terminó con error.'
      }
    }
  } catch (e) {
    error.value = e.message
  }
}

function startPolling() {
  stopPolling()
  pollTimer = setInterval(refreshStatus, 2500)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

onBeforeUnmount(stopPolling)
</script>
