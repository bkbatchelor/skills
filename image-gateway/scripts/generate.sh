#!/usr/bin/env bash
# Generate or edit images with Google's Gemini API (Interactions API).
#
# Usage: generate.sh [options] "prompt"
#
#   -m, --model ID          model (default: IMAGE_GATEWAY_MODEL from config.env)
#   -o, --out PATH          output directory, or a file path ending in an image
#                           extension (default: IMAGE_GATEWAY_OUT_DIR)
#   -n, --name NAME         base filename without extension (default: timestamp-slug)
#   -i, --input FILE|URL    reference image to edit or follow; repeatable (max 14)
#   -a, --aspect RATIO      1:1 2:3 3:2 3:4 4:3 4:5 5:4 9:16 16:9 21:9 1:4 4:1 1:8 8:1
#   -r, --resolution SIZE   1K, 2K or 4K (512 on gemini-3.1-flash-image only)
#   -c, --count N           number of images; one request per image (default 1)
#   -f, --format FMT        png | jpeg (Gemini's default is jpeg; a .png -o path implies png)
#   -x, --extra JSON        JSON object merged into the request body
#       --no-fallback       fail instead of switching to IMAGE_GATEWAY_FALLBACK_MODEL
#       --dry-run           print the request body (base64 truncated) and exit
#   -h, --help
#
# Prints one JSON line to stdout: {"files":[...],"model":...,"cost_usd":...,...}
# Progress and errors go to stderr. Exit code is non-zero on failure.

set -euo pipefail

SKILL_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
API_URL=${IMAGE_GATEWAY_API_URL:-https://generativelanguage.googleapis.com/v1beta/interactions}

die() { printf 'image-gateway: %s\n' "$*" >&2; exit 1; }
say() { printf 'image-gateway: %s\n' "$*" >&2; }
expand() { local p=$1; [[ $p == "~"* ]] && p="$HOME${p:1}"; printf '%s' "$p"; }

for cmd in curl jq base64; do
  command -v "$cmd" >/dev/null || die "missing required command: $cmd"
done

# Saved preferences. Environment variables already set win over the file.
read_conf() {  # read_conf KEY -> value from config.env, or empty
  [[ -f $SKILL_DIR/config.env ]] || return 0
  sed -n "s/^[[:space:]]*$1=//p" "$SKILL_DIR/config.env" | tail -n1 | sed -e 's/^["'\'']//' -e 's/["'\'']$//'
}
MODEL=${IMAGE_GATEWAY_MODEL:-$(read_conf IMAGE_GATEWAY_MODEL)}
OUT=${IMAGE_GATEWAY_OUT_DIR:-$(read_conf IMAGE_GATEWAY_OUT_DIR)}
ENV_FILE=${IMAGE_GATEWAY_ENV_FILE:-$(read_conf IMAGE_GATEWAY_ENV_FILE)}
FALLBACK=${IMAGE_GATEWAY_FALLBACK_MODEL-$(read_conf IMAGE_GATEWAY_FALLBACK_MODEL)}
MODEL_FROM_FLAG=0

NAME="" PROMPT="" DRY_RUN=0 EXTRA="{}" COUNT=1 ASPECT="" SIZE="" FORMAT=""
INPUTS=()

while (($#)); do
  case "$1" in
    -m|--model)      MODEL=$2; MODEL_FROM_FLAG=1; shift 2 ;;
    -o|--out)        OUT=$2; shift 2 ;;
    -n|--name)       NAME=$2; shift 2 ;;
    -i|--input)      INPUTS+=("$2"); shift 2 ;;
    -a|--aspect)     ASPECT=$2; shift 2 ;;
    -r|--resolution) SIZE=$(tr '[:lower:]' '[:upper:]' <<<"$2"); shift 2 ;;  # API rejects "2k"
    -c|--count)      COUNT=$2; shift 2 ;;
    -f|--format)     FORMAT=$2; shift 2 ;;
    -x|--extra)      EXTRA=$2; shift 2 ;;
    --no-fallback)   FALLBACK=""; shift ;;
    --dry-run)       DRY_RUN=1; shift ;;
    -h|--help)       sed -n '2,22p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    --)              shift; PROMPT="$*"; break ;;
    -*)              die "unknown option: $1 (see --help)" ;;
    *)               PROMPT=${PROMPT:+$PROMPT }$1; shift ;;
  esac
done

[[ -n $PROMPT ]] || die "a prompt is required (see --help)"
[[ -n $MODEL ]] || die "no model: set IMAGE_GATEWAY_MODEL in $SKILL_DIR/config.env or pass -m"
[[ $COUNT =~ ^[1-9][0-9]*$ ]] || die "--count must be a positive integer"
((${#INPUTS[@]} <= 14)) || die "at most 14 reference images"
case "$FORMAT" in ""|png|jpeg) ;; jpg) FORMAT=jpeg ;; *) die "--format must be png or jpeg" ;; esac
[[ -n $OUT ]] || OUT=.
OUT=$(expand "$OUT")
# Gemini returns JPEG unless asked otherwise, so honor a .png/.jpg output path.
if [[ -z $FORMAT ]]; then
  case "$OUT" in *.png) FORMAT=png ;; *.jpg|*.jpeg) FORMAT=jpeg ;; esac
