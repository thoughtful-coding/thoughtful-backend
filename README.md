# Thoughtful Coding Backend

Backend API for the Thoughtful Coding learning platform — a serverless REST API built on AWS Lambda, API Gateway, and DynamoDB. Handles user authentication (Google OAuth), progress tracking, AI-powered feedback on student code submissions (PRIMM and Reflection sections), and an instructor portal.

**Live site:** https://thoughtful-coding.github.io/ | **Project:** https://github.com/thoughtful-coding

## Related Repositories

| Repository | Description |
|------------|-------------|
| [thoughtful-coding.github.io](https://github.com/thoughtful-coding/thoughtful-coding.github.io) | React frontend (deployed to GitHub Pages) |
| [thoughtful-backend](https://github.com/thoughtful-coding/thoughtful-backend) | Python Lambda handlers (this repo) |
| [thoughtful-deploy-cdk](https://github.com/thoughtful-coding/thoughtful-deploy-cdk) | AWS CDK infrastructure |

## Development Setup

Initialize:
- `cd ${THIS_FOLDER}`
- `python3 -m venv .venv`
- `source .venv/bin/activate`
- `pip3 install -r requirements.txt`

Test:
- `export PYTHONPATH=$PYTHONPATH:$(pwd)/src`
- `python3 -m pytest test`

## CI/CD Pipeline

The GitHub Actions workflow automatically:
1. Runs linting (Black formatter check)
2. Runs tests with coverage
3. Builds Docker image and pushes to ECR
4. Triggers CDK deployment in the infrastructure repository

### Required GitHub Secrets

To enable automatic CDK deployment after Docker image is built, configure these repository secrets:

- **`INFRA_REPO_TOKEN`**: GitHub Fine-grained Personal Access Token
  - Create at: https://github.com/settings/personal-access-tokens/new
  - Resource owner: `thoughtful-coding` (organization)
  - Repository access: Only select repositories → `thoughtful-deploy-cdk`
  - Repository permissions:
    - **Contents**: Read (required for repository dispatch)
    - **Metadata**: Read (automatically included)
  - Note: May require organization approval depending on your org settings

- **`INFRA_REPO_OWNER`**: `thoughtful-coding`
  - The GitHub organization/user that owns the CDK repository

- **`INFRA_REPO_NAME`**: `thoughtful-deploy-cdk`
  - The CDK repository name

### Workflow Trigger Flow

1. Push to `main` → Backend workflow builds Docker image
2. Image pushed to ECR with tags: `<commit-sha>` and `prod`
3. Backend workflow triggers CDK workflow via `repository_dispatch`
4. CDK workflow deploys Lambda functions with the new image tag

See `.github/workflows/deploy.yml` for full workflow details.
