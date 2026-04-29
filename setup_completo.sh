#!/bin/bash
# =============================================================
#   SETUP COMPLETO — Inforlozzi Banner Bot
#   Instala tudo automaticamente no VPS
#   Uso: curl -fsSL https://raw.githubusercontent.com/Inforlozzi-ai/userbot-telegram-pro/main/setup_completo.sh | sudo bash
# =============================================================

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

REPO_OWNER="Inforlozzi-ai"
REPO_NAME="userbot-telegram-pro"
REPO_RAW="https://raw.githubusercontent.com/$REPO_OWNER/$REPO_NAME/main"
CONTAINER="banner-bot"
INSTALL_DIR="/opt/$CONTAINER"
TMP_LOGO="/tmp/logo_upload.png"

pausar() { echo ""; read -p "  Pressione ENTER para continuar..." x; }

titulo() {
  clear
  echo -e "${CYAN}${BOLD}"
  echo "  ╔══════════════════════════════════════════════════════╗"
  echo "  ║   🦁  INFORLOZZI — Setup Completo Banner Bot        ║"
  echo "  ╚══════════════════════════════════════════════════════╝"
  echo -e "${NC}"
}

# ================================================================
# UPLOAD DA LOGO — 3 formas: arquivo local, URL, ou via Telegram
# ================================================================
step_logo() {
  titulo
  echo -e "  ${BOLD}📸 ETAPA 1 — Logo do Banner${NC}\n"
  echo -e "  Escolha como enviar sua logo:\n"
  echo -e "  ${CYAN}[1]${NC} 📱 Enviar pelo Telegram (mais fácil — PC ou celular)"
  echo -e "  ${CYAN}[2]${NC} 🔗 URL direta (link de imagem público)"
  echo -e "  ${CYAN}[3]${NC} 📂 Arquivo já está no servidor (/tmp/logo.png etc)"
  echo -e "  ${CYAN}[4]${NC} ⏩ Pular (usar sem logo por enquanto)\n"
  read -p "  Escolha [1-4]: " modo_logo

  case $modo_logo in
    1) _logo_via_telegram ;;
    2) _logo_via_url ;;
    3) _logo_via_arquivo ;;
    4)
      echo -e "\n  ${YELLOW}⚠️ Logo pulada. Você pode adicionar depois em:${NC}"
      echo -e "  ${CYAN}$INSTALL_DIR/assets/logo.png${NC}\n"
      sleep 2; return 0 ;;
    *) step_logo ;;
  esac
}

