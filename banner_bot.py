#!/usr/bin/env python3
# =============================================================
#   BANNER BOT — Jogos do Dia  |  Inforlozzi-ai
#   Envia banners automáticos de NBA e Futebol para o Telegram
#
#  CONFIGURAÇÃO (variáveis de ambiente / .env):
#    TELEGRAM_BOT_TOKEN  — token do seu bot
#    TELEGRAM_CHAT_ID    — id do canal/grupo (com -100...)
#    HORA_ENVIO          — horário diário  (padrão: 08:00)
#    TZ                  — fuso (padrão:   America/Sao_Paulo)
#
#  PERSONALIZAÇÃO VISUAL:
#    LOGO_PATH     — caminho da sua logo PNG (padrão: /app/assets/logo.png)
#                    Se o arquivo não existir, o slot fica vazio.
#    COR_FUNDO     — hex sem #  (padrão: 0F0A1E  — roxo escuro)
#    COR_DESTAQUE  — hex sem #  (padrão: 8A2BE2  — violeta)
#    COR_TEXTO     — hex sem #  (padrão: FFFFFF  — branco)
#    COR_CARD      — hex sem #  (padrão: 1A1230  — card escuro)
#    COR_LINHA     — hex sem #  (padrão: igual COR_DESTAQUE)
# =============================================================

import os, io, asyncio, textwrap, logging
from datetime import datetime, timedelta, timezone
from PIL import Image, ImageDraw, ImageFont
import requests, schedule, time
from telegram import Bot

logging.basicConfig(format="%(asctime)s [%(levelname)s] %(message)s", level=logging.INFO)
log = logging.getLogger(__name__)

# ── Configuração de ambiente ──────────────────────────────────────────────────
TOKEN    = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID  = os.getenv("TELEGRAM_CHAT_ID", "")
HORA     = os.getenv("HORA_ENVIO", "08:00")
LOGO_PATH = os.getenv("LOGO_PATH", "/app/assets/logo.png")

def _hex(var, fallback):
    raw = os.getenv(var, "").strip().lstrip("#") or fallback
    return tuple(int(raw[i:i+2], 16) for i in (0, 2, 4))

C_FUNDO    = _hex("COR_FUNDO",    "0F0A1E")
C_DESTAQUE = _hex("COR_DESTAQUE", "8A2BE2")
C_TEXTO    = _hex("COR_TEXTO",    "FFFFFF")
C_CARD     = _hex("COR_CARD",     "1A1230")
C_LINHA    = _hex("COR_LINHA",    os.getenv("COR_DESTAQUE", "8A2BE2").lstrip("#") or "8A2BE2")

# ── Fontes (embutidas no Python / fallback simples) ───────────────────────────
def _font(size, bold=False):
    """Tenta fontes do sistema; cai no padrão PIL se não encontrar."""
    paths_bold = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ]
    paths_reg = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ]
    for p in (paths_bold if bold else paths_reg):
        if os.path.exists(p):
            try: return ImageFont.truetype(p, size)
            except: pass
    try: return ImageFont.load_default(size=size)
    except: return ImageFont.load_default()

# ── Busca jogos via TheSportsDB (gratuito) ────────────────────────────────────
API = "https://www.thesportsdb.com/api/v1/json/3"

