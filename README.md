# 🤖 Userbot Telegram PRO v2

Userbot de encaminhamento automático de mensagens do Telegram com painel de controle completo via bot, suporte a múltiplos bots em paralelo e instalação com um único comando.

![License](https://img.shields.io/badge/license-MIT-green)
![Python](https://img.shields.io/badge/python-3.12-blue)
![Docker](https://img.shields.io/badge/docker-ready-blue)

---

## ✨ Funcionalidades

- 📡 **Múltiplas origens** — monitora quantos grupos quiser
- 🎯 **Múltiplos destinos** — encaminha para vários grupos ao mesmo tempo
- 🔀 **Modo forward ou copy** — com ou sem indicação de origem
- 🔍 **Filtros de palavras** — exigir ou bloquear palavras
- 📁 **Filtro por tipo de mídia** — texto, foto, vídeo, áudio, doc, sticker
- ⏰ **Agendamento por horário** — só encaminha em determinados horários
- ✏️ **Prefixo e rodapé** personalizados nas mensagens
- ⏱ **Delay** entre envios para evitar flood
- 🤖 **Ignorar bots** automaticamente
- 🔐 **Sistema de admins** — só usuários autorizados controlam o bot
- 🔕 **Modo silencioso** — sem logs verbosos
- 📊 **Estatísticas por hora** com comando `/stats`
- 🤖 **Multi-bot** — rode quantos bots em paralelo quiser
- 🐳 **Docker** — instalação limpa, sem conflitos

---

## 📋 Pré-requisitos

| Item | Como obter |
|------|-----------|
| **API_ID** e **API_HASH** | [my.telegram.org](https://my.telegram.org) → API Development Tools |
| **BOT_TOKEN** | [@BotFather](https://t.me/BotFather) → `/newbot` |
| **SESSION_STRING** | Gerado automaticamente pelo instalador |
| **VPS com Docker** | O instalador instala o Docker automaticamente |

---

## 🚀 Instalação rápida (recomendado)

```bash
# 1. Clonar o repositório
git clone https://github.com/SEU_USUARIO/userbot-telegram-pro.git
cd userbot-telegram-pro

# 2. Dar permissão e rodar
chmod +x install.sh
sudo bash install.sh
```

O instalador vai guiar você por todos os passos.

---

## 📦 Instalação manual (sem git)

```bash
# Baixar direto e instalar
curl -fsSL https://raw.githubusercontent.com/SEU_USUARIO/userbot-telegram-pro/main/install.sh -o install.sh
curl -fsSL https://raw.githubusercontent.com/SEU_USUARIO/userbot-telegram-pro/main/bot.py -o bot.py
chmod +x install.sh
sudo bash install.sh
```

---

## 🔄 Instalar um segundo bot em paralelo

Cada bot precisa de:
- Um **BOT_TOKEN diferente** (crie em @BotFather)
- Um **nome único** (ex: `vendas`, `noticias`, `grupo2`)
- A **mesma SESSION_STRING** (o instalador reutiliza automaticamente)

```bash
# Simplesmente rode o instalador novamente
sudo bash install.sh
# Escolha [1] Instalar novo bot → dê um nome diferente
```

---

## 🎛 Painel de controle

Após instalar, abra o bot no Telegram e envie:

```
/menu
```

| Botão | Função |
|-------|--------|
| 📡 Origens | Adicionar/remover grupos monitorados |
| 🎯 Destinos | Adicionar/remover grupos destino |
| 🔀 Modo | Forward, Copy, Delay, Tipos de mídia |
| 🔍 Filtros | Palavras exigidas ou bloqueadas |
| ⏰ Horário | Agendamento por horário |
| ✏️ Mensagem | Prefixo e rodapé |
| 📊 Status | Ver tudo de uma vez |
| ⏸ Pausar | Pausar/retomar sem derrubar |

### Comandos disponíveis

| Comando | Descrição |
|---------|-----------|
| `/menu` | Abre o painel completo |
| `/status` | Status resumido |
| `/stats` | Estatísticas por hora |
| `/pausar` | Pausa o encaminhamento |
| `/retomar` | Retoma o encaminhamento |
| `/start` | Mensagem de boas-vindas |

---

## ⚙️ Variáveis de ambiente

| Variável | Obrigatório | Descrição |
|----------|-------------|-----------|
| `API_ID` | ✅ | ID da API do Telegram |
| `API_HASH` | ✅ | Hash da API do Telegram |
| `SESSION_STRING` | ✅ | String de sessão da conta |
| `BOT_TOKEN` | ✅ | Token do bot (@BotFather) |
| `TARGET_GROUP_ID` | ✅ | IDs dos grupos destino (vírgula) |
| `SOURCE_CHAT_IDS` | ❌ | IDs das origens (vazio = todos) |
| `FORWARD_MODE` | ❌ | `forward` ou `copy` (padrão: forward) |
| `BOT_NOME` | ❌ | Nome de exibição do bot |
| `ADMIN_IDS` | ❌ | IDs dos admins separados por vírgula |

---

## 🐳 Gerenciar containers manualmente

```bash
# Ver todos os bots
docker ps | grep userbot

# Ver logs em tempo real
docker logs -f telegram-userbot

# Reiniciar
docker restart telegram-userbot

# Parar
docker stop telegram-userbot

# Remover
docker rm -f telegram-userbot
```

---

## 🔧 Atualizar o bot

```bash
# Baixar versão mais recente
git pull

# Reiniciar todos os bots para aplicar
for c in $(docker ps --format "{{.Names}}" | grep "^userbot-"); do
  docker cp bot.py $c:/app/bot.py
  docker restart $c
  echo "✅ $c atualizado"
done
```

---

## 📁 Estrutura do projeto

```
userbot-telegram-pro/
├── bot.py          # Código principal do userbot
├── install.sh      # Instalador interativo multi-bot
├── README.md       # Esta documentação
└── .gitignore      # Ignora arquivos sensíveis
```

---

## ⚠️ Aviso legal

Este projeto é para uso educacional. O uso de userbots pode violar os [Termos de Serviço do Telegram](https://telegram.org/tos). Use com responsabilidade.

---

## 📄 Licença

MIT License — veja [LICENSE](LICENSE) para detalhes.
