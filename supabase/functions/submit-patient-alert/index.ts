// Deploy: supabase functions deploy submit-patient-alert --no-verify-jwt
// Secrets: PATIENT_ALERT_INGEST_SECRET (misma cadena que configura la app paciente)
// Supabase inyecta SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY en el entorno de la función.

import { serve } from "https://deno.land/std@0.224.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.49.1";

const corsHeaders: Record<string, string> = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type, x-patient-alert-secret",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

serve(async (req: Request) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  if (req.method !== "POST") {
    return json({ error: "Method not allowed" }, 405);
  }

  const expected = Deno.env.get("PATIENT_ALERT_INGEST_SECRET") ?? "";
  const got = req.headers.get("x-patient-alert-secret") ?? "";
  if (!expected || got !== expected) {
    return json({ error: "Unauthorized" }, 401);
  }

  let body: Record<string, unknown>;
  try {
    body = await req.json();
  } catch {
    return json({ error: "Invalid JSON" }, 400);
  }

  const patientToken = String(body["patient_token"] ?? "").trim();
  const reasonCode = String(body["reason_code"] ?? "").trim();
  if (!patientToken || !reasonCode) {
    return json({ error: "patient_token and reason_code required" }, 400);
  }

  const supabaseUrl = Deno.env.get("SUPABASE_URL") ?? "";
  const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
  if (!supabaseUrl || !serviceKey) {
    return json({ error: "Server misconfigured" }, 500);
  }

  const supabase = createClient(supabaseUrl, serviceKey);

  const empresaRaw = body["empresa_clave"];
  const empresa =
    typeof empresaRaw === "string" && empresaRaw.trim() !== ""
      ? empresaRaw.trim().toLowerCase()
      : null;

  const row = {
    patient_token: patientToken,
    patient_name: typeof body["patient_name"] === "string" ? body["patient_name"] : null,
    reason_code: reasonCode,
    reason_label: String(body["reason_label"] ?? reasonCode),
    note: typeof body["note"] === "string" ? body["note"] : null,
    latitude: typeof body["latitude"] === "number" ? body["latitude"] : null,
    longitude: typeof body["longitude"] === "number" ? body["longitude"] : null,
    accuracy_meters: typeof body["accuracy_meters"] === "number" ? body["accuracy_meters"] : null,
    sent_at:
      typeof body["sent_at"] === "string"
        ? body["sent_at"]
        : new Date().toISOString(),
    source:
      typeof body["source"] === "string"
        ? body["source"]
        : "medicare_paciente_alerta_flutter",
    empresa,
    status: "nueva",
    raw_payload: body,
  };

  const { error } = await supabase.from("patient_alerts").insert(row);

  if (error) {
    console.error("patient_alerts insert", error);
    return json({ error: error.message }, 500);
  }

  return json({ ok: true }, 200);
});

function json(data: unknown, status: number): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
}
