export { apiClient, USE_MOCK } from "@/lib/api/client";
export { tasksApi } from "@/lib/api/services/tasks";
export type { TasksApi } from "@/lib/api/services/tasks";
export { analyticsApi } from "@/lib/api/services/analytics";
export type { AnalyticsApi } from "@/lib/api/services/analytics";
export { predictionApi } from "@/lib/api/services/prediction";
export type { PredictionApi } from "@/lib/api/services/prediction";
export { contextApi } from "@/lib/api/services/context";
export type { ContextApi } from "@/lib/api/services/context";
export { recommendationApi } from "@/lib/api/services/recommendation";
export type { RecommendationApi } from "@/lib/api/services/recommendation";
export { insightsApi } from "@/lib/api/services/insights";
export type { InsightsApi } from "@/lib/api/services/insights";
export { feedbackApi } from "@/lib/api/services/feedback";
export type { FeedbackApi } from "@/lib/api/services/feedback";
export { telemetryApi } from "@/lib/api/services/telemetry";
export type { TelemetryApi } from "@/lib/api/services/telemetry";
export { adaptiveApi } from "@/lib/api/services/adaptive";
export type {
  AdaptiveApi,
  RankedTaskItem,
  TaskRankingResponse,
  TaskRankingFeedbackCreate,
} from "@/lib/api/services/adaptive";
export { schedulingApi } from "@/lib/api/services/scheduling";
export type {
  BusyBlockRead,
  AvailabilityWindowRead,
  UserAvailabilityResponse,
  ScheduleExplanationDTO,
  ScheduledSlotDTO,
  UnscheduledTaskDTO,
  ScheduleProposalResponse,
  ScheduleGenerateRequest,
  ScheduleModifySlotRequest,
  ScheduleApprovalRequest,
  ScheduleApprovalResponse,
} from "@/lib/api/services/scheduling";
export { devicesApi, activityApi } from "@/lib/api/services/timeline";
export type {
  DeviceRead,
  DeviceRegisterRequest,
  UnifiedTimelineEventDTO,
  CrossDeviceSessionRead,
} from "@/lib/api/services/timeline";
export { locationContextApi } from "@/lib/api/services/location_context";
export type {
  LocationContextRead,
  LocationContextCreate,
  LocationCheckInRead,
  LocationCheckInCreate,
  LocationReminderDTO,
  LocationRecommendationsResponse,
  LocationConsentDTO,
} from "@/lib/api/services/location_context";


