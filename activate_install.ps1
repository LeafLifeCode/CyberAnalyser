# Run this instead of the normal activate when installing packages:
#   .\activate_install.ps1
$env:TEMP = 'D:\pip-tmp'
$env:TMP  = 'D:\pip-tmp'
New-Item -ItemType Directory -Force -Path 'D:\pip-tmp' | Out-Null
New-Item -ItemType Directory -Force -Path 'D:\pip-cache' | Out-Null
& .\.venv\Scripts\Activate.ps1
Write-Host 'Venv activated with D: drive temp/cache for pip installs.'