> Previously, we looked at [Containerization (Docker)](05_containerization-docker.md).

# Chapter 6: Docker Compose
Let's begin exploring this concept. This chapter will introduce Docker Compose, a tool for defining and managing multi-container Docker applications. We'll cover its purpose, key concepts, and how to use it within the context of our sample project.
**Why Docker Compose?**
Imagine you're building a website that needs both a web server (like Nginx) and a backend application (like a Flask API). You could run each of these in separate Docker containers. But how do you manage them together? How do you ensure they can communicate? This is where Docker Compose comes in.
Docker Compose is like an orchestrator for your Docker containers. Instead of manually starting and linking containers, you define all your application's services, networks, and volumes in a single `docker-compose.yml` file. Then, with a single command (`docker-compose up`), Docker Compose takes care of building, starting, and linking all the containers based on your configuration.
**Key Concepts**
*   **`docker-compose.yml`:** This is the heart of Docker Compose. It's a YAML file that describes your application's services, networks, volumes, and other configurations.
*   **Services:** Each service in the `docker-compose.yml` file represents a Docker container. You define the image to use, the ports to expose, environment variables, dependencies, and other container-specific settings.
*   **Networks:** Docker Compose automatically creates a network for your application, allowing containers to communicate with each other using their service names as hostnames.
*   **Volumes:** Volumes allow you to persist data across container restarts. You can define volumes in your `docker-compose.yml` file to store data outside of the container's filesystem.
**How it Works**
Docker Compose reads the `docker-compose.yml` file and uses it to create and manage the Docker containers specified in the file. Here's a simplified overview of the process:
1.  **Define Services:** You specify the services your application needs in the `docker-compose.yml` file.
2.  **Configure Dependencies:** You can define dependencies between services, so Docker Compose starts them in the correct order.
3.  **Build Images (Optional):** If your `docker-compose.yml` specifies to build an image from a Dockerfile, Docker Compose will build the image for you.
4.  **Create and Start Containers:** Docker Compose creates and starts the containers based on the service definitions in the `docker-compose.yml` file.
5.  **Manage Networks and Volumes:** Docker Compose creates and manages the networks and volumes specified in the `docker-compose.yml` file, ensuring that containers can communicate with each other and persist data.
**Code Examples**
Here are examples from our project, illustrating how Docker Compose is used:
```python
--- File: app/docker-compose.yml ---
# Docker Compose for local development
version: '3.8'
services:
  app:
    build: .
    ports:
      - "5000:5000"
    volumes:
      - .:/app
```
This `docker-compose.yml` file (located in the `app/` directory) is used for local development. It defines a single service called `app`.
*   `build: .` tells Docker Compose to build an image from the Dockerfile in the current directory (`.`).
*   `ports: - "5000:5000"` maps port 5000 on the host machine to port 5000 on the container.
*   `volumes: - .:/app` mounts the current directory (`.`) into the `/app` directory in the container. This allows you to make changes to your code and see them reflected in the running container without having to rebuild the image.
Now, let's look at the `docker-compose.yml.j2` template used with Ansible:
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
This `docker-compose.yml.j2` file (a Jinja2 template) is used to generate a `docker-compose.yml` file based on Ansible variables. It demonstrates the power of combining Configuration Management with Docker Compose.
*   `{% if 'webservers' in group_names %}` and `{% if 'appservers' in group_names %}`: These are Jinja2 conditional statements that allow you to define services based on the Ansible group the host belongs to.
*   `image: nginx:latest` and `image: my-flask-app:1.0`: These specify the Docker images to use for the web and app services, respectively.
*   `DATABASE_URL={{ lookup('env', 'DATABASE_URL') | default('postgresql://user:pass@host:port/db') }}`: This sets the `DATABASE_URL` environment variable for the `app` service. The `lookup('env', 'DATABASE_URL')` function retrieves the value of the `DATABASE_URL` environment variable on the Ansible controller. If the environment variable is not set, the `default` filter provides a default value.
*   `restart: always`: Instructs Docker to always restart the container if it exits.
**Relationship to Other Chapters**
Docker Compose builds upon the concepts introduced in [Containerization (Docker)](06_containerization-docker.md). It's used alongside [Ansible Playbook](08_ansible-playbook.md) to automate the deployment and configuration of multi-container applications.
This concludes our look at this topic.

> Next, we will examine [Infrastructure as Code (IaC)](07_infrastructure-as-code-iac.md).


---

*Generated by [SourceLens AI](https://github.com/openXFlow/sourceLensAI) using LLM: `gemini` (cloud) - model: `gemini-2.0-flash` | Language Profile: `Python`*