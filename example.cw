# Example Clockwork Configuration

variable "app_name" {
  type        = "string"
  default     = "example-app"
  description = "Application name"
}

variable "port" {
  type    = "number"
  default = 8080
}

resource "service" "app" {
  name    = var.app_name
  image   = "nginx:latest"
  ports   = [{
    external = var.port
    internal = 80
  }]
  
  retries = 3
  timeout = 30
  
  health_check {
    path     = "/"
    interval = "30s"
  }
}

output "app_url" {
  value = "http://localhost:${var.port}"
}