# Build stage
FROM node:22-alpine AS build

WORKDIR /app

# Configuração da URL do API Gateway durante o build do Vite
ARG VITE_API_GATEWAY_URL
ENV VITE_API_GATEWAY_URL=${VITE_API_GATEWAY_URL}

# Instalação das dependências
COPY package*.json ./
RUN npm ci

# Compilação da aplicação React
COPY . .
RUN npm run build

# Production stage
FROM nginx:1.28-alpine AS production

# Publicação dos arquivos estáticos gerados pelo Vite
COPY --from=build /app/dist /usr/share/nginx/html

# Configuração do Nginx para suportar as rotas do React Router
RUN printf '%s\n' \
    'server {' \
    '    listen 80;' \
    '    server_name _;' \
    '    root /usr/share/nginx/html;' \
    '    index index.html;' \
    '' \
    '    location / {' \
    '        try_files $uri $uri/ /index.html;' \
    '    }' \
    '}' \
    > /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
