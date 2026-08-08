import { useCallback, useEffect, useState, type FormEvent } from "react";

import {
  ApiError,
  api,
  type DashboardAction,
  type EmployeeDashboard,
  type EvidenceCreateInput,
  type EvidenceLinkInput,
  type User,
} from "./api";

const rolePaths = {
  employee: "/employee",
  manager: "/manager",
  hr: "/hr",
} as const;

const stageLabels = {
  guided: "가이드형",
  assisted: "선택·수정형",
  autonomous: "자율 설계형",
} as const;

const fieldDefinitions = [
  {
    key: "performed_action",
    label: "실제로 수행한 행동",
    hint: "누구와 무엇을 확인했고, 어떤 행동을 했는지 적어주세요.",
  },
  {
    key: "discovery",
    label: "업무 중 발견한 내용",
    hint: "처음에는 알지 못했지만 업무를 통해 확인한 내용을 적어주세요.",
  },
  {
    key: "changed_judgment",
    label: "변경된 판단",
    hint: "조사 전후의 생각이나 접근 방식이 어떻게 달라졌나요?",
  },
  {
    key: "work_impact",
    label: "업무에 미친 영향",
    hint: "등록된 근거로 확인할 수 있는 범위에서만 적어주세요.",
  },
  {
    key: "next_action",
    label: "다음 업무에서 이어갈 행동",
    hint: "다음에도 반복하고 싶은 구체적인 행동을 적어주세요.",
  },
] as const;

type EvidenceTextKey = (typeof fieldDefinitions)[number]["key"];
type EvidenceTextValues = Record<EvidenceTextKey, string>;

const emptyEvidenceText: EvidenceTextValues = {
  performed_action: "",
  discovery: "",
  changed_judgment: "",
  work_impact: "",
  next_action: "",
};

function navigate(path: string, setPath: (path: string) => void) {
  if (window.location.pathname !== path) {
    window.history.pushState({}, "", path);
  }
  setPath(path);
}