MESES = ["Janeiro","Fevereiro","Março","Abril","Maio","Junho",
         "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]
DIAS  = ["Segunda","Terça","Quarta","Quinta","Sexta","Sábado","Domingo"]

FUTEBOL_LIGAS = [l.strip() for l in os.getenv("FOOTBALL_LEAGUES","4351,4406").split(",") if l.strip()]

def _data_ptbr(iso_date: str) -> str:
    d = datetime.strptime(iso_date, "%Y-%m-%d")
    return f"{DIAS[d.weekday()]}, {d.day} de {MESES[d.month-1]}"

def _amanha_iso() -> str:
    tz_brt = timezone(timedelta(hours=-3))
    return (datetime.now(tz_brt) + timedelta(days=1)).strftime("%Y-%m-%d")

def _hora_brt(utc_str):
    if not utc_str: return "TBD"
    try:
        dt = datetime.strptime(utc_str, "%Y-%m-%dT%H:%M:%S+00:00").replace(tzinfo=timezone.utc)
        brt = dt.astimezone(timezone(timedelta(hours=-3)))
        return brt.strftime("%H:%M")
    except: return "TBD"

def buscar_jogos_nba(data: str) -> list:
    try:
        r = requests.get(f"{API}/eventsday.php", params={"d": data, "l": "NBA"}, timeout=10)
        eventos = (r.json() or {}).get("events") or []
        jogos = []
        for e in eventos:
            jogos.append({
                "home":    e.get("strHomeTeam", "?"),
                "away":    e.get("strAwayTeam", "?"),
                "time":    _hora_brt(e.get("strTimestamp") or e.get("strTime")),
                "channel": e.get("strTVStation") or "N/D",
            })
        return jogos
    except Exception as ex:
        log.error("NBA fetch error: %s", ex)
        return []

def buscar_jogos_futebol(data: str) -> list:
    jogos = []
    for liga_id in FUTEBOL_LIGAS:
        try:
            r = requests.get(f"{API}/eventsday.php", params={"d": data, "l": liga_id}, timeout=10)
            eventos = (r.json() or {}).get("events") or []
            for e in eventos:
                jogos.append({
                    "home":    e.get("strHomeTeam", "?"),
                    "away":    e.get("strAwayTeam", "?"),
                    "time":    _hora_brt(e.get("strTimestamp") or e.get("strTime")),
                    "channel": e.get("strTVStation") or "N/D",
                    "liga":    e.get("strLeague", ""),
                })
        except Exception as ex:
            log.error("Futebol fetch error liga %s: %s", liga_id, ex)
    return jogos

# ── Geração do banner ─────────────────────────────────────────────────────────
W = 1080  # largura

def _cor_gradiente(y, h):
    """Gradiente vertical: fundo escuro → card levemente mais claro"""
    t = y / h
    r = int(C_FUNDO[0] + (C_CARD[0] - C_FUNDO[0]) * t)
    g = int(C_FUNDO[1] + (C_CARD[1] - C_FUNDO[1]) * t)
    b = int(C_FUNDO[2] + (C_CARD[2] - C_FUNDO[2]) * t)
    return (r, g, b)

def _draw_rounded_rect(draw, xy, radius, fill):
    x0, y0, x1, y1 = xy
    draw.rectangle([x0+radius, y0, x1-radius, y1], fill=fill)
    draw.rectangle([x0, y0+radius, x1, y1-radius], fill=fill)
    draw.ellipse([x0, y0, x0+2*radius, y0+2*radius], fill=fill)
    draw.ellipse([x1-2*radius, y0, x1, y0+2*radius], fill=fill)
    draw.ellipse([x0, y1-2*radius, x0+2*radius, y1], fill=fill)
    draw.ellipse([x1-2*radius, y1-2*radius, x1, y1], fill=fill)

def gerar_banner(jogos: list, esporte: str, data_ptbr: str) -> str:
    PADDING   = 48
    ROW_H     = 76      # altura de cada card de jogo
    ROW_GAP   = 12
    HEADER_H  = 180     # área do cabeçalho (logo + título)
    FOOTER_H  = 60
    TITULO_H  = 54

    total_h = HEADER_H + TITULO_H + (ROW_H + ROW_GAP) * len(jogos) + FOOTER_H + PADDING
    img = Image.new("RGB", (W, total_h), C_FUNDO)
    px  = img.load()

    # Gradiente de fundo
    for y in range(total_h):
        c = _cor_gradiente(y, total_h)
        for x in range(W):
            px[x, y] = c

    draw = ImageDraw.Draw(img)

    # ── Linha decorativa no topo ──────────────────────────────
    draw.rectangle([0, 0, W, 6], fill=C_DESTAQUE)

    # ── Logo (se existir) ─────────────────────────────────────
    logo_w = 0
    if os.path.exists(LOGO_PATH):
        try:
            logo = Image.open(LOGO_PATH).convert("RGBA")
            logo_h_max = HEADER_H - 20
            ratio = logo_h_max / logo.height
            logo_w = int(logo.width * ratio)
            logo = logo.resize((logo_w, logo_h_max), Image.LANCZOS)
            img.paste(logo, (PADDING, 10), logo)
        except Exception as ex:
            log.warning("Logo error: %s", ex)
            logo_w = 0

    # ── Cabeçalho textual ─────────────────────────────────────
    f_titulo  = _font(38, bold=True)
    f_data    = _font(26)
    f_esporte = _font(22)

    emoji = "🏀" if esporte == "nba" else "⚽"
    label = "NBA" if esporte == "nba" else "FUTEBOL"
    tx = PADDING + logo_w + (24 if logo_w else 0)

    draw.text((tx, 18),  f"{emoji}  {label} — Jogos de Amanhã", font=f_titulo, fill=C_DESTAQUE)
    draw.text((tx, 68),  data_ptbr,                               font=f_data,   fill=C_TEXTO)
    draw.text((tx, 102), f"{len(jogos)} jogo(s) programado(s)",  font=f_esporte, fill=(*C_TEXTO[:3], 180))

    # ── Linha separadora ──────────────────────────────────────
    draw.rectangle([PADDING, HEADER_H - 4, W - PADDING, HEADER_H], fill=C_DESTAQUE)

    # ── Sub-título da seção ───────────────────────────────────
    f_sub = _font(28, bold=True)
    draw.text((PADDING, HEADER_H + 10), "CONFRONTOS", font=f_sub, fill=C_TEXTO)

    # ── Cards de jogos ────────────────────────────────────────
    f_jogo = _font(26, bold=True)
    f_info = _font(20)
    f_hora = _font(22, bold=True)

    y = HEADER_H + TITULO_H
    for jogo in jogos:
        # Card arredondado
        _draw_rounded_rect(draw,
            [PADDING, y, W - PADDING, y + ROW_H],
            radius=12,
            fill=(*C_CARD, 220))

        # Barra lateral colorida
        draw.rectangle([PADDING, y, PADDING + 5, y + ROW_H], fill=C_DESTAQUE)

        # Nomes dos times
        home = textwrap.shorten(jogo["home"], width=22, placeholder="...")
        away = textwrap.shorten(jogo["away"], width=22, placeholder="...")
        confronto = f"{home}  ×  {away}"
        draw.text((PADDING + 20, y + 10), confronto, font=f_jogo, fill=C_TEXTO)

        # Horário
        hora_txt = jogo["time"]
        hora_bbox = draw.textbbox((0, 0), hora_txt, font=f_hora)
        hora_w = hora_bbox[2] - hora_bbox[0]
        draw.text((W - PADDING - hora_w - 10, y + 10), hora_txt, font=f_hora, fill=C_DESTAQUE)

        # Canal
        canal_txt = f"📺 {jogo['channel']}"
        draw.text((PADDING + 20, y + 44), canal_txt, font=f_info, fill=(*C_TEXTO[:3], 200))

        # Liga (futebol)
        if esporte != "nba" and jogo.get("liga"):
            liga_txt = jogo["liga"]
            lb = draw.textbbox((0, 0), liga_txt, font=f_info)
            lw = lb[2] - lb[0]
            draw.text((W - PADDING - lw - 10, y + 44), liga_txt, font=f_info, fill=(*C_DESTAQUE, 200))

        y += ROW_H + ROW_GAP

    # ── Rodapé ────────────────────────────────────────────────
    f_rod = _font(18)
    rodape = "gerado automaticamente  •  Inforlozzi"
    rb = draw.textbbox((0, 0), rodape, font=f_rod)
    rw = rb[2] - rb[0]
    draw.text(((W - rw) // 2, total_h - FOOTER_H + 16), rodape,
              font=f_rod, fill=(*C_TEXTO[:3], 100))
    draw.rectangle([0, total_h - 6, W, total_h], fill=C_DESTAQUE)

    # ── Salvar ────────────────────────────────────────────────
    os.makedirs("/app/output", exist_ok=True)
    path = f"/app/output/banner_{esporte}_{data_ptbr.replace(' ', '_').replace(',', '')}.png"
    img.save(path, "PNG", optimize=True)
    return path

# ── Envio para o Telegram ─────────────────────────────────────────────────────
async def _enviar(path: str, caption: str):
    bot = Bot(token=TOKEN)
    with open(path, "rb") as f:
        await bot.send_photo(chat_id=CHAT_ID, photo=f,
                             caption=caption, parse_mode="HTML")

def enviar(path, caption):
    asyncio.run(_enviar(path, caption))

# ── Job principal ─────────────────────────────────────────────────────────────
def job():
    log.info("▶  Iniciando geração de banners...")
    data    = _amanha_iso()
    data_pt = _data_ptbr(data)

    # NBA
    jogos_nba = buscar_jogos_nba(data)
    if jogos_nba:
        path = gerar_banner(jogos_nba, "nba", data_pt)
        caption = (
            f"🏀 <b>NBA — Jogos de Amanhã</b>\n"
            f"📅 {data_pt}\n\n"
            + "\n".join(
                f"• <b>{j['home']}</b> × <b>{j['away']}</b>  |  🕐 {j['time']}  |  📺 {j['channel']}"
                for j in jogos_nba
            )
        )
        enviar(path, caption)
        log.info("✅ NBA enviado (%d jogos)", len(jogos_nba))
    else:
        log.info("ℹ️  Sem jogos NBA amanhã.")

    # Futebol
    jogos_fut = buscar_jogos_futebol(data)
    if jogos_fut:
        path = gerar_banner(jogos_fut, "futebol", data_pt)
        caption = (
            f"⚽ <b>Futebol — Jogos de Amanhã</b>\n"
            f"📅 {data_pt}\n\n"
            + "\n".join(
                f"• <b>{j['home']}</b> × <b>{j['away']}</b>  |  🕐 {j['time']}  |  📺 {j['channel']}"
                + (f"  |  🏆 {j['liga']}" if j.get('liga') else "")
                for j in jogos_fut
            )
        )
        enviar(path, caption)
        log.info("✅ Futebol enviado (%d jogos)", len(jogos_fut))
    else:
        log.info("ℹ️  Sem jogos de futebol amanhã.")

# ── Agendador ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if not TOKEN or not CHAT_ID:
        log.error("TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID são obrigatórios!")
        raise SystemExit(1)

    schedule.every().day.at(HORA).do(job)
    log.info("🤖 Banner Bot ativo — envio diário às %s (BRT)", HORA)

    # Descomentar para testar na subida:
    # job()

    while True:
        schedule.run_pending()
        time.sleep(30)
