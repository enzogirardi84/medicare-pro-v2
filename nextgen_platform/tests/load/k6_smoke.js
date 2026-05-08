import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  vus: 20,
  duration: "30s",
};

const BASE = __ENV.BASE_URL || "http://localhost:8000";

export default function () {
  const res = http.get(`${BASE}/health`);
  check(res, {
    "health status 200": (r) => r.status === 200,
  });
  sleep(0.2);
}
