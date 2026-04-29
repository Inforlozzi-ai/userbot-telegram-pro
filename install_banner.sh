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

menu_principal() {
  titulo
  status=$(docker inspect --format='{{.State.Status}}' "$CONTAINER" 2>/dev/null || echo "não instalado")
  icon="❌"
  [ "$status" = "running" ] && icon="🟢"
  [ "$status" = "exited"  ] && icon="🔴"

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

configurar_visual() {
  titulo
  echo -e "  ${BOLD}🎨 CONFIGURAÇÃO VISUAL${NC}\n"

  ENV_FILE="$INSTALL_DIR/.env"
  COR_FUNDO=$(grep COR_FUNDO    "$ENV_FILE" 2>/dev/null | cut -d= -f2); COR_FUNDO=${COR_FUNDO:-0F0A1E}
  COR_DEST=$(grep  COR_DESTAQUE "$ENV_FILE" 2>/dev/null | cut -d= -f2); COR_DEST=${COR_DEST:-C8910A}
  COR_TEXTO=$(grep COR_TEXTO    "$ENV_FILE" 2>/dev/null | cut -d= -f2); COR_TEXTO=${COR_TEXTO:-FFFFFF}
  LOGO=$(grep      LOGO_PATH    "$ENV_FILE" 2>/dev/null | cut -d= -f2); LOGO=${LOGO:-/app/assets/logo.png}

  echo -e "  ${YELLOW}Valores atuais entre colchetes. ENTER para manter.${NC}\n"
  echo -e "  ${BOLD}LOGO${NC}"
  echo -e "  Arquivo atual: ${CYAN}$INSTALL_DIR/assets/logo.png${NC}"
  echo -e "  Para trocar: cole um novo PNG em $INSTALL_DIR/assets/logo.png"
  echo -e "  Ou informe outro caminho no container:"
  read -p "  Caminho [$LOGO]: " inp; [ -n "$inp" ] && LOGO="$inp"

  echo -e "\n  ${BOLD}CORES (hex sem # — ex: C8910A)${NC}"
  echo -e "  ${YELLOW}Sugestões:${NC}"
  echo -e "    0F0A1E = roxo escuro  |  C8910A = dourado Inforlozzi"
  echo -e "    1A0A00 = preto quente |  E94560 = vermelho  |  00B4D8 = azul\n"

  read -p "  COR_FUNDO    (fundo do banner)    [$COR_FUNDO]:  " inp; [ -n "$inp" ] && COR_FUNDO="${inp^^}"
  read -p "  COR_DESTAQUE (barras, horários)   [$COR_DEST]:   " inp; [ -n "$inp" ] && COR_DEST="${inp^^}"
  read -p "  COR_TEXTO    (texto principal)    [$COR_TEXTO]:  " inp; [ -n "$inp" ] && COR_TEXTO="${inp^^}"

  if [ -f "$ENV_FILE" ]; then
    sed -i "/^LOGO_PATH=/d;/^COR_FUNDO=/d;/^COR_DESTAQUE=/d;/^COR_TEXTO=/d" "$ENV_FILE"
    { echo "LOGO_PATH=$LOGO"; echo "COR_FUNDO=$COR_FUNDO"; echo "COR_DESTAQUE=$COR_DEST"; echo "COR_TEXTO=$COR_TEXTO"; } >> "$ENV_FILE"
    echo -e "\n  ${GREEN}✅ Salvo! Reiniciando...${NC}"
    _relancar
  else
    echo -e "\n  ${RED}❌ .env não encontrado. Instale primeiro (opção 1).${NC}"
  fi
  pausar; menu_principal
}

instalar() {
  [ "$EUID" -ne 0 ] && echo -e "  ${RED}Execute como root: sudo bash install_banner.sh${NC}" && exit 1
  titulo

  if ! command -v docker &>/dev/null; then
    echo -e "  ${YELLOW}Instalando Docker...${NC}"
    curl -fsSL https://get.docker.com | bash >/dev/null 2>&1
    systemctl enable docker >/dev/null 2>&1; systemctl start docker >/dev/null 2>&1
    echo -e "  ${GREEN}✅ Docker instalado!${NC}"
  fi

  titulo
  echo -e "  ${BOLD}📱 PASSO 1 — Token do Bot${NC}\n"
  echo -e "  Crie ou use um bot existente via ${CYAN}@BotFather${NC}\n"
  read -p "  BOT_TOKEN: " BOT_TOKEN
  while [[ ! "$BOT_TOKEN" == *":"* ]]; do
    echo -e "  ${RED}❌ Token inválido!${NC}"; read -p "  BOT_TOKEN: " BOT_TOKEN
  done
  pausar

  titulo
  echo -e "  ${BOLD}📢 PASSO 2 — ID do Canal/Grupo${NC}\n"
  echo -e "  Para canais: -100XXXXXXXXXX  |  Grupos: -XXXXXXXXXX"
  echo -e "  ${YELLOW}Dica: envie uma mensagem no grupo e use @userinfobot${NC}\n"
  read -p "  CHAT_ID: " CHAT_ID
  while [[ ! "$CHAT_ID" == -* ]]; do
    echo -e "  ${RED}❌ Deve começar com '-'${NC}"; read -p "  CHAT_ID: " CHAT_ID
  done
  pausar

  titulo
  echo -e "  ${BOLD}⏰ PASSO 3 — Horário de envio (Brasília)${NC}\n"
  read -p "  Horário [08:00]: " HORA_ENVIO
  HORA_ENVIO="${HORA_ENVIO:-08:00}"
  pausar

  titulo
  echo -e "  ${BOLD}⚽ PASSO 4 — Ligas de Futebol${NC}\n"
  echo -e "    ${CYAN}4351${NC} = Brasileirão  |  ${CYAN}4406${NC} = Libertadores"
  echo -e "    ${CYAN}4328${NC} = Premier League  |  ${CYAN}4480${NC} = Champions League"
  echo -e "    ${CYAN}4335${NC} = La Liga  |  ${CYAN}4331${NC} = Bundesliga\n"
  read -p "  Ligas [4351,4406]: " FOOTBALL_LEAGUES
  FOOTBALL_LEAGUES="${FOOTBALL_LEAGUES:-4351,4406}"
  pausar

  titulo
  echo -e "  ${BOLD}🎨 PASSO 5 — Visual${NC}\n"
  echo -e "  ${GREEN}Logo Inforlozzi será baixada automaticamente do repositório.${NC}"
  echo -e "  Você pode trocar depois com a opção [2] do menu.\n"
  read -p "  Configurar cores agora? [s/N]: " conf_visual

  COR_FUNDO="0F0A1E"
  COR_DESTAQUE="C8910A"
  COR_TEXTO="FFFFFF"

  if [[ "$conf_visual" =~ ^[sS]$ ]]; then
    echo -e "\n  ${BOLD}CORES (hex sem # — ENTER para usar padrão)${NC}"
    echo -e "  Padrão: fundo ${CYAN}0F0A1E${NC} | destaque ${CYAN}C8910A${NC} (dourado) | texto ${CYAN}FFFFFF${NC}\n"
    read -p "  COR_FUNDO    [0F0A1E]: " inp; [ -n "$inp" ] && COR_FUNDO="${inp^^}"
    read -p "  COR_DESTAQUE [C8910A]: " inp; [ -n "$inp" ] && COR_DESTAQUE="${inp^^}"
    read -p "  COR_TEXTO    [FFFFFF]: " inp; [ -n "$inp" ] && COR_TEXTO="${inp^^}"
  fi
  pausar

  # Criar estrutura
  mkdir -p "$INSTALL_DIR/assets" "$INSTALL_DIR/output"

  # Baixar banner_bot.py
  if curl -fsSL "$REPO_RAW/banner_bot.py" -o "$INSTALL_DIR/banner_bot.py" 2>/dev/null; then
    echo -e "  ${GREEN}✅ banner_bot.py baixado!${NC}"
  elif [ -f "$SCRIPT_DIR/banner_bot.py" ]; then
    cp "$SCRIPT_DIR/banner_bot.py" "$INSTALL_DIR/banner_bot.py"
    echo -e "  ${GREEN}✅ banner_bot.py copiado!${NC}"
  else
    echo -e "  ${RED}❌ banner_bot.py não encontrado!${NC}"; pausar; return
  fi

  # Baixar logo do repositorio
  echo -e "  🚀 Baixando logo do repositório..."
  if curl -fsSL "$REPO_RAW/assets/logo.png" \
       -o "$INSTALL_DIR/assets/logo.png" 2>/dev/null \
     && [ -s "$INSTALL_DIR/assets/logo.png" ]; then
    echo -e "  ${GREEN}✅ Logo baixada!${NC}"
  else
    echo -e "  ${YELLOW}⚠️  Logo não encontrada — banner funcionará sem logo.${NC}"
    echo -e "  ${YELLOW}   Coloque sua logo em: $INSTALL_DIR/assets/logo.png${NC}"
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

  _relancar

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
    echo -e "  Envio     : ${CYAN}$HORA_ENVIO${NC} (Brasília)"
    echo -e "  Ligas     : ${CYAN}$FOOTBALL_LEAGUES${NC}\n"
    echo -e "  ${BOLD}Próximos passos:${NC}"
    echo -e "  1. Use ${CYAN}[3] Testar agora${NC} para ver o banner"
    echo -e "  2. Ajuste cores com ${CYAN}[2] Configurar visual${NC}\n"
  else
    echo -e "\n  ${RED}❌ Erro ao iniciar! Logs:${NC}\n"
    docker logs "$CONTAINER" 2>&1 | tail -25
  fi
  pausar; menu_principal
}

_relancar() {
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

testar() {
  titulo
  echo -e "  ${BOLD}▶️  Executando job de teste agora...${NC}\n"
  docker exec "$CONTAINER" python -c "import banner_bot; banner_bot.job()" 2>&1 | tail -30
  pausar; menu_principal
}

ver_logs() {
  titulo
  echo -e "  ${YELLOW}Pressione Ctrl+C para sair${NC}\n"
  docker logs -f "$CONTAINER" 2>&1
  pausar; menu_principal
}

reiniciar() {
  titulo
  docker restart "$CONTAINER" && \
    echo -e "  ${GREEN}✅ Reiniciado!${NC}" || echo -e "  ${RED}❌ Erro.${NC}"
  pausar; menu_principal
}

parar() {
  titulo
  docker stop "$CONTAINER" && \
    echo -e "  ${GREEN}✅ Parado!${NC}" || echo -e "  ${RED}❌ Erro.${NC}"
  pausar; menu_principal
}

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
