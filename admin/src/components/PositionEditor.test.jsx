import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { searchAdminUsers } from '../lib/adminClient'
import PositionEditor from './PositionEditor'

vi.mock('../lib/adminClient', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    searchAdminUsers: vi.fn(async () => ({ results: [] })),
  }
})

const positions = [
  { id: 2, title: 'Модератор', rank: 2, kind: 'post', prefix: 'мод', rights: ['view_members'] },
  { id: 9, title: 'Спам-блок', rank: 0, kind: 'spamblock', prefix: 'спам блок', rights: [] },
  { id: 5, title: 'Создатель', rank: 5, kind: 'post', prefix: '', rights: [] },
]

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

function open(title) {
  const button = screen.getAllByRole('button').find((node) => {
    const label = node.getAttribute('aria-label') || ''
    if (/^(Перетащить|Выше|Ниже)/.test(label)) return false
    return new RegExp(title).test(node.textContent || '')
  })
  fireEvent.click(button)
}

describe('PositionEditor', () => {
  it('puts a delete button at the bottom of an administrator position', async () => {
    const onDelete = vi.fn(async () => {})
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    render(
      <PositionEditor
        positions={positions}
        creator
        chatId={-100}
        seats={[{ userId: 7, positionId: 2, name: 'Аня', username: 'anya' }]}
        onSave={vi.fn()}
        onDelete={onDelete}
        onAppoint={vi.fn()}
      />,
    )

    open('Модератор')
    expect(screen.getByRole('button', { name: 'Назначить эту должность' })).toBeTruthy()
    expect(screen.getByText('Аня')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Удалить должность' }))
    expect(window.confirm).toHaveBeenCalled()
    expect(String(window.confirm.mock.calls[0][0])).toContain('держат 1')
    await waitFor(() => expect(onDelete).toHaveBeenCalled())
    expect(onDelete.mock.calls[0][0].id).toBe(2)
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  })

  it('does not offer delete or appoint for the group creator rank', () => {
    render(
      <PositionEditor
        positions={positions}
        creator
        chatId={-100}
        onSave={vi.fn()}
        onDelete={vi.fn()}
        onAppoint={vi.fn()}
      />,
    )
    open('Создатель')
    expect(screen.queryByRole('button', { name: 'Удалить должность' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Назначить эту должность' })).toBeNull()
  })

  it('appoints the open position to the chosen person', async () => {
    const onAppoint = vi.fn(async () => ({ entryKey: 'key-1', telegram: 'В группе стоит префикс «мод».' }))
    render(
      <PositionEditor
        positions={positions}
        creator
        chatId={-100}
        onSave={vi.fn()}
        onDelete={vi.fn()}
        onAppoint={onAppoint}
      />,
    )
    open('Модератор')
    const field = screen.getByLabelText('Кому')
    fireEvent.change(field, { target: { value: '42' } })
    expect(field.value).toBe('42')
    fireEvent.click(screen.getByRole('button', { name: 'Назначить эту должность' }))
    await waitFor(() => expect(onAppoint).toHaveBeenCalled())
    expect(onAppoint.mock.calls[0][1]).toMatchObject({ userId: 42, prefix: 'мод' })
    expect(await screen.findByText(/key-1/)).toBeTruthy()
  })

  it('asks for the spam-block end date before appointing', async () => {
    const onAppoint = vi.fn()
    render(
      <PositionEditor
        positions={positions}
        creator
        chatId={-100}
        onSave={vi.fn()}
        onDelete={vi.fn()}
        onAppoint={onAppoint}
      />,
    )
    open('Спам-блок')
    fireEvent.change(screen.getByLabelText('Кому'), { target: { value: '42' } })
    fireEvent.click(screen.getByRole('button', { name: 'Назначить эту должность' }))
    expect((await screen.findByRole('alert')).textContent).toContain('по какое число')
    expect(onAppoint).not.toHaveBeenCalled()
  })

  it('keeps a typed username visible and appoints that person', async () => {
    vi.mocked(searchAdminUsers).mockResolvedValue({
      results: [{ userId: 99, username: 'anya', displayName: 'Аня' }],
    })
    const onAppoint = vi.fn(async () => ({ entryKey: 'key-2' }))
    render(
      <PositionEditor
        positions={positions}
        creator
        chatId={-100}
        onSave={vi.fn()}
        onDelete={vi.fn()}
        onAppoint={onAppoint}
      />,
    )
    open('Модератор')
    const field = screen.getByLabelText('Кому')
    fireEvent.change(field, { target: { value: '@anya' } })
    expect(field.value).toBe('@anya')
    expect(await screen.findByText(/Выбран Аня/)).toBeTruthy()
    expect(field.value).toBe('@anya')
    fireEvent.click(screen.getByRole('button', { name: 'Назначить эту должность' }))
    await waitFor(() => expect(onAppoint).toHaveBeenCalled())
    expect(onAppoint.mock.calls[0][1].userId).toBe(99)
  })

  it('saves the cabinet tabs the switches show', () => {
    const onSave = vi.fn()
    render(
      <PositionEditor
        positions={positions}
        creator
        chatId={-100}
        onSave={onSave}
      />,
    )
    open('Модератор')
    const sw = (title) => screen.getAllByRole('switch').find((node) => node.querySelector('strong')?.textContent === title)
    expect(sw('Работа').getAttribute('aria-checked')).toBe('false')
    expect(sw('Моя зарплата').getAttribute('aria-checked')).toBe('true')
    fireEvent.click(sw('Работа'))
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить должность' }))
    expect(onSave.mock.calls[0][0].pages).toEqual(['work', 'activity', 'pay'])
  })

  it('lets the creator choose cabinet tabs for a spam block', () => {
    const onSave = vi.fn()
    render(
      <PositionEditor
        positions={positions}
        creator
        chatId={-100}
        onSave={onSave}
      />,
    )
    open('Спам-блок')
    const sw = (title) => screen.getAllByRole('switch').find((node) => node.querySelector('strong')?.textContent === title)
    expect(sw('Работа').disabled).toBe(false)
    expect(sw('Мут').disabled).toBe(false)
    expect(sw('Удалять сообщения').disabled).toBe(false)
    expect(sw('Банфулл').disabled).toBe(false)
    fireEvent.click(sw('Мут'))
    fireEvent.click(sw('Банфулл'))
    fireEvent.click(sw('Работа'))
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить должность' }))
    expect(onSave.mock.calls[0][0].pages).toEqual(['work', 'activity', 'pay'])
    expect(onSave.mock.calls[0][0].rights).toEqual(expect.arrayContaining(['punish_mute', 'banfull']))
  })

  it('keeps the group creator rights locked and the project rights open', () => {
    render(
      <PositionEditor
        positions={positions}
        creator
        chatId={-100}
        onSave={vi.fn()}
      />,
    )
    open('Создатель')
    const sw = (title) => screen.getAllByRole('switch').find((node) => node.querySelector('strong')?.textContent === title)
    expect(sw('Мут').disabled).toBe(true)
    expect(sw('Банфулл').disabled).toBe(false)
  })

  it('lifts a rank-1 administrator when the order is written', async () => {
    const onOrder = vi.fn()
    render(
      <PositionEditor
        positions={[
          { id: 2, title: 'Модератор', rank: 1, kind: 'post', rights: ['view_members'] },
          { id: 4, title: 'Хелпер', rank: 1, kind: 'post', rights: ['view_members'] },
          { id: 5, title: 'Создатель', rank: 5, kind: 'post', rights: [] },
          { id: 9, title: 'Спам-блок', rank: 0, kind: 'spamblock', rights: [] },
        ]}
        creator
        canReorder
        onOrder={onOrder}
        onSave={vi.fn()}
      />,
    )
    expect(screen.getByRole('button', { name: 'Записать ранги' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: /Перетащить, Создатель/ })).toBeNull()
    expect(screen.queryByRole('button', { name: /Перетащить, Спам-блок/ })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Записать ранги' }))
    expect(onOrder).toHaveBeenCalledWith([2, 4])
    fireEvent.click(screen.getByRole('button', { name: 'Ниже, Модератор' }))
    await waitFor(() => expect(onOrder).toHaveBeenLastCalledWith([4, 2]))
  })

  it('does not drag while a search hides part of the ladder', () => {
    render(
      <PositionEditor
        positions={positions}
        creator
        canReorder={false}
        onOrder={vi.fn()}
        onSave={vi.fn()}
      />,
    )
    expect(screen.getByText('Очистите поиск, чтобы менять ранги.')).toBeTruthy()
    expect(screen.queryByRole('button', { name: /Перетащить/ })).toBeNull()
  })
})
