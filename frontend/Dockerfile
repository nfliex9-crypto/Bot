FROM ghcr.io/cirruslabs/flutter:stable AS build

WORKDIR /app

COPY pubspec.yaml ./pubspec.yaml
RUN flutter create . --platforms web --project-name trading_dashboard

COPY lib ./lib

RUN flutter pub get
RUN flutter build web --release --dart-define=API_BASE_URL=/api

FROM nginx:1.27-alpine

COPY --from=build /app/build/web /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
