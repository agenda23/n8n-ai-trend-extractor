#!/usr/bin/env bash
set -euo pipefail

PASS=0
FAIL=0

check() {
  local name="$1"
  local url="$2"
  local extra="${3:-}"
  printf "%-20s " "${name}"
  local code
  if [[ -n "${extra}" ]]; then
    code=$(curl -s -o /dev/null -w "%{http_code}" ${extra} "${url}")
  else
    code=$(curl -s -o /dev/null -w "%{http_code}" "${url}")
  fi
  if [[ "${code}" =~ ^2 ]]; then
    echo "OK (${code})"
    PASS=$((PASS + 1))
  else
    echo "FAIL (${code}) ${url}"
    FAIL=$((FAIL + 1))
  fi
}

echo "=== データソース疎通確認 ==="
echo ""

check "note AI副業 RSS" "https://note.com/hashtag/ai%E5%89%AF%E6%A5%AD/rss"
check "note AIツール RSS" "https://note.com/hashtag/ai%E3%83%84%E3%83%BC%E3%83%AB/rss"
check "Brain 検索ページ" "https://brain-market.com/search?keyword=AI"
check "Tips 検索ページ" "https://tips.jp/search?q=AI"

if [[ -n "${QIITA_ACCESS_TOKEN:-}" ]]; then
  check "Qiita API" "https://qiita.com/api/v2/items?query=tag:AI&per_page=3" \
    "-H" "Authorization: Bearer ${QIITA_ACCESS_TOKEN}"
else
  check "Qiita API (公開)" "https://qiita.com/api/v2/items?query=tag:AI&per_page=3"
fi

X_TRENDS_URL="${X_TRENDS_BASE_URL:-http://localhost:3920}"
check "x-trends health" "${X_TRENDS_URL}/health"

echo ""
echo "--- 結果: ${PASS} OK / ${FAIL} FAIL ---"

if command -v x-trends &>/dev/null; then
  echo ""
  echo "x-trends (ホスト CLI): インストール済み"
  if x-trends settings 2>/dev/null | head -c 80 | grep -q '"ok":true'; then
    echo "x-trends 認証: OK"
  else
    echo "x-trends 認証: 未設定またはトークン切れ（~/.config/x-trends/.env を確認）"
  fi
else
  echo ""
  echo "x-trends (ホスト CLI): 未インストール"
fi

[[ "${FAIL}" -eq 0 ]]
