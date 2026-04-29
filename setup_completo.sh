#!/bin/bash
# =============================================================
#   SETUP COMPLETO — Inforlozzi Banner Bot
#   1. Faz upload da logo no GitHub
#   2. Instala o banner bot no VPS
#   Uso: bash setup_completo.sh
# =============================================================

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

REPO_OWNER="Inforlozzi-ai"
REPO_NAME="userbot-telegram-pro"
REPO_RAW="https://raw.githubusercontent.com/$REPO_OWNER/$REPO_NAME/main"
CONTAINER="banner-bot"
INSTALL_DIR="/opt/$CONTAINER"

pausar() { echo ""; read -p "  Pressione ENTER para continuar..." x; }

titulo() {
  clear
  echo -e "${CYAN}${BOLD}"
  echo "  ╔══════════════════════════════════════════════════════╗"
  echo "  ║   🦁  INFORLOZZI — Setup Completo Banner Bot        ║"
  echo "  ╚══════════════════════════════════════════════════════╝"
  echo -e "${NC}"
}

# ──────────────────────────────────────────────────────────────
# ETAPA 1 — Upload da logo no GitHub
# ──────────────────────────────────────────────────────────────
step_logo() {
  titulo
  echo -e "  ${BOLD}📸 ETAPA 1 — Upload da Logo no GitHub${NC}\n"
  echo -e "  Este passo faz o upload da logo PNG diretamente no"
  echo -e "  repositório para que o instalador a baixe automaticamente.\n"
  echo -e "  ${YELLOW}Precisa de um GitHub Personal Access Token (scope: repo)${NC}"
  echo -e "  Gere em: ${CYAN}https://github.com/settings/tokens${NC}\n"

  read -p "  Você tem a logo PNG no servidor? [s/N]: " tem_logo
  if [[ ! "$tem_logo" =~ ^[sS]$ ]]; then
    echo -e "\n  ${YELLOW}⚠️  Pulando upload da logo.${NC}"
    echo -e "  A logo padrão será usada. Você pode fazer o upload depois.\n"
    sleep 2
    return 0
  fi

  read -p "  Caminho da logo PNG [/tmp/logo.png]: " LOGO_PATH
  LOGO_PATH="${LOGO_PATH:-/tmp/logo.png}"

  if [ ! -f "$LOGO_PATH" ]; then
    echo -e "\n  ${RED}❌ Arquivo não encontrado: $LOGO_PATH${NC}"
    echo -e "  ${YELLOW}Pulando upload — use a opção manual depois.${NC}\n"
    sleep 2
    return 0
  fi

  read -p "  GitHub Token (ghp_...): " GH_TOKEN
  if [ -z "$GH_TOKEN" ]; then
    echo -e "\n  ${YELLOW}Token não informado. Pulando upload.${NC}\n"
    sleep 2
    return 0
  fi

  echo -e "\n  🚀 Fazendo upload da logo...\n"

  B64=$(base64 -w0 "$LOGO_PATH")

  SHA=$(curl -s \
    -H "Authorization: Bearer $GH_TOKEN" \
    -H "Accept: application/vnd.github+json" \
    "https://api.github.com/repos/$REPO_OWNER/$REPO_NAME/contents/assets/logo.png" \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('sha',''))" 2>/dev/null)

  if [ -n "$SHA" ]; then
    PAYLOAD="{\"message\":\"feat: logo Inforlozzi PNG atualizada\",\"content\":\"$B64\",\"sha\":\"$SHA\",\"branch\":\"main\"}"
  else
    PAYLOAD="{\"message\":\"feat: logo Inforlozzi PNG\",\"content\":\"$B64\",\"branch\":\"main\"}"
  fi

  RESULT=$(curl -s -X PUT \
    -H "Authorization: Bearer $GH_TOKEN" \
    -H "Accept: application/vnd.github+json" \
    "https://api.github.com/repos/$REPO_OWNER/$REPO_NAME/contents/assets/logo.png" \
    -d "$PAYLOAD" \
    | python3 -c "
import sys, json
r = json.load(sys.stdin)
if 'content' in r:
    print('OK:' + r['content'].get('html_url',''))
else:
    print('ERRO:' + r.get('message','desconhecido'))
" 2>/dev/null)

  if [[ "$RESULT" == OK:* ]]; then
    URL="${RESULT#OK:}"
    echo -e "  ${GREEN}✅ Logo enviada com sucesso!${NC}"
    echo -e "  🔗 ${CYAN}$URL${NC}\n"
  else
    ERRO="${RESULT#ERRO:}"
    echo -e "  ${RED}❌ Erro no upload: $ERRO${NC}"
    echo -e "  ${YELLOW}Continuando sem logo...${NC}\n"
  fi

  sleep 2
}

# ──────────────────────────────────────────────────────────────
# ETAPA 2 — Coletar configurações do bot
# ──────────────────────────────────────────────────────────────
step_config() {
  titulo
  echo -e "  ${BOLD}⚙️  ETAPA 2 — Configuração do Bot${NC}\n"

  echo -e "  ${BOLD}📱 Token do Bot Telegram${NC}"
  echo -e "  Use o bot existente ou crie via ${CYAN}@BotFather${NC}\n"
  read -p "  BOT_TOKEN: " BOT_TOKEN
  while [[ ! "$BOT_TOKEN" == *":"* ]]; do
    echo -e "  ${RED}❌ Token inválido! Deve conter ':'${NC}"
    read -p "  BOT_TOKEN: " BOT_TOKEN
  done
  echo -e "  ${GREEN}✅ Token OK${NC}\n"

  echo -e "  ${BOLD}📢 ID do Canal/Grupo${NC}"
  echo -e "  Canais: ${CYAN}-100XXXXXXXXXX${NC}  |  Grupos: ${CYAN}-XXXXXXXXXX${NC}"
  echo -e "  ${YELLOW}Dica: adicione @userinfobot no grupo para descobrir o ID${NC}\n"
  read -p "  CHAT_ID: " CHAT_ID
  while [[ ! "$CHAT_ID" == -* ]]; do
    echo -e "  ${RED}❌ Deve começar com '-'${NC}"
    read -p "  CHAT_ID: " CHAT_ID
  done
  echo -e "  ${GREEN}✅ Chat ID OK${NC}\n"

  echo -e "  ${BOLD}⏰ Horário de Envio (Brasília)${NC}\n"
  read -p "  Horário [08:00]: " HORA_ENVIO
  HORA_ENVIO="${HORA_ENVIO:-08:00}"
  echo -e "  ${GREEN}✅ Envio às $HORA_ENVIO${NC}\n"

  echo -e "  ${BOLD}⚽ Ligas de Futebol${NC}"
  echo -e "  ${CYAN}4351${NC}=Brasileirão  ${CYAN}4406${NC}=Libertadores  ${CYAN}4328${NC}=Premier"
  echo -e "  ${CYAN}4480${NC}=Champions    ${CYAN}4335${NC}=La Liga       ${CYAN}4331${NC}=Bundesliga\n"
  read -p "  Ligas [4351,4406]: " FOOTBALL_LEAGUES
  FOOTBALL_LEAGUES="${FOOTBALL_LEAGUES:-4351,4406}"
  echo -e "  ${GREEN}✅ Ligas: $FOOTBALL_LEAGUES${NC}\n"

  echo -e "  ${BOLD}🎨 Cores do Banner${NC}"
  echo -e "  Padrão: fundo ${CYAN}0F0A1E${NC} (escuro) | destaque ${CYAN}C8910A${NC} (dourado)\n"
  read -p "  Personalizar cores? [s/N]: " mudar_cores

  COR_FUNDO="0F0A1E"
  COR_DESTAQUE="C8910A"
  COR_TEXTO="FFFFFF"

  if [[ "$mudar_cores" =~ ^[sS]$ ]]; then
    read -p "  COR_FUNDO    (hex sem #) [0F0A1E]: " inp; [ -n "$inp" ] && COR_FUNDO="${inp^^}"
    read -p "  COR_DESTAQUE (hex sem #) [C8910A]: " inp; [ -n "$inp" ] && COR_DESTAQUE="${inp^^}"
    read -p "  COR_TEXTO    (hex sem #) [FFFFFF]: " inp; [ -n "$inp" ] && COR_TEXTO="${inp^^}"
  fi

  echo ""
  pausar
}

# ──────────────────────────────────────────────────────────────
# ETAPA 3 — Instalar Docker se necessário
# ──────────────────────────────────────────────────────────────
step_docker() {
  titulo
  echo -e "  ${BOLD}🐳 ETAPA 3 — Docker${NC}\n"

  if command -v docker &>/dev/null; then
    VER=$(docker --version)
    echo -e "  ${GREEN}✅ Docker já instalado: $VER${NC}\n"
  else
    echo -e "  ${YELLOW}Docker não encontrado. Instalando...${NC}\n"
    curl -fsSL https://get.docker.com | bash > /dev/null 2>&1
    systemctl enable docker > /dev/null 2>&1
    systemctl start docker > /dev/null 2>&1
    if command -v docker &>/dev/null; then
      echo -e "  ${GREEN}✅ Docker instalado com sucesso!${NC}\n"
    else
      echo -e "  ${RED}❌ Falha ao instalar Docker. Instale manualmente.${NC}"
      exit 1
    fi
  fi
  sleep 1
}

# ──────────────────────────────────────────────────────────────
# ETAPA 4 — Criar estrutura e baixar arquivos
# ──────────────────────────────────────────────────────────────
step_arquivos() {
  titulo
  echo -e "  ${BOLD}📂 ETAPA 4 — Criando estrutura de arquivos${NC}\n"

  mkdir -p "$INSTALL_DIR/assets" "$INSTALL_DIR/output"
  echo -e "  ${GREEN}✅ Diretórios criados: $INSTALL_DIR${NC}"

  echo -e "  ⬇️  Baixando banner_bot.py..."
  if curl -fsSL "$REPO_RAW/banner_bot.py" -o "$INSTALL_DIR/banner_bot.py" 2>/dev/null \
     && [ -s "$INSTALL_DIR/banner_bot.py" ]; then
    echo -e "  ${GREEN}✅ banner_bot.py baixado!${NC}"
  else
    echo -e "  ${RED}❌ Falha ao baixar banner_bot.py!${NC}"
    exit 1
  fi

  echo -e "  ⬇️  Baixando logo..."
  if curl -fsSL "$REPO_RAW/assets/logo.png" \
       -o "$INSTALL_DIR/assets/logo.png" 2>/dev/null \
     && [ -s "$INSTALL_DIR/assets/logo.png" ]; then
    echo -e "  ${GREEN}✅ Logo baixada!${NC}"
  else
    echo -e "  ${YELLOW}⚠️  Logo não encontrada — banner funcionará sem logo.${NC}"
    echo -e "  ${YELLOW}   Coloque sua logo em: $INSTALL_DIR/assets/logo.png${NC}"
  fi

  cat > "$INSTALL_DIR/.env" << ENVEOF
TELEGRAM_BOT_TOKEN=$BOT_TOKEN
TELEGRAM_CHAT_ID=$CHAT_ID
HORA_ENVIO=$HORA_ENVIO
FOOTBALL_LEAGUES=$FOOTBALL_LEAGUES
LOGO_PATH=/app/assets/logo.png
COR_FUNDO=$COR_FUNDO
COR_DESTAQUE=$COR_DESTAQUE
COR_TEXTO=$COR_TEXTO
TZ=America/Sao_Paulo
ENVEOF
  chmod 600 "$INSTALL_DIR/.env"
  echo -e "  ${GREEN}✅ .env criado!${NC}\n"
  sleep 1
}

# ──────────────────────────────────────────────────────────────
# ETAPA 5 — Subir container
# ──────────────────────────────────────────────────────────────
step_container() {
  titulo
  echo -e "  ${BOLD}🚀 ETAPA 5 — Subindo container Docker${NC}\n"

  docker rm -f "$CONTAINER" 2>/dev/null || true

  docker run -d \
    --name "$CONTAINER" \
    --restart unless-stopped \
    --env-file "$INSTALL_DIR/.env" \
    -v "$INSTALL_DIR/banner_bot.py:/app/banner_bot.py:ro" \
    -v "$INSTALL_DIR/assets:/app/assets" \
    -v "$INSTALL_DIR/output:/app/output" \
    -w /app \
    python:3.12-slim \
    bash -c "apt-get update -qq && \
             apt-get install -y --no-install-recommends fonts-dejavu-core -qq 2>/dev/null; \
             pip install pillow requests python-telegram-bot schedule \
             -q --root-user-action=ignore && \
             python banner_bot.py" > /dev/null

  echo -e "  ⏳ Aguardando container iniciar (20s)...\n"
  sleep 20

  if docker ps --filter "name=$CONTAINER" --filter "status=running" | grep -q "$CONTAINER"; then
    titulo
    echo -e "${GREEN}${BOLD}"
    echo "  ╔══════════════════════════════════════════════════════╗"
    echo "  ║   🎉 BANNER BOT INSTALADO COM SUCESSO!              ║"
    echo "  ╚══════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo -e "  Container  : ${GREEN}$CONTAINER${NC} (rodando)"
    echo -e "  Envio      : ${CYAN}$HORA_ENVIO${NC} (Brasília)"
    echo -e "  Ligas      : ${CYAN}$FOOTBALL_LEAGUES${NC}"
    echo -e "  Dir        : ${CYAN}$INSTALL_DIR${NC}\n"
    echo -e "  ${BOLD}Comandos úteis:${NC}"
    echo -e "  ${CYAN}docker logs -f $CONTAINER${NC}          → Ver logs em tempo real"
    echo -e "  ${CYAN}docker exec $CONTAINER python -c 'import banner_bot; banner_bot.job()'${NC}"
    echo -e "                                       → Testar envio agora\n"
  else
    echo -e "  ${RED}❌ Container não iniciou. Logs:${NC}\n"
    docker logs "$CONTAINER" 2>&1 | tail -30
    echo -e "\n  ${YELLOW}Verifique o token e o chat_id:${NC}"
    echo -e "  ${CYAN}cat $INSTALL_DIR/.env${NC}\n"
  fi
}

# ──────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────
main() {
  if [ "$EUID" -ne 0 ]; then
    echo -e "\n  ${RED}Execute como root: sudo bash setup_completo.sh${NC}\n"
    exit 1
  fi

  for cmd in curl python3 base64; do
    command -v $cmd &>/dev/null || apt-get install -y $cmd -qq 2>/dev/null || true
  done

  titulo
  echo -e "  Bem-vindo ao instalador automático do ${BOLD}Inforlozzi Banner Bot${NC}!\n"
  echo -e "  Este script irá:\n"
  echo -e "   ${GREEN}1.${NC} Fazer upload da sua logo no GitHub (opcional)"
  echo -e "   ${GREEN}2.${NC} Configurar token, canal e horário"
  echo -e "   ${GREEN}3.${NC} Instalar Docker (se necessário)"
  echo -e "   ${GREEN}4.${NC} Baixar os arquivos do repositório"
  echo -e "   ${GREEN}5.${NC} Subir o container Docker automaticamente\n"
  pausar

  step_logo
  step_config
  step_docker
  step_arquivos
  step_container
}

main
