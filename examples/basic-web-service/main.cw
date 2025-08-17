# Basic Web Service Example

variable "app_name" {
  type        = "string"
  default     = "my-web-app"
  description = "Name of the web application"
}

variable "port" {
  type        = "number"
  default     = 8080
  description = "External port for the web service"
}

variable "image" {
  type    = "string"
  default = "nginx:latest"
}

resource "service" "web" {
  name    = var.app_name
  image   = var.image
  ports   = [{
    external = var.port
    internal = 80
  }]
  
  environment = {
    SERVER_NAME = var.app_name
    PORT        = "80"
  }
  
  health_check {
    path     = "/"
    interval = "30s"
    timeout  = "5s"
    retries  = 3
  }
}

output "web_url" {
  value       = "http://localhost:${var.port}"
  description = "URL to access the web service"
}