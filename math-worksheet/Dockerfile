FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install --omit=dev --no-fund --no-audit

COPY server.js ./
COPY public ./public

# 共有データの永続化用（docker run -v や compose の volume でマウントする想定）
RUN mkdir -p data

ENV PORT=3000
EXPOSE 3000

CMD ["node", "server.js"]
