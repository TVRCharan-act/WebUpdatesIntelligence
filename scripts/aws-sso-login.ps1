[CmdletBinding()]
param(
    [string]$Profile = $(if ($env:AWS_PROFILE) { $env:AWS_PROFILE } else { "actalyst-dev" }),
    [switch]$Configure,
    [switch]$UseDeviceCode
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command aws -ErrorAction SilentlyContinue)) {
    throw "AWS CLI v2 is required. Install it, then rerun this script."
}

if ($Configure) {
    $configureArgs = @("configure", "sso", "--profile", $Profile)
    if ($UseDeviceCode) {
        $configureArgs += "--use-device-code"
    }

    & aws @configureArgs
    if ($LASTEXITCODE -ne 0) {
        throw "AWS SSO profile configuration did not complete."
    }
}

& aws sso login --profile $Profile
if ($LASTEXITCODE -ne 0) {
    throw "AWS SSO login did not complete."
}

# Confirm the temporary role credentials work without printing account details.
$null = & aws sts get-caller-identity --profile $Profile --output json
if ($LASTEXITCODE -ne 0) {
    throw "SSO login succeeded, but the profile cannot obtain AWS role credentials."
}

Write-Host "AWS SSO login succeeded for profile '$Profile'."
