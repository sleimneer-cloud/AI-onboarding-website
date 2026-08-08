import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { BrowserRouter } from "react-router-dom";

import App from "./App";
import type { EmployeeDashboard } from "./api";

const employee = {
  id: "00000000-0000-4000-8000-000000000001",
  name: "김가온",
  email: "employee@ix-demo.test",
  role: "employee" as const,
};

const actionId = "00000000-0000-4000-8000-000000000101";
const assignmentId = "00000000-0000-4000-8000-000000000201";
const evidenceId = "00000000-0000-4000-8000-000000000501";
const cardId = "00000000-0000-4000-8000-000000000601";

function dashboard(overrides: Partial<EmployeeDashboard> = {}): EmployeeDashboard {
  return {
    onboarding: {
      profile_id: "00000000-0000-4000-8000-000000000301",
      overall_status: "active",
      week_number: 2,
      stage: "guided",
      week_status: "ready",
      starts_on: "2026-07-27",
      ends_on: "2026-08-02",
    },
    core_value: {
      id: "00000000-0000-4000-8000-000000000401",
      code: "obsessive_curiosity",
      name: "강박적 호기심",
      short_description: "질문과 검증으로 문제의 본질을 탐색합니다.",
    },
    assignment: {
      id: assignmentId,
      title: "반복적인 HR 문의 분석 및 자동화 프로토타입 구축",
      description: "반복 문의의 원인을 확인하고 단일 문의 진입점을 만듭니다.",
      work_type: "prototype_build",
      start_date: "2026-07-27",
      due_date: "2026-08-02",
      status: "active",
    },
    actions: [
      {
        id: actionId,
        text: "처음 가설과 조사 후 판단이 어떻게 달라졌는지 기록한다.",
        completion_criteria: "조사 전후의 판단 변화가 기록되어 있다.",
        recommended_evidence: ["변경된 기능 정의서"],
        is_required: true,
        display_order: 1,
        status: "pending",
        completed_at: null,
        version: 1,
      },
    ],
    progress: { completed_actions: 0, total_actions: 1, percentage: 0 },
    evidence: null,
    evidence_card: null,
    permissions: { can_update_actions: true, can_submit_evidence: false },
    ...overrides,
  };
}

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function authError() {
  return jsonResponse(
    {
      error: {
        code: "AUTH_REQUIRED",
        message: "로그인이 필요합니다.",
        field_errors: [],
        details: {},
        request_id: "request-id",
      },
    },
    401,
  );
}

function cardResponse(overrides: Record<string, unknown> = {}) {
  return {
    id: cardId,
    evidence_id: evidenceId,
    status: "user_review",
    content: {
      schema_version: "1.0",
      key_actions: [
        { text: "담당자를 인터뷰했습니다.", source_refs: ["evidence.performed_action"] },
      ],
      value_connection: {
        text: "공식 가치 정의와 기록한 행동을 함께 확인했습니다.",
        source_refs: ["core_value.definition", "evidence.performed_action"],
      },
      evidence_summary: {
        text: "인터뷰 기록을 근거로 사용했습니다.",
        source_refs: ["evidence.performed_action"],
      },
      discovery: { text: "문의 경로가 분산되어 있었습니다.", source_refs: ["evidence.discovery"] },
      judgment_change: {
        text: "단일 문의 진입점을 우선하기로 했습니다.",
        source_refs: ["evidence.changed_judgment"],
      },
      work_impact: { text: "프로토타입 범위를 줄였습니다.", source_refs: ["evidence.work_impact"] },
      next_action: {
        text: "다음에도 사용자 흐름을 먼저 확인합니다.",
        source_refs: ["evidence.next_action"],
      },
      grounding_warnings: [],
    },
    generation: {
      provider: "mock",
      model_name: null,
      prompt_version: "v1",
      schema_version: "1.0",
      latency_ms: 2,
    },
    version: 1,
    confirmed_at: null,
    manager_reviewed_at: null,
    permissions: { can_edit: true, can_confirm: true, can_retry: false },
    ...overrides,
  };
}

function renderApp() {
  return render(
    <BrowserRouter>
      <App />
    </BrowserRouter>,
  );
}