fi
[[ $OUT =~ \.webp$ ]] && die "Gemini outputs png or jpeg only; use a .png or .jpg path"
echo "$EXTRA" | jq -e 'type == "object"' >/dev/null 2>&1 || die "--extra must be a JSON object"

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

# Input: the prompt, then each reference image as inline base64. URLs are
# downloaded first, because the API only takes inline data or Files API URIs.
jq -n --arg t "$PROMPT" '[{type: "text", text: $t}]' > "$TMP/input.json"
for idx in "${!INPUTS[@]}"; do
  ref=${INPUTS[$idx]}
  if [[ $ref =~ ^https?:// ]]; then
    curl -sSfL --max-time 60 -o "$TMP/dl$idx" "$ref" || die "could not download: $ref"
    ref="$TMP/dl$idx"
  else
    ref=$(expand "$ref")
    [[ -f $ref ]] || die "input image not found: $ref"
  fi
  mime=$(file -b --mime-type "$ref" 2>/dev/null || echo image/png)
  [[ $mime == image/* ]] || die "not an image ($mime): ${INPUTS[$idx]}"
  base64 -w0 "$ref" > "$TMP/ref$idx"
  jq --rawfile d "$TMP/ref$idx" --arg m "$mime" '. + [{type: "image", data: $d, mime_type: $m}]' \
    "$TMP/input.json" > "$TMP/input2.json" && mv "$TMP/input2.json" "$TMP/input.json"
done

build_body() {  # build_body MODEL -> writes $TMP/body.json
  jq -n --arg model "$1" --slurpfile input "$TMP/input.json" \
    --arg aspect "$ASPECT" --arg size "$SIZE" --arg fmt "$FORMAT" --argjson extra "$EXTRA" \
    '{model: $model, input: $input[0], store: false,
      response_format: ({type: "image"}
        + (if $aspect != "" then {aspect_ratio: $aspect} else {} end)
        + (if $size   != "" then {image_size: $size}     else {} end)
        + (if $fmt    != "" then {mime_type: ("image/" + $fmt)} else {} end))}
     + $extra' > "$TMP/body.json"
}
build_body "$MODEL"

if ((DRY_RUN)); then
  jq '(.input[] | select(.type == "image") | .data) |= (.[:60] + "...(truncated)")' "$TMP/body.json"
  exit 0
fi

# Read the key from the env file without sourcing it (sourcing would run code).
[[ -n $ENV_FILE ]] || die "no env file configured: set IMAGE_GATEWAY_ENV_FILE in $SKILL_DIR/config.env"
ENV_FILE=$(expand "$ENV_FILE")
[[ -f $ENV_FILE ]] || die "env file not found: $ENV_FILE (add a line GEMINI_API_KEY=...)"
KEY=$(sed -n 's/^[[:space:]]*\(export[[:space:]]\{1,\}\)\{0,1\}GEMINI_API_KEY=//p' "$ENV_FILE" | tail -n1 \
      | sed -e 's/[[:space:]]*$//' -e 's/^["'\'']//' -e 's/["'\'']$//')
[[ -n $KEY ]] || die "GEMINI_API_KEY is missing or empty in $ENV_FILE"

# Decide where files go: a directory, or an explicit file path.
if [[ $OUT =~ \.(png|jpe?g)$ ]]; then
  OUT_DIR=$(dirname "$OUT"); NAME=$(basename "${OUT%.*}")
else
  OUT_DIR=$OUT
fi
mkdir -p "$OUT_DIR"
if [[ -z $NAME ]]; then
  slug=$(printf '%s' "$PROMPT" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '-' | cut -c1-40 | sed 's/^-*//; s/-*$//')
  NAME="$(date +%Y%m%d-%H%M%S)-${slug:-image}"
fi

post() {
  # The key goes to curl on stdin as a config line, so it never shows in `ps`.
  printf 'header = "x-goog-api-key: %s"\n' "$KEY" | curl -sS -K - \
    -X POST "$API_URL" \
    -H "Content-Type: application/json" \
    --data-binary "@$TMP/body.json" \
    --max-time "${IMAGE_GATEWAY_TIMEOUT:-300}" \
    -o "$TMP/resp.json" -w '%{http_code}'
}
transient() { [[ $1 == 429 || $1 == 500 || $1 == 503 || $1 == 504 || $1 == 000 ]]; }

# One request = one image. Retries 429/5xx with backoff, then falls back once
# to the fallback model (only when the model came from config, not -m).
request_image() {
  local try attempts=${IMAGE_GATEWAY_RETRIES:-3} wait_s
  for ((try = 1; ; try++)); do
    http=$(post) || http=000
    transient "$http" || break
    ((try < attempts)) || break
    wait_s=$((try * 10))
    say "HTTP $http (attempt $try/$attempts), retrying in ${wait_s}s ..."
    sleep "$wait_s"
  done
  if transient "$http" && ((!MODEL_FROM_FLAG)) && [[ -n $FALLBACK && $FALLBACK != "$MODEL" ]]; then
    say "HTTP $http from $MODEL; falling back to $FALLBACK for the rest of this run"
    MODEL=$FALLBACK; FALLBACK=""
    build_body "$MODEL"
    http=$(post) || http=000
  fi
  [[ $http != 000 ]] || die "request failed (network or timeout)"
  if [[ $http != 2* ]]; then
    local msg
    msg=$(jq -r '.error | "\(.status // .code // ""): \(.message // .)"' "$TMP/resp.json" 2>/dev/null || true)
    [[ -n $msg ]] || msg=$(head -c 500 "$TMP/resp.json")
    die "HTTP $http from Gemini API: $msg"
  fi
}

# Prices in USD per 1M tokens, Standard tier (ai.google.dev/gemini-api/docs/pricing,
# checked 2026-10-19): input, text+thinking output, image output.
price_of() {
  case "$1" in
    gemini-3-pro-image*)          echo "2.00 12.00 120.00" ;;
    gemini-nano-banana-2.1*)      echo "1.50 7.50 30.00" ;;
    gemini-3.1-flash-image*)      echo "0.50 3.00 60.00" ;;
    *)                            echo "" ;;
  esac
}

