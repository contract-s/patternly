# Deploying to AWS

One EC2 instance (t3.small, Ubuntu 24.04) runs the same Docker Compose stack as local development, with
[`docker-compose.prod.yml`](docker-compose.prod.yml) layered on top. CloudFront in front of it serves HTTPS
on a `*.cloudfront.net` address, so no domain or certificate is needed.

```
browser --HTTPS--> CloudFront --HTTP:80--> EC2 (nginx -> FastAPI -> Postgres)
```

- **Inbound:** only port 80, and only from CloudFront's origin-facing prefix list. There is no SSH; use
  Session Manager.
- **Secrets:** the database password and JWT secret are generated on the instance at first boot and never
  leave it. The tutor's API key is read from the SSM SecureString parameter `/patternly/anthropic-api-key`.
  Without it, the API runs with `--offline`.
- **Data:** Postgres lives on the instance's encrypted root volume. Replacing or terminating the instance
  deletes learner data.

Everything is in [`patternly.yaml`](patternly.yaml), created in the project's Region (us-east-2).

## First deploy

Store the tutor's API key (read from `backend/.env` so it isn't typed or echoed):

```
aws ssm put-parameter --region us-east-2 --name /patternly/anthropic-api-key --type SecureString \
  --value "$(grep '^ANTHROPIC_API_KEY=' backend/.env | cut -d= -f2-)"
```

Create the stack (the default VPC's ID goes in `VpcId`):

```
aws cloudformation create-stack --region us-east-2 --stack-name patternly \
  --template-body file://deploy/patternly.yaml --capabilities CAPABILITY_IAM \
  --parameters ParameterKey=VpcId,ParameterValue=<default-vpc-id>
aws cloudformation wait stack-create-complete --region us-east-2 --stack-name patternly
aws cloudformation describe-stacks --region us-east-2 --stack-name patternly --query 'Stacks[0].Outputs'
```

The stack finishes in about 5 minutes. The instance takes about 10 more to install Docker and build the
images, and CloudFront returns 502 until it's done. The setup log is `/var/log/patternly-setup.log`.

## Deploying new code

Push to `main`, then rerun the setup script, which pulls, rebuilds, and restarts:

```
aws ssm send-command --region us-east-2 --document-name AWS-RunShellScript \
  --targets Key=tag:Name,Values=patternly \
  --parameters 'commands=["/opt/patternly/deploy/setup-instance.sh us-east-2 /patternly"]'
```

Run the same command after adding or changing the API key parameter.

For a shell on the instance: `aws ssm start-session --region us-east-2 --target <InstanceId>` (needs the
Session Manager plugin for the AWS CLI).

## Cost and teardown

About $15/month for the instance, $4 for the public IPv4 address, and a few cents for CloudFront at tester
traffic. To remove everything (this deletes the database):

```
aws cloudformation delete-stack --region us-east-2 --stack-name patternly
aws ssm delete-parameter --region us-east-2 --name /patternly/anthropic-api-key
```

## Limits

- CloudFront reaches the instance over plain HTTP. The security group only admits CloudFront, but traffic
  between CloudFront and the instance isn't encrypted.
- One instance and no backups: a lost instance means lost accounts and history.
- The images build on the instance, so a deploy takes a few minutes and briefly uses most of its memory.
