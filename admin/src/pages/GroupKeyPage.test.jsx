import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import GroupKeyPage from './GroupKeyPage'
import { checkGroupKey, enterGroupKey, fetchAdminAuthStatus, readGroupEntry, clearGroupEntry } from '../lib/adminClient'

vi.mock('../lib/adminClient', async (importOriginal) => ({
  ...(await importOriginal()),
  checkGroupKey: vi.fn(),
  enterGroupKey: vi.fn(),
  fetchAdminAuthStatus: vi.fn(),
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
    vi.mocked(fetchAdminAuthStatus).mockReset()
    vi.mocked(fetchAdminAuthStatus).mockResolvedValue({ groupCanEnter: true, isProjectCreator: false })
  })

  async function showKey(ui) {
    const view = render(ui)
    await act(async () => {
      await Promise.resolve()
    })
    return view
  }

  afterEach(() => {
    vi.useRealTimers()
    clearGroupEntry()
  })

  it('прячет кнопку кабинета, пока ключ не сошёлся', async () => {
    vi.mocked(checkGroupKey).mockRejectedValue(Object.assign(new Error('Ключ не подошёл'), { status: 403 }))
    await showKey(<GroupKeyPage onBack={() => {}} onPassed={() => {}} onApply={() => {}} onPreview={() => {}} />)

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
    await showKey(<GroupKeyPage onBack={() => {}} onPassed={onPassed} onApply={() => {}} onPreview={() => {}} />)

    fireEvent.change(screen.getByLabelText('Ключ кабинета'), { target: { value: 'right-key-123' } })
    expect(screen.queryByRole('button', { name: 'Войти' })).toBeNull()
    await vi.advanceTimersByTimeAsync(800)

    fireEvent.click(screen.getByRole('button', { name: 'Войти' }))
    await vi.advanceTimersByTimeAsync(0)
    expect(onPassed).toHaveBeenCalledTimes(1)
  })

  it('после ключа показывает QR и кнопку ключа приложения', async () => {
    vi.mocked(checkGroupKey).mockResolvedValue({
      ok: true,
      needCode: true,
      setup: { qrDataUrl: 'data:image/png;base64,abc', totpSecret: 'APPSECRETKEY' },
    })
    await showKey(<GroupKeyPage onBack={() => {}} onPassed={() => {}} onApply={() => {}} onPreview={() => {}} />)

    fireEvent.change(screen.getByLabelText('Ключ кабинета'), { target: { value: 'right-key-123' } })
    await vi.advanceTimersByTimeAsync(800)

    const copy = screen.getByRole('button', { name: 'Скопировать ключ приложения' })
    const veil = screen.getByRole('button', { name: 'Нажмите, чтобы увидеть' })
    expect(copy.compareDocumentPosition(veil) & Node.DOCUMENT_POSITION_FOLLOWING).toBe(0)
    expect(screen.getByAltText('QR-код для приложения с кодами').getAttribute('src')).toBe('data:image/png;base64,abc')
    expect(screen.queryByText('APPSECRETKEY')).toBeNull()
    fireEvent.click(veil)
    await vi.advanceTimersByTimeAsync(400)
    expect(screen.getByText('APPSECRETKEY')).toBeTruthy()
  })

  it('после ключа просит код из приложения', async () => {
    vi.mocked(checkGroupKey).mockResolvedValue({ ok: true, needCode: true })
    vi.mocked(enterGroupKey).mockResolvedValue({ ok: true, entryPass: 'g.kept.pass' })
    const onPassed = vi.fn()
    await showKey(<GroupKeyPage onBack={() => {}} onPassed={onPassed} onApply={() => {}} onPreview={() => {}} />)

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

  it('без ключа сразу открывает заявку и не показывает поле', async () => {
    vi.mocked(fetchAdminAuthStatus).mockResolvedValue({ groupCanEnter: false, isProjectCreator: false })
    const onApply = vi.fn()
    await showKey(<GroupKeyPage onBack={() => {}} onPassed={() => {}} onApply={onApply} onPreview={() => {}} />)
    expect(onApply).toHaveBeenCalledTimes(1)
    expect(screen.queryByLabelText('Ключ кабинета')).toBeNull()
  })

  it('ответ сервера без ключа тоже ведёт в заявку', async () => {
    const onApply = vi.fn()
    vi.mocked(checkGroupKey).mockRejectedValue(Object.assign(new Error('Личного ключа ещё нет'), { status: 403, code: 'need_apply' }))
    await showKey(<GroupKeyPage onBack={() => {}} onPassed={() => {}} onApply={onApply} onPreview={() => {}} />)
    fireEvent.change(screen.getByLabelText('Ключ кабинета'), { target: { value: 'typed-key-123' } })
    await vi.advanceTimersByTimeAsync(800)
    expect(onApply).toHaveBeenCalledTimes(1)
    expect(screen.queryByRole('alert')).toBeNull()
  })
})
