#!/usr/bin/env bash
# HTTP checks for post-release: /health, /live, /ready + standard build headers.
# Modes (POST_RELEASE_MODE):
#   rounds — POST_RELEASE_ROUNDS + POST_RELEASE_SLEEP_SECONDS between rounds
#   watch  — POST_RELEASE_WATCH_DURATION_SECONDS + POST_RELEASE_WATCH_INTERVAL_SECONDS
# Optional latency guards:
#   Global: POST_RELEASE_MAX_TOTAL_TIME_SECONDS
#   Per endpoint:
#     POST_RELEASE_MAX_TOTAL_TIME_HEALTH_SECONDS
#     POST_RELEASE_MAX_TOTAL_TIME_LIVE_SECONDS
#     POST_RELEASE_MAX_TOTAL_TIME_READY_SECONDS
# Optional retry guards:
#   POST_RELEASE_RETRY_ATTEMPTS (default: 1)
#   POST_RELEASE_RETRY_SLEEP_SECONDS (default: 2)
# Optional report output:
#   POST_RELEASE_REPORT_PATH (default: nextgen_platform/ci_artifacts/post-release-report.csv)
# Aggregate tables / guardrail (CI Job Summary): scripts/post_release_aggregate_latency.sh
set -euo pipefail

record_report() {
  round_label="$1"
  endpoint="$2"
  time_total="$3"
  attempt="$4"
  outcome="$5"
  threshold_used="$6"
  if [ -n "${POST_RELEASE_REPORT_PATH:-}" ]; then
    printf "%s,%s,%s,%s,%s,%s\n" "$round_label" "$endpoint" "$time_total" "$attempt" "$outcome" "$threshold_used" >> "$POST_RELEASE_REPORT_PATH"
  fi
}

check_endpoint() {
  endpoint="$1"
  round_label="$2"
  url="${BASE_URL%/}${endpoint}"
  headers_file="$(mktemp)"
  body_file="$(mktemp)"
  endpoint_threshold=""
  retry_attempts="${POST_RELEASE_RETRY_ATTEMPTS:-1}"
  retry_sleep_seconds="${POST_RELEASE_RETRY_SLEEP_SECONDS:-2}"
  case "$retry_attempts" in ''|*[!0-9]*) echo "[FAIL] POST_RELEASE_RETRY_ATTEMPTS must be numeric"; rm -f "$headers_file" "$body_file"; exit 1 ;; esac
  case "$retry_sleep_seconds" in ''|*[!0-9]*) echo "[FAIL] POST_RELEASE_RETRY_SLEEP_SECONDS must be numeric"; rm -f "$headers_file" "$body_file"; exit 1 ;; esac
  if [ "$retry_attempts" -lt 1 ]; then
    echo "[FAIL] POST_RELEASE_RETRY_ATTEMPTS must be >= 1"
    rm -f "$headers_file" "$body_file"
    exit 1
  fi
  case "$endpoint" in
    "/health") endpoint_threshold="${POST_RELEASE_MAX_TOTAL_TIME_HEALTH_SECONDS:-}" ;;
    "/live") endpoint_threshold="${POST_RELEASE_MAX_TOTAL_TIME_LIVE_SECONDS:-}" ;;
    "/ready") endpoint_threshold="${POST_RELEASE_MAX_TOTAL_TIME_READY_SECONDS:-}" ;;
  esac

  attempt=1
  last_failure="unknown"
  while [ "$attempt" -le "$retry_attempts" ]; do
    IFS=' ' read -r http_code time_total <<< "$(curl -sS -o "$body_file" -D "$headers_file" -w '%{http_code} %{time_total}' "$url")"
    last_failure=""

    if [ "$http_code" -ne 200 ]; then
      last_failure="HTTP $http_code"
    elif ! grep -qi '^x-api-version:' "$headers_file"; then
      last_failure="missing x-api-version header"
    elif ! grep -qi '^x-deploy-id:' "$headers_file"; then
      last_failure="missing x-deploy-id header"
    elif ! grep -qi '^x-git-sha:' "$headers_file"; then
      last_failure="missing x-git-sha header"
    elif ! grep -qi '^x-environment:' "$headers_file"; then
      last_failure="missing x-environment header"
    elif ! grep -qi '^x-region:' "$headers_file"; then
      last_failure="missing x-region header"
    elif ! grep -qi '^x-node-id:' "$headers_file"; then
      last_failure="missing x-node-id header"
    fi

    if [ -z "$last_failure" ] && [ -n "${EXPECTED_VERSION:-}" ]; then
      got_version="$(awk -F': ' 'tolower($1)=="x-api-version" {print $2}' "$headers_file" | tr -d '\r' | tail -n1)"
      [ "$got_version" = "$EXPECTED_VERSION" ] || last_failure="x-api-version mismatch (got=$got_version expected=$EXPECTED_VERSION)"
    fi
    if [ -z "$last_failure" ] && [ -n "${EXPECTED_DEPLOY_ID:-}" ]; then
      got_deploy_id="$(awk -F': ' 'tolower($1)=="x-deploy-id" {print $2}' "$headers_file" | tr -d '\r' | tail -n1)"
      [ "$got_deploy_id" = "$EXPECTED_DEPLOY_ID" ] || last_failure="x-deploy-id mismatch (got=$got_deploy_id expected=$EXPECTED_DEPLOY_ID)"
    fi
    if [ -z "$last_failure" ] && [ -n "${EXPECTED_GIT_SHA:-}" ]; then
      got_git_sha="$(awk -F': ' 'tolower($1)=="x-git-sha" {print $2}' "$headers_file" | tr -d '\r' | tail -n1)"
      [ "$got_git_sha" = "$EXPECTED_GIT_SHA" ] || last_failure="x-git-sha mismatch (got=$got_git_sha expected=$EXPECTED_GIT_SHA)"
    fi

  effective_threshold="${endpoint_threshold:-${POST_RELEASE_MAX_TOTAL_TIME_SECONDS:-}}"
  threshold_used="${effective_threshold:-none}"
    if [ -z "$last_failure" ] && [ -n "${effective_threshold:-}" ]; then
      if ! awk -v got="$time_total" -v max="$effective_threshold" 'BEGIN{if (got+0 > max+0) exit 1; exit 0}'; then
        last_failure="total time too high (${time_total}s > ${effective_threshold}s max)"
      fi
    fi

    if [ -z "$last_failure" ]; then
      rm -f "$headers_file" "$body_file"
      record_report "$round_label" "$endpoint" "$time_total" "$attempt" "ok" "$threshold_used"
      echo "[OK] $url (${time_total}s) [attempt $attempt/$retry_attempts]"
      return
    fi

    if [ "$attempt" -lt "$retry_attempts" ]; then
      echo "[WARN] $url attempt $attempt/$retry_attempts failed: $last_failure. Retrying in ${retry_sleep_seconds}s..."
      sleep "$retry_sleep_seconds"
    fi
    attempt=$((attempt + 1))
  done

  record_report "$round_label" "$endpoint" "$time_total" "$retry_attempts" "fail" "$threshold_used"
  echo "[FAIL] $url failed after $retry_attempts attempts: $last_failure"
  cat "$body_file"
  rm -f "$headers_file" "$body_file"
  exit 1
}

