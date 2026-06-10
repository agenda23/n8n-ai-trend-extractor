#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DOCKER_TGZ="${ROOT_DIR}/docker/x-trends-0.1.0.tgz"
SRC_TGZ="${HOME}/.local/share/x-trends/x-trends-0.1.0.tgz"
SRC_REPO="/Volumes/SSD/workspace/twitter-cli-test"

echo "=== x-trends Docker セットアップ ==="
echo ""

if [[ -f "${DOCKER_TGZ}" ]]; then
  echo "1. tarball 既存: ${DOCKER_TGZ}"
elif [[ -f "${SRC_TGZ}" ]]; then
  echo "1. tarball をコピー: ${SRC_TGZ} → ${DOCKER_TGZ}"
  cp "${SRC_TGZ}" "${DOCKER_TGZ}"
elif [[ -d "${SRC_REPO}" ]]; then
  echo "1. ソースから pack: ${SRC_REPO}"
  (cd "${SRC_REPO}" && pnpm pack)
  cp "${SRC_REPO}/x-trends-"*.tgz "${DOCKER_TGZ}"
else
  echo "ERROR: x-trends tarball が見つかりません。"
  echo "  - ${SRC_TGZ} を配置するか"
  echo "  - ${SRC_REPO} で pnpm pack してください"
  exit 1
fi

echo ""
echo "2. X 認証（TWITTER_AUTH_TOKEN）"
echo "   .env または ~/.config/x-trends/.env に設定してください"
echo ""
echo "3. 起動:"
echo "   docker compose up -d --build"
echo ""
echo "4. 疎通確認:"
echo "   curl http://localhost:3920/health"
echo "   curl 'http://localhost:3920/api/v1/search?query=Dify&count=1'"
