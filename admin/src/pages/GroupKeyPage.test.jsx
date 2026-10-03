import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import GroupKeyPage from './GroupKeyPage'
import { checkGroupKey, enterGroupKey, readGroupEntry, clearGroupEntry } from '../lib/adminClient'

vi.mock('../lib/adminClient', async (importOriginal) => ({
  ...(await importOriginal()),
  checkGroupKey: vi.fn(),
  enterGroupKey: vi.fn(),
}))

vi.mock('../components/AccentAura', () => ({ default: () => null }))
vi.mock('../components/EpsilonLogo', () => ({ default: () => null }))

afterEach(() => {
  cleanup()
})

describe('GroupKeyPage', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.mocked(checkGroupKey).mockReset()
    vi.mocked(enterGroupKey).mockReset()
  })

  afterEach(() => {
    vi.useRealTimers()
    clearGroupEntry()
  })

  it('прячет кнопку кабинета, пока ключ не сошёлся', async () => {
    vi.mocked(checkGroupKey).mockRejectedValue(Object.assign(new Error('Ключ не подошёл'), { status: 403 }))
    render(<GroupKeyPage onBack={() => {}} onPassed={() => {}} onPreview={() => {}} />)

    expect(screen.queryByRole('button', { name: 'Войти' })).toBeNull()
    fireEvent.change(screen.getByLabelText('Ключ кабинета'), { target: { value: 'wrong-key-123' } })
    await vi.advanceTimersByTimeAsync(800)

    expect(screen.queryByRole('button', { name: 'Войти' })).toBeNull()
    expect(screen.getByRole('alert').textContent).toContain('Ключ не подошёл')
    expect(screen.getByRole('button', { name: 'К выбору панели' })).toBeTruthy()
  })

  it('показывает вход без кода, если код не нужен', async () => {
    vi.mocked(checkGroupKey).mockResolvedValue({ ok: true, needCode: false })
    const onPassed = vi.fn()
    render(<GroupKeyPage onBack={() => {}} onPassed={onPassed} onPreview={() => {}} />)

    fireEvent.change(screen.getByLabelText('Ключ кабинета'), { target: { value: 'right-key-123' } })
    expect(screen.queryByRole('button', { name: 'Войти' })).toBeNull()
    await vi.advanceTimersByTimeAsync(800)

    fireEvent.click(screen.getByRole('button', { name: 'Войти' }))
    await vi.advanceTimersByTimeAsync(0)
    expect(onPassed).toHaveBeenCalledTimes(1)
  })

  it('после ключа просит код из приложения', async () => {
    vi.mocked(checkGroupKey).mockResolvedValue({ ok: true, needCode: true })
    vi.mocked(enterGroupKey).mockResolvedValue({ ok: true, entryPass: 'g.kept.pass' })
    const onPassed = vi.fn()
    render(<GroupKeyPage onBack={() => {}} onPassed={onPassed} onPreview={() => {}} />)

    fireEvent.change(screen.getByLabelText('Ключ кабинета'), { target: { value: 'right-key-123' } })
    await vi.advanceTimersByTimeAsync(800)

    const code = screen.getByLabelText('Код из приложения')
    expect(screen.getByRole('button', { name: 'Войти' }).disabled).toBe(true)
    fireEvent.change(code, { target: { value: '123456' } })
    fireEvent.click(screen.getByRole('button', { name: 'Войти' }))
    await vi.advanceTimersByTimeAsync(0)
    expect(enterGroupKey).toHaveBeenCalledWith('right-key-123', '123456')
    expect(onPassed).toHaveBeenCalledTimes(1)
    expect(readGroupEntry()).toBe('g.kept.pass')
  })
})
