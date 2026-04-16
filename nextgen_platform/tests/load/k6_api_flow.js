import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  scenarios: {
    auth_and_reads: {
      executor: "ramping-vus",
      startVUs: 5,
      stages: [
        { duration: "30s", target: 40 },
        { duration: "60s", target: 120 },
        { duration: "30s", target: 0 },
      ],
      gracefulRampDown: "10s",
    },
  },
  thresholds: {
    http_req_duration: ["p(95)<800"],
    http_req_failed: ["rate<0.03"],
  },
};

const BASE = __ENV.BASE_URL || "http://localhost:8000";

export default function () {
  const tenant = "clinica-scale-test";
  const email = "admin-scale@test.com";
  const password = "StrongPass123!";

  const loginRes = http.post(
    `${BASE}/v1/auth/login`,
    JSON.stringify({ tenant_name: tenant, email, password }),
    { headers: { "Content-Type": "application/json" } }
  );
  check(loginRes, { "login ok": (r) => r.status === 200 });
  if (loginRes.status !== 200) {
    sleep(1);
    return;
  }

  const token = loginRes.json("access_token");
  const params = { headers: { Authorization: `Bearer ${token}` } };

  const pRes = http.get(`${BASE}/v1/patients?limit=20&offset=0`, params);
  check(pRes, { "patients ok": (r) => r.status === 200 });

  const vRes = http.get(`${BASE}/v1/visits?limit=20&offset=0`, params);
  check(vRes, { "visits ok": (r) => r.status === 200 });

  sleep(0.2);
}
