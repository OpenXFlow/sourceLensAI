> Previously, we looked at [Cloud Provider (AWS)](03_cloud-provider-aws.md).

# Chapter 4: Configuration Management
Let's begin exploring this concept. In this chapter, we'll delve into configuration management, specifically how Ansible is used to automate the setup of our servers and deploy our application.
Configuration management addresses a fundamental problem: consistently and reliably configuring multiple servers. Imagine manually installing Docker and all its dependencies on ten, twenty, or even a hundred servers. It's tedious, error-prone, and difficult to keep consistent over time. Configuration management tools like Ansible solve this by defining the desired state of your servers in code, allowing you to automate the entire configuration process.
Think of it like using a recipe to bake a cake. Instead of trying to remember all the ingredients and steps each time, you follow the recipe, ensuring that every cake you bake is consistent. Ansible acts as the "recipe book" for your servers.
**Key Concepts:**
*   **Idempotency:** A crucial principle. Running an Ansible playbook multiple times should result in the same outcome. If Docker is already installed, running the Ansible task to install Docker again won't break anything or install it twice.
*   **Desired State:** You define the state you *want* your servers to be in, rather than specifying a sequence of commands to execute. Ansible figures out how to achieve that state.
*   **Playbooks:** YAML files that contain a series of tasks to be executed on target hosts. Our `ansible/playbook.yml` is the central playbook for this project.
*   **Roles:** A way to organize and reuse Ansible tasks. We use a role called `docker_app` in our playbook.
*   **Inventory:** A list of the servers you want to manage. In our case, the `ansible/inventory.ini` file (or, ideally, a dynamically generated inventory from Terraform) provides this list.
**How it Works in Our Project:**
In our project, configuration management (using Ansible) comes *after* infrastructure provisioning (using Terraform, covered in [Terraform Resources](04_terraform-resources.md)). Terraform creates the virtual machines, and Ansible then takes over to:
1.  Install Docker and its dependencies.
2.  Deploy our application containers using Docker Compose.
3.  Configure other necessary settings on the servers.
Here's a sequence diagram to illustrate the interaction between Terraform and Ansible:
```mermaid
sequenceDiagram
    participant Terraform
    participant Ansible
    participant TargetServer
    Terraform->>Terraform: `terraform apply`
    activate Terraform
    Terraform->>CloudProvider: Request VMs
    CloudProvider-->>Terraform: VM details (IPs)
    deactivate Terraform
    Terraform->>Ansible: Output IPs to inventory
    Ansible->>Ansible: Read inventory
    activate Ansible
    Ansible->>TargetServer: Connect via SSH
    activate TargetServer
    TargetServer-->>Ansible: Authentication Success
    Ansible->>TargetServer: Execute Ansible tasks (install Docker, deploy containers)
    TargetServer-->>Ansible: Task Completion Status
    deactivate TargetServer
    Ansible-->>Terraform: Playbook completed
    deactivate Ansible
```
This diagram shows how Terraform first provisions the infrastructure (the VMs), and then passes the IP addresses of those VMs to Ansible. Ansible then connects to the VMs and executes the tasks defined in the playbook to configure them.
Let's examine some relevant code snippets:
```python
---
- name: Deploy Multi-Tier Application
  hosts: all
  become: true
  tasks:
    - name: Update apt cache
      apt:
        update_cache: yes
        cache_valid_time: 3600
    - name: Install required system packages
      apt:
        name:
          - apt-transport-https
          - ca-certificates
          - curl
          - gnupg
          - lsb-release
        state: present
    - name: Add Docker GPG key
      apt_key:
        url: https://download.docker.com/linux/ubuntu/gpg
        state: present
    - name: Add Docker repository
      apt_repository:
        repo: deb [arch=amd64] https://download.docker.com/linux/ubuntu {{ ansible_lsb.codename }} stable
        state: present
    - name: Install Docker and Docker Compose
      apt:
        name:
          - docker-ce
          - docker-ce-cli
          - containerd.io
          - docker-compose-plugin
        state: present
    - name: Include the docker_app role to deploy containers
      include_role:
        name: docker_app
```
This is a snippet from our `ansible/playbook.yml`. The `hosts: all` line indicates that these tasks will be executed on all servers defined in our inventory. The tasks themselves use the `apt` module to install necessary packages for Docker.  After installing docker, it includes the `docker_app` role.
The `docker_app` role then configures Docker Compose and uses it to deploy the containers. As you'll see in [Docker Compose](07_docker-compose.md) and [Application Deployment](09_application-deployment.md), this allows us to define the relationship between our web and app containers.
The Ansible playbook benefits from Jinja2 templating in `ansible/roles/docker_app/templates/docker-compose.yml.j2`, allowing for conditional container deployment based on the target server's group. This is essential for managing the distinct roles of our web and app servers. The template checks if a server belongs to the `webservers` or `appservers` group (defined in the inventory) and deploys the corresponding container. For example:
```python
--- File: ansible/roles/docker_app/templates/docker-compose.yml.j2 ---
# Jinja2 template for Docker Compose file
# Allows for dynamic configuration based on Ansible variables.
version: '3.8'
services:
  {% if 'webservers' in group_names %}
  web:
    image: nginx:latest
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
  {% endif %}
  {% if 'appservers' in group_names %}
  app:
    image: my-flask-app:1.0 # Assumes this image is pre-built and available
    restart: always
    environment:
      - DATABASE_URL={{ lookup('env', 'DATABASE_URL') | default('postgresql://user:pass@host:port/db') }}
    ports:
      - "5000:5000"
  {% endif %}
```
Ansible also utilizes the concepts of [Ansible Playbook](08_ansible-playbook.md).
This concludes our look at this topic.

> Next, we will examine [Containerization (Docker)](05_containerization-docker.md).


---

*Generated by [SourceLens AI](https://github.com/openXFlow/sourceLensAI) using LLM: `gemini` (cloud) - model: `gemini-2.0-flash` | Language Profile: `Python`*