beforeEach(() => {
  window.history.replaceState({}, "", "/");
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("IX Value Loop employee flow", () => {
  it("shows the login form when no server session exists", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(authError()));

    renderApp();

    expect(await screen.findByRole("heading", { name: "IX Value Loop" })).toBeVisible();
    expect(screen.getByLabelText("이메일")).toHaveValue("employee@ix-demo.test");
    expect(screen.getByRole("button", { name: "로그인" })).toBeVisible();
  });

  it("logs an employee in and follows the server-selected default path", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(authError())
      .mockResolvedValueOnce(
        jsonResponse({
          user: employee,
          csrf_token: "csrf-token",
          expires_at: "2026-08-02T12:00:00Z",
          default_path: "/employee",
        }),
      )
      .mockResolvedValueOnce(jsonResponse(dashboard()));
    vi.stubGlobal("fetch", fetchMock);

    renderApp();

    fireEvent.change(await screen.findByLabelText("비밀번호"), {
      target: { value: "DemoPassword!" },
    });
    fireEvent.click(screen.getByRole("button", { name: "로그인" }));

    expect(await screen.findByRole("heading", { name: "강박적 호기심" })).toBeVisible();
    expect(window.location.pathname).toBe("/employee");
    const loginRequest = fetchMock.mock.calls[1];
    expect(loginRequest[0]).toBe("/api/v1/auth/login");
    expect(loginRequest[1]).toMatchObject({ method: "POST", credentials: "include" });
  });

  it("restores the employee session and updates an Action", async () => {
    const completedDashboard = dashboard({
      onboarding: { ...dashboard().onboarding, week_status: "in_progress" },
      actions: [
        {
          ...dashboard().actions[0],
          status: "completed",
          completed_at: "2026-08-02T04:00:00Z",
          version: 2,
        },
      ],
      progress: { completed_actions: 1, total_actions: 1, percentage: 100 },
      permissions: { can_update_actions: true, can_submit_evidence: true },
    });
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(employee))
      .mockResolvedValueOnce(jsonResponse({ csrf_token: "csrf-token" }))
      .mockResolvedValueOnce(jsonResponse(dashboard()))
      .mockResolvedValueOnce(
        jsonResponse({
          id: actionId,
          status: "completed",
          completed_at: "2026-08-02T04:00:00Z",
          version: 2,
        }),
      )
      .mockResolvedValueOnce(jsonResponse(completedDashboard));
    vi.stubGlobal("fetch", fetchMock);

    renderApp();

    expect(await screen.findByRole("heading", { name: "강박적 호기심" })).toBeVisible();
    expect(screen.getByText("0%")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "이번 주 업무 시작하기" }));

    fireEvent.click(
      screen.getByLabelText("처음 가설과 조사 후 판단이 어떻게 달라졌는지 기록한다. 완료"),
    );

    await waitFor(() =>
      expect(
        screen.getByLabelText(
          "처음 가설과 조사 후 판단이 어떻게 달라졌는지 기록한다. 완료",
        ),
      ).toBeChecked(),
    );
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(5));
    const updateRequest = fetchMock.mock.calls[3];
    expect(updateRequest[0]).toBe(`/api/v1/assigned-actions/${actionId}`);
    expect(updateRequest[1]).toMatchObject({ method: "PATCH", credentials: "include" });
  });

  it("submits the Evidence form after all required Actions are complete", async () => {
    const readyDashboard = dashboard({
      onboarding: { ...dashboard().onboarding, week_status: "in_progress" },
      actions: [
        {
          ...dashboard().actions[0],
          status: "completed",
          completed_at: "2026-08-02T04:00:00Z",
          version: 2,
        },
      ],
      progress: { completed_actions: 1, total_actions: 1, percentage: 100 },
      permissions: { can_update_actions: true, can_submit_evidence: true },
    });
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(employee))
      .mockResolvedValueOnce(jsonResponse({ csrf_token: "csrf-token" }))
      .mockResolvedValueOnce(jsonResponse(readyDashboard))
      .mockResolvedValueOnce(
        jsonResponse(
          {
            id: evidenceId,
            assignment_id: assignmentId,
            assigned_action_ids: [actionId],
            performed_action: "담당자 인터뷰를 진행하고 흐름을 정리했습니다.",
            discovery: "문의 진입 경로가 여러 곳으로 나뉘어 있었습니다.",
            changed_judgment: "FAQ보다 단일 진입점을 먼저 만들기로 했습니다.",
            work_impact: "프로토타입의 범위를 핵심 흐름으로 줄였습니다.",
            next_action: "다음 업무에서도 사용자 흐름을 먼저 확인합니다.",
            links: [],
            submitted_at: "2026-08-02T05:00:00Z",
          },
          201,
        ),
      )
      .mockResolvedValueOnce(jsonResponse(cardResponse(), 201))
      .mockResolvedValueOnce(jsonResponse(cardResponse()));
    vi.stubGlobal("fetch", fetchMock);

    renderApp();

    fireEvent.click(await screen.findByRole("button", { name: "행동 근거 작성하기" }));
    const inputText = "담당자 인터뷰를 진행하고 실제 업무 흐름을 확인했습니다.";
    fireEvent.change(screen.getByLabelText(/실제로 수행한 행동/), {
      target: { value: inputText },
    });
    fireEvent.change(screen.getByLabelText(/업무 중 발견한 내용/), {
      target: { value: "문의 진입 경로가 여러 곳으로 나뉘어 있었습니다." },
    });
    fireEvent.change(screen.getByLabelText(/변경된 판단/), {
      target: { value: "FAQ보다 단일 진입점을 먼저 만들기로 했습니다." },
    });
    fireEvent.change(screen.getByLabelText(/업무에 미친 영향/), {
      target: { value: "프로토타입의 범위를 핵심 흐름으로 줄였습니다." },
    });
    fireEvent.change(screen.getByLabelText(/다음 업무에서 이어갈 행동/), {
      target: { value: "다음 업무에서도 사용자 흐름을 먼저 확인합니다." },
    });
    fireEvent.click(screen.getByRole("button", { name: "행동 근거 제출" }));

    expect(await screen.findByRole("heading", { name: "근거로 정리된 이번 주의 행동" })).toBeVisible();
    expect(window.location.pathname).toBe(`/employee/cards/${cardId}`);
    const createRequest = fetchMock.mock.calls[3];
    expect(createRequest[0]).toBe("/api/v1/evidence");
    const requestBody = JSON.parse((createRequest[1] as RequestInit).body as string);
    expect(requestBody.assigned_action_ids).toEqual([actionId]);
    expect(requestBody.performed_action).toBe(inputText);
    expect(fetchMock.mock.calls[4][0]).toBe(`/api/v1/evidence/${evidenceId}/card`);
  });

  it("restores a direct employee assignment route without redirecting home", async () => {
    window.history.replaceState({}, "", "/employee/assignment");
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(employee))
      .mockResolvedValueOnce(jsonResponse({ csrf_token: "csrf-token" }))
      .mockResolvedValueOnce(jsonResponse(dashboard()));
    vi.stubGlobal("fetch", fetchMock);

    renderApp();

    expect(await screen.findByRole("heading", { name: "가치를 행동으로 옮겨보세요" })).toBeVisible();
    expect(window.location.pathname).toBe("/employee/assignment");
  });

  it("redirects an authenticated manager away from employee routes", async () => {
    window.history.replaceState({}, "", "/employee/assignment");
    const manager = { ...employee, role: "manager" as const, name: "박도윤" };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(manager))
      .mockResolvedValueOnce(jsonResponse({ csrf_token: "csrf-token" }));
    vi.stubGlobal("fetch", fetchMock);

    renderApp();

    expect(await screen.findByRole("heading", { name: "팀장 검토 화면" })).toBeVisible();
    expect(window.location.pathname).toBe("/manager");
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("edits and confirms an Evidence Card while keeping source references read-only", async () => {
    window.history.replaceState({}, "", `/employee/cards/${cardId}`);
    const initialCard = cardResponse();
    const editedContent = structuredClone(initialCard.content as Record<string, unknown>) as {
      next_action: { text: string; source_refs: string[] };
    } & Record<string, unknown>;
    editedContent.next_action.text = "다음 업무에서는 사용자 흐름을 먼저 문서로 정리합니다.";
    const updatedCard = cardResponse({ content: editedContent, version: 2 });
    const confirmedCard = cardResponse({
      content: editedContent,
      version: 3,
      status: "user_confirmed",
      confirmed_at: "2026-08-02T06:00:00Z",
      permissions: { can_edit: false, can_confirm: false, can_retry: false },
    });
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(employee))
      .mockResolvedValueOnce(jsonResponse({ csrf_token: "csrf-token" }))
      .mockResolvedValueOnce(jsonResponse(dashboard()))
      .mockResolvedValueOnce(jsonResponse(initialCard))
      .mockResolvedValueOnce(jsonResponse(updatedCard))
      .mockResolvedValueOnce(jsonResponse(confirmedCard));
    vi.stubGlobal("fetch", fetchMock);

    renderApp();

    expect(await screen.findByText("데모 대체 생성 · deterministic Mock")).toBeVisible();
    expect(screen.getByText("evidence.next_action")).toBeVisible();
    const nextAction = screen.getByDisplayValue("다음에도 사용자 흐름을 먼저 확인합니다.");
    fireEvent.change(nextAction, { target: { value: editedContent.next_action.text } });
    fireEvent.click(screen.getByRole("button", { name: "Evidence Card 확정" }));

    expect(await screen.findByText(/확정 완료/)).toBeVisible();
    expect(fetchMock.mock.calls[4][0]).toBe(`/api/v1/evidence-cards/${cardId}`);
    expect(fetchMock.mock.calls[5][0]).toBe(`/api/v1/evidence-cards/${cardId}/confirm`);
    const updatePayload = JSON.parse((fetchMock.mock.calls[4][1] as RequestInit).body as string);
    expect(updatePayload.content.next_action.source_refs).toEqual(["evidence.next_action"]);
  });
});
