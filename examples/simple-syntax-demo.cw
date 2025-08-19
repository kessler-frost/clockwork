# Simple Syntax Demo - Deploy a web service with minimal configuration

deploy "web-app" {
  port = 8080
  image = "nginx:latest"
  env = {
    SERVER_NAME = "my-web-app"
    DEBUG = "false"
  }
  health_path = "/health"
}

create_file "/app/config.json" {
  content = {
    name = "my-web-app"
    port = 8080
    environment = "production"
  }
  mode = "0644"
}

run_command "database-setup" {
  script = "npm run migrate && npm run seed"
  working_dir = "/app"
  timeout = "60s"
}

verify_http "health-check" {
  url = "http://localhost:8080/health"
  status = 200
  timeout = "30s"
}

wait_for "database-ready" {
  service = "postgres"
  timeout = "120s"
}