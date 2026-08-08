import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

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

    render(<App />);

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

    render(<App />);

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

    render(<App />);

    expect(await screen.findByRole("heading", { name: "강박적 호기심" })).toBeVisible();
    expect(screen.getByText("0%")).toBeVisible();

    fireEvent.click(
      screen.getByLabelText("처음 가설과 조사 후 판단이 어떻게 달라졌는지 기록한다. 완료"),
    );

    expect(await screen.findByText("100%")).toBeVisible();
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
    const submittedDashboard = dashboard({
      ...readyDashboard,
      onboarding: { ...readyDashboard.onboarding, week_status: "evidence_submitted" },
      evidence: {
        id: "00000000-0000-4000-8000-000000000501",
        submitted_at: "2026-08-02T05:00:00Z",
      },
      permissions: { can_update_actions: false, can_submit_evidence: false },
    });
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(employee))
      .mockResolvedValueOnce(jsonResponse({ csrf_token: "csrf-token" }))
      .mockResolvedValueOnce(jsonResponse(readyDashboard))
      .mockResolvedValueOnce(
        jsonResponse(
          {
            id: "00000000-0000-4000-8000-000000000501",
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
      .mockResolvedValueOnce(jsonResponse(submittedDashboard));
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: "행동 근거 등록" }));
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

    expect(await screen.findByRole("heading", { name: "행동 근거를 제출했습니다" })).toBeVisible();
    const createRequest = fetchMock.mock.calls[3];
    expect(createRequest[0]).toBe("/api/v1/evidence");
    const requestBody = JSON.parse((createRequest[1] as RequestInit).body as string);
    expect(requestBody.assigned_action_ids).toEqual([actionId]);
    expect(requestBody.performed_action).toBe(inputText);
  });
});
