export TENANT_SUBDOMAIN_ID="tiger-prod"
export IDIRA_IDENTITY_URL="https://${TENANT_SUBDOMAIN_ID}.cyberark.cloud/api/idadmin"
export IDIRA_ADMIN_USER="adminbot@tiger.com"
# Store the confidential client secret in a keyring to keep it out of the codebase.
export IDIRA_ADMIN_PWD=$(keyring get cybrid tigerbotpwd)
export SECAI_TENANT_URL="https://${TENANT_SUBDOMAIN_ID}.aigw.cyberark.cloud"
export SECAI_TOKEN=$(uv run python3 get-auth-token.py)
export SECAI_TIMEOUT="30"
export SECAI_OUTPUT="table"
