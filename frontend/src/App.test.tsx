import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import App from "./App";

describe("App scaffold", () => {
  it("renders the IX Value Loop foundation", () => {
    render(<App />);

    expect(screen.getByRole("heading", { level: 1, name: "IX Value Loop" })).toBeVisible();
    expect(screen.getByText("Foundation ready")).toBeVisible();
    expect(screen.getByRole("heading", { name: "FastAPI" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "React + TypeScript" })).toBeVisible();
  });
});
