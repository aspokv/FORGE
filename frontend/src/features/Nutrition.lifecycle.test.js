import React, {act} from "react";
import {createRoot} from "react-dom/client";
import axios from "axios";
import Nutrition from "./Nutrition";

jest.mock("axios", () => ({get: jest.fn()}));

test("leaving Nutrition cancels plan and assessment requests", async () => {
  global.IS_REACT_ACT_ENVIRONMENT = true;
  axios.get.mockImplementation(() => new Promise(() => {}));
  const container = document.createElement("div");
  const root = createRoot(container);
  await act(async () => root.render(<Nutrition API="/api" />));
  const calls = axios.get.mock.calls;
  const assessment = calls.filter(([url]) => url.endsWith("/nutrition/assessment"));
  const plan = calls.find(([url]) => url.endsWith("/nutrition/plan"));
  expect(assessment).toHaveLength(1);
  expect(plan[1].signal.aborted).toBe(false);
  await act(async () => root.unmount());
  expect(plan[1].signal.aborted).toBe(true);
  expect(assessment[0][1].signal.aborted).toBe(true);
});
