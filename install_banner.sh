#!/bin/bash
# =============================================================
#   BANNER BOT — Instalador  |  Inforlozzi-ai
#   Instala/gerencia o bot de banners de jogos (NBA + Futebol)
# =============================================================
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_RAW="https://raw.githubusercontent.com/Inforlozzi-ai/userbot-telegram-pro/main"
CONTAINER="banner-bot"
INSTALL_DIR="/opt/$CONTAINER"

pausar() { echo ""; read -p "  Pressione ENTER para continuar..." x; }
limpar() { clear; }

titulo() {
  limpar
  echo -e "${CYAN}${BOLD}"
  echo "  ╔══════════════════════════════════════════════════╗"
  echo "  ║        🎨 BANNER BOT — Jogos do Dia            ║"
  echo "  ╚══════════════════════════════════════════════════╝"
  echo -e "${NC}"
}

# ── MENU ───────────────────────────────────────────────────────────────────
menu_principal() {
  titulo
  status=$(docker inspect --format='{{.State.Status}}' "$CONTAINER" 2>/dev/null || echo "não instalado")
  icon="❌"
  [ "$status" = "running" ]  && icon="🟢"
  [ "$status" = "exited"  ]  && icon="🔴"

  echo -e "  Status: $icon ${BOLD}$CONTAINER${NC} ($status)\n"
  echo -e "  ${CYAN}[1]${NC} 🆕 Instalar / Reinstalar"
  echo -e "  ${CYAN}[2]${NC} 🎨 Configurar logo e cores"
  echo -e "  ${CYAN}[3]${NC} ▶️  Testar agora (gerar e enviar)"
  echo -e "  ${CYAN}[4]${NC} 📋 Ver logs"
  echo -e "  ${CYAN}[5]${NC} 🔄 Reiniciar container"
  echo -e "  ${CYAN}[6]${NC} ⏹  Parar container"
  echo -e "  ${CYAN}[7]${NC} 🗑  Desinstalar"
  echo -e "  ${CYAN}[8]${NC} ❌ Sair\n"
  read -p "  Escolha [1-8]: " op
  case $op in
    1) instalar ;;
    2) configurar_visual ;;
    3) testar ;;
    4) ver_logs ;;
    5) reiniciar ;;
    6) parar ;;
    7) desinstalar ;;
    8) echo -e "\n  ${GREEN}Até logo! 👋${NC}\n"; exit 0 ;;
    *) menu_principal ;;
  esac
}

