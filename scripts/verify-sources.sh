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

echo ""
echo "--- 結果: ${PASS} OK / ${FAIL} FAIL ---"

if command -v twitter &>/dev/null; then
  echo ""
  echo "twitter-cli (ホスト): インストール済み"
  if twitter search "Dify" --json 2>/dev/null | head -c 80 | grep -q "text\|\["; then
    echo "twitter-cli 認証: OK"
  else
    echo "twitter-cli 認証: 未設定またはセッション切れ（twitter login を実行）"
  fi
else
  echo ""
  echo "twitter-cli (ホスト): 未インストール（npm install -g @public-clis/twitter-cli）"
fi

[[ "${FAIL}" -eq 0 ]]
