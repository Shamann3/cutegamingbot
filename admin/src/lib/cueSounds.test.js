import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  CUE_VOLUME,
  FOG_CUE_DELAY_MS,
  LOGO_CUE_DELAY_MS,
  armSaveCue,
  disarmSaveCue,
  isCommitControl,
  noteCommittedWrite,
  noteSuccessToast,
  pathIsSilent,
  playEnterCue,
  playSealCue,
  readCueSoundsEnabled,
  writeCueSoundsEnabled,
  writeShouldChime,
} from './cueSounds'

describe('cue sounds', () => {
  afterEach(() => {
    disarmSaveCue()
    localStorage.removeItem('cf_admin_cue_sounds')
  })

  it('is on until the person turns it off', () => {
    localStorage.removeItem('cf_admin_cue_sounds')
    expect(readCueSoundsEnabled()).toBe(true)
    writeCueSoundsEnabled(false)
    expect(readCueSoundsEnabled()).toBe(false)
    writeCueSoundsEnabled(true)
    expect(readCueSoundsEnabled()).toBe(true)
    expect(CUE_VOLUME).toBe(0.5)
  })

  it('recognises a save or a confirmation, not a search', () => {
    expect(isCommitControl('Сохранить должность')).toBe(true)
    expect(isCommitControl('Подходит')).toBe(true)
    expect(isCommitControl('Выдать бан')).toBe(true)
    expect(isCommitControl('Кикнуть из чата')).toBe(true)
    expect(isCommitControl('Разбанить')).toBe(true)
    expect(isCommitControl('Зарплата сохранена')).toBe(true)
    expect(isCommitControl('Найти')).toBe(false)
    expect(isCommitControl('Отмена')).toBe(false)
    expect(isCommitControl('Скопировано')).toBe(false)
  })

  it('chimes only a real write that the person just confirmed', () => {
    expect(LOGO_CUE_DELAY_MS).toBe(1100)
    expect(FOG_CUE_DELAY_MS).toBe(2600)
    expect(writeShouldChime('POST', '/group-realm/act/1')).toBe(false)
    armSaveCue()
    expect(writeShouldChime('POST', '/group-realm/act/1')).toBe(true)
    expect(writeShouldChime('GET', '/group-realm/summary/1')).toBe(false)
    expect(writeShouldChime('POST', '/auth/login')).toBe(false)
    expect(writeShouldChime('POST', '/deed-pay/pulse')).toBe(false)
    expect(pathIsSilent('/staff/contract-templates/render')).toBe(true)
    expect(noteCommittedWrite('POST', '/auth/refresh', true)).toBe(false)
    expect(writeShouldChime('POST', '/group-realm/act/1')).toBe(true)
    expect(noteCommittedWrite('POST', '/group-realm/act/1', false)).toBe(false)
    armSaveCue()
    expect(noteCommittedWrite('POST', '/group-realm/act/1', true)).toBe(true)
    expect(writeShouldChime('POST', '/group-realm/act/1')).toBe(false)
  })

  it('opens no clip when additional sounds are off', () => {
    writeCueSoundsEnabled(false)
    const created = vi.fn()
    vi.stubGlobal('Audio', created)
    expect(playEnterCue()).toBe(false)
    expect(playSealCue()).toBe(false)
    expect(noteSuccessToast('Наказание выдано')).toBe(false)
    expect(created).not.toHaveBeenCalled()
    vi.unstubAllGlobals()
  })

  it('does not treat an error toast as a save', () => {
    expect(noteSuccessToast('Не сохранилась', 'error')).toBe(false)
    expect(noteSuccessToast('Скопировано')).toBe(false)
  })
})
