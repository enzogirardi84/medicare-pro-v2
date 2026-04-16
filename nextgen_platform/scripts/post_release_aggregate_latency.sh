#!/usr/bin/env bash
# Aggregate latency helpers for post-release CSV (from post_release_http_verify.sh).
#
# Subcommands:
#   detail-table       — Markdown table of raw rows (no section header).
#   aggregates-table   — Markdown aggregate table with status column (no section header).
#   red-count          — Print integer: endpoints whose average time exceeds aggregate threshold.
#   red-endpoints      — One breaching endpoint path per line, sorted (for diagnostics).
#   guardrail          — Enforce or skip aggregate failure; optional non-blocking Job Summary note.
#
# Env:
#   POST_RELEASE_REPORT_PATH — default: nextgen_platform/ci_artifacts/post-release-report.csv
#   FAIL_ON_LATENCY_BREACH   — for guardrail: true (default) | false | 0 | no
#   POST_RELEASE_GUARDRAIL_SKIP_HINT — optional text after "because" in non-blocking warning
#   GITHUB_STEP_SUMMARY      — append path (set by GitHub Actions)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPORT="${POST_RELEASE_REPORT_PATH:-${SCRIPT_DIR}/../ci_artifacts/post-release-report.csv}"

# Same aggregation logic as workflows: per-endpoint avg vs effective threshold column.
_AGG_AWK=$'
NR > 1 {
  gsub(/\r/, "", $0)
  c[$2]++; s[$2] += $3
  if (!(($2) in mn) || $3 < mn[$2]) mn[$2] = $3
  if (!(($2) in mx) || $3 > mx[$2]) mx[$2] = $3
  if (!(($2) in th) || (th[$2] == "none" && $6 != "none")) th[$2] = $6
}
END {
  for (e in c) {
    avg = s[e] / c[e]
    thr = (e in th) ? th[e] : "none"
    status = "⚪ no-threshold"
    if (thr != "none") {
      t = thr + 0
      if (avg <= t * 0.8) status = "🟢 healthy"
      else if (avg <= t) status = "🟡 near-limit"
      else status = "🔴 above-limit"
    }
    printf "| %s | %d | %.4f | %.4f | %.4f | %s | %s |\n", e, c[e], avg, mn[e], mx[e], thr, status
  }
}'

_RED_COUNT_AWK=$'
NR > 1 {
  gsub(/\r/, "", $0)
  c[$2]++; s[$2] += $3
  if (!(($2) in th) || (th[$2] == "none" && $6 != "none")) th[$2] = $6
}
END {
  reds = 0
  for (e in c) {
    avg = s[e] / c[e]
    thr = (e in th) ? th[e] : "none"
    if (thr != "none" && avg > (thr + 0)) reds++
  }
  print reds + 0
}'

_RED_EP_AWK=$'
NR > 1 {
  gsub(/\r/, "", $0)
  c[$2]++; s[$2] += $3
  if (!(($2) in th) || (th[$2] == "none" && $6 != "none")) th[$2] = $6
}
END {
  for (e in c) {
    avg = s[e] / c[e]
    thr = (e in th) ? th[e] : "none"
    if (thr != "none" && avg > (thr + 0)) print e
  }
}'

usage() {
  echo "Usage: $0 {detail-table|aggregates-table|red-count|red-endpoints|guardrail}" >&2
  exit 1
}

require_report() {
  if [ ! -f "$REPORT" ]; then
    echo "[FAIL] POST-release report not found: $REPORT" >&2
    exit 1
  fi
}

cmd="${1:-}"
[ -n "$cmd" ] || usage

case "$cmd" in
  detail-table)
    require_report
    awk -F',' 'NR > 1 {
      gsub(/\r/, "", $0)
      printf "| %s | %s | %s | %s | %s | %s |\n", $1, $2, $3, $4, $5, $6
    }' "$REPORT"
    ;;
  aggregates-table)
    require_report
    awk -F',' "$_AGG_AWK" "$REPORT" | sort
    ;;
  red-count)
    require_report
    awk -F',' "$_RED_COUNT_AWK" "$REPORT"
    ;;
  red-endpoints)
    require_report
    awk -F',' "$_RED_EP_AWK" "$REPORT" | sort -u
    ;;
  guardrail)
    require_report
    summary_file="${GITHUB_STEP_SUMMARY:-}"
    fail_flag="${FAIL_ON_LATENCY_BREACH:-true}"
    case "$fail_flag" in
      false|False|FALSE|0|no|No) enforce=false ;;
      *) enforce=true ;;
    esac

    red_count="$(awk -F',' "$_RED_COUNT_AWK" "$REPORT")"
    hint="${POST_RELEASE_GUARDRAIL_SKIP_HINT:-\`fail_on_latency_breach=false\`}"

    if [ "$enforce" = false ]; then
      echo "[SKIP] Aggregate latency guardrail disabled for this run (informational tables only)."
      if [ -n "$summary_file" ] && [ "$red_count" -gt 0 ]; then
        eps="$(awk -F',' "$_RED_EP_AWK" "$REPORT" | sort -u)"
        eps_md="$(printf '%s\n' "$eps" | sed '/^$/d' | while read -r ep; do echo "- \`${ep}\`"; done)"
        if [ -z "$eps_md" ]; then
          eps_md="- _(none)_"
        fi
        {
          echo ""
          echo "### Aggregate latency guardrail (non-blocking)"
          echo ""
          echo "> **Warning:** \`${red_count}\` endpoint(s) have average latency **above** the configured aggregate threshold, but this run did **not** fail the workflow because ${hint}. Review the table above before production."
          echo ""
          echo "**Breaching endpoints (aggregate):**"
          echo "$eps_md"
        } >>"$summary_file"
      fi
      exit 0
    fi

    if [ "$red_count" -gt 0 ]; then
      eps_line="$(awk -F',' "$_RED_EP_AWK" "$REPORT" | sort -u | paste -sd', ' -)"
      echo "[FAIL] Latency guardrail violated: ${red_count} endpoint(s) above configured threshold (${eps_line})."
      exit 1
    fi
    echo "[OK] Latency guardrail passed."
    ;;
  *)
    usage
    ;;
esac
