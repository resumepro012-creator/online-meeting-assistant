// -----------------------------------------------------------------------------
// This is the ONLY service module pages/components import from.
//
// It re-exports the real backend implementations from `./api`. Every function
// keeps the same name and signature it had when it was backed by
// `mockService.ts`, so no page needed rewriting to move off dummy data.
//
// `mockService.ts` / `mockData.ts` are kept on disk untouched but are no longer
// imported by anything in the running app.
// -----------------------------------------------------------------------------

export { ApiError } from './api'

export {
  login,
  signUp,
  logout,
  verifyEmail,
  resendVerificationCode,
  forgotPassword,
  resetPassword,
  getAuthPolicy,
  isAllowedUniversityEmail,
  getDashboardSummary,
  getPipelineHealth,
  getMeetingPolicy,
  joinMeetingAsBot,
  getBotStatus,
  stopMeetingBot,
  startMeetingRecording,
  stopMeetingRecording,
  getPreviousClasses,
  getClassById,
  getRecentClasses,
  getAllNotes,
  getRecentNotes,
  getNoteByClassId,
  getAllAnnouncements,
  getRecentAnnouncements,
  getAnnouncementsForClass,
  getProcessingStages,
  startSession,
  listClassLectures,
  getJobStatus,
  startProcessing,
  getLectureResults,
  getClassResults,
  getResultsForClass,
  getCurrentStudent,
  hasAccessToken,
} from './api'

export type {
  ApiErrorCode,
  AuthPolicy,
  BotJoinResult,
  BotStatus,
  MeetingPolicy,
  RegisterResult,
  ResendVerificationResult,
  StartedSession,
  StartSessionInput,
} from './api'

/** The app is no longer reading dummy data. */
export const IS_DEMO_MODE = false
