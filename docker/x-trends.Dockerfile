FROM node:22-alpine

RUN apk add --no-cache wget

COPY x-trends-0.1.0.tgz /tmp/x-trends.tgz
RUN npm install -g /tmp/x-trends.tgz && rm /tmp/x-trends.tgz

EXPOSE 3920

# `x-trends serve` は commander 完了後に process.exit するため index.js を直接起動
CMD ["node", "/usr/local/lib/node_modules/x-trends/dist/index.js"]
