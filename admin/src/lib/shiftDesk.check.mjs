import { compareTone, repeatCounts, watchLevel, watchLine } from './shiftDesk.js'

if (compareTone(null, 4) !== null) throw new Error('missing current')
if (compareTone(10, null) !== null) throw new Error('missing previous')
if (compareTone(12, 9) !== 'good') throw new Error('more is good')
if (compareTone(4, 20) !== 'bad') throw new Error('less is bad')
if (compareTone(8, 8) !== 'same') throw new Error('equal')

if (watchLevel(0) !== null) throw new Error('zero warns')
if (watchLevel(1) !== 'watch') throw new Error('one warn')
if (watchLevel(2) !== 'close') throw new Error('two warns')
if (watchLevel(3) !== 'limit') throw new Error('limit')
if (!watchLine('close', 2).includes('2 из 3')) throw new Error('close copy')

const counts = repeatCounts([
  { action: 'mute', target_user_id: 7 },
  { action: 'ban', target_user_id: 7 },
  { action: 'unmute', target_user_id: 7 },
])
if (counts.get(7) !== 2) throw new Error('unmute must not count')

console.log('shift desk checks ok')
