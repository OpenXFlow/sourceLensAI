# Server Automation Scripts

This project contains a collection of shell scripts for automating common server administration and application deployment tasks. It includes examples for both Linux (Bash) and Windows (PowerShell/Batch) environments.

## Scripts
- **`backup`**: Creates a compressed archive of application data and database dumps.
- **`deploy`**: Pulls the latest application code from a Git repository, installs dependencies, and restarts the service.
- **`monitor`**: Checks the status of critical services (e.g., web server, database).

## Orchestration
The `Makefile` in the root directory provides simple commands (`make backup`, `make deploy`) to run the Linux scripts.