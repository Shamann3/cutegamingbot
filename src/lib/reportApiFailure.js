import { reportClientError } from './errorReporter'
import { codeForApiError } from './errorCodes'

export function reportApiFailure(error, path, context = '') {
  if (error?.status >= 400) return
  const code = codeForApiError(error, path)
  reportClientError({
    code,
    message: error?.message ?? '',
    path,
    context,
  })
}
