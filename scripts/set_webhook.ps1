
param(
  [string]$BotToken = $env:TELEGRAM_BOT_TOKEN,
  [string]$PublicUrl = $env:PUBLIC_URL,
  [string]$Route = $(if($env:WEBHOOK_ROUTE){$env:WEBHOOK_ROUTE}else{"/webhook"})
)
if(-not $BotToken){ throw "TELEGRAM_BOT_TOKEN missing" }
if(-not $PublicUrl){ throw "PUBLIC_URL missing" }
if(-not $Route.StartsWith("/")){ $Route = "/" + $Route }
$setUrl = "https://api.telegram.org/bot$BotToken/setWebhook?url=$($PublicUrl.TrimEnd('/'))$Route&drop_pending_updates=true"
Write-Host "Setting webhook: $setUrl"
try{
  $res = Invoke-RestMethod -Uri $setUrl -Method Get -TimeoutSec 20
  $res | ConvertTo-Json -Depth 6
}catch{
  Write-Error $_
}
