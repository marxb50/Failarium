$ErrorActionPreference = "Stop"

uv tool install --editable $PSScriptRoot\..
failarium --json doctor
