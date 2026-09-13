# FORGE frontend — build CRA e serve estatico com nginx (proxy /api -> backend)
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
COPY --from=build /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
