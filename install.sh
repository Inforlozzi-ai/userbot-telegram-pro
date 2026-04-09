#!/bin/bash
# ============================================================
#   USERBOT TELEGRAM PRO v2 — GERENCIADOR MULTI-BOT
# ============================================================
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

pausar() { echo ""; read -p "  Pressione ENTER para continuar..." x; }
limpar() { clear; }

titulo() {
  limpar
  echo -e "${CYAN}${BOLD}"
  echo "  ╔══════════════════════════════════════════════════╗"
  echo "  ║     🤖 USERBOT TELEGRAM PRO v2 — MULTI-BOT     ║"
  echo "  ╚══════════════════════════════════════════════════╝"
  echo -e "${NC}"
}

# ── MENU PRINCIPAL ─────────────────────────────────────────
menu_principal() {
  titulo
  bots=($(docker ps -a --format "{{.Names}}" 2>/dev/null | grep "^userbot-"))
  if [ ${#bots[@]} -gt 0 ]; then
    echo -e "  ${BOLD}Bots instalados:${NC}"
    for nome in "${bots[@]}"; do
      status=$(docker inspect --format='{{.State.Status}}' "$nome" 2>/dev/null)
      icon="🔴"; [ "$status" = "running" ] && icon="🟢"
      echo -e "    $icon  $nome  (${status})"
    done
    echo ""
  fi

  echo -e "  ${CYAN}[1]${NC} 🆕 Instalar novo bot"
  echo -e "  ${CYAN}[2]${NC} 📋 Gerenciar bots"
  echo -e "  ${CYAN}[3]${NC} 🗑  Desinstalar bot"
  echo -e "  ${CYAN}[4]${NC} 📊 Ver logs em tempo real"
  echo -e "  ${CYAN}[5]${NC} 🔁 Regerar Session String de um bot"
  echo -e "  ${CYAN}[6]${NC} 🧹 Limpar tudo (todos os bots)"
  echo -e "  ${CYAN}[7]${NC} ❌ Sair"
  echo ""
  read -p "  Escolha [1-7]: " op
  case $op in
    1) instalar_bot ;;
    2) gerenciar_bots ;;
    3) desinstalar_bot ;;
    4) ver_logs ;;
    5) regerar_session ;;
    6) limpar_tudo ;;
    7) echo -e "\n  ${GREEN}Até logo! 👋${NC}\n"; exit 0 ;;
    *) menu_principal ;;
  esac
}

