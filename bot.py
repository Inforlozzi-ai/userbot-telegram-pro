import os, logging, asyncio, re
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from telethon.tl.types import Channel, Chat, User
from datetime import datetime
from collections import defaultdict

logging.basicConfig(format="%(asctime)s [%(levelname)s] %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
SESSION = os.environ["SESSION_STRING"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
BOT_NOME = os.environ.get("BOT_NOME", "UserBot")
ADMIN_IDS = set(int(x) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip().isdigit())

_tgt_raw = os.environ.get("TARGET_GROUP_ID", "")
DESTINOS = set(int(x) for x in re.split(r"[,; ]+", _tgt_raw) if x.strip().lstrip("-").isdigit())
SRC_RAW = os.environ.get("SOURCE_CHAT_IDS", "")
SRC = set(int(x) for x in re.split(r"[,; ]+", SRC_RAW) if x.strip().lstrip("-").isdigit())

MOD = os.environ.get("FORWARD_MODE", "forward")
stats = {"n": 0, "err": 0, "start": datetime.now(), "por_hora": defaultdict(int)}
PAUSADO = False
FILTROS_ON = set()
FILTROS_OFF = set()
IGNORADOS = set()
HISTORICO = []
AGUARDANDO = {}
PREFIXO = ""
RODAPE = ""
DELAY = 0
SOMENTE_TIPOS = set()
SEM_BOTS = False
AGENDAMENTO = {"ativo": False, "inicio": "00:00", "fim": "23:59"}
ultimo_envio = 0
MODO_SILENCIOSO = False

E_ORIGEM   = "\U0001F4E1"
E_DESTINO  = "\U0001F3AF"
E_MODO     = "\U0001F504"
E_FILTRO   = "\U0001F50D"
E_HORARIO  = "\u23F0"
E_MSG      = "\U0001F4AC"
E_STATUS   = "\U0001F4CA"
E_HIST     = "\U0001F4DC"
E_INFO     = "\u2139\ufe0f"
E_ID       = "\U0001F50E"
E_PAUSAR   = "\u23F8\ufe0f"
E_RETOMAR  = "\u25B6\ufe0f"
E_SIL      = "\U0001F514"
E_SILOFF   = "\U0001F515"
E_FECHAR   = "\u274C"
E_MAIS     = "\u2795"
E_MENOS    = "\u2796"
E_VER      = "\U0001F4CB"
E_LIMPAR   = "\U0001F9F9"
E_VOLTAR   = "\u2B05\ufe0f"
E_USER     = "\U0001F464"
E_VIP      = "\u2B50"
E_BOT      = "\U0001F916"
E_GROUP    = "\U0001F465"
E_CHANNEL  = "\U0001F4E2"
E_FORUM    = "\U0001F4AC"
E_OK       = "\u2705"
E_MANUAL   = "\u270F\ufe0f"

_dialogs_cache = {}
_dialogs_ts = 0
DIALOGS_TTL = 120

userbot = TelegramClient(StringSession(SESSION), API_ID, API_HASH)
bot = TelegramClient(StringSession(""), API_ID, API_HASH)

def is_admin(uid):
    return not ADMIN_IDS or uid in ADMIN_IDS

async def get_dialogs():
    global _dialogs_cache, _dialogs_ts
    agora = asyncio.get_event_loop().time()
    if _dialogs_cache and (agora - _dialogs_ts) < DIALOGS_TTL:
        return _dialogs_cache

    dialogs = {}
    try:
        async for d in userbot.iter_dialogs(limit=200):
            e = d.entity
            if isinstance(e, Channel):
                if getattr(e, "forum", False):
                    cat = "myforum"
                elif e.megagroup:
                    cat = "mygroup"
                elif e.broadcast:
                    cat = "mychannel"
                else:
                    cat = "mygroup"
            elif isinstance(e, Chat):
                cat = "mygroup"
            elif isinstance(e, User):
                if e.bot:
                    cat = "bot"
                elif getattr(e, "premium", False):
                    cat = "premium"
                else:
                    cat = "user"
            else:
                continue

            dialogs.setdefault(cat, []).append({
                "id": d.id,
                "name": (d.name or getattr(e, "first_name", "?"))[:35],
                "username": getattr(e, "username", None)
            })
    except Exception as ex:
        logger.error("Erro ao carregar dialogs: %s", ex)

    _dialogs_cache = dialogs
    _dialogs_ts = agora
    return dialogs

async def get_dialogs_with_timeout():
    try:
        return await asyncio.wait_for(get_dialogs(), timeout=15)
    except asyncio.TimeoutError:
        logger.error("Timeout ao carregar dialogs")
        return _dialogs_cache if _dialogs_cache else {}

def kb_principal():
    estado = E_PAUSAR + " Pausar" if not PAUSADO else E_RETOMAR + " Retomar"
    sil = E_SIL + " Silenc." if not MODO_SILENCIOSO else E_SILOFF + " Silenc."
    return [
        [Button.inline(E_ORIGEM + " Origens", b"m_origens"),
         Button.inline(E_DESTINO + " Destinos", b"m_destinos"),
         Button.inline(E_MODO + " Modo", b"m_modo")],
        [Button.inline(E_FILTRO + " Filtros", b"m_filtros"),
         Button.inline(E_HORARIO + " Horario", b"m_agenda"),
         Button.inline(E_MSG + " Mensagem", b"m_msg")],
        [Button.inline(E_STATUS + " Status", b"m_status"),
         Button.inline(E_HIST + " Historico", b"m_hist"),
         Button.inline(E_INFO + " Info", b"m_info")],
        [Button.inline(E_ID + " Descobrir ID", b"disc_menu")],
        [Button.inline(estado, b"m_toggle"),
         Button.inline(sil, b"m_silencioso"),
         Button.inline(E_FECHAR + " Fechar", b"m_fechar")],
    ]

def kb_tipo_selector(ctx):
    c = ctx.encode()
    if ctx in ("src", "src_ign", "src_rem"):
        volta = b"m_origens"
    elif ctx in ("dst", "dst_rem"):
        volta = b"m_destinos"
    else:
        volta = b"disc_menu"
    return [
        [Button.inline(E_USER + " User", c + b"|user"),
         Button.inline(E_VIP + " Premium", c + b"|premium"),
         Button.inline(E_BOT + " Bot", c + b"|bot")],
        [Button.inline(E_GROUP + " Grupos", c + b"|mygroup"),
         Button.inline(E_CHANNEL + " Canais", c + b"|mychannel"),
         Button.inline(E_FORUM + " Forums", c + b"|myforum")],
        [Button.inline(E_MANUAL + " Digitar ID manual", c + b"|manual")],
        [Button.inline(E_VOLTAR + " Voltar", volta)],
    ]

def kb_lista_chats(items, ctx, cat, pagina=0, por_pagina=8):
    inicio = pagina * por_pagina
    pagina_items = items[inicio:inicio + por_pagina]
    linhas = []
    for item in pagina_items:
        dado = f"{ctx}|sel|{item['id']}|{cat}".encode()
        linhas.append([Button.inline(item["name"][:48], dado)])
    nav = []
    if pagina > 0:
        nav.append(Button.inline(E_VOLTAR + " Anterior", f"{ctx}|pg|{cat}|{pagina-1}".encode()))
    if inicio + por_pagina < len(items):
        nav.append(Button.inline("Proxima " + E_DESTINO, f"{ctx}|pg|{cat}|{pagina+1}".encode()))
    if nav:
        linhas.append(nav)
    linhas.append([
        Button.inline(E_MANUAL + " Manual", f"{ctx}|manual".encode()),
        Button.inline(E_VOLTAR + " Voltar", f"{ctx}|back".encode())
    ])
    return linhas

def kb_origens():
    return [
        [Button.inline(E_MAIS + " Adicionar origem", b"src|tipo"),
         Button.inline(E_MENOS + " Remover origem", b"src_rem|tipo")],
        [Button.inline(E_FECHAR + " Ignorar chat", b"src_ign|tipo"),
         Button.inline(E_OK + " Designorar", b"o_des")],
        [Button.inline(E_VER + " Ver origens", b"o_list"),
         Button.inline(E_LIMPAR + " Limpar tudo", b"o_clear")],
        [Button.inline(E_VOLTAR + " Voltar", b"m_back")],
    ]

def kb_destinos():
    return [
        [Button.inline(E_MAIS + " Adicionar destino", b"dst|tipo"),
         Button.inline(E_MENOS + " Remover destino", b"dst_rem|tipo")],
        [Button.inline(E_VER + " Ver destinos", b"d_list"),
         Button.inline(E_LIMPAR + " Limpar destinos", b"d_clear")],
        [Button.inline(E_VOLTAR + " Voltar", b"m_back")],
    ]

def kb_modo():
    bots_txt = "Ignorar bots: SIM" if SEM_BOTS else "Ignorar bots: NAO"
    return [
        [Button.inline(">> Forward (mostra origem)", b"mo_fwd"),
         Button.inline(">> Copy (sem origem)", b"mo_copy")],
        [Button.inline(E_BOT + " " + bots_txt, b"mo_bots")],
        [Button.inline(E_HORARIO + " Delay", b"mo_delay"),
         Button.inline(E_FILTRO + " Tipos de midia", b"mo_tipos")],
        [Button.inline(E_VOLTAR + " Voltar", b"m_back")],
    ]

def kb_filtros():
    return [
        [Button.inline(E_MAIS + " Exigir palavra", b"f_add_on"),
         Button.inline(E_FECHAR + " Bloquear palavra", b"f_add_off")],
        [Button.inline(E_MENOS + " Remover filtro", b"f_rem"),
         Button.inline(E_VER + " Ver filtros", b"f_list")],
        [Button.inline(E_LIMPAR + " Limpar filtros", b"f_clear"),
         Button.inline(E_VOLTAR + " Voltar", b"m_back")],
    ]

def kb_agenda():
    ativo = "ATIVO" if AGENDAMENTO["ativo"] else "INATIVO"
    return [
        [Button.inline(E_HORARIO + " Definir horario", b"ag_set"),
         Button.inline(E_STATUS + " Agendamento: " + ativo, b"ag_toggle")],
        [Button.inline(E_VER + " Ver configuracao", b"ag_ver"),
         Button.inline(E_VOLTAR + " Voltar", b"m_back")],
    ]

def kb_msg():
    return [
        [Button.inline(E_MAIS + " Definir prefixo", b"mg_prefix"),
         Button.inline(E_MAIS + " Definir rodape", b"mg_suffix")],
        [Button.inline(E_MENOS + " Remover prefixo", b"mg_rmpre"),
         Button.inline(E_MENOS + " Remover rodape", b"mg_rmsuf")],
        [Button.inline(E_VER + " Ver config", b"mg_ver"),
         Button.inline(E_VOLTAR + " Voltar", b"m_back")],
    ]

def kb_tipos():
    tipos = ["texto", "foto", "video", "audio", "doc", "sticker"]
    linhas = []
    for i in range(0, len(tipos), 3):
        linha = []
        for t in tipos[i:i+3]:
            ativo = E_OK if t in SOMENTE_TIPOS else "[ ]"
            linha.append(Button.inline(ativo + " " + t, ("tp_" + t).encode()))
        linhas.append(linha)
    linhas.append([
        Button.inline(E_LIMPAR + " Todos (sem filtro)", b"tp_clear"),
        Button.inline(E_VOLTAR + " Voltar", b"mo_tipos_back")
    ])
    return linhas

def kb_info():
    return [
        [Button.inline("Ping", b"i_ping"),
         Button.inline(E_ID + " ID deste chat", b"i_id")],
        [Button.inline(E_STATUS + " Estatisticas", b"i_stats"),
         Button.inline(E_LIMPAR + " Zerar stats", b"i_reset")],
        [Button.inline(E_OK + " Testar destinos", b"i_teste"),
         Button.inline(E_VOLTAR + " Voltar", b"m_back")],
    ]

def status_texto():
    up = datetime.now() - stats["start"]
    h, r = divmod(int(up.total_seconds()), 3600)
    mi, s = divmod(r, 60)
    agenda_txt = AGENDAMENTO["inicio"] + " ate " + AGENDAMENTO["fim"] if AGENDAMENTO["ativo"] else "desativado"
    tipos_txt = ", ".join(SOMENTE_TIPOS) if SOMENTE_TIPOS else "todos"
    estado = "PAUSADO" if PAUSADO else "ATIVO"
    silenc = "ON" if MODO_SILENCIOSO else "OFF"
    sep = "=" * 22
    lines = [
        BOT_NOME + " -- STATUS", sep,
        "Estado   : " + estado,
        "Silenc.  : " + silenc,
        "Modo     : " + MOD + ("  |sem bots" if SEM_BOTS else ""),
        "Delay    : " + str(DELAY) + "s", sep,
        "Destinos (" + str(len(DESTINOS)) + "): " + str(DESTINOS or "nenhum"),
        "Origens  (" + str(len(SRC)) + "): " + str(SRC or "todos"),
        "Ignorados: " + str(IGNORADOS or "nenhum"), sep,
        "Filtros +: " + str(FILTROS_ON or "nenhum"),
        "Filtros -: " + str(FILTROS_OFF or "nenhum"),
        "Tipos    : " + tipos_txt,
        "Horario  : " + agenda_txt, sep,
        "Prefixo  : " + (PREFIXO or "nenhum"),
        "Rodape   : " + (RODAPE or "nenhum"), sep,
        "Enviadas : " + str(stats["n"]) + "  |  Erros: " + str(stats["err"]),
        "Uptime   : " + str(h) + "h " + str(mi) + "m " + str(s) + "s",
    ]
    return "\n".join(lines)

def painel_txt():
    return (
        BOT_NOME + " -- Painel de Controle\n"
        + "=" * 24 + "\n"
        + "Destinos: " + str(len(DESTINOS)) + "  |  Origens: " + str(len(SRC) or "todos") + "\n"
        + "Estado: " + ("PAUSADO" if PAUSADO else "ATIVO") + "  |  Modo: " + MOD
    )

@bot.on(events.NewMessage(pattern=r"^/menu$"))
async def cmd_menu(ev):
    if not is_admin(ev.sender_id): return
    await ev.respond(painel_txt(), buttons=kb_principal())

@bot.on(events.NewMessage(pattern=r"^/status$"))
async def cmd_status(ev):
    if not is_admin(ev.sender_id): return
    await ev.respond(status_texto())

@bot.on(events.NewMessage(pattern=r"^/start$"))
async def cmd_start(ev):
    await ev.respond("Ola! Sou o " + BOT_NOME + ".\nDigite /menu para abrir o painel.")

@bot.on(events.NewMessage())
async def entrada_usuario(ev):
    global PREFIXO, RODAPE, DELAY
    uid = ev.sender_id
    if not is_admin(uid): return
    if uid not in AGUARDANDO: return
    acao = AGUARDANDO.pop(uid)
    txt = ev.raw_text.strip()

    def parse_ids(t):
        return [x.strip() for x in re.split(r"[,; ]+", t) if x.strip().lstrip("-").isdigit()]

    if acao == "src|manual":
        ids = parse_ids(txt)
        for i in ids: SRC.add(int(i))
        await ev.respond("Origens adicionadas: " + str(ids), buttons=kb_origens())
    elif acao == "src_rem|manual":
        ids = parse_ids(txt)
        for i in ids: SRC.discard(int(i))
        await ev.respond("Removidas: " + str(ids), buttons=kb_origens())
    elif acao == "src_ign|manual":
        ids = parse_ids(txt)
        for i in ids: IGNORADOS.add(int(i))
        await ev.respond("Ignorando: " + str(ids), buttons=kb_origens())
    elif acao == "dst|manual":
        ids = parse_ids(txt)
        for i in ids: DESTINOS.add(int(i))
        await ev.respond("Destinos adicionados: " + str(ids), buttons=kb_destinos())
    elif acao == "dst_rem|manual":
        ids = parse_ids(txt)
        for i in ids: DESTINOS.discard(int(i))
        await ev.respond("Removidos: " + str(ids), buttons=kb_destinos())
    elif acao == "disc_manual":
        try:
            entity = await userbot.get_entity(txt)
            eid = getattr(entity, "id", None)
            nome = getattr(entity, "title", None) or getattr(entity, "first_name", "?")
            uname = getattr(entity, "username", None)
            tipo = "Canal" if isinstance(entity, Channel) and entity.broadcast else \
                   "Grupo" if isinstance(entity, (Channel, Chat)) else \
                   "Bot" if isinstance(entity, User) and entity.bot else "Usuario"
            resp = "Resultado:\n" + "=" * 16 + "\nTipo: " + tipo + "\nNome: " + nome + "\nID: " + str(eid)
            if uname:
                resp += "\nUsername: @" + uname
            await ev.respond(resp, buttons=[[Button.inline(E_ID + " Descobrir outro", b"disc_menu"),
                                             Button.inline(E_VOLTAR + " Menu", b"m_back")]])
        except Exception as e:
            await ev.respond("Nao encontrado: " + str(e))
    elif acao == "mg_prefix":
        PREFIXO = txt
        await ev.respond("Prefixo: " + PREFIXO, buttons=kb_msg())
    elif acao == "mg_suffix":
        RODAPE = txt
        await ev.respond("Rodape: " + RODAPE, buttons=kb_msg())
    elif acao == "mo_delay":
        if txt.isdigit():
            DELAY = int(txt)
            await ev.respond("Delay: " + str(DELAY) + "s", buttons=kb_modo())

@bot.on(events.CallbackQuery)
async def callback(ev):
    global PAUSADO, MOD, SEM_BOTS, MODO_SILENCIOSO
    if not is_admin(ev.sender_id):
        await ev.answer("Sem permissao!", alert=True)
        return

    d = ev.data
    uid = ev.sender_id

    if d == b"m_back":
        await ev.edit(painel_txt(), buttons=kb_principal())

    elif d == b"m_origens":
        src_lista = ", ".join(str(x) for x in SRC) if SRC else "todos os chats"
        await ev.edit(E_ORIGEM + " ORIGENS\n" + "=" * 20 + "\nAtivas: " + src_lista +
                      "\nIgnorados: " + str(len(IGNORADOS)), buttons=kb_origens())

    elif d == b"m_destinos":
        dst_lista = ", ".join(str(x) for x in DESTINOS) if DESTINOS else "nenhum"
        await ev.edit(E_DESTINO + " DESTINOS\n" + "=" * 20 + "\nAtivos (" + str(len(DESTINOS)) +
                      "): " + dst_lista, buttons=kb_destinos())

    elif d == b"m_modo":
        await ev.edit(E_MODO + " MODO\n" + "=" * 20 + "\nAtual: " + MOD +
                      "\nDelay: " + str(DELAY) + "s  |  Sem bots: " + ("SIM" if SEM_BOTS else "NAO"),
                      buttons=kb_modo())

    elif d == b"m_filtros":
        await ev.edit(E_FILTRO + " FILTROS\n" + "=" * 20 + "\nExigidas: " + str(FILTROS_ON or "nenhuma") +
                      "\nBloqueadas: " + str(FILTROS_OFF or "nenhuma"), buttons=kb_filtros())

    elif d == b"m_agenda":
        ativo = "ATIVO" if AGENDAMENTO["ativo"] else "INATIVO"
        await ev.edit(E_HORARIO + " HORARIO\n" + "=" * 20 + "\nEstado: " + ativo +
                      "\nJanela: " + AGENDAMENTO["inicio"] + " ate " + AGENDAMENTO["fim"],
                      buttons=kb_agenda())

    elif d == b"m_msg":
        await ev.edit(E_MSG + " MENSAGEM\n" + "=" * 20 + "\nPrefixo: " + (PREFIXO or "nenhum") +
                      "\nRodape: " + (RODAPE or "nenhum"), buttons=kb_msg())

    elif d == b"m_info":
        await ev.edit(E_INFO + " INFO\n" + "=" * 20, buttons=kb_info())

    elif d == b"m_hist":
        if not HISTORICO:
            await ev.edit("Nenhuma mensagem ainda.", buttons=[[Button.inline(E_VOLTAR + " Voltar", b"m_back")]])
        else:
            t = E_HIST + " Ultimas mensagens:\n" + "".join(h["time"] + " -- " + h["chat"] + "\n" for h in HISTORICO[-15:])
            await ev.edit(t, buttons=[[Button.inline(E_VOLTAR + " Voltar", b"m_back")]])

    elif d == b"m_status":
        await ev.edit(status_texto(), buttons=[[Button.inline("Atualizar", b"m_status"),
                                                Button.inline(E_VOLTAR + " Voltar", b"m_back")]])

    elif d == b"m_fechar":
        await ev.delete()

    elif d == b"m_toggle":
        PAUSADO = not PAUSADO
        await ev.edit(painel_txt(), buttons=kb_principal())
        await ev.answer("PAUSADO!" if PAUSADO else "RETOMADO!", alert=True)

    elif d == b"m_silencioso":
        MODO_SILENCIOSO = not MODO_SILENCIOSO
        await ev.edit(painel_txt(), buttons=kb_principal())
        await ev.answer("Silencioso ON" if MODO_SILENCIOSO else "Silencioso OFF", alert=True)

    elif d in (b"src|tipo", b"src_rem|tipo", b"src_ign|tipo", b"dst|tipo", b"dst_rem|tipo"):
        ctx = d.decode().split("|")[0]
        label_map = {
            "src": "ADICIONAR ORIGEM",
            "src_rem": "REMOVER ORIGEM",
            "src_ign": "IGNORAR CHAT",
            "dst": "ADICIONAR DESTINO",
            "dst_rem": "REMOVER DESTINO"
        }
        await ev.edit(label_map.get(ctx, "SELECIONAR") + "\n" + "=" * 20 + "\nEscolha o tipo:",
                      buttons=kb_tipo_selector(ctx))

    elif b"|pg|" in d:
        partes = d.decode().split("|")
        ctx, cat, pagina = partes[0], partes[2], int(partes[3])
        await ev.answer("Carregando...", alert=False)
        dialogs = await get_dialogs_with_timeout()
        items = dialogs.get(cat, [])
        if not items:
            await ev.answer("Nenhum " + cat + " encontrado.", alert=True)
            return
        await ev.edit(cat.upper() + " (" + str(len(items)) + ")\nSelecione:",
                      buttons=kb_lista_chats(items, ctx, cat, pagina))

    elif b"|" in d and not any(d.startswith(x) for x in [b"disc", b"tp_", b"mo_", b"mg_", b"ag_", b"f_", b"i_", b"o_", b"d_", b"m_"]):
        partes = d.decode().split("|")
        if len(partes) < 2:
            return
        ctx, sub = partes[0], partes[1]

        if sub == "back":
            if ctx in ("src", "src_rem", "src_ign"):
                await ev.edit(E_ORIGEM + " ORIGENS", buttons=kb_origens())
            elif ctx in ("dst", "dst_rem"):
                await ev.edit(E_DESTINO + " DESTINOS", buttons=kb_destinos())
            else:
                await ev.edit(E_ID + " DESCOBRIR ID", buttons=[[Button.inline(E_VOLTAR + " Menu", b"m_back")]])
            return

        if sub == "manual":
            AGUARDANDO[uid] = ctx + "|manual"
            await ev.answer("Digite o @username ou ID:", alert=True)
            return

        if sub == "sel" and len(partes) >= 4:
            chat_id = int(partes[2])
            dialogs = await get_dialogs_with_timeout()
            all_items = [i for its in dialogs.values() for i in its]
            item = next((i for i in all_items if i["id"] == chat_id), None)
            nome = item["name"] if item else str(chat_id)

            if ctx == "src":
                SRC.add(chat_id)
                await ev.edit(E_OK + " ORIGEM ADICIONADA\n" + "=" * 20 + "\n" + nome + "\nID: " + str(chat_id),
                              buttons=[[Button.inline(E_MAIS + " Adicionar outra", b"src|tipo")],
                                       [Button.inline(E_VOLTAR + " Origens", b"m_origens"), Button.inline("Home", b"m_back")]])
            elif ctx == "dst":
                DESTINOS.add(chat_id)
                await ev.edit(E_OK + " DESTINO ADICIONADO\n" + "=" * 20 + "\n" + nome + "\nID: " + str(chat_id),
                              buttons=[[Button.inline(E_MAIS + " Adicionar outro", b"dst|tipo")],
                                       [Button.inline(E_VOLTAR + " Destinos", b"m_destinos"), Button.inline("Home", b"m_back")]])
            elif ctx == "src_rem":
                SRC.discard(chat_id)
                await ev.edit(E_MENOS + " ORIGEM REMOVIDA\n" + "=" * 20 + "\n" + nome,
                              buttons=[[Button.inline(E_VOLTAR + " Origens", b"m_origens"), Button.inline("Home", b"m_back")]])
            elif ctx == "dst_rem":
                DESTINOS.discard(chat_id)
                await ev.edit(E_MENOS + " DESTINO REMOVIDO\n" + "=" * 20 + "\n" + nome,
                              buttons=[[Button.inline(E_VOLTAR + " Destinos", b"m_destinos"), Button.inline("Home", b"m_back")]])
            elif ctx == "src_ign":
                IGNORADOS.add(chat_id)
                await ev.edit(E_FECHAR + " CHAT IGNORADO\n" + "=" * 20 + "\n" + nome,
                              buttons=[[Button.inline(E_VOLTAR + " Origens", b"m_origens"), Button.inline("Home", b"m_back")]])
            return

        cat = sub
        if cat not in ("user", "premium", "bot", "mygroup", "mychannel", "myforum"):
            return

        await ev.answer("Carregando lista...", alert=False)
        dialogs = await get_dialogs_with_timeout()
        items = dialogs.get(cat, [])
        if not items:
            await ev.answer("Nenhum " + cat + " encontrado na conta.", alert=True)
            return
        await ev.edit(cat.upper() + " (" + str(len(items)) + ")\nSelecione:",
                      buttons=kb_lista_chats(items, ctx, cat, 0))

    elif d == b"disc_menu":
        await ev.edit(E_ID + " DESCOBRIR ID\n" + "=" * 20 + "\nEscolha o tipo ou busque pelo username:",
                      buttons=[
                          [Button.inline(E_USER + " User", b"disc|user"),
                           Button.inline(E_VIP + " Premium", b"disc|premium"),
                           Button.inline(E_BOT + " Bot", b"disc|bot")],
                          [Button.inline(E_GROUP + " Grupos", b"disc|mygroup"),
                           Button.inline(E_CHANNEL + " Canais", b"disc|mychannel"),
                           Button.inline(E_FORUM + " Forums", b"disc|myforum")],
                          [Button.inline(E_MANUAL + " Buscar @username / ID", b"disc|manual")],
                          [Button.inline(E_VOLTAR + " Voltar", b"m_back")]
                      ])

    elif d == b"disc|manual":
        AGUARDANDO[uid] = "disc_manual"
        await ev.answer("Digite o @username ou ID:", alert=True)

    elif d.startswith(b"disc|"):
        cat = d.decode().split("|")[1]
        await ev.answer("Carregando lista...", alert=False)
        dialogs = await get_dialogs_with_timeout()
        items = dialogs.get(cat, [])
        if not items:
            await ev.answer("Nenhum " + cat + " encontrado na conta.", alert=True)
            return
        linhas = []
        for item in items[:20]:
            uname = " @" + item["username"] if item.get("username") else ""
            linhas.append([Button.inline(item["name"] + uname, ("disc_show|" + str(item["id"])).encode())])
        linhas.append([Button.inline(E_MANUAL + " Buscar manual", b"disc|manual"),
                       Button.inline(E_VOLTAR + " Voltar", b"disc_menu")])
        await ev.edit(cat.upper() + " (" + str(len(items)) + ")\nToque para ver o ID:", buttons=linhas)

    elif d.startswith(b"disc_show|"):
        chat_id = int(d.decode().split("|")[1])
        dialogs = await get_dialogs_with_timeout()
        all_items = [i for its in dialogs.values() for i in its]
        item = next((i for i in all_items if i["id"] == chat_id), None)
        nome = item["name"] if item else "?"
        uname = "\nUsername: @" + item["username"] if item and item.get("username") else ""
        await ev.answer(nome + "\nID: " + str(chat_id) + uname, alert=True)

def dentro_do_horario():
    if not AGENDAMENTO["ativo"]:
        return True
    agora = datetime.now().strftime("%H:%M")
    return AGENDAMENTO["inicio"] <= agora <= AGENDAMENTO["fim"]

def tipo_permitido(msg):
    if not SOMENTE_TIPOS: return True
    if "texto" in SOMENTE_TIPOS and msg.text and not msg.media: return True
    if "foto" in SOMENTE_TIPOS and msg.photo: return True
    if "video" in SOMENTE_TIPOS and msg.video: return True
    if "audio" in SOMENTE_TIPOS and (msg.audio or msg.voice): return True
    if "doc" in SOMENTE_TIPOS and msg.document: return True
    if "sticker" in SOMENTE_TIPOS and msg.sticker: return True
    return False

@userbot.on(events.NewMessage(incoming=True))
async def handler(event):
    global ultimo_envio
    try:
        if PAUSADO or not DESTINOS: return
        if not dentro_do_horario(): return
        if event.chat_id in DESTINOS or event.chat_id in IGNORADOS: return
        if SRC and event.chat_id not in SRC: return
        if not tipo_permitido(event.message): return
        if SEM_BOTS and event.sender and getattr(event.sender, "bot", False): return

        texto = (event.message.text or "").lower()
        if FILTROS_ON and not any(p in texto for p in FILTROS_ON): return
        if FILTROS_OFF and any(p in texto for p in FILTROS_OFF): return

        if DELAY > 0:
            agora = asyncio.get_event_loop().time()
            espera = DELAY - (agora - ultimo_envio)
            if espera > 0:
                await asyncio.sleep(espera)
            ultimo_envio = asyncio.get_event_loop().time()

        ok = 0
        for dst in DESTINOS:
            try:
                if MOD == "copy":
                    if (PREFIXO or RODAPE) and event.message.text:
                        novo = (PREFIXO + "\n" + event.message.text + "\n" + RODAPE).strip()
                        await userbot.send_message(dst, novo)
                    else:
                        await userbot.send_message(dst, event.message)
                else:
                    await userbot.forward_messages(dst, event.message)
                ok += 1
            except Exception as e:
                stats["err"] += 1
                logger.error("Erro ao enviar %s: %s", dst, e)

        if ok > 0:
            stats["n"] += 1
            stats["por_hora"][datetime.now().hour] += 1
            try:
                chat = await event.get_chat()
                name = getattr(chat, "title", None) or getattr(chat, "first_name", "?")
            except:
                name = str(event.chat_id)
            HISTORICO.append({"time": datetime.now().strftime("%H:%M"), "chat": name})
            if len(HISTORICO) > 200:
                HISTORICO.pop(0)
            if not MODO_SILENCIOSO:
                logger.info("[%s] #%s de '%s' -> %s destino(s)", BOT_NOME, stats["n"], name, ok)
    except Exception as e:
        stats["err"] += 1
        logger.error("Erro geral: %s", e)

async def main():
    await userbot.start()
    await bot.start(bot_token=BOT_TOKEN)
    me = await userbot.get_me()
    bme = await bot.get_me()
    logger.info("[%s] Userbot: %s | Bot: @%s", BOT_NOME, me.first_name, bme.username)
    logger.info("Destinos=%s | Origens=%s | Modo=%s", DESTINOS, SRC or "todos", MOD)
    asyncio.create_task(get_dialogs())
    await asyncio.gather(userbot.run_until_disconnected(), bot.run_until_disconnected())

asyncio.run(main())
