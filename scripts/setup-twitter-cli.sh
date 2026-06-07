#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DATA_DIR="${ROOT_DIR}/data/twitter-cli"

echo "=== twitter-cli セットアップ（Python版）==="
echo ""

echo "1. ホストに twitter-cli をインストール（未インストールの場合）"
if ! command -v twitter &>/dev/null; then
  if command -v uv &>/dev/null; then
    uv tool install twitter-cli
  elif command -v pipx &>/dev/null; then
    pipx install twitter-cli
  else
    pip3 install --user twitter-cli
  fi
else
  echo "   twitter-cli は既にインストール済みです"
fi

echo ""
echo "2. X Cookie 認証"
echo "   ブラウザ DevTools → Application → Cookies → x.com から"
echo "   auth_token と ct0 を取得し、.env に設定してください:"
echo ""
echo "   TWITTER_AUTH_TOKEN=<auth_token>"
echo "   TWITTER_CT0=<ct0>"
echo ""
echo "   またはホストでブラウザ Cookie 自動抽出:"
echo "   twitter whoami"
echo ""

mkdir -p "${DATA_DIR}"
echo "3. Cookie キャッシュ共有先: ${DATA_DIR}"
echo "   docker-compose.yml でコンテナ (~/.cache/twitter-cli) と共有されます"
echo ""

if docker compose ps n8n 2>/dev/null | grep -q "running\|Up"; then
  echo "4. コンテナ内での動作確認:"
  echo "   docker compose exec n8n twitter search 'Dify' --json --max 1"
else
  echo "4. n8n 起動後にコンテナ内で確認:"
  echo "   docker compose up -d"
  echo "   docker compose exec n8n twitter search 'Dify' --json --max 1"
fi
