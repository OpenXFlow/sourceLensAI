output "web_server_ip" {
  description = "Public IP address of the Web Server instance."
  value       = aws_instance.web_server.public_ip
}

output "app_server_ip" {
  description = "Public IP address of the App Server instance."
  value       = aws_instance.app_server.public_ip
}