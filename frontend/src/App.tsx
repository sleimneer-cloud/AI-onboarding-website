import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  Navigate,
  Route,
  Routes,
  useLocation,
  useNavigate,
  useParams,
} from "react-router-dom";

import {
  ApiError,
  api,
  type DashboardAction,
  type CardContent,
  type EmployeeDashboard,
  type EvidenceCard,
  type EvidenceCreateInput,
  type EvidenceLinkInput,
  type EvidenceResponse,
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
  onSubmitted: (evidence: EvidenceResponse) => Promise<void>;
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
      const evidence = await api.createEvidence(payload, csrfToken);
      await onSubmitted(evidence);
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
  const navigate = useNavigate();
  const [dashboard, setDashboard] = useState<EmployeeDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [pageError, setPageError] = useState<string | null>(null);
  const [busyActionId, setBusyActionId] = useState<string | null>(null);
  const [creatingCard, setCreatingCard] = useState(false);

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
  }, []);

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

  async function openCard(evidenceId: string) {
    setCreatingCard(true);
    setPageError(null);
    try {
      const card = await api.createCard(evidenceId, csrfToken);
      navigate(`/employee/cards/${card.id}`);
    } catch (error) {
      setPageError(errorMessage(error));
      throw error;
    } finally {
      setCreatingCard(false);
    }
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
          <Routes>
            <Route
              index
              element={
                <EmployeeHome
                  dashboard={dashboard}
                  creatingCard={creatingCard}
                  onOpenCard={openCard}
                />
              }
            />
            <Route
              path="assignment"
              element={
                <AssignmentPage
                  dashboard={dashboard}
                  busyActionId={busyActionId}
                  onToggle={toggleAction}
                />
              }
            />
            <Route
              path="evidence/new"
              element={
                <EvidencePage
                  dashboard={dashboard}
                  csrfToken={csrfToken}
                  creatingCard={creatingCard}
                  onOpenCard={openCard}
                />
              }
            />
            <Route
              path="cards/:cardId"
              element={
                <EvidenceCardPage
                  csrfToken={csrfToken}
                  onSessionExpired={onSessionExpired}
                />
              }
            />
            <Route path="report" element={<EmployeeReportPlaceholder />} />
            <Route path="*" element={<Navigate to="/employee" replace />} />
          </Routes>
        )}
      </main>
    </div>
  );
}

function WeekHero({ dashboard }: { dashboard: EmployeeDashboard }) {
  return (
    <section className="week-hero" aria-labelledby="dashboard-title">
      <div className="week-index">
        <span>WEEK</span>
        <strong>{String(dashboard.onboarding.week_number).padStart(2, "0")}</strong>
      </div>
      <div className="week-copy">
        <div className="week-meta">
          <span>{stageLabels[dashboard.onboarding.stage]}</span>
          <span>
            {formatDate(dashboard.onboarding.starts_on)} — {formatDate(dashboard.onboarding.ends_on)}
          </span>
        </div>
        <p className="section-label">THIS WEEK'S CORE VALUE</p>
        <h1 id="dashboard-title">{dashboard.core_value.name}</h1>
        <p>{dashboard.core_value.short_description}</p>
      </div>
      <div
        className="progress-ring"
        style={{ "--progress": `${dashboard.progress.percentage * 3.6}deg` } as React.CSSProperties}
      >
        <div><strong>{dashboard.progress.percentage}%</strong><span>Action 완료</span></div>
      </div>
    </section>
  );
}

function AssignmentSummary({ dashboard }: { dashboard: EmployeeDashboard }) {
  if (!dashboard.assignment) {
    return (
      <section className="empty-state">
        <h2>이번 주에 설정된 대표 업무가 없습니다.</h2>
        <p>업무가 배정되면 핵심가치와 Value Action이 표시됩니다.</p>
      </section>
    );
  }
  return (
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
      <span className="status-pill">
        {dashboard.assignment.status === "active" ? "진행 중" : "완료"}
      </span>
    </section>
  );
}

