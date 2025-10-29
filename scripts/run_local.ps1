# Run local (Windows PowerShell): builds and starts docker compose
param(
  [switch]$Rebuild = $false
)
$ErrorActionPreference="Stop"

if(Test-Path ".env" -PathType Leaf){
  Write-Host "Using .env" -ForegroundColor Green
}else{
  Copy-Item ".env.example" ".env"
  Write-Host "Created .env from example. Fill values." -ForegroundColor Yellow
}

if($Rebuild){
  docker compose build --no-cache
}
docker compose up --build