# ── SELECIONAR BOT ─────────────────────────────────────────
selecionar_bot() {
  local prompt="$1"
  bots=($(docker ps -a --format "{{.Names}}" 2>/dev/null | grep "^userbot-"))
  if [ ${#bots[@]} -eq 0 ]; then
    echo -e "\n  ${YELLOW}Nenhum bot instalado.${NC}"
    pausar; menu_principal; return
  fi
  echo -e "\n  ${BOLD}$prompt${NC}"
  for i in "${!bots[@]}"; do
    nome="${bots[$i]}"
    status=$(docker inspect --format='{{.State.Status}}' "$nome" 2>/dev/null)
    icon="🔴"; [ "$status" = "running" ] && icon="🟢"
    echo -e "  ${CYAN}[$((i+1))]${NC} $icon $nome"
  done
  echo ""
  read -p "  Número: " num
  SELECTED_BOT="${bots[$((num-1))]}"
  if [ -z "$SELECTED_BOT" ]; then
    echo -e "  ${RED}Inválido.${NC}"; pausar; menu_principal
  fi
}

# ── GERAR SESSION STRING ───────────────────────────────────
gerar_session_string() {
  local api_id="$1"
  local api_hash="$2"

  echo -e "\n  ${BOLD}📱 Gerando Session String...${NC}"
  echo -e "  ${YELLOW}Você precisará do número de telefone e código do Telegram.${NC}\n"

  # Cria script Python temporário
  cat > /tmp/gen_session.py << 'PYEOF'
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
import os, sys

api_id  = int(os.environ.get("API_ID", "0"))
api_hash = os.environ.get("API_HASH", "")

async def main():
    async with TelegramClient(StringSession(), api_id, api_hash) as c:
        sess = c.session.save()
        print(sess, flush=True)
        with open("/tmp/session_out.txt", "w") as f:
            f.write(sess)

asyncio.run(main())
PYEOF

  rm -f /tmp/session_out.txt

  docker run --rm -it \
    -e API_ID="$api_id" \
    -e API_HASH="$api_hash" \
    -v /tmp/gen_session.py:/app/gen_session.py \
    -v /tmp:/tmp \
    python:3.12-slim \
    bash -c "pip install telethon -q --root-user-action=ignore 2>/dev/null && python /app/gen_session.py"

  rm -f /tmp/gen_session.py

  if [ -f /tmp/session_out.txt ]; then
    SESSION_GERADA=$(cat /tmp/session_out.txt)
    rm -f /tmp/session_out.txt
  fi

  if [ -z "$SESSION_GERADA" ] || [ ${#SESSION_GERADA} -lt 50 ]; then
    echo -e "\n  ${RED}❌ Geração falhou. Cole a Session String manualmente:${NC}"
    read -p "  SESSION_STRING: " SESSION_GERADA
  else
    echo -e "\n  ${GREEN}✅ Session String gerada com sucesso!${NC}"
  fi
}

# ── REGERAR SESSION DE BOT EXISTENTE ──────────────────────
regerar_session() {
  titulo
  selecionar_bot "Regerar session de qual bot?"
  [ -z "$SELECTED_BOT" ] && return

  INSTALL_DIR="/opt/$SELECTED_BOT"
  API_ID=$(docker inspect "$SELECTED_BOT" --format='{{range .Config.Env}}{{println .}}{{end}}' 2>/dev/null | grep "^API_ID=" | cut -d= -f2)
  API_HASH=$(docker inspect "$SELECTED_BOT" --format='{{range .Config.Env}}{{println .}}{{end}}' 2>/dev/null | grep "^API_HASH=" | cut -d= -f2)

  titulo
  echo -e "  ${BOLD}🔁 Regerando session de ${CYAN}$SELECTED_BOT${NC}\n"

  SESSION_GERADA=""
  gerar_session_string "$API_ID" "$API_HASH"

  if [ -z "$SESSION_GERADA" ] || [ ${#SESSION_GERADA} -lt 50 ]; then
    echo -e "  ${RED}❌ Session inválida. Abortando.${NC}"
    pausar; menu_principal; return
  fi

  # Atualiza .env
  sed -i "s|^SESSION_STRING=.*|SESSION_STRING=$SESSION_GERADA|" "$INSTALL_DIR/.env"

  # Reinicia container com nova session
  BOT_TOKEN=$(docker inspect "$SELECTED_BOT" --format='{{range .Config.Env}}{{println .}}{{end}}' 2>/dev/null | grep "^BOT_TOKEN=" | cut -d= -f2-)
  BOT_NOME=$(docker inspect "$SELECTED_BOT" --format='{{range .Config.Env}}{{println .}}{{end}}' 2>/dev/null | grep "^BOT_NOME=" | cut -d= -f2-)
  TARGET_GROUP_ID=$(docker inspect "$SELECTED_BOT" --format='{{range .Config.Env}}{{println .}}{{end}}' 2>/dev/null | grep "^TARGET_GROUP_ID=" | cut -d= -f2-)
  SOURCE_CHAT_IDS=$(docker inspect "$SELECTED_BOT" --format='{{range .Config.Env}}{{println .}}{{end}}' 2>/dev/null | grep "^SOURCE_CHAT_IDS=" | cut -d= -f2-)
  FORWARD_MODE=$(docker inspect "$SELECTED_BOT" --format='{{range .Config.Env}}{{println .}}{{end}}' 2>/dev/null | grep "^FORWARD_MODE=" | cut -d= -f2-)
  ADMIN_IDS=$(docker inspect "$SELECTED_BOT" --format='{{range .Config.Env}}{{println .}}{{end}}' 2>/dev/null | grep "^ADMIN_IDS=" | cut -d= -f2-)

  docker rm -f "$SELECTED_BOT" 2>/dev/null

  docker run -d \
    --name "$SELECTED_BOT" \
    --restart unless-stopped \
    -e API_ID="$API_ID" \
    -e API_HASH="$API_HASH" \
    -e SESSION_STRING="$SESSION_GERADA" \
    -e BOT_TOKEN="$BOT_TOKEN" \
    -e BOT_NOME="$BOT_NOME" \
    -e TARGET_GROUP_ID="$TARGET_GROUP_ID" \
    -e SOURCE_CHAT_IDS="$SOURCE_CHAT_IDS" \
    -e FORWARD_MODE="$FORWARD_MODE" \
    -e ADMIN_IDS="$ADMIN_IDS" \
    -v "$INSTALL_DIR/bot.py:/app/bot.py:ro" \
    -w /app \
    python:3.12-slim \
    bash -c "pip install telethon -q --root-user-action=ignore && python bot.py" >/dev/null

  echo -e "\n  ⏳ Aguardando inicialização (15s)..."
  sleep 15

  if docker ps | grep -q "$SELECTED_BOT"; then
    echo -e "  ${GREEN}✅ Bot reiniciado com nova session!${NC}"
  else
    echo -e "  ${RED}❌ Erro ao reiniciar. Logs:${NC}\n"
    docker logs "$SELECTED_BOT" 2>&1 | tail -20
  fi
  pausar; menu_principal
}

# ── LIMPAR TUDO ────────────────────────────────────────────
limpar_tudo() {
  titulo
  echo -e "  ${RED}${BOLD}⚠️  ATENÇÃO — AÇÃO IRREVERSÍVEL!${NC}\n"
  echo -e "  Isso irá remover TODOS os containers userbot- e seus arquivos.\n"
  bots=($(docker ps -a --format "{{.Names}}" 2>/dev/null | grep "^userbot-"))
  if [ ${#bots[@]} -eq 0 ]; then
    echo -e "  ${YELLOW}Nenhum bot para remover.${NC}"
    pausar; menu_principal; return
  fi
  echo -e "  Serão removidos:"
  for nome in "${bots[@]}"; do echo -e "    • $nome"; done
  echo ""
  read -p "  Tem certeza? Digite CONFIRMAR: " conf
  if [ "$conf" = "CONFIRMAR" ]; then
    for nome in "${bots[@]}"; do
      docker rm -f "$nome" 2>/dev/null
      rm -rf "/opt/$nome"
      echo -e "  ${GREEN}✅ $nome removido${NC}"
    done
    echo -e "\n  ${GREEN}✅ Limpeza concluída!${NC}"
  else
    echo -e "\n  ${YELLOW}Cancelado.${NC}"
  fi
  pausar; menu_principal
}

# ── GERENCIAR ──────────────────────────────────────────────
gerenciar_bots() {
  titulo
  selecionar_bot "Selecione o bot:"
  [ -z "$SELECTED_BOT" ] && return
  titulo
  status=$(docker inspect --format='{{.State.Status}}' "$SELECTED_BOT" 2>/dev/null)
  icon="🔴"; [ "$status" = "running" ] && icon="🟢"
  echo -e "  Bot: ${CYAN}$SELECTED_BOT${NC} $icon ($status)\n"
  echo -e "  ${CYAN}[1]${NC} 📋 Ver logs (últimas 30 linhas)"
  echo -e "  ${CYAN}[2]${NC} 🔄 Reiniciar"
  echo -e "  ${CYAN}[3]${NC} ⏹  Parar"
  echo -e "  ${CYAN}[4]${NC} ▶️  Iniciar"
  echo -e "  ${CYAN}[5]${NC} 🔍 Inspecionar variáveis"
  echo -e "  ${CYAN}[6]${NC} ⬅️  Voltar"
  echo ""
  read -p "  Escolha: " acao
  case $acao in
    1) titulo; echo -e "  ${BOLD}Logs de $SELECTED_BOT:${NC}\n"; docker logs "$SELECTED_BOT" 2>&1 | tail -30; pausar; gerenciar_bots ;;
    2) docker restart "$SELECTED_BOT" && echo -e "\n  ${GREEN}✅ Reiniciado!${NC}" || echo -e "\n  ${RED}❌ Erro${NC}"; pausar; gerenciar_bots ;;
    3) docker stop "$SELECTED_BOT" && echo -e "\n  ${GREEN}✅ Parado!${NC}" || echo -e "\n  ${RED}❌ Erro${NC}"; pausar; gerenciar_bots ;;
    4) docker start "$SELECTED_BOT" && echo -e "\n  ${GREEN}✅ Iniciado!${NC}" || echo -e "\n  ${RED}❌ Erro${NC}"; pausar; gerenciar_bots ;;
    5) titulo; echo -e "  ${BOLD}Variáveis de $SELECTED_BOT:${NC}\n"; docker inspect "$SELECTED_BOT" --format='{{range .Config.Env}}{{println .}}{{end}}' | grep -E "^(API_ID|API_HASH|BOT_TOKEN|TARGET_GROUP_ID|SOURCE_CHAT_IDS|FORWARD_MODE|BOT_NOME|ADMIN_IDS)"; pausar; gerenciar_bots ;;
    6) menu_principal ;;
    *) gerenciar_bots ;;
  esac
}

# ── VER LOGS ───────────────────────────────────────────────
ver_logs() {
  titulo
  selecionar_bot "Ver logs de qual bot?"
  [ -z "$SELECTED_BOT" ] && return
  echo -e "\n  ${YELLOW}Pressione Ctrl+C para sair dos logs${NC}\n"
  docker logs -f "$SELECTED_BOT" 2>&1
  pausar; menu_principal
}

# ── DESINSTALAR ────────────────────────────────────────────
desinstalar_bot() {
  titulo
  selecionar_bot "Qual bot deseja remover?"
  [ -z "$SELECTED_BOT" ] && return
  echo -e "\n  ${RED}${BOLD}⚠️  ATENÇÃO!${NC}"
  echo -e "  Isso vai apagar o container e os arquivos de ${CYAN}$SELECTED_BOT${NC}"
  read -p "  Tem certeza? [s/N]: " conf
  if [[ "$conf" =~ ^[sS]$ ]]; then
    docker rm -f "$SELECTED_BOT" 2>/dev/null
    rm -rf "/opt/$SELECTED_BOT"
    echo -e "\n  ${GREEN}✅ '$SELECTED_BOT' removido!${NC}"
  else
    echo -e "\n  ${YELLOW}Cancelado.${NC}"
  fi
  pausar; menu_principal
}

# ── INSTALAR ───────────────────────────────────────────────
instalar_bot() {
  [ "$EUID" -ne 0 ] && echo -e "  ${RED}Execute como root: sudo bash install.sh${NC}" && exit 1

  titulo
  echo -e "  ${BOLD}🔍 Verificando o sistema...${NC}\n"
  if ! command -v docker &>/dev/null; then
    echo -e "  ${YELLOW}Instalando Docker...${NC}"
    curl -fsSL https://get.docker.com | bash >/dev/null 2>&1
    systemctl enable docker >/dev/null 2>&1; systemctl start docker >/dev/null 2>&1
    echo -e "  ${GREEN}✅ Docker instalado!${NC}"
  else
    echo -e "  ${GREEN}✅ Docker: $(docker --version | cut -d' ' -f3 | tr -d ',')${NC}"
  fi
  pausar

  # Passo 1 — Nome do bot
  titulo
  echo -e "  ${BOLD}🏷  PASSO 1 — Nome do bot${NC}\n"
  echo -e "  Dê um nome único para identificar este bot."
  echo -e "  ${YELLOW}Ex: principal, vendas, noticias, grupo2${NC}\n"
  read -p "  Nome (sem espaços): " BOT_SLUG
  BOT_SLUG=$(echo "${BOT_SLUG:-bot1}" | tr ' ' '-' | tr -cd 'a-zA-Z0-9-')
  CONTAINER_NAME="userbot-$BOT_SLUG"
  INSTALL_DIR="/opt/$CONTAINER_NAME"
  if docker ps -a --format "{{.Names}}" | grep -q "^${CONTAINER_NAME}$"; then
    echo -e "\n  ${RED}❌ Já existe um bot com esse nome!${NC}"
    echo -e "  ${YELLOW}Escolha outro nome ou desinstale o existente primeiro.${NC}"
    pausar; instalar_bot; return
  fi
  echo -e "\n  ${GREEN}✅ Container: $CONTAINER_NAME${NC}"
  pausar

  # Passo 2 — Nome de exibição
  titulo
  echo -e "  ${BOLD}🏷  PASSO 2 — Nome de exibição${NC}\n"
  read -p "  Nome de exibição (padrão: UserBot): " BOT_NOME
  BOT_NOME="${BOT_NOME:-UserBot}"
  pausar

  # Passo 3 — API
  titulo
  echo -e "  ${BOLD}🔑 PASSO 3 — Chaves da API do Telegram${NC}\n"
  echo -e "  Acesse: ${CYAN}https://my.telegram.org${NC}"
  echo -e "  Login → API Development Tools → Crie um app\n"
  echo -e "  ${CYAN}[1]${NC} Usar API padrão (Inforlozzi) ✅ recomendado"
  echo -e "  ${CYAN}[2]${NC} Digitar outra API\n"
  read -p "  Escolha: " op_api
  if [ "$op_api" = "2" ]; then
    read -p "  API_ID (números): " API_ID
    while ! [[ "$API_ID" =~ ^[0-9]+$ ]]; do
      echo -e "  ${RED}❌ Apenas números!${NC}"; read -p "  API_ID: " API_ID
    done
    read -p "  API_HASH: " API_HASH
    while [ ${#API_HASH} -lt 10 ]; do
      echo -e "  ${RED}❌ Hash inválido!${NC}"; read -p "  API_HASH: " API_HASH
    done
  else
    API_ID="33720900"
    API_HASH="b42f6ce16216a7be8b55ba960e03ba2f"
    echo -e "  ${GREEN}✅ API carregada!${NC}"
  fi
  pausar

  # Passo 4 — Session String
  SESSION_STRING=""

  # Verificar se já existe bot com mesmo API_ID para reutilizar session
  for cn in $(docker ps -a --format "{{.Names}}" | grep "^userbot-"); do
    existing_api=$(docker inspect "$cn" --format='{{range .Config.Env}}{{println .}}{{end}}' 2>/dev/null | grep "^API_ID=" | cut -d= -f2)
    if [ "$existing_api" = "$API_ID" ]; then
      SESSION_STRING=$(docker inspect "$cn" --format='{{range .Config.Env}}{{println .}}{{end}}' 2>/dev/null | grep "^SESSION_STRING=" | cut -d= -f2-)
      echo -e "\n  ${GREEN}✅ Session String reutilizada do bot '$cn'!${NC}"
      echo -e "  ${YELLOW}(Mesma conta Telegram)${NC}"
      pausar; break
    fi
  done

  if [ -z "$SESSION_STRING" ]; then
    titulo
    echo -e "  ${BOLD}📱 PASSO 4 — Conta do Telegram${NC}\n"
    echo -e "  ${CYAN}[1]${NC} Gerar nova Session String agora ✅ recomendado"
    echo -e "  ${CYAN}[2]${NC} Colar manualmente\n"
    read -p "  Escolha: " op_sess

    SESSION_GERADA=""
    if [ "$op_sess" = "2" ]; then
      read -p "  SESSION_STRING: " SESSION_STRING
    else
      gerar_session_string "$API_ID" "$API_HASH"
      SESSION_STRING="$SESSION_GERADA"
    fi

    if [ -z "$SESSION_STRING" ] || [ ${#SESSION_STRING} -lt 50 ]; then
      echo -e "\n  ${RED}❌ Session String inválida. Abortando instalação.${NC}"
      pausar; menu_principal; return
    fi
  fi
  pausar

  # Passo 5 — BOT TOKEN
  titulo
  echo -e "  ${BOLD}🤖 PASSO 5 — Token do Bot${NC}\n"
  echo -e "  Crie em ${CYAN}@BotFather${NC} → /newbot"
  echo -e "  ${YELLOW}⚠️  Cada bot paralelo precisa de um BOT TOKEN diferente!${NC}\n"
  read -p "  BOT_TOKEN: " BOT_TOKEN
  while [[ ! "$BOT_TOKEN" == *":"* ]]; do
    echo -e "  ${RED}❌ Token inválido!${NC}"; read -p "  BOT_TOKEN: " BOT_TOKEN
  done
  pausar

  # Passo 6 — Destinos
  titulo
  echo -e "  ${BOLD}🎯 PASSO 6 — Grupo(s) DESTINO${NC}\n"
  echo -e "  ${CYAN}[1]${NC} Configurar agora"
  echo -e "  ${CYAN}[2]${NC} Pular — configurar depois pelo /menu ✅\n"
  read -p "  Escolha: " op_dest
  TARGET_GROUP_ID=""
  if [ "$op_dest" = "1" ]; then
    echo -e "  Pode enviar vários IDs separados por vírgula."
    echo -e "  ${YELLOW}Como descobrir o ID: adicione @userinfobot no grupo${NC}\n"
    read -p "  ID(s) destino: " TARGET_GROUP_ID
    while [[ ! "$TARGET_GROUP_ID" == -* ]]; do
      echo -e "  ${RED}❌ ID deve começar com '-'${NC}"; read -p "  TARGET_GROUP_ID: " TARGET_GROUP_ID
    done
    echo -e "  ${GREEN}✅ Destino(s) salvo(s)!${NC}"
  else
    echo -e "  ${YELLOW}⏭ Pulado — configure depois com 🎯 Destinos no /menu${NC}"
  fi
  pausar

  # Passo 7 — Origens
  titulo
  echo -e "  ${BOLD}📡 PASSO 7 — Grupos de ORIGEM${NC}\n"
  echo -e "  ${CYAN}[1]${NC} Monitorar TODOS os grupos (padrão)"
  echo -e "  ${CYAN}[2]${NC} Apenas grupos específicos"
  echo -e "  ${CYAN}[3]${NC} Pular — configurar depois pelo /menu ✅\n"
  read -p "  Escolha: " op_orig
  SOURCE_CHAT_IDS=""
  if [ "$op_orig" = "2" ]; then
    read -p "  IDs separados por vírgula: " SOURCE_CHAT_IDS
    echo -e "  ${GREEN}✅ Origens salvas!${NC}"
  elif [ "$op_orig" = "3" ]; then
    echo -e "  ${YELLOW}⏭ Pulado — configure depois com 📡 Origens no /menu${NC}"
  else
    echo -e "  ${GREEN}✅ Monitorará todos os grupos!${NC}"
  fi
  pausar

  # Passo 8 — Modo
  titulo
  echo -e "  ${BOLD}🔀 PASSO 8 — Modo de encaminhamento${NC}\n"
  echo -e "  ${CYAN}[1]${NC} forward — mostra de onde veio"
  echo -e "  ${CYAN}[2]${NC} copy    — aparece como mensagem nova\n"
  read -p "  Escolha: " op_modo
  FORWARD_MODE="forward"; [ "$op_modo" = "2" ] && FORWARD_MODE="copy"
  pausar

  # Passo 9 — Admins
  titulo
  echo -e "  ${BOLD}🔐 PASSO 9 — Administradores (opcional)${NC}\n"
  echo -e "  IDs dos usuários que podem controlar este bot."
  echo -e "  ${YELLOW}Deixe em branco para permitir qualquer pessoa.${NC}"
  echo -e "  ${YELLOW}Como saber seu ID: envie /start para @userinfobot${NC}\n"
  read -p "  ADMIN_IDS (ex: 123456789,987654321): " ADMIN_IDS_INPUT
  pausar

  # Resumo
  titulo
  echo -e "  ${BOLD}📋 RESUMO${NC}\n"
  echo -e "  ${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "  Container  : ${GREEN}$CONTAINER_NAME${NC}"
  echo -e "  Nome       : ${GREEN}$BOT_NOME${NC}"
  echo -e "  API_ID     : ${GREEN}$API_ID${NC}"
  echo -e "  Destino(s) : ${GREEN}${TARGET_GROUP_ID:-não configurado}${NC}"
  echo -e "  Origens    : ${GREEN}${SOURCE_CHAT_IDS:-todos}${NC}"
  echo -e "  Modo       : ${GREEN}$FORWARD_MODE${NC}"
  echo -e "  Admins     : ${GREEN}${ADMIN_IDS_INPUT:-qualquer um}${NC}"
  echo -e "  ${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
  read -p "  Confirmar instalação? [s/N]: " CONF
  [[ ! "$CONF" =~ ^[sS]$ ]] && echo -e "\n  ${YELLOW}Cancelado.${NC}" && pausar && menu_principal && return

  # Instalando
  titulo
  echo -e "  ${BOLD}⚙️  Instalando $CONTAINER_NAME...${NC}\n"
  mkdir -p "$INSTALL_DIR"

  if [ -f "$SCRIPT_DIR/bot.py" ]; then
    cp "$SCRIPT_DIR/bot.py" "$INSTALL_DIR/bot.py"
    echo -e "  ${GREEN}✅ bot.py copiado!${NC}"
  else
    echo -e "  ${RED}❌ bot.py não encontrado em $SCRIPT_DIR${NC}"
    echo -e "  ${YELLOW}Coloque bot.py na mesma pasta do install.sh${NC}"
    pausar; return
  fi

  cat > "$INSTALL_DIR/.env" << ENVEOF
API_ID=$API_ID
API_HASH=$API_HASH
SESSION_STRING=$SESSION_STRING
BOT_TOKEN=$BOT_TOKEN
BOT_NOME=$BOT_NOME
TARGET_GROUP_ID=$TARGET_GROUP_ID
SOURCE_CHAT_IDS=$SOURCE_CHAT_IDS
FORWARD_MODE=$FORWARD_MODE
ADMIN_IDS=$ADMIN_IDS_INPUT
CONTAINER_NAME=$CONTAINER_NAME
ENVEOF
  chmod 600 "$INSTALL_DIR/.env"

  docker rm -f "$CONTAINER_NAME" 2>/dev/null || true
  echo -e "  🚀 Iniciando container..."

  docker run -d \
    --name "$CONTAINER_NAME" \
    --restart unless-stopped \
    -e API_ID="$API_ID" \
    -e API_HASH="$API_HASH" \
    -e SESSION_STRING="$SESSION_STRING" \
    -e BOT_TOKEN="$BOT_TOKEN" \
    -e BOT_NOME="$BOT_NOME" \
    -e TARGET_GROUP_ID="$TARGET_GROUP_ID" \
    -e SOURCE_CHAT_IDS="$SOURCE_CHAT_IDS" \
    -e FORWARD_MODE="$FORWARD_MODE" \
    -e ADMIN_IDS="$ADMIN_IDS_INPUT" \
    -v "$INSTALL_DIR/bot.py:/app/bot.py:ro" \
    -w /app \
    python:3.12-slim \
    bash -c "pip install telethon -q --root-user-action=ignore && python bot.py" >/dev/null

  echo -e "  ⏳ Aguardando inicialização (15s)..."
  sleep 15

  if docker ps | grep -q "$CONTAINER_NAME"; then
    BOT_USER=$(docker logs "$CONTAINER_NAME" 2>&1 | grep -oP 'Bot: @\S+' | head -1)
    titulo
    echo -e "${GREEN}${BOLD}"
    echo "  ╔══════════════════════════════════════════════════╗"
    echo "  ║         🎉 BOT INSTALADO COM SUCESSO!           ║"
    echo "  ╚══════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo -e "  Container : ${GREEN}$CONTAINER_NAME${NC}"
    echo -e "  Bot       : ${CYAN}${BOT_USER:-'ver no Telegram'}${NC}\n"
    echo -e "  ${BOLD}Próximos passos:${NC}"
    echo -e "  1. Adicione ${CYAN}${BOT_USER}${NC} como admin no grupo destino"
    echo -e "  2. Envie ${CYAN}/menu${NC} para o bot\n"
    total=$(docker ps --format "{{.Names}}" | grep "^userbot-" | wc -l)
    echo -e "  ${YELLOW}Total de bots rodando: $total${NC}"
  else
    echo -e "\n  ${RED}❌ Erro! Logs:${NC}\n"
    docker logs "$CONTAINER_NAME" 2>&1 | tail -20
  fi
  pausar
  menu_principal
}

menu_principal
