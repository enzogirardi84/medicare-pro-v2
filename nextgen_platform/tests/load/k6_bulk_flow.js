import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  scenarios: {
    bulk_patients_and_visits: {
      executor: "ramping-vus",
      startVUs: 2,
      stages: [
        { duration: "30s", target: 10 },
        { duration: "60s", target: 30 },
        { duration: "30s", target: 0 },
      ],
      gracefulRampDown: "10s",
    },
  },
  thresholds: {
    http_req_duration: ["p(95)<1200"],
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
  return res.json("access_token");
}

export default function () {
  const token = login();
  if (!token) {
    sleep(1);
    return;
  }
  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  const docsuffix = `${__VU}-${__ITER}`;
  const bulkPatientsPayload = {
    items: [
      { full_name: `Paciente Bulk ${docsuffix}-1`, document_number: `B-${docsuffix}-1` },
      { full_name: `Paciente Bulk ${docsuffix}-2`, document_number: `B-${docsuffix}-2` },
    ],
  };
  const pRes = http.post(`${BASE}/v1/patients/bulk`, JSON.stringify(bulkPatientsPayload), { headers });
  check(pRes, { "patients bulk 201": (r) => r.status === 201 });
  if (pRes.status !== 201) {
    sleep(0.5);
    return;
  }
  const createdPatients = pRes.json();
  if (!Array.isArray(createdPatients) || createdPatients.length === 0) {
    sleep(0.5);
    return;
  }
  const visitItems = createdPatients.map((p) => ({ patient_id: p.id, notes: `Bulk visit ${docsuffix}` }));
  const vRes = http.post(`${BASE}/v1/visits/bulk`, JSON.stringify({ items: visitItems }), { headers });
  check(vRes, { "visits bulk 201": (r) => r.status === 201 });

  sleep(0.2);
}