# ---- Opção 1: Telegram ----------------------------------------
_logo_via_telegram() {
  titulo
  echo -e "  ${BOLD}📱 Envio via Telegram${NC}\n"
  echo -e "  Vamos usar um bot temporário para receber sua logo.\n"
  echo -e "  ${BOLD}Passo a passo:${NC}\n"
  echo -e "   1. Abra o Telegram no celular ou PC"
  echo -e "   2. Vá para ${CYAN}@userinfobot${NC} e envie /start para pegar seu user ID"
  echo -e "   3. Crie um bot rápido no ${CYAN}@BotFather${NC} — ou use o token do seu bot atual"
  echo -e "   4. Envie a logo como ${BOLD}DOCUMENTO${NC} (não como foto, para não comprimir)\n"
  echo -e "  ${YELLOW}⚠️  Envie como DOCUMENTO para manter qualidade original!${NC}\n"

  read -p "  Token do bot para receber a logo: " TMP_TOKEN
  if [[ ! "$TMP_TOKEN" == *":"* ]]; then
    echo -e "  ${RED}❌ Token inválido.${NC}"
    _logo_via_telegram
    return
  fi

  read -p "  Seu Telegram User ID (de @userinfobot): " TG_USER_ID
  if [ -z "$TG_USER_ID" ]; then
    echo -e "  ${RED}❌ User ID não informado.${NC}"
    return 1
  fi

  echo -e "\n  ${GREEN}Aguardando você enviar a logo como documento no Telegram...${NC}"
  echo -e "  ${YELLOW}(Aguardando por até 5 minutos)${NC}\n"

  # Limpa updates antigos
  OFFSET=$(curl -s "https://api.telegram.org/bot$TMP_TOKEN/getUpdates" \
    | python3 -c "import sys,json; ups=json.load(sys.stdin).get('result',[]); print(ups[-1]['update_id']+1 if ups else 0)" 2>/dev/null)

  # Envia mensagem de instrução pro usuário
  curl -s -X POST "https://api.telegram.org/bot$TMP_TOKEN/sendMessage" \
    -d chat_id="$TG_USER_ID" \
    -d text="🦁 *Inforlozzi Setup*%0A%0AEnvie agora sua logo como *DOCUMENTO* 📄%0A%0A⚠️ Use 'Anexar arquivo' (não foto) para manter qualidade!" \
    -d parse_mode="Markdown" > /dev/null 2>&1

  FILE_ID=""
  TENTATIVAS=0
  MAX=60  # 60 x 5s = 5 minutos

  while [ -z "$FILE_ID" ] && [ $TENTATIVAS -lt $MAX ]; do
    sleep 5
    TENTATIVAS=$((TENTATIVAS+1))
    printf "  ⏳ Aguardando... (%ds)\r" $((TENTATIVAS*5))

    RESP=$(curl -s "https://api.telegram.org/bot$TMP_TOKEN/getUpdates?offset=$OFFSET&timeout=4")

    FILE_ID=$(echo "$RESP" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for upd in data.get('result', []):
    msg = upd.get('message', {})
    if str(msg.get('chat', {}).get('id', '')) == '$TG_USER_ID':
        doc = msg.get('document', {})
        if doc.get('file_name','').lower().endswith(('.png','.jpg','.jpeg')):
            print(doc.get('file_id',''))
            break
        photo = msg.get('photo', [])
        if photo:
            print(photo[-1].get('file_id',''))
            break
" 2>/dev/null)

    OFFSET=$(echo "$RESP" | python3 -c "
import sys,json
ups=json.load(sys.stdin).get('result',[])
print(ups[-1]['update_id']+1 if ups else $OFFSET)
" 2>/dev/null || echo $OFFSET)
  done

  echo ""

  if [ -z "$FILE_ID" ]; then
    echo -e "  ${RED}❌ Tempo esgotado. Nenhuma logo recebida.${NC}"
    echo -e "  ${YELLOW}Tente outra opção ou pule e adicione a logo depois.${NC}\n"
    sleep 2; return 1
  fi

  echo -e "  ${GREEN}✅ Logo recebida! Baixando...${NC}"

  # Pega URL de download
  FILE_PATH=$(curl -s "https://api.telegram.org/bot$TMP_TOKEN/getFile?file_id=$FILE_ID" \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['result']['file_path'])" 2>/dev/null)

  curl -fsSL "https://api.telegram.org/file/bot$TMP_TOKEN/$FILE_PATH" -o "$TMP_LOGO" 2>/dev/null

  if [ -s "$TMP_LOGO" ]; then
    SIZE=$(du -h "$TMP_LOGO" | cut -f1)
    echo -e "  ${GREEN}✅ Logo salva! ($SIZE)${NC}\n"
    # Confirma via Telegram
    curl -s -X POST "https://api.telegram.org/bot$TMP_TOKEN/sendMessage" \
      -d chat_id="$TG_USER_ID" \
      -d text="✅ Logo recebida com sucesso! Continuando instalação..." > /dev/null 2>&1
    _upload_logo_github "$TMP_LOGO"
  else
    echo -e "  ${RED}❌ Falha ao baixar o arquivo.${NC}\n"
    return 1
  fi
}

# ---- Opção 2: URL direta ------------------------------------
_logo_via_url() {
  titulo
  echo -e "  ${BOLD}🔗 Logo via URL${NC}\n"
  echo -e "  Cole o link direto da imagem (PNG ou JPG).\n"
  echo -e "  ${YELLOW}Dicas para obter link direto:${NC}"
  echo -e "   • Google Drive: clique em compartilhar → 'Qualquer pessoa' → copie o link"
  echo -e "     depois substitua '/view' por '/uc?export=download'"
  echo -e "   • Telegram Web: abra a imagem → botão direito → Copiar endereço da imagem"
  echo -e "   • Discord: clique na imagem → 'Abrir link original' → copie a URL\n"
  read -p "  URL da logo: " LOGO_URL

  if [ -z "$LOGO_URL" ]; then
    echo -e "  ${RED}❌ URL não informada.${NC}\n"
    return 1
  fi

  echo -e "  ⬇️  Baixando imagem...\n"
  if curl -fsSL -A "Mozilla/5.0" "$LOGO_URL" -o "$TMP_LOGO" 2>/dev/null && [ -s "$TMP_LOGO" ]; then
    SIZE=$(du -h "$TMP_LOGO" | cut -f1)
    echo -e "  ${GREEN}✅ Imagem baixada! ($SIZE)${NC}\n"
    _upload_logo_github "$TMP_LOGO"
  else
    echo -e "  ${RED}❌ Falha ao baixar. Verifique se a URL é pública e direta.${NC}\n"
    sleep 2; return 1
  fi
}

# ---- Opção 3: Arquivo local ---------------------------------
_logo_via_arquivo() {
  titulo
  echo -e "  ${BOLD}📂 Arquivo local${NC}\n"
  echo -e "  ${YELLOW}Para copiar do PC para o VPS:${NC}"
  echo -e "  ${CYAN}scp logo.png root@SEU_IP:/tmp/logo.png${NC}\n"
  read -p "  Caminho do arquivo [/tmp/logo.png]: " LOGO_PATH
  LOGO_PATH="${LOGO_PATH:-/tmp/logo.png}"

  if [ ! -f "$LOGO_PATH" ]; then
    echo -e "\n  ${RED}❌ Arquivo não encontrado: $LOGO_PATH${NC}\n"
    sleep 2; return 1
  fi

  cp "$LOGO_PATH" "$TMP_LOGO"
  SIZE=$(du -h "$TMP_LOGO" | cut -f1)
  echo -e "  ${GREEN}✅ Arquivo encontrado! ($SIZE)${NC}\n"
  _upload_logo_github "$TMP_LOGO"
}

# ---- Upload para o GitHub -----------------------------------
_upload_logo_github() {
  local LOGO_FILE="$1"

  echo -e "  ${BOLD}🚀 Enviar logo para o GitHub?${NC}"
  echo -e "  (Assim ela será baixada automaticamente em toda instalação)\n"
  echo -e "  Precisa de um GitHub Token (scope: repo)"
  echo -e "  Gere em: ${CYAN}https://github.com/settings/tokens${NC}\n"
  read -p "  Token (ENTER para pular): " GH_TOKEN

  if [ -z "$GH_TOKEN" ]; then
    echo -e "  ${YELLOW}Pulando upload GitHub. Logo será usada apenas neste servidor.${NC}\n"
    mkdir -p "$INSTALL_DIR/assets"
    cp "$LOGO_FILE" "$INSTALL_DIR/assets/logo.png"
    sleep 2; return 0
  fi

  echo -e "  🚀 Enviando para GitHub...\n"
  B64=$(base64 -w0 "$LOGO_FILE")

  SHA=$(curl -s \
    -H "Authorization: Bearer $GH_TOKEN" \
    -H "Accept: application/vnd.github+json" \
    "https://api.github.com/repos/$REPO_OWNER/$REPO_NAME/contents/assets/logo.png" \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('sha',''))" 2>/dev/null)

  if [ -n "$SHA" ]; then
    PAYLOAD="{\"message\":\"feat: logo Inforlozzi atualizada\",\"content\":\"$B64\",\"sha\":\"$SHA\",\"branch\":\"main\"}"
  else
    PAYLOAD="{\"message\":\"feat: logo Inforlozzi\",\"content\":\"$B64\",\"branch\":\"main\"}"
  fi

  RESULT=$(curl -s -X PUT \
    -H "Authorization: Bearer $GH_TOKEN" \
    -H "Accept: application/vnd.github+json" \
    "https://api.github.com/repos/$REPO_OWNER/$REPO_NAME/contents/assets/logo.png" \
    -d "$PAYLOAD" \
    | python3 -c "
import sys,json
r=json.load(sys.stdin)
if 'content' in r: print('OK:'+r['content'].get('html_url',''))
else: print('ERRO:'+r.get('message','desconhecido'))
" 2>/dev/null)

  if [[ "$RESULT" == OK:* ]]; then
    echo -e "  ${GREEN}✅ Logo salva no GitHub!${NC}"
    echo -e "  🔗 ${CYAN}${RESULT#OK:}${NC}\n"
  else
    echo -e "  ${RED}❌ Erro: ${RESULT#ERRO:}${NC}"
    echo -e "  ${YELLOW}Logo será usada apenas localmente.${NC}\n"
    mkdir -p "$INSTALL_DIR/assets"
    cp "$LOGO_FILE" "$INSTALL_DIR/assets/logo.png"
  fi
  sleep 2
}

# ================================================================
# ETAPA 2 — Configurações do bot
# ================================================================
step_config() {
  titulo
  echo -e "  ${BOLD}⚙️  ETAPA 2 — Configuração do Bot${NC}\n"

  echo -e "  ${BOLD}📱 Token do Bot Telegram${NC}"
  echo -e "  Use o bot já existente ou crie via ${CYAN}@BotFather${NC}\n"
  read -p "  BOT_TOKEN: " BOT_TOKEN
  while [[ ! "$BOT_TOKEN" == *":"* ]]; do
    echo -e "  ${RED}❌ Token inválido!${NC}"
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
    read -p "  COR_FUNDO    [0F0A1E]: " inp; [ -n "$inp" ] && COR_FUNDO="${inp^^}"
    read -p "  COR_DESTAQUE [C8910A]: " inp; [ -n "$inp" ] && COR_DESTAQUE="${inp^^}"
    read -p "  COR_TEXTO    [FFFFFF]: " inp; [ -n "$inp" ] && COR_TEXTO="${inp^^}"
  fi

  echo ""
  pausar
}

# ================================================================
# ETAPA 3 — Docker
# ================================================================
step_docker() {
  titulo
  echo -e "  ${BOLD}🐳 ETAPA 3 — Docker${NC}\n"

  if command -v docker &>/dev/null; then
    echo -e "  ${GREEN}✅ Docker já instalado: $(docker --version)${NC}\n"
  else
    echo -e "  ${YELLOW}Instalando Docker...${NC}\n"
    curl -fsSL https://get.docker.com | bash > /dev/null 2>&1
    systemctl enable docker > /dev/null 2>&1
    systemctl start docker > /dev/null 2>&1
    command -v docker &>/dev/null \
      && echo -e "  ${GREEN}✅ Docker instalado!${NC}\n" \
      || { echo -e "  ${RED}❌ Falha no Docker.${NC}"; exit 1; }
  fi
  sleep 1
}

# ================================================================
# ETAPA 4 — Arquivos
# ================================================================
step_arquivos() {
  titulo
  echo -e "  ${BOLD}📂 ETAPA 4 — Arquivos${NC}\n"

  mkdir -p "$INSTALL_DIR/assets" "$INSTALL_DIR/output"
  echo -e "  ${GREEN}✅ Diretórios criados${NC}"

  echo -e "  ⬇️  Baixando banner_bot.py..."
  curl -fsSL "$REPO_RAW/banner_bot.py" -o "$INSTALL_DIR/banner_bot.py" 2>/dev/null \
    && [ -s "$INSTALL_DIR/banner_bot.py" ] \
    && echo -e "  ${GREEN}✅ banner_bot.py OK${NC}" \
    || { echo -e "  ${RED}❌ Falha!${NC}"; exit 1; }

  # Logo: prioridade — (1) já copiada na etapa 1, (2) baixar do repo, (3) sem logo
  if [ -f "$INSTALL_DIR/assets/logo.png" ] && [ -s "$INSTALL_DIR/assets/logo.png" ]; then
    echo -e "  ${GREEN}✅ Logo já em assets/ (copiada na etapa 1)${NC}"
  elif [ -f "$TMP_LOGO" ] && [ -s "$TMP_LOGO" ]; then
    cp "$TMP_LOGO" "$INSTALL_DIR/assets/logo.png"
    echo -e "  ${GREEN}✅ Logo copiada do temp${NC}"
  else
    echo -e "  ⬇️  Baixando logo do repositório..."
    curl -fsSL "$REPO_RAW/assets/logo.png" -o "$INSTALL_DIR/assets/logo.png" 2>/dev/null \
      && [ -s "$INSTALL_DIR/assets/logo.png" ] \
      && echo -e "  ${GREEN}✅ Logo baixada do GitHub${NC}" \
      || echo -e "  ${YELLOW}⚠️  Logo não encontrada — banner funcionará sem logo${NC}"
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

# ================================================================
# ETAPA 5 — Container
# ================================================================
step_container() {
  titulo
  echo -e "  ${BOLD}🚀 ETAPA 5 — Subindo container${NC}\n"

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

  echo -e "  ⏳ Aguardando inicialização (20s)...\n"
  sleep 20

  if docker ps --filter "name=$CONTAINER" --filter "status=running" | grep -q "$CONTAINER"; then
    titulo
    echo -e "${GREEN}${BOLD}"
    echo "  ╔══════════════════════════════════════════════════════╗"
    echo "  ║   🎉 BANNER BOT INSTALADO COM SUCESSO!              ║"
    echo "  ╚══════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo -e "  Container : ${GREEN}$CONTAINER${NC} (rodando)"
    echo -e "  Envio     : ${CYAN}$HORA_ENVIO${NC} (Brasília)"
    echo -e "  Ligas     : ${CYAN}$FOOTBALL_LEAGUES${NC}"
    echo -e "  Dir       : ${CYAN}$INSTALL_DIR${NC}\n"
    echo -e "  ${BOLD}Testar agora:${NC}"
    echo -e "  ${CYAN}docker exec $CONTAINER python -c 'import banner_bot; banner_bot.job()'${NC}\n"
    echo -e "  ${BOLD}Ver logs:${NC}"
    echo -e "  ${CYAN}docker logs -f $CONTAINER${NC}\n"
  else
    echo -e "  ${RED}❌ Container não iniciou. Logs:${NC}\n"
    docker logs "$CONTAINER" 2>&1 | tail -30
  fi
}

# ================================================================
# MAIN
# ================================================================
main() {
  [ "$EUID" -ne 0 ] && echo -e "\n  ${RED}Execute como root: sudo bash setup_completo.sh${NC}\n" && exit 1

  for cmd in curl python3 base64; do
    command -v $cmd &>/dev/null || apt-get install -y $cmd -qq 2>/dev/null || true
  done

  titulo
  echo -e "  Bem-vindo ao instalador do ${BOLD}Inforlozzi Banner Bot${NC}!\n"
  echo -e "  O script vai:\n"
  echo -e "   ${GREEN}1.${NC} 📸 Receber sua logo (Telegram, URL ou arquivo)"
  echo -e "   ${GREEN}2.${NC} ⚙️  Configurar token, canal e horário"
  echo -e "   ${GREEN}3.${NC} 🐳 Instalar Docker se necessário"
  echo -e "   ${GREEN}4.${NC} 📂 Baixar arquivos do repositório"
  echo -e "   ${GREEN}5.${NC} 🚀 Subir o container automaticamente\n"
  pausar

  step_logo
  step_config
  step_docker
  step_arquivos
  step_container
}

main
