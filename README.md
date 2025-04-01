# Readme

## Hosting

### Pre-requisites

We use copilot for deployment to AWS. The AWS environments are protected by PennKey authentication.

You will need the following, much of which is already configured in the VSCode devcontainer (see local dev section below):

- A PennKey account
- Access to the BCFG AWS account (336162656437) through the PennKey

And the following tools

1. AWS copilot CLI: https://aws.github.io/copilot-cli/
1. AWS CLI: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html
1. aws-federated-auth package, which allows for auth via PennKey: pip install git+ssh://git@github.com/upenn/aws-federated-auth.git

Run `aws-federated-auth` to authenticate with PennKey. This will create a new AWS profile in your local AWS credentials file. The token will need to be refreshed by rerunning this command periodically.

When running copilot commands, make sure that the correct profile is configured locally:
```bash
export AWS_PROFILE=bcfg-student-ai-chatbot-AdministratorAccess
```


### Deployment - First Time

These steps only need to be run once per environment (where ENVIRONMENT_NAME = dev, test, or prod)

1. Initialize the app (perform this step once, not once per environment)
    ```bash
    copilot app init wwbp-bcfg-chatbot --domain wwbp-bcfg-chatbot.org
    ```
1. Make some temporary changes for the first deploy only because copilot does not handle order of operations correctly:
    1. Temporarily delete or move out of the copilot directory the redis.yml file
    1. Comment out `access_log: true` in the environment manifest.yml
1. Iniitialize the environment
    ```bash
    copilot env init -n ENVIRONMENT_NAME --container-insights --region us-east-1
    copilot env deploy --name ENVIRONMENT_NAME
    ```
1. Undo the temporary changes you previously made for the first deploy only and then re-deploy:
    ```bash
    copilot env deploy --name ENVIRONMENT_NAME
    ```
1. Initialize the secrets (see Setting and updating secrets section)
1. Initialize the services (perform this step once per service, not once per environment)
    ```bash
    copilot svc init --name web
    copilot svc init --name worker
    copilot svc init --name scheduler
    ```
1. Run first time deploy
    ```bash
    copilot svc deploy --name web --env ENVIRONMENT_NAME
    copilot svc deploy --name worker --env ENVIRONMENT_NAME
    copilot svc deploy --name scheduler --env ENVIRONMENT_NAME
    ```
1. Create an admin user. Set the username and password to the PennKey of the desired user. Authentication is done via PennKey.
    ```bash
    copilot svc exec --name web --env ENVIRONMENT_NAME --command "python manage.py createsuperuser"
    ```

### Deployments

Deployments are automated via BitBucket pipelines. If you want to deploy manually, you can do so using the same command as described above for first-time deployments.

### Setting and updating secrets

The application likely won't work without settings secrets as defined in the various service manifests (manifest.yml files).

```bash
copilot secret init --name SECRET_NAME --values="ENVIRONMENT_NAME=VALUE"
```

## Local Dev

We use devcontainer for local dev in VSCode
1. Install VSCode and Docker Desktop
1. Clone and open the repo
1. When prompted, click "Reopen in Container" in the bottom right corner of the window (or do so via command palette)
1. It should finish building - confirm that all containers are running. If not, troubleshoot failures based on logs
1. Run `make migrate` to apply migrations to the postgres database
1. Launch the server via the launch command "Python: Django Web"
  1. If this fails because Django isn't found, set your VSCode python interpreter path via the command palette to match that returned when you inspect the location of django pip package (eg via pip show django)
1. The server should be running at http://localhost:8000
1. Create an admin via `python manage.py createsuperuser`
1. You can access the admin at http://localhost:8000/admin and login with the superuser credentials

### Dev tools
- Linting: we use ruff for linting, black for formatting. Run `make lint` to lint the codebase
- Package Management: We use pipenv for package management. Modify the Pipfile as needed, run `make requirements`, and then rebuild the devcontainer
- Testing: We use pytest for testing. Run `make test` to run the tests, or run from the test explorer in VSCode. Keep an eye on coverage reports.

### Continous Integration (CI)

We use BitBucket pipelines for CI. The pipeline is defined in the `bitbucket-pipelines.yml` file. The pipeline executes tests, linting, and security dependency checks. It also automatically deployes upon commits to specific branches:
* `main` - deploys to prod
* `staging` - deploys to test
* `develop` - deploys to dev

The runner is hosted in EC2 on the same AWS account as the application.