interface EmployeeHomeProps {
  dashboard: EmployeeDashboard;
  creatingCard: boolean;
  onOpenCard: (evidenceId: string) => Promise<void>;
}

function EmployeeHome({ dashboard, creatingCard, onOpenCard }: EmployeeHomeProps) {
  const navigate = useNavigate();
  let ctaLabel = "이번 주 업무 시작하기";
  let ctaAction = () => navigate("/employee/assignment");

  if (dashboard.progress.completed_actions > 0) {
    ctaLabel = `계속하기 · ${dashboard.progress.completed_actions}/${dashboard.progress.total_actions} 완료`;
  }
  if (dashboard.permissions.can_submit_evidence) {
    ctaLabel = "행동 근거 작성하기";
    ctaAction = () => navigate("/employee/evidence/new");
  }
  if (dashboard.evidence) {
    ctaLabel = creatingCard ? "Evidence Card 생성 중…" : "Evidence Card 확인하기";
    ctaAction = dashboard.evidence_card
      ? () => navigate(`/employee/cards/${dashboard.evidence_card?.id}`)
      : () => void onOpenCard(dashboard.evidence!.id);
  }
  if (
    dashboard.evidence_card?.status === "user_confirmed" ||
    dashboard.evidence_card?.status === "manager_reviewed"
  ) {
    ctaLabel = "가치 리포트 보기";
    ctaAction = () => navigate("/employee/report");
  }

  return (
    <>
      <WeekHero dashboard={dashboard} />
      <AssignmentSummary dashboard={dashboard} />
      {dashboard.assignment ? (
        <section className="evidence-cta home-next-step">
          <div>
            <p className="section-label">NEXT STEP</p>
            <h2>현재 단계에서 이어갈 한 가지 행동</h2>
            <p>상세 입력은 단계별 화면에서 진행하며, 새로고침 후에도 현재 상태가 유지됩니다.</p>
          </div>
          <button
            className="button button-accent"
            type="button"
            onClick={ctaAction}
            disabled={creatingCard}
          >
            {ctaLabel}
          </button>
        </section>
      ) : null}
    </>
  );
}

interface AssignmentPageProps {
  dashboard: EmployeeDashboard;
  busyActionId: string | null;
  onToggle: (action: DashboardAction) => Promise<void>;
}

function AssignmentPage({ dashboard, busyActionId, onToggle }: AssignmentPageProps) {
  const navigate = useNavigate();
  if (!dashboard.assignment) {
    return <AssignmentSummary dashboard={dashboard} />;
  }
  return (
    <>
      <button className="button button-ghost page-back" type="button" onClick={() => navigate("/employee")}>← 이번 주 홈</button>
      <AssignmentSummary dashboard={dashboard} />
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
          onToggle={onToggle}
        />
      </section>
      <section className="evidence-cta">
        <div>
          <p className="section-label">NEXT STEP</p>
          <h2>{dashboard.evidence ? "행동 근거 제출이 완료되었습니다" : dashboard.permissions.can_submit_evidence ? "행동 근거를 남길 차례입니다" : "필수 Action을 먼저 완료해 주세요"}</h2>
          <p>Evidence를 제출한 뒤에는 Action을 변경할 수 없습니다.</p>
        </div>
        <button
          className="button button-accent"
          type="button"
          disabled={!dashboard.permissions.can_submit_evidence}
          onClick={() => navigate("/employee/evidence/new")}
        >
          행동 근거 작성하기
        </button>
      </section>
    </>
  );
}

interface EvidencePageProps extends EmployeeHomeProps {
  csrfToken: string;
}

