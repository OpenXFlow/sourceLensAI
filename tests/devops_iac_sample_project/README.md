# Multi-Tier Web Application Infrastructure as Code

This project uses Terraform, Ansible, and Docker to define and deploy a simple two-tier web application.

## Architecture:
1.  **Terraform (`terraform/`)**: Provisions the core cloud infrastructure, including a VPC, subnets, and two virtual machines (one for the web server, one for the application server).
2.  **Ansible (`ansible/`)**: Configures the provisioned servers. It generates a dynamic inventory from Terraform's output, installs Docker, and deploys the application containers using a Docker Compose template.
3.  **Docker (`app/`)**: Contains the Dockerfile for the Python Flask application.

## Deployment Workflow:
1.  Run `terraform apply` to create the infrastructure.
2.  Terraform will output the IP addresses of the created servers.
3.  Ansible uses these IPs (via an inventory file) to connect and run the `playbook.yml`.
4.  The playbook deploys the web and app containers.