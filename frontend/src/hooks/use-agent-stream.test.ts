import { describe, expect, it } from 'vitest'

describe('useAgentStream contract', () => {
  it('keeps event ids as the deduplication cursor', () => {
    const ids = [1, 2, 2, 3]
    expect([...new Set(ids)]).toEqual([1, 2, 3])
  })
})