function EvidencePage({ dashboard, csrfToken, creatingCard, onOpenCard }: EvidencePageProps) {
  const navigate = useNavigate();
  if (!dashboard.assignment) {
    return <AssignmentSummary dashboard={dashboard} />;
  }
  if (dashboard.evidence) {
    return (
      <section className="evidence-complete-card standalone-state">
        <div className="complete-icon">✓</div>
        <div>
          <p className="section-label">EVIDENCE SUBMITTED</p>
          <h1>행동 근거를 제출했습니다</h1>
          <p>{formatDateTime(dashboard.evidence.submitted_at)} 제출 · 다음 단계에서 Evidence Card를 확인합니다.</p>
          <button
            className="button button-accent"
            type="button"
            disabled={creatingCard}
            onClick={() => dashboard.evidence_card
              ? navigate(`/employee/cards/${dashboard.evidence_card.id}`)
              : void onOpenCard(dashboard.evidence!.id)}
          >
            {creatingCard ? "Evidence Card 생성 중…" : "Evidence Card 확인하기"}
          </button>
        </div>
      </section>
    );
  }
  if (!dashboard.permissions.can_submit_evidence) {
    return (
      <section className="empty-state">
        <h1>필수 Action을 먼저 완료해 주세요.</h1>
        <p>업무·Value Action 화면에서 진행 상태를 확인할 수 있습니다.</p>
        <button className="button button-primary" type="button" onClick={() => navigate("/employee/assignment")}>업무·Value Action 보기</button>
      </section>
    );
  }
  return (
    <>
      <button className="button button-ghost page-back" type="button" onClick={() => navigate("/employee/assignment")}>← 업무·Value Action</button>
      <EvidenceForm
        assignmentId={dashboard.assignment.id}
        actions={dashboard.actions}
        csrfToken={csrfToken}
        onSubmitted={(evidence) => onOpenCard(evidence.id)}
        onCancel={() => navigate("/employee/assignment")}
      />
    </>
  );
}

const cardFieldLabels: Array<[Exclude<keyof CardContent, "schema_version" | "key_actions" | "grounding_warnings">, string]> = [
  ["value_connection", "핵심가치와 업무의 연결"],
  ["evidence_summary", "행동 근거 요약"],
  ["discovery", "업무 중 발견"],
  ["judgment_change", "판단 변화"],
  ["work_impact", "업무 영향"],
  ["next_action", "다음 업무에서 이어갈 행동"],
];

interface EvidenceCardPageProps {
  csrfToken: string;
  onSessionExpired: () => void;
}

