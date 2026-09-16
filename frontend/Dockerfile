# FORGE frontend — duas pecas servidas pelo mesmo nginx:
#
#   /            a landing (Vite + React + Three.js), pagina de venda
#   /login, /app o aplicativo (CRA), o produto em si
#
# Sao dois pacotes separados de proposito. A landing usa Vite 6, Tailwind 4 e Three.js; o
# aplicativo usa CRA com Tailwind 3. Juntar os dois num build so exigiria mudar a landing,
# e a instrucao foi nao mudar nada nela.

# ── Landing ─────────────────────────────────────────────────────────────────────────
FROM node:20-alpine AS landing

WORKDIR /landing

COPY landing/package.json landing/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY landing/ ./
RUN npm run build

# ── Aplicativo ──────────────────────────────────────────────────────────────────────
FROM node:20-alpine AS build

WORKDIR /app

COPY package.json yarn.lock ./
RUN yarn install --frozen-lockfile --network-timeout 600000

COPY . .

# String vazia => a API vira relativa (/api), servida pelo mesmo dominio via nginx.
# CRA congela isso no bundle em tempo de build: mudar depois exige rebuild.
ENV REACT_APP_BACKEND_URL="" \
    GENERATE_SOURCEMAP=false \
    NODE_OPTIONS=--max-old-space-size=2048 \
    CI=false

RUN yarn build

FROM nginx:1.27-alpine

# O aplicativo entra primeiro. O index.html dele vira `app.html`: a raiz passa a ser da
# landing, e o nginx usa `app.html` como destino do fallback de rota do SPA.
COPY --from=build /app/build /usr/share/nginx/html
RUN mv /usr/share/nginx/html/index.html /usr/share/nginx/html/app.html

# A landing por cima. Ela traz o proprio index.html (a raiz), `assets/`, o modelo 3D e as
# capturas. Nao ha colisao: o CRA guarda tudo em `static/`, a landing em `assets/`.
COPY --from=landing /landing/dist /usr/share/nginx/html

COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
