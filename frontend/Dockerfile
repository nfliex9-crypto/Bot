FROM ghcr.io/cirruslabs/flutter:3.19.0 AS builder

WORKDIR /app
COPY pubspec.yaml pubspec.lock* ./
RUN flutter pub get

COPY . .
ARG API_BASE_URL=http://localhost:8000
RUN flutter build web --release --dart-define=API_BASE_URL=$API_BASE_URL

FROM nginx:alpine
COPY --from=builder /app/build/web /usr/share/nginx/html
COPY nginx_flutter.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
