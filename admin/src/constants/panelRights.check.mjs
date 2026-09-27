import { filterSectionTabs } from './panelAccessTree.js'
import { visibleSections } from './panelNav.js'

const junior = visibleSections(
  ['view_players'],
  ['users'],
  'junior_admin',
)
const ids = junior.map((item) => item.id)
if (!ids.includes('users')) throw new Error('open players page is missing')
if (ids.includes('economy')) throw new Error('closed economy page is visible')
if (ids.includes('panelAccess')) throw new Error('owner page is visible to junior')

const none = visibleSections(['view_players', 'manage_economy'], [], 'junior_admin')
const noneIds = none.map((item) => item.id)
if (noneIds.includes('users') || noneIds.includes('economy')) {
  throw new Error('empty page list must hide pages')
}

const untouched = visibleSections(['view_players'], null, 'junior_admin')
if (!untouched.some((item) => item.id === 'users')) {
  throw new Error('missing map must keep permission pages')
}

const creator = visibleSections([], [], 'owner', { isProjectCreator: true })
if (!creator.some((item) => item.id === 'rights')) {
  throw new Error('creator must keep the rights page')
}
if (!creator.some((item) => item.id === 'groupGuard')) {
  throw new Error('creator must keep the guard page')
}

const tabs = filterSectionTabs('staff', [{ id: 'salaries' }, { id: 'applications' }], {
  staff: ['salaries'],
})
if (tabs.length !== 1 || tabs[0].id !== 'salaries') {
  throw new Error('inner tab filter failed')
}

const hidden = filterSectionTabs('staff', [{ id: 'salaries' }], { staff: [] })
if (hidden.length !== 0) throw new Error('empty inner list must hide tabs')

console.log('panel rights checks ok')
