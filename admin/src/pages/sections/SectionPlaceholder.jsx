import { getSectionById } from '../../constants/panelNav'

export default function SectionPlaceholder({ sectionId }) {
  const section = getSectionById(sectionId)

  return (
    <article className="panel-shelf panel-shelf-page">
      <p className="panel-shelf-label">{section.label}</p>
      <h2 className="panel-page-title">{section.labelRu}</h2>
      <p className="panel-page-lead">Раздел не найден.</p>
    </article>
  )
}
