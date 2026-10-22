import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import {
  createGuardian,
  fetchGuardians,
  removeGuardian,
  updateGuardian,
  type GuardianPayload
} from '@/api/guardians'
import { humanizeError } from '@/api/http'
import type { Guardian } from '@/api/types'

export const useGuardianStore = defineStore('guardian', () => {
  const items = ref<Guardian[]>([])
  const maxCount = ref(3)
  const loading = ref(false)
  const saving = ref(false)
  const error = ref<string | null>(null)
  const loaded = ref(false)

  const remaining = computed(() => Math.max(maxCount.value - items.value.length, 0))
  const canAddMore = computed(() => remaining.value > 0)

  async function load(force = false): Promise<void> {
    if (loaded.value && !force) return
    loading.value = true
    try {
      const data = await fetchGuardians()
      items.value = data.items
      maxCount.value = data.maxCount
      error.value = null
      loaded.value = true
    } catch (err) {
      error.value = humanizeError(err)
    } finally {
      loading.value = false
    }
  }

  async function add(payload: GuardianPayload): Promise<Guardian> {
    saving.value = true
    try {
      const created = await createGuardian(payload)
      items.value = [...items.value, created]
      return created
    } finally {
      saving.value = false
    }
  }

  async function edit(id: number, payload: Partial<GuardianPayload>): Promise<Guardian> {
    saving.value = true
    try {
      const updated = await updateGuardian(id, payload)
      items.value = items.value.map((item) => (item.id === id ? updated : item))
      return updated
    } finally {
      saving.value = false
    }
  }

  async function remove(id: number): Promise<void> {
    saving.value = true
    try {
      await removeGuardian(id)
      items.value = items.value.filter((item) => item.id !== id)
    } finally {
      saving.value = false
    }
  }

  function reset(): void {
    items.value = []
    loaded.value = false
    error.value = null
  }

  return {
    items,
    maxCount,
    remaining,
    canAddMore,
    loading,
    saving,
    error,
    loaded,
    load,
    add,
    edit,
    remove,
    reset
  }
})