# ── CONFIGURAR LOGO E CORES ────────────────────────────────────────────────
configurar_visual() {
  titulo
  echo -e "  ${BOLD}🎨 CONFIGURAÇÃO VISUAL${NC}\n"

  # Carrega valores atuais do .env
  ENV_FILE="$INSTALL_DIR/.env"
  COR_FUNDO=$(grep COR_FUNDO     "$ENV_FILE" 2>/dev/null | cut -d= -f2) ; COR_FUNDO=${COR_FUNDO:-0F0A1E}
  COR_DEST=$(grep  COR_DESTAQUE  "$ENV_FILE" 2>/dev/null | cut -d= -f2) ; COR_DEST=${COR_DEST:-8A2BE2}
  COR_TEXTO=$(grep COR_TEXTO     "$ENV_FILE" 2>/dev/null | cut -d= -f2) ; COR_TEXTO=${COR_TEXTO:-FFFFFF}
  LOGO=$(grep      LOGO_PATH     "$ENV_FILE" 2>/dev/null | cut -d= -f2) ; LOGO=${LOGO:-/app/assets/logo.png}

  echo -e "  ${YELLOW}Valores atuais entre colchetes. ENTER para manter.${NC}\n"

  # Logo
  echo -e "  ${BOLD}LOGO${NC}"
  echo -e "  Coloque seu arquivo PNG em:  ${CYAN}$INSTALL_DIR/assets/logo.png${NC}"
  echo -e "  Ou informe outro caminho no container (ex: /app/assets/logo.png)"
  read -p "  Caminho da logo no container [$LOGO]: " inp
  [ -n "$inp" ] && LOGO="$inp"

  # Cores (hex sem #)
  echo -e "\n  ${BOLD}CORES (hex sem # — ex: 8A2BE2)${NC}"
  echo -e "  ${YELLOW}Paleta de referência:${NC}"
  echo -e "    0F0A1E = roxo muito escuro  |  1A1230 = card escuro"
  echo -e "    8A2BE2 = violeta            |  00B4D8 = azul ciano"
  echo -e "    E94560 = vermelho           |  F5A623 = laranja\n"

  read -p "  COR_FUNDO    (cor de fundo do banner) [$COR_FUNDO]: "   inp; [ -n "$inp" ] && COR_FUNDO="${inp^^}"
  read -p "  COR_DESTAQUE (barra lateral, horário) [$COR_DEST]:  "   inp; [ -n "$inp" ] && COR_DEST="${inp^^}"
  read -p "  COR_TEXTO    (texto principal)        [$COR_TEXTO]:  "  inp; [ -n "$inp" ] && COR_TEXTO="${inp^^}"

  # Escreve no .env
  if [ -f "$ENV_FILE" ]; then
    sed -i "/^LOGO_PATH=/d;/^COR_FUNDO=/d;/^COR_DESTAQUE=/d;/^COR_TEXTO=/d" "$ENV_FILE"
    {
      echo "LOGO_PATH=$LOGO"
      echo "COR_FUNDO=$COR_FUNDO"
      echo "COR_DESTAQUE=$COR_DEST"
      echo "COR_TEXTO=$COR_TEXTO"
    } >> "$ENV_FILE"
    echo -e "\n  ${GREEN}✅ Configuração salva em $ENV_FILE${NC}"
    echo -e "  ${YELLOW}Reiniciando container para aplicar...${NC}"
    _relançar
  else
    echo -e "\n  ${RED}❌ .env não encontrado. Instale primeiro (opção 1).${NC}"
  fi
  pausar; menu_principal
}

