# FORGE frontend — artefato CRA validado e servido pelo nginx (proxy /api -> backend).
# O pacote e gerado com REACT_APP_BACKEND_URL="" e sem source maps. Mantemos a
# compilacao fora da VPS para que o deploy nao dispute memoria com o app em producao.
FROM nginx:1.27-alpine
ADD forge-frontend-build.tar.gz /usr/share/nginx/html/
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