mode_rounds() {
  ROUNDS="${POST_RELEASE_ROUNDS:?}"
  SLEEP_SECONDS="${POST_RELEASE_SLEEP_SECONDS:?}"
  case "$ROUNDS" in ''|*[!0-9]*) echo "[FAIL] POST_RELEASE_ROUNDS must be numeric"; exit 1 ;; esac
  case "$SLEEP_SECONDS" in ''|*[!0-9]*) echo "[FAIL] POST_RELEASE_SLEEP_SECONDS must be numeric"; exit 1 ;; esac
  if [ "$ROUNDS" -lt 1 ]; then echo "[FAIL] POST_RELEASE_ROUNDS must be >= 1"; exit 1; fi

  i=1
  while [ "$i" -le "$ROUNDS" ]; do
    round_label="round_${i}_of_${ROUNDS}"
    echo "== Verification round $i/$ROUNDS =="
    check_endpoint "/health" "$round_label"
    check_endpoint "/live" "$round_label"
    check_endpoint "/ready" "$round_label"
    if [ "$i" -lt "$ROUNDS" ]; then
      echo "Sleeping ${SLEEP_SECONDS}s before next round..."
      sleep "$SLEEP_SECONDS"
    fi
    i=$((i + 1))
  done
}

mode_watch() {
  DURATION="${POST_RELEASE_WATCH_DURATION_SECONDS:?}"
  INTERVAL="${POST_RELEASE_WATCH_INTERVAL_SECONDS:?}"
  case "$DURATION" in ''|*[!0-9]*) echo "[FAIL] POST_RELEASE_WATCH_DURATION_SECONDS must be numeric"; exit 1 ;; esac
  case "$INTERVAL" in ''|*[!0-9]*) echo "[FAIL] POST_RELEASE_WATCH_INTERVAL_SECONDS must be numeric"; exit 1 ;; esac
  if [ "$DURATION" -lt 1 ]; then echo "[FAIL] duration must be >= 1"; exit 1; fi
  if [ "$INTERVAL" -lt 1 ]; then echo "[FAIL] interval must be >= 1"; exit 1; fi

  start_ts="$(date +%s)"
  end_ts=$((start_ts + DURATION))
  iter=0
  while true; do
    iter=$((iter + 1))
    round_label="watch_iter_${iter}"
    echo "== Watch iteration $iter at $(date -u +"%Y-%m-%dT%H:%M:%SZ") =="
    check_endpoint "/health" "$round_label"
    check_endpoint "/live" "$round_label"
    check_endpoint "/ready" "$round_label"
    now_ts="$(date +%s)"
    if [ "$now_ts" -ge "$end_ts" ]; then
      echo "Watch window complete (${DURATION}s)."
      break
    fi
    remaining=$((end_ts - now_ts))
    if [ "$remaining" -le "$INTERVAL" ]; then
      echo "Remaining ${remaining}s < interval; ending watch."
      break
    fi
    echo "Sleeping ${INTERVAL}s before next iteration..."
    sleep "$INTERVAL"
  done
}

MODE="${POST_RELEASE_MODE:-rounds}"
POST_RELEASE_REPORT_PATH="${POST_RELEASE_REPORT_PATH:-nextgen_platform/ci_artifacts/post-release-report.csv}"
mkdir -p "$(dirname "$POST_RELEASE_REPORT_PATH")"
echo "round,endpoint,time_total_seconds,attempt_used,outcome,threshold_used" > "$POST_RELEASE_REPORT_PATH"

case "$MODE" in
  rounds) mode_rounds ;;
  watch) mode_watch ;;
  *)
    echo "[FAIL] POST_RELEASE_MODE must be 'rounds' or 'watch'"
    exit 1
    ;;
esac