# ── INSTALAR ───────────────────────────────────────────────────────────────
instalar() {
  [ "$EUID" -ne 0 ] && echo -e "  ${RED}Execute como root: sudo bash install_banner.sh${NC}" && exit 1
  titulo

  # Verificar Docker
  if ! command -v docker &>/dev/null; then
    echo -e "  ${YELLOW}Instalando Docker...${NC}"
    curl -fsSL https://get.docker.com | bash >/dev/null 2>&1
    systemctl enable docker >/dev/null 2>&1; systemctl start docker >/dev/null 2>&1
    echo -e "  ${GREEN}✅ Docker instalado!${NC}"
  fi

  echo -e "  ${BOLD}📱 PASSO 1 — Token do Bot (BOT_TOKEN)${NC}\n"
  echo -e "  Crie ou use um bot existente via ${CYAN}@BotFather${NC}\n"
  read -p "  BOT_TOKEN: " BOT_TOKEN
  while [[ ! "$BOT_TOKEN" == *":"* ]]; do
    echo -e "  ${RED}❌ Token inválido!${NC}"; read -p "  BOT_TOKEN: " BOT_TOKEN
  done
  pausar

  titulo
  echo -e "  ${BOLD}📢 PASSO 2 — ID do Canal/Grupo${NC}\n"
  echo -e "  Para canais: -100XXXXXXXXXX"
  echo -e "  Para grupos: -XXXXXXXXXX"
  echo -e "  ${YELLOW}Dica: use @userinfobot no Telegram para descobrir o ID${NC}\n"
  read -p "  CHAT_ID: " CHAT_ID
  while [[ ! "$CHAT_ID" == -* ]]; do
    echo -e "  ${RED}❌ Deve começar com '-'${NC}"; read -p "  CHAT_ID: " CHAT_ID
  done
  pausar

  titulo
  echo -e "  ${BOLD}⏰ PASSO 3 — Horário de envio${NC}\n"
  echo -e "  Horário diário para enviar os banners (fuso de Brasília)."
  read -p "  Horário [08:00]: " HORA_ENVIO
  HORA_ENVIO="${HORA_ENVIO:-08:00}"
  pausar

  titulo
  echo -e "  ${BOLD}⚽ PASSO 4 — Ligas de Futebol${NC}\n"
  echo -e "  IDs das ligas TheSportsDB separados por vírgula:"
  echo -e "    ${CYAN}4351${NC} = Brasileirão Série A"
  echo -e "    ${CYAN}4406${NC} = Copa Libertadores"
  echo -e "    ${CYAN}4328${NC} = Premier League"
  echo -e "    ${CYAN}4335${NC} = La Liga"
  echo -e "    ${CYAN}4331${NC} = Bundesliga"
  echo -e "    ${CYAN}4480${NC} = UEFA Champions League\n"
  read -p "  Ligas [4351,4406]: " FOOTBALL_LEAGUES
  FOOTBALL_LEAGUES="${FOOTBALL_LEAGUES:-4351,4406}"
  pausar

  titulo
  echo -e "  ${BOLD}🎨 PASSO 5 — Visual (logo e cores)${NC}\n"
  echo -e "  ${YELLOW}Você pode pular agora e configurar depois com a opção [2]${NC}\n"
  read -p "  Configurar agora? [s/N]: " conf_visual

  COR_FUNDO="0F0A1E"
  COR_DESTAQUE="8A2BE2"
  COR_TEXTO="FFFFFF"

  if [[ "$conf_visual" =~ ^[sS]$ ]]; then
    echo -e "\n  ${BOLD}CORES (hex sem # — ENTER para usar padrão)${NC}\n"
    read -p "  COR_FUNDO    (fundo escuro)  [0F0A1E]: " inp; [ -n "$inp" ] && COR_FUNDO="${inp^^}"
    read -p "  COR_DESTAQUE (destaque)      [8A2BE2]: " inp; [ -n "$inp" ] && COR_DESTAQUE="${inp^^}"
    read -p "  COR_TEXTO    (texto)         [FFFFFF]: " inp; [ -n "$inp" ] && COR_TEXTO="${inp^^}"
  fi
  pausar

  # Criar estrutura
  mkdir -p "$INSTALL_DIR/assets" "$INSTALL_DIR/output"

  echo -e "\n  ${YELLOW}💡 Coloque sua logo PNG em: ${CYAN}$INSTALL_DIR/assets/logo.png${NC}"
  echo -e "  ${YELLOW}   (se não colocar, o espaço fica em branco — sem erro)${NC}\n"
  pausar

  # Baixar banner_bot.py
  if curl -fsSL "$REPO_RAW/banner_bot.py" -o "$INSTALL_DIR/banner_bot.py" 2>/dev/null; then
    echo -e "  ${GREEN}✅ banner_bot.py baixado!${NC}"
  elif [ -f "$SCRIPT_DIR/banner_bot.py" ]; then
    cp "$SCRIPT_DIR/banner_bot.py" "$INSTALL_DIR/banner_bot.py"
    echo -e "  ${GREEN}✅ banner_bot.py copiado!${NC}"
  else
    echo -e "  ${RED}❌ banner_bot.py não encontrado!${NC}"; pausar; return
  fi

  # Escrever .env
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

  _relançar

  echo -e "  ⏳ Aguardando inicialização (15s)..."
  sleep 15

  if docker ps | grep -q "$CONTAINER"; then
    titulo
    echo -e "${GREEN}${BOLD}"
    echo "  ╔══════════════════════════════════════════════════╗"
    echo "  ║       🎉 BANNER BOT INSTALADO COM SUCESSO!     ║"
    echo "  ╚══════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo -e "  Container : ${GREEN}$CONTAINER${NC}"
    echo -e "  Envio     : ${CYAN}$HORA_ENVIO${NC} (horário de Brasília)"
    echo -e "  Ligas     : ${CYAN}$FOOTBALL_LEAGUES${NC}\n"
    echo -e "  ${BOLD}Próximos passos:${NC}"
    echo -e "  1. Coloque sua logo em: ${CYAN}$INSTALL_DIR/assets/logo.png${NC}"
    echo -e "  2. Use a opção ${CYAN}[3] Testar agora${NC} para ver o resultado"
    echo -e "  3. Ajuste cores quando quiser com a opção ${CYAN}[2]${NC}\n"
  else
    echo -e "\n  ${RED}❌ Erro ao iniciar! Logs:${NC}\n"
    docker logs "$CONTAINER" 2>&1 | tail -25
  fi
  pausar; menu_principal
}

