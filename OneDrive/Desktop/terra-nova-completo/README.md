# TERRA NOVA — Nexo Veterinária (Django)

Loja e painel da clínica veterinária **TERRA NOVA**, monograma **VT** em **verde cana**.

## Como rodar

### Windows (PowerShell)

```powershell
cd $HOME\OneDrive\Desktop\terra-nova-completo
pip install -r requirements.txt
$env:CLINIC_WHATSAPP="5511999999999"
$env:STRIPE_SECRET_KEY="sk_test_..."
python manage.py migrate
python manage.py seed_loja
python manage.py runserver 0.0.0.0:8000
```

### Linux / macOS

```bash
pip install -r requirements.txt
export CLINIC_WHATSAPP=5511999999999
python manage.py migrate
python manage.py seed_loja
python manage.py runserver 0.0.0.0:8000
```

- Loja: http://127.0.0.1:8000/
- App celular: http://127.0.0.1:8000/m/
- Painel: http://127.0.0.1:8000/painel/
- WhatsApp flutuante: canto direito (número em `CLINIC_WHATSAPP`)
- Login admin demo: `admin` / `TerraNova@2026`
- Cupons: `TERRA10` (10%) e `CANA20` (R$ 20)

## Gateway de pagamento (Mercado Pago + PIX)

Sem token, o checkout gera um QR PIX local (modo desenvolvimento).

Com token, cada pedido cria uma cobrança real no Mercado Pago:

```bash
export MP_ACCESS_TOKEN="APP_USR-seu-token"
export MP_API_MODE=payments   # ou orders
python manage.py runserver
```

1. Crie o app em [developers.mercadopago.com](https://www.mercadopago.com.br/developers/panel/app).
2. Use o Access Token de **teste** (`APP_USR-…`) ou o de **produção**.
3. Cadastre o webhook `https://SEU_DOMINIO/webhooks/mercadopago/` nos tópicos **Payments** (e **Orders** se `MP_API_MODE=orders`).
4. A página do pedido consulta o status a cada 4s e o webhook confirma o crédito automaticamente.
5. O estoque só baixa quando o PIX é aprovado.

Painel: `/painel/pagamentos/` mostra se o token está ativo e o log de eventos.

## Módulos

- Páginas: Início, Sobre, Produtos, Mais relevantes, Garantia, Baixar app
- Busca de produtos (página + autocomplete)
- Carrinho com segurança (token HMAC, CSRF, preço no servidor, limite de itens)
- PIX via Mercado Pago (QR + copia-e-cola + webhook)
- Painel admin: dashboard, produtos, descontos, pedidos, pagamentos, cadastro de administrador


## App para celular (PWA)

- Abrir o app: http://127.0.0.1:8000/m/
- Página de instalação: http://127.0.0.1:8000/app/
- Manifesto: `/static/app/manifest.webmanifest`
- Service worker: `/static/app/sw.js`

No Android, use o Chrome → Instalar app. No iPhone, Safari → Compartilhar → Adicionar à Tela de Início.


## Offline e notificações push

O service worker (`/m/sw.js`) agora separa três caches:

- **shell** — CSS, ícones, JS (cache-first)
- **pages** — telas do app (network-first, cai em `/m/offline/`)
- **data** — `/m/catalogo.json` (network-first com fallback)

Push nativo (Web Push + VAPID):

1. No celular, instale o PWA e abra **Conta → Ativar notificações**.
2. Informe o e-mail para receber aviso de PIX pago.
3. No painel: `/painel/push/` envia campanha para todos os aparelhos.

Chaves VAPID em `terranova/vapid.json` (já geradas). Em produção use HTTPS — push não funciona em HTTP, só em `localhost`.

## Stripe (cartão)

```powershell
$env:STRIPE_SECRET_KEY="sk_test_..."
$env:STRIPE_PUBLISHABLE_KEY="pk_test_..."
$env:STRIPE_WEBHOOK_SECRET="whsec_..."
```

Webhook: `https://SEU_DOMINIO/webhooks/stripe/` (evento `checkout.session.completed`).
Sem chave, o checkout Stripe roda em modo teste local (botão Simular pagamento).
