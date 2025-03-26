# Readme

## Local Dev

We use devcontainer for local dev in VSCode
1. Install VSCode and Docker Desktop
1. Clone and open the repo
1. When prompted, click "Reopen in Container" in the bottom right corner of the window (or do so via command palette)
1. It should finish building - confirm that all containers are running. If not, troubleshoot failures based on logs
1. Run `make migrate` to apply migrations to the mysql database
1. Launch the server via the launch command "Python: Django Web"
  1. If this fails because Django isn't found, set your VSCode python interpreter path via the command palette to match that returned when you inspect the location of django pip package (eg via pip show django)
1. The server should be running at http://localhost:8000
1. Create an admin via `python manage.py createsuperuser`
1. You can access the admin at http://localhost:8000/admin and login with the superuser credentials