function formatDate(value: string) {
  return value.replaceAll("-", ".");
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("ko-KR", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function errorMessage(error: unknown) {
  if (error instanceof ApiError) {
    if (error.code === "RESOURCE_VERSION_CONFLICT") {
      return "다른 화면에서 변경된 내용이 있습니다. 최신 상태를 불러왔습니다.";
    }
    return error.message;
  }
  return "요청을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.";
}

function LoadingScreen() {
  return (
    <main className="loading-screen" aria-live="polite">
      <span className="brand-mark">IX</span>
      <div className="loading-dot" />
      <p>온보딩 정보를 불러오고 있습니다.</p>
    </main>
  );
}

interface LoginPageProps {
  initialError: string | null;
  onLogin: (email: string, password: string) => Promise<void>;
}

function LoginPage({ initialError, onLogin }: LoginPageProps) {
  const [email, setEmail] = useState("employee@ix-demo.test");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(initialError);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!email.trim() || !password) {
      setFormError("이메일과 비밀번호를 모두 입력해 주세요.");
      return;
    }
    setSubmitting(true);
    setFormError(null);
    try {
      await onLogin(email, password);
    } catch (error) {
      setFormError(errorMessage(error));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="login-layout">
      <section className="login-story" aria-labelledby="login-title">
        <div>
          <span className="brand-mark brand-mark-light">IX</span>
          <p className="eyebrow">INTERX ONBOARDING</p>
        </div>
        <div className="login-message">
          <p className="story-kicker">일하면서 배우고, 근거로 성장합니다.</p>
          <h1 id="login-title">IX Value Loop</h1>
          <p>
            이번 주 핵심가치를 실제 업무의 행동으로 연결하고, 발견과 판단 변화를
            차곡차곡 기록하세요.
          </p>
        </div>
        <ol className="loop-steps" aria-label="Value Loop 단계">
          <li><span>01</span> 가치</li>
          <li><span>02</span> 행동</li>
          <li><span>03</span> 근거</li>
          <li><span>04</span> 피드백</li>
        </ol>
      </section>

      <section className="login-panel" aria-label="로그인">
        <div className="login-card">
          <p className="section-label">WELCOME BACK</p>
          <h2>온보딩을 이어가세요</h2>
          <p className="muted">데모 계정으로 이번 주 Value Loop를 확인할 수 있습니다.</p>

          {formError ? <div className="alert alert-error" role="alert">{formError}</div> : null}

          <form onSubmit={handleSubmit} className="login-form">
            <label>
              이메일
              <input
                type="email"
                name="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                autoComplete="username"
                disabled={submitting}
              />
            </label>
            <label>
              비밀번호
              <input
                type="password"
                name="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete="current-password"
                placeholder="데모 비밀번호 입력"
                disabled={submitting}
              />
            </label>
            <button className="button button-primary button-wide" type="submit" disabled={submitting}>
              {submitting ? "로그인 중…" : "로그인"}
            </button>
          </form>

          <div className="demo-accounts">
            <p>허구 데모 계정</p>
            <button type="button" onClick={() => setEmail("employee@ix-demo.test")}>직원</button>
            <button type="button" onClick={() => setEmail("manager@ix-demo.test")}>팀장</button>
            <button type="button" onClick={() => setEmail("hr@ix-demo.test")}>인사팀</button>
          </div>
        </div>
      </section>
    </main>
  );
}

interface AppHeaderProps {
  user: User;
  onLogout: () => Promise<void>;
}

function AppHeader({ user, onLogout }: AppHeaderProps) {
  const [loggingOut, setLoggingOut] = useState(false);
  const roleLabel = { employee: "신규 입사자", manager: "팀장", hr: "인사팀" }[user.role];

  async function handleLogout() {
    setLoggingOut(true);
    try {
      await onLogout();
    } finally {
      setLoggingOut(false);
    }
  }

  return (
    <header className="app-header">
      <div className="header-brand">
        <span className="brand-mark">IX</span>
        <div><strong>Value Loop</strong><span>Employee onboarding</span></div>
      </div>
      <div className="user-menu">
        <span className="avatar" aria-hidden="true">{user.name.slice(0, 1)}</span>
        <div><strong>{user.name}</strong><span>{roleLabel}</span></div>
        <button className="button button-ghost" type="button" onClick={handleLogout} disabled={loggingOut}>
          {loggingOut ? "종료 중…" : "로그아웃"}
        </button>
      </div>
    </header>
  );
}

interface ActionListProps {
  actions: DashboardAction[];
  canUpdate: boolean;
  busyActionId: string | null;
  onToggle: (action: DashboardAction) => Promise<void>;
}

function ActionList({ actions, canUpdate, busyActionId, onToggle }: ActionListProps) {
  return (
    <div className="action-list">
      {actions.map((action) => {
        const completed = action.status === "completed";
        return (
          <label className={`action-item ${completed ? "is-complete" : ""}`} key={action.id}>
            <input
              type="checkbox"
              checked={completed}
              disabled={!canUpdate || busyActionId !== null}
              onChange={() => void onToggle(action)}
              aria-label={`${action.text} 완료`}
            />
            <span className="custom-check" aria-hidden="true">{completed ? "✓" : ""}</span>
            <span className="action-copy">
              <span className="action-number">ACTION {String(action.display_order).padStart(2, "0")}</span>
              <strong>{action.text}</strong>
              <span>{action.completion_criteria}</span>
              {action.recommended_evidence.length > 0 ? (
                <span className="evidence-hint">권장 근거 · {action.recommended_evidence.join(" · ")}</span>
              ) : null}
            </span>
            <span className="action-state">{busyActionId === action.id ? "저장 중" : completed ? "완료" : "진행 전"}</span>
          </label>
        );
      })}
    </div>
  );
}

interface EvidenceFormProps {
  assignmentId: string;
  actions: DashboardAction[];
  csrfToken: string;
  onSubmitted: () => Promise<void>;
  onCancel: () => void;
}

function EvidenceForm({ assignmentId, actions, csrfToken, onSubmitted, onCancel }: EvidenceFormProps) {
  const completedActions = actions.filter((action) => action.status === "completed");
  const [selectedActionIds, setSelectedActionIds] = useState(
    completedActions.map((action) => action.id),
  );
  const [values, setValues] = useState<EvidenceTextValues>(emptyEvidenceText);
  const [links, setLinks] = useState<EvidenceLinkInput[]>([]);
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function updateText(key: EvidenceTextKey, value: string) {
    setValues((current) => ({ ...current, [key]: value }));
  }

  function toggleAction(actionId: string) {
    setSelectedActionIds((current) =>
      current.includes(actionId)
        ? current.filter((candidate) => candidate !== actionId)
        : [...current, actionId],
    );
  }

  function addLink() {
    if (links.length < 3) {
      setLinks((current) => [...current, { external_url: "", title: "", description: "" }]);
    }
  }

  function updateLink(index: number, key: keyof EvidenceLinkInput, value: string) {
    setLinks((current) =>
      current.map((link, linkIndex) => linkIndex === index ? { ...link, [key]: value } : link),
    );
  }

  function removeLink(index: number) {
    setLinks((current) => current.filter((_, linkIndex) => linkIndex !== index));
  }

  function validate(): string | null {
    if (selectedActionIds.length === 0) {
      return "근거로 연결할 완료 Action을 하나 이상 선택해 주세요.";
    }
    const incompleteField = fieldDefinitions.find(({ key }) => values[key].trim().length < 10);
    if (incompleteField) {
      return `${incompleteField.label}을 10자 이상 입력해 주세요.`;
    }
    for (const link of links) {
      if (!link.external_url.trim() || !link.title.trim() || !link.description.trim()) {
        return "추가한 링크의 주소, 제목, 설명을 모두 입력해 주세요.";
      }
      try {
        const parsed = new URL(link.external_url);
        if (!(["http:", "https:"] as string[]).includes(parsed.protocol)) {
          return "링크는 HTTP 또는 HTTPS 주소만 사용할 수 있습니다.";
        }
      } catch {
        return "올바른 링크 주소를 입력해 주세요.";
      }
    }
    return null;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const validationError = validate();
    if (validationError) {
      setFormError(validationError);
      return;
    }
    const payload: EvidenceCreateInput = {
      assignment_id: assignmentId,
      assigned_action_ids: selectedActionIds,
      ...Object.fromEntries(
        Object.entries(values).map(([key, value]) => [key, value.trim()]),
      ) as EvidenceTextValues,
      links: links.map((link) => ({
        external_url: link.external_url.trim(),
        title: link.title.trim(),
        description: link.description.trim(),
      })),
    };

    setSubmitting(true);
    setFormError(null);
    try {
      await api.createEvidence(payload, csrfToken);
      await onSubmitted();
    } catch (error) {
      setFormError(errorMessage(error));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="evidence-form-card" aria-labelledby="evidence-form-title">
      <div className="section-heading">
        <div>
          <p className="section-label">BEHAVIOR EVIDENCE</p>
          <h2 id="evidence-form-title">이번 업무의 행동 근거</h2>
          <p>별도 보고서가 아니라 실제 업무에서 확인한 사실과 판단 변화를 기록합니다.</p>
        </div>
        <button className="button button-ghost" type="button" onClick={onCancel}>닫기</button>
      </div>

      {formError ? <div className="alert alert-error" role="alert">{formError}</div> : null}

      <form onSubmit={handleSubmit} className="evidence-form">
        <fieldset>
          <legend>근거로 연결할 완료 Action</legend>
          <div className="selected-actions">
            {completedActions.map((action) => (
              <label key={action.id}>
                <input
                  type="checkbox"
                  checked={selectedActionIds.includes(action.id)}
                  onChange={() => toggleAction(action.id)}
                />
                <span>{action.text}</span>
              </label>
            ))}
          </div>
        </fieldset>

        <div className="form-grid">
          {fieldDefinitions.map((field) => (
            <label className={field.key === "performed_action" ? "form-field form-field-wide" : "form-field"} key={field.key}>
              <span>{field.label}</span>
              <small>{field.hint}</small>
              <textarea
                value={values[field.key]}
                onChange={(event) => updateText(field.key, event.target.value)}
                maxLength={field.key === "next_action" ? 1000 : 2000}
                rows={4}
                disabled={submitting}
              />
              <small className="char-count">{values[field.key].length}자</small>
            </label>
          ))}
        </div>

        <fieldset className="link-fieldset">
          <div className="fieldset-heading">
            <div><legend>관련 업무 링크</legend><p>링크 내용은 가져오지 않으며 입력한 제목과 설명만 저장합니다.</p></div>
            <button className="button button-secondary" type="button" onClick={addLink} disabled={links.length >= 3 || submitting}>
              링크 추가 {links.length}/3
            </button>
          </div>
          {links.map((link, index) => (
            <div className="link-row" key={`link-${index + 1}`}>
              <input
                aria-label={`링크 ${index + 1} 주소`}
                type="url"
                placeholder="https://example.test/document"
                value={link.external_url}
                onChange={(event) => updateLink(index, "external_url", event.target.value)}
              />
              <input
                aria-label={`링크 ${index + 1} 제목`}
                placeholder="문서 제목"
                value={link.title}
                onChange={(event) => updateLink(index, "title", event.target.value)}
              />
              <textarea
                aria-label={`링크 ${index + 1} 설명`}
                placeholder="이 링크가 어떤 근거인지 직접 설명해 주세요."
                value={link.description}
                onChange={(event) => updateLink(index, "description", event.target.value)}
                rows={2}
              />
              <button className="remove-link" type="button" onClick={() => removeLink(index)} aria-label={`링크 ${index + 1} 삭제`}>×</button>
            </div>
          ))}
        </fieldset>

        <div className="form-actions">
          <p>제출 후에는 Action과 Evidence를 수정할 수 없습니다.</p>
          <button className="button button-primary" type="submit" disabled={submitting}>
            {submitting ? "제출 중…" : "행동 근거 제출"}
          </button>
        </div>
      </form>
    </section>
  );
}

interface EmployeePageProps {
  user: User;
  csrfToken: string;
  onLogout: () => Promise<void>;
  onSessionExpired: () => void;
}

function EmployeePage({ user, csrfToken, onLogout, onSessionExpired }: EmployeePageProps) {
  const [dashboard, setDashboard] = useState<EmployeeDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [pageError, setPageError] = useState<string | null>(null);
  const [busyActionId, setBusyActionId] = useState<string | null>(null);
  const [showEvidenceForm, setShowEvidenceForm] = useState(false);

  const loadDashboard = useCallback(async () => {
    try {
      const result = await api.dashboard();
      setDashboard(result);
      setPageError(null);
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        onSessionExpired();
        return;
      }
      setPageError(errorMessage(error));
    } finally {
      setLoading(false);
    }
  }, [onSessionExpired]);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

  async function toggleAction(action: DashboardAction) {
    setBusyActionId(action.id);
    setPageError(null);
    try {
      await api.updateAction(
        action.id,
        action.status === "completed" ? "pending" : "completed",
        action.version,
        csrfToken,
      );
      await loadDashboard();
    } catch (error) {
      setPageError(errorMessage(error));
      if (error instanceof ApiError && error.code === "RESOURCE_VERSION_CONFLICT") {
        await loadDashboard();
      }
    } finally {
      setBusyActionId(null);
    }
  }

  async function evidenceSubmitted() {
    setShowEvidenceForm(false);
    await loadDashboard();
  }

  if (loading) {
    return <LoadingScreen />;
  }

  return (
    <div className="app-frame">
      <AppHeader user={user} onLogout={onLogout} />
      <main className="dashboard-shell">
        {pageError ? <div className="alert alert-error" role="alert">{pageError}</div> : null}

        {!dashboard ? (
          <section className="empty-state">
            <h1>주간 정보를 불러오지 못했습니다.</h1>
            <p>연결 상태를 확인한 뒤 다시 시도해 주세요.</p>
            <button className="button button-primary" type="button" onClick={() => void loadDashboard()}>다시 시도</button>
          </section>
        ) : (
          <>
            <section className="week-hero" aria-labelledby="dashboard-title">
              <div className="week-index">
                <span>WEEK</span>
                <strong>{String(dashboard.onboarding.week_number).padStart(2, "0")}</strong>
              </div>
              <div className="week-copy">
                <div className="week-meta">
                  <span>{stageLabels[dashboard.onboarding.stage]}</span>
                  <span>{formatDate(dashboard.onboarding.starts_on)} — {formatDate(dashboard.onboarding.ends_on)}</span>
                </div>
                <p className="section-label">THIS WEEK'S CORE VALUE</p>
                <h1 id="dashboard-title">{dashboard.core_value.name}</h1>
                <p>{dashboard.core_value.short_description}</p>
              </div>
              <div className="progress-ring" style={{ "--progress": `${dashboard.progress.percentage * 3.6}deg` } as React.CSSProperties}>
                <div><strong>{dashboard.progress.percentage}%</strong><span>Action 완료</span></div>
              </div>
            </section>

            {dashboard.assignment ? (
              <>
                <section className="assignment-card" aria-labelledby="assignment-title">
                  <div className="assignment-number">01</div>
                  <div className="assignment-copy">
                    <p className="section-label">PRIMARY ASSIGNMENT</p>
                    <h2 id="assignment-title">{dashboard.assignment.title}</h2>
                    <p>{dashboard.assignment.description}</p>
                    <div className="assignment-meta">
                      <span>업무 유형 · {dashboard.assignment.work_type.replaceAll("_", " ")}</span>
                      <span>마감 · {formatDate(dashboard.assignment.due_date)}</span>
                    </div>
                  </div>
                  <span className="status-pill">{dashboard.assignment.status === "active" ? "진행 중" : "완료"}</span>
                </section>

                <section className="content-section" aria-labelledby="actions-title">
                  <div className="section-heading">
                    <div>
                      <p className="section-label">VALUE ACTIONS</p>
                      <h2 id="actions-title">가치를 행동으로 옮겨보세요</h2>
                      <p>업무 중 의식해야 할 행동을 완료하면 체크하세요.</p>
                    </div>
                    <div className="progress-summary"><strong>{dashboard.progress.completed_actions}</strong><span>/ {dashboard.progress.total_actions} 완료</span></div>
                  </div>
                  <ActionList
                    actions={dashboard.actions}
                    canUpdate={dashboard.permissions.can_update_actions}
                    busyActionId={busyActionId}
                    onToggle={toggleAction}
                  />
                </section>

                {dashboard.evidence ? (
                  <section className="evidence-complete-card">
                    <div className="complete-icon">✓</div>
                    <div>
                      <p className="section-label">EVIDENCE SUBMITTED</p>
                      <h2>행동 근거를 제출했습니다</h2>
                      <p>{formatDateTime(dashboard.evidence.submitted_at)} 제출 · 다음 단계에서 Evidence Card를 생성합니다.</p>
                    </div>
                  </section>
                ) : showEvidenceForm ? (
                  <EvidenceForm
                    assignmentId={dashboard.assignment.id}
                    actions={dashboard.actions}
                    csrfToken={csrfToken}
                    onSubmitted={evidenceSubmitted}
                    onCancel={() => setShowEvidenceForm(false)}
                  />
                ) : (
                  <section className="evidence-cta">
                    <div>
                      <p className="section-label">NEXT STEP</p>
                      <h2>{dashboard.permissions.can_submit_evidence ? "행동의 근거를 남길 차례입니다" : "필수 Action을 먼저 완료해 주세요"}</h2>
                      <p>{dashboard.permissions.can_submit_evidence ? "실제 업무에서 확인한 발견과 판단 변화를 기록하세요." : "모든 필수 Action이 완료되면 행동 근거를 제출할 수 있습니다."}</p>
                    </div>
                    <button
                      className="button button-accent"
                      type="button"
                      disabled={!dashboard.permissions.can_submit_evidence}
                      onClick={() => setShowEvidenceForm(true)}
                    >
                      행동 근거 등록
                    </button>
                  </section>
                )}
              </>
            ) : (
              <section className="empty-state">
                <h2>이번 주에 설정된 대표 업무가 없습니다.</h2>
                <p>업무가 배정되면 핵심가치와 Value Action이 이곳에 표시됩니다.</p>
              </section>
            )}
          </>
        )}
      </main>
    </div>
  );
}

interface RolePlaceholderProps {
  user: User;
  onLogout: () => Promise<void>;
}

function RolePlaceholder({ user, onLogout }: RolePlaceholderProps) {
  return (
    <div className="app-frame">
      <AppHeader user={user} onLogout={onLogout} />
      <main className="dashboard-shell">
        <section className="empty-state role-placeholder">
          <span className="brand-mark">IX</span>
          <h1>{user.role === "manager" ? "팀장 검토 화면" : "인사팀 조회 화면"}</h1>
          <p>로그인과 권한 확인이 완료되었습니다. 이 역할의 업무 화면은 다음 Phase에서 연결됩니다.</p>
        </section>
      </main>
    </div>
  );
}

export default function App() {
  const [path, setPath] = useState(window.location.pathname);
  const [loading, setLoading] = useState(true);
  const [user, setUser] = useState<User | null>(null);
  const [csrfToken, setCsrfToken] = useState<string | null>(null);
  const [authError, setAuthError] = useState<string | null>(null);

  const clearSession = useCallback(() => {
    setUser(null);
    setCsrfToken(null);
    navigate("/login", setPath);
  }, []);

  useEffect(() => {
    function handlePopState() {
      setPath(window.location.pathname);
    }
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  useEffect(() => {
    let active = true;
    async function restoreSession() {
      try {
        const restoredUser = await api.me();
        const csrf = await api.csrf();
        if (!active) return;
        setUser(restoredUser);
        setCsrfToken(csrf.csrf_token);
        setAuthError(null);
        if (path === "/" || path === "/login" || path !== rolePaths[restoredUser.role]) {
          navigate(rolePaths[restoredUser.role], setPath);
        }
      } catch (error) {
        if (!active) return;
        if (!(error instanceof ApiError) || error.status !== 401) {
          setAuthError(errorMessage(error));
        }
        setUser(null);
        setCsrfToken(null);
        if (path !== "/" && path !== "/login") {
          navigate("/login", setPath);
        }
      } finally {
        if (active) setLoading(false);
      }
    }
    void restoreSession();
    return () => {
      active = false;
    };
  }, []);

  async function login(email: string, password: string) {
    const result = await api.login(email, password);
    setUser(result.user);
    setCsrfToken(result.csrf_token);
    setAuthError(null);
    navigate(result.default_path, setPath);
  }

  async function logout() {
    if (csrfToken) {
      await api.logout(csrfToken);
    }
    clearSession();
  }

  if (loading) {
    return <LoadingScreen />;
  }
  if (!user || !csrfToken) {
    return <LoginPage initialError={authError} onLogin={login} />;
  }
  if (user.role === "employee") {
    return (
      <EmployeePage
        user={user}
        csrfToken={csrfToken}
        onLogout={logout}
        onSessionExpired={clearSession}
      />
    );
  }
  return <RolePlaceholder user={user} onLogout={logout} />;
}