# ── LANÇAR / RELANÇAR CONTAINER ────────────────────────────────────────────
_relançar() {
  # Carrega .env
  source "$INSTALL_DIR/.env" 2>/dev/null
  docker rm -f "$CONTAINER" 2>/dev/null || true
  echo -e "  🚀 Subindo container..."
  docker run -d \
    --name "$CONTAINER" \
    --restart unless-stopped \
    --env-file "$INSTALL_DIR/.env" \
    -v "$INSTALL_DIR/banner_bot.py:/app/banner_bot.py:ro" \
    -v "$INSTALL_DIR/assets:/app/assets" \
    -v "$INSTALL_DIR/output:/app/output" \
    -w /app \
    python:3.12-slim \
    bash -c "apt-get update -qq && apt-get install -y --no-install-recommends \
             fonts-dejavu-core 2>/dev/null; \
             pip install pillow requests python-telegram-bot schedule \
             -q --root-user-action=ignore && \
             python banner_bot.py" >/dev/null
  echo -e "  ${GREEN}✅ Container iniciado!${NC}"
}

# ── TESTAR ─────────────────────────────────────────────────────────────────
testar() {
  titulo
  echo -e "  ${BOLD}▶️  Executando job de teste agora...${NC}\n"
  docker exec "$CONTAINER" \
    python -c "import banner_bot; banner_bot.job()" 2>&1 | tail -30
  pausar; menu_principal
}

# ── LOGS ───────────────────────────────────────────────────────────────────
ver_logs() {
  titulo
  echo -e "  ${YELLOW}Pressione Ctrl+C para sair${NC}\n"
  docker logs -f "$CONTAINER" 2>&1
  pausar; menu_principal
}

# ── REINICIAR ──────────────────────────────────────────────────────────────
reiniciar() {
  titulo
  docker restart "$CONTAINER" && \
    echo -e "  ${GREEN}✅ Reiniciado!${NC}" || \
    echo -e "  ${RED}❌ Erro.${NC}"
  pausar; menu_principal
}

# ── PARAR ──────────────────────────────────────────────────────────────────
parar() {
  titulo
  docker stop "$CONTAINER" && \
    echo -e "  ${GREEN}✅ Parado!${NC}" || \
    echo -e "  ${RED}❌ Erro.${NC}"
  pausar; menu_principal
}

# ── DESINSTALAR ────────────────────────────────────────────────────────────
desinstalar() {
  titulo
  echo -e "  ${RED}${BOLD}⚠️  Isso vai remover o container e todos os arquivos!${NC}\n"
  read -p "  Tem certeza? Digite CONFIRMAR: " conf
  if [ "$conf" = "CONFIRMAR" ]; then
    docker rm -f "$CONTAINER" 2>/dev/null
    rm -rf "$INSTALL_DIR"
    echo -e "  ${GREEN}✅ Banner Bot removido!${NC}"
  else
    echo -e "  ${YELLOW}Cancelado.${NC}"
  fi
  pausar; menu_principal
}

menu_principal
