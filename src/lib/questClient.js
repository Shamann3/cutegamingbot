import { apiRequest } from './apiClient'

export function mapQuestsState(data) {
  return {
    kut: data?.kut ?? 0,
    sections: data?.sections ?? { hourly: [], daily: [], weekly: [], events: [] },
    readyCount: data?.readyCount ?? 0,
    npcName: data?.npcName ?? 'Задания',
    npcEmoji: data?.npcEmoji ?? '📜',
    periodLabels: data?.periodLabels ?? {
      hourly: 'На час',
      daily: 'На день',
      weekly: 'На неделю',
      events: 'Ивенты',
    },
    periodTimers: data?.periodTimers ?? {},
    acceptRules: data?.acceptRules ?? { hourly: 1, daily: 1, weekly: 1 },
    slotLimits: data?.slotLimits ?? { hourly: 2, daily: 3, weekly: 1 },
    seedEconomy: data?.seedEconomy ?? null,
    farmCrops: data?.farmCrops ?? [],
    questReward: data?.questReward ?? null,
  }
}

export function fetchQuestsState() {
  return apiRequest('/api/quests/state')
}

export function acceptQuest(questId) {
  return apiRequest('/api/quests/accept', {
    method: 'POST',
    body: { questId },
  })
}

export function cancelQuest(questId) {
  return apiRequest('/api/quests/cancel', {
    method: 'POST',
    body: { questId },
  })
}

export function claimQuestReward(questId) {
  return apiRequest('/api/quests/claim', {
    method: 'POST',
    body: { questId },
  })
}

export function claimDailySeed(seedItemId) {
  return apiRequest('/api/farm/claim-daily-seed', {
    method: 'POST',
    body: seedItemId ? { seedItemId } : {},
  })
}
