# Production NGINX Reverse Proxy Dockerfile
FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/nginx.conf

EXPOSE 80 443

HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
  CMD wget -qO- http://localhost/health/live || exit 1

CMD ["nginx", "-g", "daemon off;"]
