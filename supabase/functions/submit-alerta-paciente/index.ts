// Deploy: supabase functions deploy submit-alerta-paciente --no-verify-jwt
// Secret: PATIENT_ALERT_INGEST_SECRET (misma que la app paciente)
// Tabla: public.alertas_pacientes

import { serve } from "https://deno.land/std@0.224.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.49.1";

const corsHeaders: Record<string, string> = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type, x-patient-alert-secret",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

const NIVELES = new Set(["Rojo", "Amarillo", "Verde"]);

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

  const pacienteId = String(body["paciente_id"] ?? "").trim();
  const sintoma = String(body["sintoma"] ?? "").trim();
  const nivel = String(body["nivel_urgencia"] ?? "").trim();

  if (!pacienteId || !sintoma || !NIVELES.has(nivel)) {
    return json(
      { error: "paciente_id, sintoma and nivel_urgencia (Rojo|Amarillo|Verde) required" },
      400,
    );
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

  const lat = typeof body["latitud"] === "number" ? body["latitud"] : null;
  const lon = typeof body["longitud"] === "number" ? body["longitud"] : null;
  const prec = typeof body["precision_m"] === "number" ? body["precision_m"] : null;

  const fechaHora =
    typeof body["fecha_hora"] === "string"
      ? body["fecha_hora"]
      : new Date().toISOString();

  const row = {
    paciente_id: pacienteId,
    sintoma,
    nivel_urgencia: nivel,
    latitud: lat,
    longitud: lon,
    precision_m: prec,
    empresa,
    estado: "Pendiente",
    fecha_hora: fechaHora,
    raw_payload: body,
  };

  const { error } = await supabase.from("alertas_pacientes").insert(row);

  if (error) {
    console.error("alertas_pacientes insert", error);
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
