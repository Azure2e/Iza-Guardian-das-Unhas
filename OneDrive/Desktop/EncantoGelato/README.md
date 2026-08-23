# Encanto Gelato — Sistema completo (atualizado)

Site, pedidos, PDV, estoque, segurança, **PIX real**, modo escuro, garantia e config centralizada.

## Instalação rápida (Windows)

1. Extraia este zip em `Desktop\EncantoGelato`
2. Crie o `.env` (veja abaixo)
3. Rode:

```powershell
cd C:\Users\Dell\OneDrive\Desktop\EncantoGelato
pip install -r requirements.txt
python app.py
```

Abra http://127.0.0.1:5000 e use **Ctrl+F5**.

## Arquivo `.env` (obrigatório para PIX)

Na **mesma pasta** do `app.py`:

```env
ENCANTO_SECRET_KEY=fcdd2d61443ca1c47ff6ace4da63ee9f86e679ea338e3cf0e5a8fa00e86029b6
ENCANTO_ADMIN_PASS=Encanto@2026
ENCANTO_CAIXA_PASS=Caixa@2026

PIX_KEY=sua-chave-pix-aqui
PIX_MERCHANT_NAME=Encanto Gelato
PIX_CITY=SAO PAULO
```

```powershell
copy .env.example .env
notepad .env
```

## O que está incluso

- Site premium + modo escuro
- Carta, pedidos, confirmação
- PIX (QR + copia e cola) padrão BC
- Garantia 60 dias
- Admin: dashboard, PDV, pedidos, estoque, relatórios, segurança
- Config por injeção (`config.py`) — chaves não espalhadas no código

## Login

| Usuário | Senha |
|---------|--------|
| admin | Encanto@2026 |
| caixa | Caixa@2026 |

## GitHub

```powershell
git add .
git commit -m "Sistema completo atualizado"
git push
```

O `.gitignore` bloqueia `.env` e o banco.