function EvidenceCardPage({ csrfToken, onSessionExpired }: EvidenceCardPageProps) {
  const { cardId } = useParams();
  const navigate = useNavigate();
  const [card, setCard] = useState<EvidenceCard | null>(null);
  const [draft, setDraft] = useState<CardContent | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [pageError, setPageError] = useState<string | null>(null);

  const loadCard = useCallback(async () => {
    if (!cardId) return;
    try {
      const result = await api.getCard(cardId);
      setCard(result);
      setDraft(result.content ? structuredClone(result.content) : null);
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
  }, [cardId, onSessionExpired]);

  useEffect(() => {
    void loadCard();
  }, [loadCard]);

  useEffect(() => {
    if (card?.status !== "ai_processing") return;
    const timer = window.setTimeout(() => void loadCard(), 1000);
    return () => window.clearTimeout(timer);
  }, [card?.status, loadCard]);

  function updateKeyAction(index: number, text: string) {
    setDraft((current) => current ? {
      ...current,
      key_actions: current.key_actions.map((item, itemIndex) => itemIndex === index ? { ...item, text } : item),
    } : current);
  }

  function updateCardField(key: (typeof cardFieldLabels)[number][0], text: string) {
    setDraft((current) => current ? { ...current, [key]: { ...current[key], text } } : current);
  }

  async function saveDraft(): Promise<EvidenceCard | null> {
    if (!card || !draft) return null;
    const updated = await api.updateCard(card.id, card.version, draft, csrfToken);
    setCard(updated);
    setDraft(updated.content ? structuredClone(updated.content) : null);
    return updated;
  }

  async function handleSave() {
    setBusy(true);
    setPageError(null);
    try {
      await saveDraft();
    } catch (error) {
      setPageError(errorMessage(error));
      if (error instanceof ApiError && error.code === "RESOURCE_VERSION_CONFLICT") {
        await loadCard();
      }
    } finally {
      setBusy(false);
    }
  }

  async function handleConfirm() {
    if (!card || !draft) return;
    setBusy(true);
    setPageError(null);
    try {
      let currentCard = card;
      if (JSON.stringify(draft) !== JSON.stringify(card.content)) {
        currentCard = (await saveDraft()) ?? card;
      }
      const confirmed = await api.confirmCard(currentCard.id, currentCard.version, csrfToken);
      setCard(confirmed);
      setDraft(confirmed.content ? structuredClone(confirmed.content) : null);
    } catch (error) {
      setPageError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  async function handleRetry() {
    if (!card) return;
    setBusy(true);
    setPageError(null);
    try {
      const retried = await api.createCard(card.evidence_id, csrfToken);
      setCard(retried);
      setDraft(retried.content ? structuredClone(retried.content) : null);
    } catch (error) {
      setPageError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <LoadingScreen />;
  if (!card) {
    return (
      <section className="empty-state">
        <h1>Evidence Card를 불러오지 못했습니다.</h1>
        {pageError ? <div className="alert alert-error" role="alert">{pageError}</div> : null}
        <button className="button button-primary" type="button" onClick={() => void loadCard()}>다시 시도</button>
      </section>
    );
  }

  const editable = card.permissions.can_edit && draft !== null;
  const providerLabel = card.generation.provider === "mock"
    ? "데모 대체 생성 · deterministic Mock"
    : card.generation.provider === "groq"
      ? `Groq · ${card.generation.model_name}`
      : "생성 대기";

  return (
    <>
      <button className="button button-ghost page-back" type="button" onClick={() => navigate("/employee")}>← 이번 주 홈</button>
      {pageError ? <div className="alert alert-error" role="alert">{pageError}</div> : null}
      <section className="card-review-header">
        <div>
          <p className="section-label">AI EVIDENCE CARD</p>
          <h1>근거로 정리된 이번 주의 행동</h1>
          <p>AI는 입력한 근거를 구조화하며 직원을 평가하지 않습니다.</p>
        </div>
        <span className={`provider-pill ${card.generation.provider === "mock" ? "is-mock" : ""}`}>{providerLabel}</span>
      </section>

      {card.status === "ai_processing" ? (
        <section className="empty-state"><h2>Evidence Card를 생성하고 있습니다.</h2><p>잠시 후 자동으로 최신 상태를 확인합니다.</p></section>
      ) : card.status === "generation_failed" ? (
        <section className="empty-state">
          <h2>Evidence Card를 생성하지 못했습니다.</h2>
          <p>내부 오류 내용은 노출하지 않습니다. 다시 시도하면 Groq 또는 Mock으로 생성합니다.</p>
          <button className="button button-primary" type="button" disabled={busy} onClick={() => void handleRetry()}>{busy ? "재시도 중…" : "다시 생성하기"}</button>
        </section>
      ) : draft ? (
        <section className="card-editor">
          <div className="card-section">
            <p className="section-label">KEY ACTIONS</p>
            <h2>핵심 행동</h2>
            {draft.key_actions.map((item, index) => (
              <CardTextEditor key={`key-action-${index + 1}`} label={`핵심 행동 ${index + 1}`} text={item.text} sourceRefs={item.source_refs} editable={editable} onChange={(text) => updateKeyAction(index, text)} maxLength={300} />
            ))}
          </div>
          {cardFieldLabels.map(([key, label]) => (
            <div className="card-section" key={key}>
              <CardTextEditor label={label} text={draft[key].text} sourceRefs={draft[key].source_refs} editable={editable} onChange={(text) => updateCardField(key, text)} maxLength={key === "evidence_summary" ? 600 : 500} />
            </div>
          ))}
          {draft.grounding_warnings.length > 0 ? (
            <div className="grounding-warnings">
              <strong>근거 확인 안내</strong>
              {draft.grounding_warnings.map((warning, index) => <p key={`${warning.field}-${index + 1}`}>{warning.message}</p>)}
            </div>
          ) : null}
          <div className="card-actions">
            {editable ? <button className="button button-secondary" type="button" disabled={busy} onClick={() => void handleSave()}>수정 내용 저장</button> : null}
            {card.permissions.can_confirm ? <button className="button button-accent" type="button" disabled={busy} onClick={() => void handleConfirm()}>{busy ? "처리 중…" : "Evidence Card 확정"}</button> : null}
            {card.status === "user_confirmed" ? <div className="confirmation-note">✓ 확정 완료 · 팀장 검토를 기다리고 있습니다.</div> : null}
          </div>
        </section>
      ) : null}
    </>
  );
}

interface CardTextEditorProps {
  label: string;
  text: string;
  sourceRefs: string[];
  editable: boolean;
  onChange: (text: string) => void;
  maxLength: number;
}

function CardTextEditor({ label, text, sourceRefs, editable, onChange, maxLength }: CardTextEditorProps) {
  return (
    <label className="card-text-field">
      <strong>{label}</strong>
      {editable ? <textarea value={text} onChange={(event) => onChange(event.target.value)} maxLength={maxLength} rows={4} /> : <p>{text}</p>}
      <span className="source-ref-list" aria-label={`${label} 근거`}>
        {sourceRefs.map((sourceRef) => <code key={sourceRef}>{sourceRef}</code>)}
      </span>
    </label>
  );
}

function EmployeeReportPlaceholder() {
  const navigate = useNavigate();
  return (
    <section className="empty-state role-placeholder">
      <span className="brand-mark">IX</span>
      <h1>가치 리포트는 팀장 검토 후 완성됩니다</h1>
      <p>Card 확정까지 완료되었습니다. 팀장 피드백과 누적 리포트는 Phase 5에서 연결됩니다.</p>
      <button className="button button-primary" type="button" onClick={() => navigate("/employee")}>이번 주 홈으로</button>
    </section>
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
  const navigate = useNavigate();
  const location = useLocation();
  const [loading, setLoading] = useState(true);
  const [user, setUser] = useState<User | null>(null);
  const [csrfToken, setCsrfToken] = useState<string | null>(null);
  const [authError, setAuthError] = useState<string | null>(null);

  const clearSession = useCallback(() => {
    setUser(null);
    setCsrfToken(null);
    navigate("/login", { replace: true });
  }, [navigate]);

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
        const rolePath = rolePaths[restoredUser.role];
        const pathAllowed =
          location.pathname === rolePath || location.pathname.startsWith(`${rolePath}/`);
        if (!pathAllowed) {
          navigate(rolePath, { replace: true });
        }
      } catch (error) {
        if (!active) return;
        if (!(error instanceof ApiError) || error.status !== 401) {
          setAuthError(errorMessage(error));
        }
        setUser(null);
        setCsrfToken(null);
        if (location.pathname !== "/login") {
          navigate("/login", { replace: true });
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
    navigate(result.default_path);
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
  return (
    <Routes>
      <Route
        path="/employee/*"
        element={user.role === "employee" ? (
          <EmployeePage
            user={user}
            csrfToken={csrfToken}
            onLogout={logout}
            onSessionExpired={clearSession}
          />
        ) : <Navigate to={rolePaths[user.role]} replace />}
      />
      <Route
        path="/manager/*"
        element={user.role === "manager" ? <RolePlaceholder user={user} onLogout={logout} /> : <Navigate to={rolePaths[user.role]} replace />}
      />
      <Route
        path="/hr/*"
        element={user.role === "hr" ? <RolePlaceholder user={user} onLogout={logout} /> : <Navigate to={rolePaths[user.role]} replace />}
      />
      <Route path="*" element={<Navigate to={rolePaths[user.role]} replace />} />
    </Routes>
  );
}
