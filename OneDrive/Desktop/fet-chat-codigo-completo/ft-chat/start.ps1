Set-Location -Path $PSScriptRoot
if (-not $env:PORT) { $env:PORT = "3000" }
New-Item -ItemType Directory -Force -Path data, "public\uploads" | Out-Null

$py = $null
if (Get-Command py -ErrorAction SilentlyContinue) { $py = "py" }
elseif (Get-Command python -ErrorAction SilentlyContinue) { $py = "python" }
else {
  Write-Host "Python nao encontrado. Instale em https://www.python.org/downloads/"
  Write-Host "Marque a opcao: Add python.exe to PATH"
  exit 1
}

Write-Host "Iniciando Chat Aberto em http://localhost:$($env:PORT)"
while ($true) {
  if ($py -eq "py") { py -3 -u server.py } else { python -u server.py }
  Write-Host "Servidor saiu. Subindo de novo em 1s..."
  Start-Sleep -Seconds 1
}
