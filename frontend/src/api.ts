export type UserRole = "employee" | "manager" | "hr";
export type ActionStatus = "pending" | "completed";

export interface User {
  id: string;
  name: string;
  email: string;
  role: UserRole;
}

export interface LoginResponse {
  user: User;
  csrf_token: string;
  expires_at: string;
  default_path: string;
}

export interface DashboardAction {
  id: string;
  text: string;
  completion_criteria: string;
  recommended_evidence: string[];
  is_required: boolean;
  display_order: number;
  status: ActionStatus;
  completed_at: string | null;
  version: number;
}

export interface EmployeeDashboard {
  onboarding: {
    profile_id: string;
    overall_status: "not_started" | "active" | "completed";
    week_number: number;
    stage: "guided" | "assisted" | "autonomous";
    week_status: string;
    starts_on: string;
    ends_on: string;
  };
  core_value: {
    id: string;
    code: string;
    name: string;
    short_description: string;
  };
  assignment: {
    id: string;
    title: string;
    description: string;
    work_type: string;
    start_date: string;
    due_date: string;
    status: "active" | "completed" | "cancelled";
  } | null;
  actions: DashboardAction[];
  progress: {
    completed_actions: number;
    total_actions: number;
    percentage: number;
  };
  evidence: { id: string; submitted_at: string } | null;
  evidence_card: { id: string; status: string } | null;
  permissions: {
    can_update_actions: boolean;
    can_submit_evidence: boolean;
  };
}

export interface EvidenceLinkInput {
  external_url: string;
  title: string;
  description: string;
}

export interface EvidenceCreateInput {
  assignment_id: string;
  assigned_action_ids: string[];
  performed_action: string;
  discovery: string;
  changed_judgment: string;
  work_impact: string;
  next_action: string;
  links: EvidenceLinkInput[];
}

export interface EvidenceResponse extends EvidenceCreateInput {
  id: string;
  links: Array<EvidenceLinkInput & { id: string }>;
  submitted_at: string;
}

interface ApiFieldError {
  field: string;
  reason: string;
}

interface ApiErrorBody {
  error?: {
    code?: string;
    message?: string;
    field_errors?: ApiFieldError[];
    details?: Record<string, unknown>;
  };
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly fieldErrors: ApiFieldError[];
  readonly details: Record<string, unknown>;

  constructor(status: number, payload: ApiErrorBody) {
    const error = payload.error;
    super(error?.message ?? "요청을 처리하지 못했습니다.");
    this.name = "ApiError";
    this.status = status;
    this.code = error?.code ?? "UNKNOWN_ERROR";
    this.fieldErrors = error?.field_errors ?? [];
    this.details = error?.details ?? {};
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (init.body !== undefined) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(path, {
    ...init,
    credentials: "include",
    headers,
  });
  if (response.status === 204) {
    return undefined as T;
  }

  let payload: unknown = {};
  try {
    payload = await response.json();
  } catch {
    payload = {};
  }
  if (!response.ok) {
    throw new ApiError(response.status, payload as ApiErrorBody);
  }
  return payload as T;
}

export const api = {
  me: () => request<User>("/api/v1/auth/me"),
  csrf: () => request<{ csrf_token: string }>("/api/v1/auth/csrf"),
  login: (email: string, password: string) =>
    request<LoginResponse>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  logout: (csrfToken: string) =>
    request<void>("/api/v1/auth/logout", {
      method: "POST",
      headers: { "X-CSRF-Token": csrfToken },
    }),
  dashboard: () => request<EmployeeDashboard>("/api/v1/employee/dashboard"),
  updateAction: (
    actionId: string,
    status: ActionStatus,
    version: number,
    csrfToken: string,
  ) =>
    request<{ id: string; status: ActionStatus; completed_at: string | null; version: number }>(
      `/api/v1/assigned-actions/${actionId}`,
      {
        method: "PATCH",
        headers: { "X-CSRF-Token": csrfToken },
        body: JSON.stringify({ status, version }),
      },
    ),
  createEvidence: (payload: EvidenceCreateInput, csrfToken: string) =>
    request<EvidenceResponse>("/api/v1/evidence", {
      method: "POST",
      headers: { "X-CSRF-Token": csrfToken },
      body: JSON.stringify(payload),
    }),
};
