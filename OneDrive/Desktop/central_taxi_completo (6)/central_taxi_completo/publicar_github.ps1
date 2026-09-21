# Rode DENTRO da pasta do projeto (central_taxi_completo)
Set-Location -Path $PSScriptRoot

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
  Write-Host "Instale o Git: https://git-scm.com/download/win"
  exit 1
}

if (-not (Test-Path .git)) { git init -b main }

git add .gitignore .env.example README.md app.py requirements.txt limpar_frota.py static templates
git status

Write-Host ""
Write-Host "1. Crie o repo em https://github.com/new  (nome: central-taxi-cone-sul)"
Write-Host "2. Rode, trocando SEU_USUARIO:"
Write-Host "   git commit -m `"Central Taxi Cone Sul`""
Write-Host "   git remote add origin https://github.com/SEU_USUARIO/central-taxi-cone-sul.git"
Write-Host "   git push -u origin main"
