# FT Chat

Bate-papo PWA com logo **FT**, visual escuro/teal, mensagens, vídeo, grupos e E2E.

## Dependências Python

```bash
pip install -r requirements.txt
```

No Windows:

```powershell
py -3 -m pip install -r requirements.txt
py -3 -u server.py
```

(`requeriments.txt` também existe, com o mesmo conteúdo.)

## Hospedar de graça (Render)

1. Crie conta em https://render.com  
2. New → Web Service → ligue este repositório ou faça upload da pasta  
3. Build: `pip install -r requirements.txt`  
4. Start: `python -u server.py`  
5. A plataforma define `PORT` sozinha  

Variáveis recomendadas no Render:

- `ADMIN_CODE` — código do admin  
- `JWT_SECRET` — frase longa e aleatória (senão o servidor gera `data/jwt-secret.json`)  
- `JWT_ACCESS_TTL` — validade do access token em segundos (padrão 900)  
- `JWT_TTL` — validade do refresh token em segundos (padrão 7 dias)  

O arquivo `render.yaml` e o `Procfile` já vêm no projeto. No celular use o endereço `https://....onrender.com` e toque em **Abrir no celular** → Adicionar à tela inicial.

Outras opções gratuitas parecidas: Railway e Fly.io. Todas precisam de HTTPS para PWA e push.

## O que tem

- Chat aberto (uma sala pública)
- Mensagens instantâneas via WebSocket
- Ticks estilo WhatsApp: 🕒 fila, ✓ enviado, ✓✓ entregue, ✓✓ azul lido
- Responder (toque na bolha) e apagar (clique direito / toque longo)
- Envio de vídeo e imagem com prévia e player no balão
- Miniatura e duração do vídeo geradas com `ffmpeg`
- Histórico persistente em `data/messages.json`
- Lista de quem está online e indicador de digitação
- PWA instalável no celular
- Envio offline: texto, foto e vídeo entram no chat na hora e sobem sozinhos quando a internet volta
- Alta disponibilidade: gravação atômica + backup, watchdog do processo e dos sockets, heartbeat e reconexão com backoff
- Disponibilidade das pessoas: Disponível, Ausente, Ocupado e visto por último
- Ausente automático ao sair da aba; ocupado não é sobrescrito
- Módulo de administrador: silenciar, bloquear e banir usuários
- Interface em português

## Administrador

Código padrão: `admin123`  
Troque com a variável `ADMIN_CODE`.

```bash
ADMIN_CODE='sua-senha' ./start.sh
```

No app, toque no escudo 🛡️, digite o código e use:

- **Silenciar** — a pessoa continua na sala, mas não envia (10 min, 1 h ou até liberar)
- **Bloquear** — não envia e as mensagens dela somem para os outros
- **Banir** — é expulsa e não consegue entrar de novo
- **Liberar / desbanir** — devolve o acesso

O estado fica em `data/moderation.json`.
Os logs ficam em `data/moderation-logs.json` e aparecem no painel 🛡️.

## Notificações de mensagem no celular

Cada pessoa toca em **Ativar avisos** no topo do chat e aceita a permissão.

Quando alguém envia texto, foto ou vídeo, o celular das outras pessoas recebe a notificação — mesmo com o app fechado. Quem enviou não é avisado. Se o chat estiver aberto na frente, o aviso não duplica.

## Push para administradores

No painel 🛡️ também existe **Ativar notificações push** (moderação). Aceite a permissão do navegador.

- Chaves VAPID em `data/vapid.json` (geradas sozinhas na primeira vez)
- Inscrições em `data/push-subs.json`
- O service worker mostra a notificação mesmo com o app em segundo plano
- Em celular precisa de HTTPS (no computador, `localhost` basta)

Opcional:

```bash
VAPID_MAILTO='mailto:voce@email.com' ./start.sh
```

## Como rodar

Não precisa de `npm`. Só Python 3.10+ (e `ffmpeg` se for gerar miniatura de vídeo).

### Windows (PowerShell)

O ZIP já pode ser extraído com o Explorador: clique com o botão direito no `.zip` → **Extrair tudo**.

```powershell
cd "$env:USERPROFILE\Desktop\chat-aberto-pwa-completo (1)\chat-aberto-pwa"
py -3 -u server.py
```

Ou dê dois cliques em `start.bat`.

Se aparecer "py não é reconhecido", instale Python em https://www.python.org/downloads/ e marque **Add python.exe to PATH**. Depois feche e abra o PowerShell de novo.

### Linux / macOS

```bash
cd chat-aberto-pwa
./start.sh
# ou: python3 server.py
```

Abra `http://localhost:3000`.

No celular da mesma rede use o IP do computador, por exemplo `http://192.168.0.10:3000`.
Para instalar: no Chrome, **Adicionar à tela inicial**.

Porta alternativa:

```bash
PORT=8080 python3 server.py
```

## Limites

- Vídeo/imagem até 80 MB
- Texto até 2.000 caracteres
- Últimas 300 mensagens ficam salvas
- Arquivos em `public/uploads`