REQUESTED_MODEL=$MODEL
files=() total_cost=0 cost_known=1 usage_all='[]'
say "generating $COUNT image(s) with $MODEL ..."
start=$(date +%s)
for ((k = 1; k <= COUNT; k++)); do
  request_image

  # The final image is the last image block in the model_output steps.
  # (Interim "thought images" are not part of model_output and aren't billed.)
  img=$(jq -c '[.steps[]? | select(.type == "model_output") | .content[]? | select(.type == "image")] | last // empty' "$TMP/resp.json")
  if [[ -z $img ]]; then
    txt=$(jq -r '[.steps[]? | .content[]? | select(.type == "text") | .text] | join(" ")' "$TMP/resp.json" | head -c 400)
    die "no image in the response (status: $(jq -r '.status // "?"' "$TMP/resp.json"))${txt:+. Model said: $txt}"
  fi
  mt=$(jq -r '.mime_type // "image/png"' <<<"$img")
  case "$mt" in image/jpeg) ext=jpg ;; image/webp) ext=webp ;; *) ext=png ;; esac
  f="$OUT_DIR/$NAME.$ext"
  ((COUNT > 1)) && f="$OUT_DIR/$NAME-$k.$ext"
  if jq -e '.data' <<<"$img" >/dev/null; then
    jq -r '.data' <<<"$img" | base64 -d > "$f"
  elif uri=$(jq -er '.uri' <<<"$img"); then
    printf 'header = "x-goog-api-key: %s"\n' "$KEY" | curl -sSfL -K - --max-time 120 -o "$f" "$uri"
  else
    die "image block has neither data nor uri"
  fi
  [[ -s $f ]] || die "wrote an empty file: $f"
  files+=("$(cd "$(dirname "$f")" && pwd)/$(basename "$f")")

  # Cost estimate. The API reports tokens, not dollars. Image tokens come from
  # output_tokens_by_modality; other output (caption text) and thinking are
  # billed at the text rate. Pro adds ~100 caption tokens to each image.
  usage=$(jq -c '.usage // {}' "$TMP/resp.json")
  usage_all=$(jq -c --argjson u "$usage" '. + [$u]' <<<"$usage_all")
  read -r p_in p_txt p_img <<<"$(price_of "$MODEL")" || true
  if [[ -n ${p_img:-} ]]; then
    c=$(jq -n --argjson u "$usage" --argjson a "$p_in" --argjson b "$p_txt" --argjson i "$p_img" \
      '($u.total_output_tokens // 0) as $out
       | ([$u.output_tokens_by_modality[]? | select(.modality == "image") | .tokens] | add // $out) as $img
       | (($u.total_input_tokens // 0) * $a
          + (($u.total_thought_tokens // 0) + ($out - $img)) * $b
          + $img * $i) / 1e6')
    total_cost=$(jq -n --argjson t "$total_cost" --argjson c "$c" '$t + $c')
  else
    cost_known=0
  fi
done
elapsed=$(( $(date +%s) - start ))
((cost_known)) || total_cost=null

summary=$(jq -c -n --args \
  --arg model "$MODEL" --arg requested "$REQUESTED_MODEL" --arg prompt "$PROMPT" \
  --argjson secs "$elapsed" --argjson cost "$total_cost" --argjson usage "$usage_all" \
  '{files: $ARGS.positional, model: $model, fell_back: ($model != $requested),
    cost_usd: (if $cost == null then null else ($cost * 10000 | round / 10000) end),
    cost_is_estimate: true, usage: $usage, seconds: $secs, prompt: $prompt}' "${files[@]}")

# Keep a running log next to the images: what was made, with what, for how much.
printf '%s\n' "$(jq -c --arg t "$(date -Iseconds)" '{time: $t} + .' <<<"$summary")" >> "$OUT_DIR/.image-gateway-log.jsonl"

printf '%s\n' "$summary"
