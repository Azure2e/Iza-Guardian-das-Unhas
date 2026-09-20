# Central Táxi Cone Sul

Sistema real da central (Vilhena e Cone Sul / RO). Python + Flask + SQLite.

A instalação sobe só com as rotas e o administrador. Taxista e cliente são cadastrados na operação.

## Windows

```powershell
cd caminho\central_taxi_cone_sul
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

http://127.0.0.1:5000

Primeiro acesso: beto@conesul.taxi / admin123

## Publicar no GitHub

```powershell
cd caminho\central_taxi_cone_sul
git init
git add .
git commit -m "Central Taxi Cone Sul"
git branch -M main
gh repo create central-taxi-cone-sul --private --source=. --push
```

Sem `gh`, crie o repositório vazio no github.com e rode:

```powershell
git remote add origin https://github.com/SEU_USUARIO/central-taxi-cone-sul.git
git push -u origin main
```

Não envie `taxi.db`, `.venv` nem `.env` — já estão no `.gitignore`.

Depois: Admin > Motoristas cadastra a frota. Cliente usa Criar conta.
