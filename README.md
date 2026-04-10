🤖 Userbot Telegram PRO v2 — Multi-Bot
Gerenciador de múltiplos userbots de encaminhamento para Telegram, com painel de controle via bot, menu inline completo e descoberta de IDs.
---
🚀 Instalação na VPS
Copie e cole o comando abaixo de uma vez no terminal:
```bash
cd ~ && rm -rf ~/userbot-telegram-pro && git clone https://github.com/Inforlozzi-ai/userbot-telegram-pro.git && cd ~/userbot-telegram-pro && chmod +x install.sh && sudo bash install.sh
```
---
🔄 Atualizar (já instalado)
```bash
cd ~/userbot-telegram-pro && git pull origin main && sudo bash install.sh
```
---
📋 Funcionalidades
✅ Multi-bot — instale quantos bots quiser em paralelo
🎯 Destinos e origens configuráveis pelo /menu
🔀 Modo forward ou copy
🔍 Filtros por palavra (exigir/bloquear)
⏰ Agendamento por horário
✏️ Prefixo e rodapé personalizados
📁 Filtro por tipo de mídia
🔎 Descobrir ID de usuários, grupos, canais, bots e fóruns
📊 Estatísticas e histórico
🔕 Modo silencioso
🔁 Regerar Session String sem reinstalar
🔄 Atualizar bot.py sem reinstalar
---
🎛 Comandos do Bot
Comando	Descrição
`/menu`	Abre o painel de controle
`/status`	Mostra status atual
`/pausar`	Pausa o encaminhamento
`/retomar`	Retoma o encaminhamento
`/stats`	Estatísticas por hora
---
🔎 Descobrir ID
No painel `/menu` → botão 🔎 Descobrir ID:
Escolha o tipo: User, Premium, Bot, Group, Channel, Forum, My Group, My Channel, My Forum
Encaminhe uma mensagem ou envie o `@username`
O bot retorna o ID automaticamente
---
🗂 Estrutura
```
userbot-telegram-pro/
├── bot.py          # Código principal do bot
├── install.sh      # Script de instalação interativo
└── README.md       # Este arquivo
```
---
⚙️ Requisitos
VPS com Linux (Ubuntu/Debian recomendado)
Docker instalado (o install.sh instala automaticamente se necessário)
Conta no Telegram + API Key em my.telegram.org
Bot criado via @BotFather
