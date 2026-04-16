import http from "k6/http";
import { check, sleep } from "k6";
import { Counter, Rate } from "k6/metrics";

const busyResponses = new Counter("guardrail_busy_total");
const timeoutResponses = new Counter("guardrail_timeout_total");
const payloadRejectedResponses = new Counter("guardrail_payload_rejected_total");
const payloadRejectRate = new Rate("guardrail_payload_reject_rate");

export const options = {
  scenarios: {
    guardrails_resilience: {
      executor: "ramping-arrival-rate",
      startRate: 20,
      timeUnit: "1s",
      preAllocatedVUs: 40,
      maxVUs: 300,
      stages: [
        { duration: "30s", target: 60 },
        { duration: "60s", target: 120 },
        { duration: "60s", target: 200 },
        { duration: "30s", target: 0 },
      ],
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.35"],
    http_req_duration: ["p(95)<2500"],
    guardrail_payload_reject_rate: ["rate>0.90"],
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
  if (res.status !== 200) {
    return null;
  }
  return res.json("access_token");
}

export default function () {
  const token = login();
  if (!token) {
    sleep(0.2);
    return;
  }

  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
  const roll = Math.random();

  if (roll < 0.7) {
    const res = http.get(`${BASE}/v1/patients?limit=20&offset=0`, { headers });
    if (res.status === 503) {
      busyResponses.add(1);
    } else if (res.status === 504) {
      timeoutResponses.add(1);
    }
    check(res, {
      "read patients guarded": (r) => [200, 503, 504].includes(r.status),
    });
  } else if (roll < 0.9) {
    const suffix = `${__VU}-${__ITER}`;
    const res = http.post(
      `${BASE}/v1/patients/bulk`,
      JSON.stringify({
        items: [{ full_name: `Guardrail Paciente ${suffix}`, document_number: `G-${suffix}` }],
      }),
      { headers }
    );
    if (res.status === 503) {
      busyResponses.add(1);
    } else if (res.status === 504) {
      timeoutResponses.add(1);
    }
    check(res, {
      "bulk guarded": (r) => [201, 503, 504].includes(r.status),
    });
  } else {
    const oversized = "X".repeat(6_000_000);
    const res = http.post(
      `${BASE}/v1/patients/bulk`,
      JSON.stringify({
        items: [{ full_name: oversized, document_number: `OV-${__VU}-${__ITER}` }],
      }),
      { headers }
    );
    if (res.status === 413) {
      payloadRejectedResponses.add(1);
      payloadRejectRate.add(1);
    } else {
      payloadRejectRate.add(0);
    }
    check(res, {
      "payload guardrail enforced": (r) => r.status === 413 || r.status === 503 || r.status === 504,
    });
  }

  sleep(0.1);
}
