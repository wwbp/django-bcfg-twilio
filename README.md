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
1. Create a DNS record to route traffic to the load balancer in Route53
    1. Find the load balancer via ECS > your cluster > web service > load balancer
    1. Create a new record set in Route53 for the domain you specified in the app init step
    1. Set the type to A - IPv4 address, with the name being the subdomain you want to use (e.g. dev.wwbp-bcfg-chatbot.org)
    1. Toggle Alias to True
    1. Choose "Alias to Application and Classic Load Balancer" for the alias target
    1. Choose the region where the load balancer is located
    1. Choose the load balancer you found in the first step from the list
    1. Leave the remainder of the config untouched (TTL 300s, simple routing)
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

#### Runners

##### New Runner

We use self-hosted runners that are hosted in EC2 on the same AWS account as the application.

To create a new runner
1. Launch a new EC2 instance with a name you choose (eg "Bitbucket Pipeline Runner")
    1. Use default AWS Linux AMI
    1. Set size to t2.medium
    1. Use a new or existing keypair so you can access via SSH for configuration (use existing if you already have the private key)
    1. Change network settings to choose a public subnet and allow ssh traffic only from your machine
    1. Launch instance
1. Now configure it via ssh once launch. You'll need the ssh key from the keypair you used or generated in the launch step. You can grab the connection command from AWS by navigating to the instance > Connect button (top right) > SSH client tab
    1. In Bitbucket, go to Repositories > your repo > Settings > Repository settings > Runners
    1. Click "Add runner"
    1. You'll be given a new command. Keep that for a moment
    1. Back in the SSH session, run
        ```bash
        sudo -s
        dnf install docker -y
        systemctl start docker
        usermod -a -G docker ec2-user
        systemctl enable docker
        ```
    1. Now create a new service to keep the docker container running
        ```bash
        cat > /etc/systemd/system/docker-runner.service
        ```
    1. Then paste a command into the new service file that looks like the following, but make sure to update the various variables (`REPLACE_WITH_`) that you grab from the command that Bitbucket has presented
        ```
        [Unit]
        Description=Run Docker Container for Bitbucket Pipelines Runner
        After=docker.service
        Requires=docker.service

        [Service]
        Restart=on-failure
        ExecStartPre=-/usr/bin/docker rm -f runner-76368873-9fa8-5b0e-ba95-f179a2335080
        ExecStartPre=/bin/sleep 5
        ExecStart=/usr/bin/docker container run -d \
            -v /tmp:/tmp \
            -v /var/run/docker.sock:/var/run/docker.sock \
            -v /var/lib/docker/containers:/var/lib/docker/containers:ro \
            -e ACCOUNT_UUID={REPLACE_WITH_YOUR_ACCOUNT_UUID} \
            -e REPOSITORY_UUID={REPLACE_WITH_REPOSITORY_UUID} \
            -e RUNNER_UUID={REPLACE_WITH_RUNNER_UUID} \
            -e RUNTIME_PREREQUISITES_ENABLED=true \
            -e OAUTH_CLIENT_ID=REPLACE_WITH_OAUTH_CLIENT_ID \
            -e OAUTH_CLIENT_SECRET=REPLACE_WITH_OAUTH_CLIENT_SECRET \
            -e WORKING_DIRECTORY=/tmp \
            --name runner-REPLACE_WITH_NAME \
            docker-public.packages.atlassian.com/sox/atlassian/bitbucket-pipelines-runner

        [Install]
        WantedBy=multi-user.target
        ```
    1. Set this service to autostart and then start it
        ```bash
        systemctl daemon-reload
        systemctl enable docker-runner
        systemctl start docker-runner
        ```
    1. Back in Bitbucket, you can click through the rest of the dialog and after a minute you should see the new runner listed as "Online" in the runners page
1. Setup docker prune to run regularly so that we don't run out of space
    1. Back in the ssh session, run
        ```bash
        sudo -s
        yum install cronie -y
        systemctl enable crond.service
        systemctl start crond.service
        crontab -e
        ```
    1. Add the following line to the crontab file to run docker prune every 6 hours
        ```
        0 */6 * * * /usr/bin/docker system prune -f
        ```
    1. Save and exit the crontab file

##### Fix: docker: command not found

See https://support.atlassian.com/bitbucket-cloud/kb/docker-command-not-found-error-while-running-docker-commands-in-self-hosted-runner/

Quickest fix:
1. SSH into the instance (see steps above)
1. Run `ls -l /tmp` and identify the runner ID by the single folder whose name is simply a GUID
1. Confirm that the docker subdirectory is empty `ls -l /tmp/{RUNNER_ID}/docker`
1. Remove the docker subdirectory `sudo rm -rf /tmp/{RUNNER_ID}/docker`
1. Restart the instance from the AWS console
