FROM ghcr.io/cirruslabs/flutter:stable AS build

WORKDIR /app

COPY frontend/pubspec.yaml /app/pubspec.yaml
RUN flutter create --platforms web . --project-name ai_trading_dashboard --org com.example

COPY frontend/pubspec.yaml /app/pubspec.yaml
COPY frontend/lib /app/lib

RUN flutter pub get

ARG FLUTTER_API_BASE_URL=http://localhost:8000
RUN flutter build web --release --dart-define=API_BASE_URL=${FLUTTER_API_BASE_URL}

FROM nginx:1.27-alpine
COPY frontend/nginx/default.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/build/web /usr/share/nginx/html
