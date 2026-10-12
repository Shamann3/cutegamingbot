import { cleanup, render } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import PanelBackgroundMusic from './PanelBackgroundMusic'
import { musicGain } from '../lib/musicMode'

describe('music gain', () => {
  it('keeps 100 percent at full file volume', () => {
    expect(musicGain(1)).toBe(1)
    expect(musicGain(0)).toBe(0)
    expect(musicGain(0.5)).toBe(0.25)
  })
})

describe('panel music', () => {
  let audio

  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
  })

  it('starts the track when the slider is at 100 percent', async () => {
    vi.stubGlobal('Audio', class {
      constructor() {
        audio = this
        this.volume = 0
        this.paused = true
        this.loop = false
        this.preload = ''
        this.src = ''
        this.play = vi.fn(() => {
          this.paused = false
          return Promise.resolve()
        })
        this.pause = vi.fn(() => { this.paused = true })
        this.load = vi.fn()
        this.removeAttribute = vi.fn()
      }
    })
    const view = render(<PanelBackgroundMusic volume={1} />)
    await vi.waitFor(() => expect(audio.play).toHaveBeenCalled())
    expect(audio.volume).toBe(1)
    expect(audio.loop).toBe(true)
    window.dispatchEvent(new CustomEvent('epsilon-cue-sounds', { detail: false }))
    expect(audio.paused).toBe(false)
    view.rerender(<PanelBackgroundMusic volume={0} />)
    expect(audio.pause).toHaveBeenCalled()
    expect(audio.volume).toBe(0)
  })
})
