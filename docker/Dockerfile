# twitter-cli（Python）をビルド
FROM python:3.12-alpine AS twitter-cli-builder
RUN apk add --no-cache gcc musl-dev libffi-dev \
  && pip install --no-cache-dir twitter-cli \
  && apk del gcc musl-dev

# n8n 本体（Hardened Alpine）に Python ランタイム + CLI をコピー
FROM n8nio/n8n:2.23.4

USER root

COPY --from=twitter-cli-builder /usr/local/bin/python3 /usr/local/bin/python3
COPY --from=twitter-cli-builder /usr/local/bin/python3.12 /usr/local/bin/python3.12
COPY --from=twitter-cli-builder /usr/local/bin/twitter /usr/local/bin/twitter
COPY --from=twitter-cli-builder /usr/local/lib/python3.12 /usr/local/lib/python3.12
COPY --from=twitter-cli-builder /usr/local/lib/libpython3.12.so* /usr/local/lib/

ENV PYTHONPATH=/usr/local/lib/python3.12/site-packages \
    LD_LIBRARY_PATH=/usr/local/lib

RUN mkdir -p /home/node/.cache/twitter-cli \
  && chown -R node:node /home/node/.cache

USER node
