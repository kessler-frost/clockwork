# Hello World - Minimal Service Example

variable "message" {
  type        = "string"
  default     = "Hello from Clockwork!"
  description = "Welcome message to display"
}

resource "service" "hello" {
  name    = "hello-world"
  image   = "nginx:alpine"
  ports   = [{
    external = 8080
    internal = 80
  }]

  environment = {
    WELCOME_MESSAGE = var.message
  }
}