# Environment variables for the Secure AI SDK

# The tenant subdomain ID is the unique identifier for the tenant
# in Idira's cloud. It is used to construct the URLs for the Identity API
# and the Secure AI API. It is the "friendly" name for the tenant.
export TENANT_SUBDOMAIN_ID="tiger-prod"
export IDIRA_IDENTITY_URL="https://${TENANT_SUBDOMAIN_ID}.cyberark.cloud/api/idadmin"

# The admin user is an OAuth confidential client (service account) in
# the tenant, with the Secure AI Admin role. The client secret is used to
# authenticate the admin user and to get an access token for API calls. Best
# practice is to store the client secret in a keyring to keep it out of
# the codebase.
export IDIRA_ADMIN_USER="adminbot@tiger.com"
export IDIRA_ADMIN_PWD=$(keyring get cybrid tigerbotpwd)
export SECAI_TENANT_URL="https://${TENANT_SUBDOMAIN_ID}.aigw.cyberark.cloud"

# get-auth-token.py is a helper script that uses the admin credentials and
# identity URL to authenticate the user and retrieve an access token.
export SECAI_TOKEN=$(uv run python3 get-auth-token.py)

# SECAI_TIMEOUT is the timeout for API calls in seconds. It can be overridden
# by setting the environment variable before running the script. The default
# is 30 seconds.
export SECAI_TIMEOUT="30"

# SECAI_OUTPUT is the output format for the API calls. It can be "json"
# "table", or "quiet". The default is "table".
export SECAI_OUTPUT="table"

# SECAI_DEBUG is a flag to enable debug logging for the API calls.
# 0=disabled, 1=enabled. The default is 0 (disabled).
export SECAI_DEBUG=0
