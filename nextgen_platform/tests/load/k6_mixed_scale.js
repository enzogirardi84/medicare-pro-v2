import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  scenarios: {
    mixed_scale: {
      executor: "ramping-vus",
      startVUs: 5,
      stages: [
        { duration: "30s", target: 30 },
        { duration: "60s", target: 80 },
        { duration: "60s", target: 120 },
        { duration: "30s", target: 0 },
      ],
      gracefulRampDown: "15s",
    },
  },
  thresholds: {
    http_req_duration: ["p(95)<1300"],
    http_req_failed: ["rate<0.05"],
  },
};

const BASE = __ENV.BASE_URL || "http://localhost:8000";

function login() {
  const res = http.post(
    `${BASE}/v1/auth/login`,
    JSON.stringify({
      tenant_name: "clinica-scale-test",
      email: "admin-scale@test.com",
      password: "StrongPass123!",
    }),
    { headers: { "Content-Type": "application/json" } }
  );
  if (res.status !== 200) return null;
  return res.json();
}

export default function () {
  const auth = login();
  if (!auth) {
    sleep(1);
    return;
  }
  const token = auth.access_token;
  const refreshToken = auth.refresh_token;
  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  const r = Math.random();
  if (r < 0.55) {
    check(http.get(`${BASE}/v1/patients?limit=20&offset=0`, { headers }), { "read patients": (x) => x.status === 200 });
    check(http.get(`${BASE}/v1/visits?limit=20&offset=0`, { headers }), { "read visits": (x) => x.status === 200 });
  } else if (r < 0.85) {
    const suffix = `${__VU}-${__ITER}`;
    const pRes = http.post(
      `${BASE}/v1/patients/bulk`,
      JSON.stringify({
        items: [
          { full_name: `Mix Paciente ${suffix}-1`, document_number: `M-${suffix}-1` },
          { full_name: `Mix Paciente ${suffix}-2`, document_number: `M-${suffix}-2` },
        ],
      }),
      { headers }
    );
    check(pRes, { "bulk patients": (x) => x.status === 201 });
  } else {
    const rr = http.post(
      `${BASE}/v1/auth/refresh`,
      JSON.stringify({ refresh_token: refreshToken }),
      { headers: { "Content-Type": "application/json" } }
    );
    check(rr, { "refresh ok": (x) => x.status === 200 });
  }
  sleep(0.2);
}
