import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import TgPhoto, { dropTgPhoto, sniffImageType } from './TgPhoto'

afterEach(() => {
  cleanup()
  dropTgPhoto('proof-file')
  vi.unstubAllGlobals()
})

describe('TgPhoto', () => {
  it('recognises photo bytes even when the header is not an image', () => {
    const jpeg = new Uint8Array([0xff, 0xd8, 0xff, 0xe0])
    expect(sniffImageType(jpeg, 'application/octet-stream')).toBe('image/jpeg')
    expect(sniffImageType(new Uint8Array([1, 2, 3]), 'text/html')).toBe('')
  })

  it('shows the proof image from the proxy', async () => {
    const jpeg = new Uint8Array([0xff, 0xd8, 0xff, 0xe0, 1, 2, 3])
    vi.stubGlobal('fetch', vi.fn(async () => new Response(jpeg, {
      status: 200,
      headers: { 'content-type': 'application/octet-stream' },
    })))
    vi.stubGlobal('URL', {
      ...URL,
      createObjectURL: () => 'blob:proof',
      revokeObjectURL: () => {},
    })

    render(<TgPhoto fileId="proof-file" lazy={false} alt="Фото-доказательство" />)

    const img = await screen.findByRole('img', { name: 'Фото-доказательство' })
    await waitFor(() => expect(img.getAttribute('src')).toBe('blob:proof'))
    expect(screen.queryByText(/не загрузилось/)).toBeNull()
  })
})
