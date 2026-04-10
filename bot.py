import os,logging,asyncio,json,re
from telethon import TelegramClient,events,Button
from telethon.sessions import StringSession
from telethon.tl.types import User,Chat,Channel
from datetime import datetime
from collections import defaultdict

logging.basicConfig(format="%(asctime)s [%(levelname)s] %(message)s",level=logging.INFO)
logger=logging.getLogger(__name__)

API_ID=int(os.environ["API_ID"])
API_HASH=os.environ["API_HASH"]
SESSION=os.environ["SESSION_STRING"]
BOT_TOKEN=os.environ["BOT_TOKEN"]
BOT_NOME=os.environ.get("BOT_NOME","UserBot")
ADMIN_IDS=set(int(x) for x in os.environ.get("ADMIN_IDS","").split(",") if x.strip().isdigit())

_tgt_raw=os.environ.get("TARGET_GROUP_ID","")
DESTINOS=set(int(x) for x in re.split(r"[,; ]+",_tgt_raw) if x.strip().lstrip("-").isdigit())

SRC_RAW=os.environ.get("SOURCE_CHAT_IDS","")
SRC=set(int(x) for x in re.split(r"[,; ]+",SRC_RAW) if x.strip().lstrip("-").isdigit())

MOD=os.environ.get("FORWARD_MODE","forward")
stats={"n":0,"err":0,"start":datetime.now(),"por_hora":defaultdict(int)}
PAUSADO=False
FILTROS_ON=set()
FILTROS_OFF=set()
IGNORADOS=set()
HISTORICO=[]
AGUARDANDO={}
PREFIXO=""
RODAPE=""
DELAY=0
SOMENTE_TIPOS=set()
SEM_BOTS=False
AGENDAMENTO={"ativo":False,"inicio":"00:00","fim":"23:59"}
ultimo_envio=0
MODO_SILENCIOSO=False

# ── DISCOVER ID STATE ────────────────────────────────────────
DISCOVER_STATE={}  # {user_id: chave_tipo}

userbot=TelegramClient(StringSession(SESSION),API_ID,API_HASH)
bot=TelegramClient(StringSession(""),API_ID,API_HASH)

# ── ADMIN CHECK ──────────────────────────────────────────────
def is_admin(uid):
    return not ADMIN_IDS or uid in ADMIN_IDS

# ── TECLADOS PRINCIPAIS ──────────────────────────────────────
def kb_principal():
    estado="⏸ PAUSAR" if not PAUSADO else "▶️ RETOMAR"
    return [
        [Button.inline("📡 Origens",b"m_origens"),Button.inline("🎯 Destinos",b"m_destinos"),Button.inline("🔀 Modo",b"m_modo")],
        [Button.inline("🔍 Filtros",b"m_filtros"),Button.inline("⏰ Horário",b"m_agenda"),Button.inline("✏️ Mensagem",b"m_msg")],
        [Button.inline("📊 Status",b"m_status"),Button.inline("📜 Histórico",b"m_hist"),Button.inline("ℹ️ Info",b"m_info")],
        [Button.inline("🔎 Descobrir ID",b"m_discover")],
        [Button.inline(estado,b"m_toggle"),Button.inline("🔕 Silencioso" if not MODO_SILENCIOSO else "🔔 Normal",b"m_silencioso"),Button.inline("❌ Fechar",b"m_fechar")],
    ]

def kb_origens():
    return [
        [Button.inline("➕ Adicionar origem",b"o_add"),Button.inline("➖ Remover origem",b"o_rem")],
        [Button.inline("🚫 Ignorar chat",b"o_ign"),Button.inline("✅ Designorar",b"o_des")],
        [Button.inline("📋 Listar origens",b"o_list"),Button.inline("🗑 Limpar tudo",b"o_clear")],
        [Button.inline("⬅️ Voltar",b"m_back")],
    ]

def kb_destinos():
    return [
        [Button.inline("➕ Adicionar destino",b"d_add"),Button.inline("➖ Remover destino",b"d_rem")],
        [Button.inline("📋 Listar destinos",b"d_list"),Button.inline("🗑 Limpar destinos",b"d_clear")],
        [Button.inline("⬅️ Voltar",b"m_back")],
    ]

def kb_modo():
    return [
        [Button.inline("📨 Forward (mostra origem)",b"mo_fwd"),Button.inline("📋 Copy (sem origem)",b"mo_copy")],
        [Button.inline("🤖 Ignorar bots: "+("✅" if SEM_BOTS else "❌"),b"mo_bots")],
        [Button.inline("⏱ Delay entre envios",b"mo_delay"),Button.inline("📁 Tipos de mídia",b"mo_tipos")],
        [Button.inline("⬅️ Voltar",b"m_back")],
    ]

def kb_filtros():
    return [
        [Button.inline("🔍 Exigir palavra",b"f_add_on"),Button.inline("🚫 Bloquear palavra",b"f_add_off")],
        [Button.inline("➖ Remover filtro",b"f_rem"),Button.inline("📋 Ver filtros",b"f_list")],
        [Button.inline("🗑 Limpar filtros",b"f_clear"),Button.inline("⬅️ Voltar",b"m_back")],
    ]

def kb_agenda():
    return [
        [Button.inline("⏰ Definir horário",b"ag_set"),Button.inline("🔛 Ativar" if not AGENDAMENTO["ativo"] else "🔴 Desativar",b"ag_toggle")],
        [Button.inline("📋 Ver configuração",b"ag_ver"),Button.inline("⬅️ Voltar",b"m_back")],
    ]

def kb_msg():
    return [
        [Button.inline("✏️ Definir prefixo",b"mg_prefix"),Button.inline("📝 Definir rodapé",b"mg_suffix")],
        [Button.inline("❌ Remover prefixo",b"mg_rmpre"),Button.inline("❌ Remover rodapé",b"mg_rmsuf")],
        [Button.inline("👁 Ver configuração",b"mg_ver"),Button.inline("⬅️ Voltar",b"m_back")],
    ]

def kb_tipos():
    tipos=["texto","foto","video","audio","doc","sticker"]
    linhas=[]
    for i in range(0,len(tipos),2):
        linha=[]
        for t in tipos[i:i+2]:
            ativo="✅" if t in SOMENTE_TIPOS else "☐"
            linha.append(Button.inline(f"{ativo} {t}",f"tp_{t}".encode()))
        linhas.append(linha)
    linhas.append([Button.inline("🗑 Todos (limpar filtro)",b"tp_clear"),Button.inline("⬅️ Voltar",b"mo_tipos_back")])
    return linhas

def kb_info():
    return [
        [Button.inline("🏓 Ping",b"i_ping"),Button.inline("🆔 ID deste chat",b"i_id")],
        [Button.inline("📊 Estatísticas",b"i_stats"),Button.inline("🔄 Reiniciar stats",b"i_reset")],
        [Button.inline("📤 Testar destinos",b"i_teste"),Button.inline("⬅️ Voltar",b"m_back")],
    ]

# ── TECLADOS DISCOVER ID ─────────────────────────────────────
def kb_discover_menu():
    return [
        [Button.inline("👤 User",      b"disc_user"),
         Button.inline("⭐ Premium",   b"disc_premium"),
         Button.inline("🤖 Bot",       b"disc_bot")],
        [Button.inline("👥 Group",     b"disc_group"),
         Button.inline("📢 Channel",   b"disc_channel"),
         Button.inline("💬 Forum",     b"disc_forum")],
        [Button.inline("👥 My Group",  b"disc_mygroup"),
         Button.inline("📢 My Channel",b"disc_mychannel"),
         Button.inline("💬 My Forum",  b"disc_myforum")],
        [Button.inline("⬅️ Voltar",   b"m_back")],
    ]

DISCOVER_INSTRUCTIONS={
    "disc_user":      ("👤 User",       "Encaminhe uma mensagem de qualquer usuário aqui ou envie o @username."),
    "disc_premium":   ("⭐ Premium",    "Encaminhe uma mensagem de um usuário Premium do Telegram."),
    "disc_bot":       ("🤖 Bot",        "Encaminhe uma mensagem de um bot ou envie o @username do bot."),
    "disc_group":     ("👥 Group",      "Encaminhe uma mensagem do grupo aqui ou envie o @username."),
    "disc_channel":   ("📢 Channel",    "Encaminhe uma mensagem do canal aqui ou envie o @username."),
    "disc_forum":     ("💬 Forum",      "Encaminhe uma mensagem do fórum (supergrupo com tópicos) aqui."),
    "disc_mygroup":   ("👥 My Group",   "Encaminhe uma mensagem do seu grupo ou envie o @username."),
    "disc_mychannel": ("📢 My Channel", "Encaminhe uma mensagem do seu canal ou envie o @username."),
    "disc_myforum":   ("💬 My Forum",   "Encaminhe uma mensagem do seu fórum aqui."),
}

def status_texto():
    up=datetime.now()-stats["start"];h,r=divmod(int(up.total_seconds()),3600);mi,s=divmod(r,60)
    agenda_txt=f"{AGENDAMENTO['inicio']}–{AGENDAMENTO['fim']}" if AGENDAMENTO["ativo"] else "desativado"
    tipos_txt=", ".join(SOMENTE_TIPOS) if SOMENTE_TIPOS else "todos"
    return (
        f"📊 *{BOT_NOME} — STATUS*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"Estado : {'⏸ PAUSADO' if PAUSADO else '✅ ATIVO'}\n"
        f"Silenc.: {'🔕 ON' if MODO_SILENCIOSO else '🔔 OFF'}\n"
        f"Modo   : {MOD} {'| 🤖sem bots' if SEM_BOTS else ''}\n"
        f"Delay  : {DELAY}s\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"Destinos ({len(DESTINOS)}): {DESTINOS or 'nenhum'}\n"
        f"Origens ({len(SRC)}): {SRC or 'todos'}\n"
        f"Ignorados: {IGNORADOS or 'nenhum'}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"Filtros ON : {FILTROS_ON or 'nenhum'}\n"
        f"Filtros OFF: {FILTROS_OFF or 'nenhum'}\n"
        f"Tipos  : {tipos_txt}\n"
        f"Horário: {agenda_txt}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"Prefixo: {PREFIXO or 'nenhum'}\n"
        f"Rodapé : {RODAPE or 'nenhum'}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"Encaminhadas: {stats['n']} | Erros: {stats['err']}\n"
        f"Uptime: {h}h{mi}m{s}s"
    )

# ── COMANDOS ─────────────────────────────────────────────────
@bot.on(events.NewMessage(pattern=r"^/menu$"))
async def cmd_menu(ev):
    if not is_admin(ev.sender_id): return
    await ev.respond(f"🎛 *{BOT_NOME} — Painel de Controle*",buttons=kb_principal(),parse_mode="md")

@bot.on(events.NewMessage(pattern=r"^/status$"))
async def cmd_status(ev):
    if not is_admin(ev.sender_id): return
    await ev.respond(status_texto(),parse_mode="md")

@bot.on(events.NewMessage(pattern=r"^/start$"))
async def cmd_start(ev):
    await ev.respond(f"👋 Olá! Sou o *{BOT_NOME}*.\nDigite /menu para abrir o painel.",parse_mode="md")

@bot.on(events.NewMessage(pattern=r"^/pausar$"))
async def cmd_pausar(ev):
    global PAUSADO
    if not is_admin(ev.sender_id): return
    PAUSADO=True; await ev.respond("⏸ Bot pausado!")

@bot.on(events.NewMessage(pattern=r"^/retomar$"))
async def cmd_retomar(ev):
    global PAUSADO
    if not is_admin(ev.sender_id): return
    PAUSADO=False; await ev.respond("▶️ Bot retomado!")

@bot.on(events.NewMessage(pattern=r"^/stats$"))
async def cmd_stats(ev):
    if not is_admin(ev.sender_id): return
    horas=dict(sorted(stats["por_hora"].items()))
    t="📊 *Encaminhamentos por hora:*\n"
    t+="".join(f"  `{h:02d}h` {'█'*min(n,20)} {n}\n" for h,n in horas.items())
    t+=f"\n*Total: {stats['n']}* | Erros: {stats['err']}"
    await ev.respond(t,parse_mode="md")

# ── CAPTURA DE TEXTO (AGUARDANDO + DISCOVER) ─────────────────
@bot.on(events.NewMessage())
async def entrada_usuario(ev):
    global PAUSADO,MOD,PREFIXO,RODAPE,DELAY,SEM_BOTS,AGENDAMENTO
    uid=ev.sender_id
    if not is_admin(uid): return

    # ── DISCOVER: captura mensagem encaminhada ou @username ──
    if uid in DISCOVER_STATE:
        key=DISCOVER_STATE[uid]
        result_lines=[]
        handled=False

        # Mensagem encaminhada
        if ev.forward:
            handled=True
            fwd=ev.forward
            sender=getattr(fwd,"sender",None)
            if sender:
                eid=sender.id
                name=getattr(sender,"first_name","") or getattr(sender,"title","") or "Desconhecido"
                uname=getattr(sender,"username",None)
                if isinstance(sender,User):
                    if sender.bot: tipo="🤖 Bot"
                    elif getattr(sender,"premium",False): tipo="⭐ Premium"
                    else: tipo="👤 Usuário"
                    result_lines.append(f"🆔 **ID:** `{eid}`")
                    result_lines.append(f"👤 **Nome:** {name}")
                elif isinstance(sender,(Chat,Channel)):
                    is_ch=isinstance(sender,Channel) and not sender.megagroup
                    is_fo=getattr(sender,"forum",False)
                    tipo="📢 Canal" if is_ch else ("💬 Fórum" if is_fo else "👥 Grupo")
                    real_id=int(f"-100{eid}") if isinstance(sender,Channel) else -eid
                    result_lines.append(f"🆔 **ID:** `{real_id}`")
                    result_lines.append(f"📛 **Nome:** {name}")
                else:
                    tipo="❓ Desconhecido"
                    result_lines.append(f"🆔 **ID:** `{eid}`")
                if uname: result_lines.append(f"🔗 **Username:** @{uname}")
                result_lines.append(f"📌 **Tipo:** {tipo}")
            elif getattr(fwd,"channel_id",None):
                handled=True
                result_lines.append(f"🆔 **ID do canal:** `{int(f'-100{fwd.channel_id}')}`")

        # @username digitado
        elif ev.raw_text and ev.raw_text.strip().startswith("@"):
            handled=True
            username=ev.raw_text.strip()
            try:
                entity=await bot.get_entity(username)
                eid=entity.id
                name=getattr(entity,"first_name","") or getattr(entity,"title","") or "Desconhecido"
                uname=getattr(entity,"username",None)
                if isinstance(entity,User):
                    if entity.bot: tipo="🤖 Bot"
                    elif getattr(entity,"premium",False): tipo="⭐ Premium"
                    else: tipo="👤 Usuário"
                    result_lines.append(f"🆔 **ID:** `{eid}`")
                    result_lines.append(f"👤 **Nome:** {name}")
                elif isinstance(entity,(Chat,Channel)):
                    is_ch=isinstance(entity,Channel) and not entity.megagroup
                    is_fo=getattr(entity,"forum",False)
                    tipo="📢 Canal" if is_ch else ("💬 Fórum" if is_fo else "👥 Grupo")
                    real_id=int(f"-100{eid}") if isinstance(entity,Channel) else -eid
                    result_lines.append(f"🆔 **ID:** `{real_id}`")
                    result_lines.append(f"📛 **Nome:** {name}")
                else:
                    tipo="❓ Desconhecido"
                    result_lines.append(f"🆔 **ID:** `{eid}`")
                if uname: result_lines.append(f"🔗 **Username:** @{uname}")
                result_lines.append(f"📌 **Tipo:** {tipo}")
            except Exception as e:
                result_lines.append(f"❌ Não encontrado: `{username}`\nErro: `{e}`")

        if handled:
            DISCOVER_STATE.pop(uid,None)
            resp="✅ **ID Encontrado!**\n\n"+"\n".join(result_lines)
            await ev.respond(resp,buttons=[[Button.inline("🔎 Descobrir outro",b"disc_new"),Button.inline("⬅️ Menu",b"disc_menu")]],parse_mode="md")
            return

    # ── AGUARDANDO: entrada de configuração ──────────────────
    if uid not in AGUARDANDO: return
    acao=AGUARDANDO.pop(uid)
    txt=ev.raw_text.strip()

    def parse_ids(t): return [x.strip() for x in re.split(r"[,; ]+",t) if x.strip().lstrip("-").isdigit()]

    if acao=="o_add":
        ids=parse_ids(txt)
        for i in ids: SRC.add(int(i))
        await ev.respond(f"➕ Adicionado(s): `{ids}`\n📡 Origens: `{SRC or 'todos'}`",buttons=kb_origens(),parse_mode="md")
    elif acao=="o_rem":
        ids=parse_ids(txt)
        for i in ids: SRC.discard(int(i))
        await ev.respond(f"➖ Removido(s): `{ids}`\n📡 Origens: `{SRC or 'todos'}`",buttons=kb_origens(),parse_mode="md")
    elif acao=="o_ign":
        ids=parse_ids(txt)
        for i in ids: IGNORADOS.add(int(i))
        await ev.respond(f"🚫 Ignorando: `{ids}`",buttons=kb_origens(),parse_mode="md")
    elif acao=="o_des":
        ids=parse_ids(txt)
        for i in ids: IGNORADOS.discard(int(i))
        await ev.respond(f"✅ Designorado(s): `{ids}`",buttons=kb_origens(),parse_mode="md")
    elif acao=="d_add":
        ids=parse_ids(txt)
        for i in ids: DESTINOS.add(int(i))
        await ev.respond(f"➕ Destino(s) adicionado(s): `{ids}`\n🎯 Destinos: `{DESTINOS}`",buttons=kb_destinos(),parse_mode="md")
    elif acao=="d_rem":
        ids=parse_ids(txt)
        for i in ids: DESTINOS.discard(int(i))
        await ev.respond(f"➖ Removido(s): `{ids}`\n🎯 Destinos: `{DESTINOS}`",buttons=kb_destinos(),parse_mode="md")
    elif acao=="f_add_on":
        palavras=[p.lower() for p in txt.split()]
        FILTROS_ON.update(palavras)
        await ev.respond(f"🔍 Palavras exigidas: `{FILTROS_ON}`",buttons=kb_filtros(),parse_mode="md")
    elif acao=="f_add_off":
        palavras=[p.lower() for p in txt.split()]
        FILTROS_OFF.update(palavras)
        await ev.respond(f"🚫 Palavras bloqueadas: `{FILTROS_OFF}`",buttons=kb_filtros(),parse_mode="md")
    elif acao=="f_rem":
        palavras=[p.lower() for p in txt.split()]
        for p in palavras: FILTROS_ON.discard(p);FILTROS_OFF.discard(p)
        await ev.respond(f"🗑 Removido.\nON:`{FILTROS_ON}` | OFF:`{FILTROS_OFF}`",buttons=kb_filtros(),parse_mode="md")
    elif acao=="mg_prefix":
        PREFIXO=txt
        await ev.respond(f"✏️ Prefixo: `{PREFIXO}`",buttons=kb_msg(),parse_mode="md")
    elif acao=="mg_suffix":
        RODAPE=txt
        await ev.respond(f"📝 Rodapé: `{RODAPE}`",buttons=kb_msg(),parse_mode="md")
    elif acao=="mo_delay":
        if txt.isdigit(): DELAY=int(txt);await ev.respond(f"⏱ Delay: `{DELAY}s`",buttons=kb_modo(),parse_mode="md")
        else: await ev.respond("❌ Digite apenas números",buttons=kb_modo())
    elif acao=="ag_set":
        try:
            partes=txt.split()
            AGENDAMENTO["inicio"]=partes[0];AGENDAMENTO["fim"]=partes[1]
            await ev.respond(f"⏰ Horário: `{AGENDAMENTO['inicio']} – {AGENDAMENTO['fim']}`",buttons=kb_agenda(),parse_mode="md")
        except: await ev.respond("❌ Formato: `HH:MM HH:MM`  ex: `08:00 22:00`",buttons=kb_agenda(),parse_mode="md")

# ── CALLBACKS ────────────────────────────────────────────────
@bot.on(events.CallbackQuery)
async def callback(ev):
    global PAUSADO,MOD,SEM_BOTS,AGENDAMENTO,PREFIXO,RODAPE,MODO_SILENCIOSO
    if not is_admin(ev.sender_id):
        await ev.answer("⛔ Sem permissão!",alert=True); return
    d=ev.data; uid=ev.sender_id

    # ── DISCOVER ID ──────────────────────────────────────────
    if d==b"m_discover":
        DISCOVER_STATE.pop(uid,None)
        await ev.edit("🔎 *Descobrir ID*\n\nEscolha o tipo de entidade:",buttons=kb_discover_menu(),parse_mode="md")
        return

    if d in (b"disc_new",b"disc_menu"):
        DISCOVER_STATE.pop(uid,None)
        if d==b"disc_menu":
            await ev.edit(f"🎛 *{BOT_NOME} — Painel de Controle*",buttons=kb_principal(),parse_mode="md")
        else:
            await ev.edit("🔎 *Descobrir ID*\n\nEscolha o tipo de entidade:",buttons=kb_discover_menu(),parse_mode="md")
        return

    if d.startswith(b"disc_"):
        key=d.decode()
        if key in DISCOVER_INSTRUCTIONS:
            DISCOVER_STATE[uid]=key
            title,instruction=DISCOVER_INSTRUCTIONS[key]
            await ev.edit(
                f"*{title}*\n\n{instruction}\n\n⬇️ Encaminhe a mensagem ou envie o @username:",
                buttons=[[Button.inline("⬅️ Voltar",b"m_discover")]],
                parse_mode="md"
            )
            return

    # ── MENU PRINCIPAL ───────────────────────────────────────
    if d==b"m_back":
        DISCOVER_STATE.pop(uid,None)
        await ev.edit(f"🎛 *{BOT_NOME} — Painel*",buttons=kb_principal(),parse_mode="md")
    elif d==b"m_origens": await ev.edit("📡 *Gerenciar Origens*\nVários IDs separados por vírgula.",buttons=kb_origens(),parse_mode="md")
    elif d==b"m_destinos": await ev.edit(f"🎯 *Destinos* ({len(DESTINOS)} configurado(s))",buttons=kb_destinos(),parse_mode="md")
    elif d==b"m_modo": await ev.edit("🔀 *Modo de Encaminhamento*",buttons=kb_modo(),parse_mode="md")
    elif d==b"m_filtros": await ev.edit("🔍 *Filtros de Mensagem*",buttons=kb_filtros(),parse_mode="md")
    elif d==b"m_agenda": await ev.edit(f"⏰ *Agendamento* {'✅' if AGENDAMENTO['ativo'] else '❌'}\n{AGENDAMENTO['inicio']}–{AGENDAMENTO['fim']}",buttons=kb_agenda(),parse_mode="md")
    elif d==b"m_msg": await ev.edit("✏️ *Personalizar Mensagens*",buttons=kb_msg(),parse_mode="md")
    elif d==b"m_info": await ev.edit("ℹ️ *Informações*",buttons=kb_info(),parse_mode="md")
    elif d==b"m_hist":
        if not HISTORICO: await ev.edit("📜 Nenhuma mensagem ainda.",buttons=[[Button.inline("⬅️ Voltar",b"m_back")]])
        else:
            t="📜 *Últimas mensagens:*\n"+"".join(f"`{h['time']}` {h['chat']}\n" for h in HISTORICO[-15:])
            await ev.edit(t,buttons=[[Button.inline("⬅️ Voltar",b"m_back")]],parse_mode="md")
    elif d==b"m_status": await ev.edit(status_texto(),buttons=[[Button.inline("🔄 Atualizar",b"m_status"),Button.inline("⬅️ Voltar",b"m_back")]],parse_mode="md")
    elif d==b"m_fechar": await ev.delete()
    elif d==b"m_toggle":
        PAUSADO=not PAUSADO
        await ev.edit(f"🎛 *{BOT_NOME} — Painel*",buttons=kb_principal(),parse_mode="md")
        await ev.answer("⏸ PAUSADO!" if PAUSADO else "▶️ RETOMADO!",alert=True)
    elif d==b"m_silencioso":
        MODO_SILENCIOSO=not MODO_SILENCIOSO
        await ev.edit(f"🎛 *{BOT_NOME} — Painel*",buttons=kb_principal(),parse_mode="md")
        await ev.answer("🔕 Modo silencioso ON" if MODO_SILENCIOSO else "🔔 Modo normal ON",alert=True)
    # Origens
    elif d==b"o_add": AGUARDANDO[uid]="o_add";await ev.answer("Digite o(s) ID(s) de origem.\nEx: -1001234567890",alert=True)
    elif d==b"o_rem": AGUARDANDO[uid]="o_rem";await ev.answer(f"Origens: {SRC or 'todos'}\nDigite IDs para remover:",alert=True)
    elif d==b"o_ign": AGUARDANDO[uid]="o_ign";await ev.answer("Digite IDs para ignorar:",alert=True)
    elif d==b"o_des": AGUARDANDO[uid]="o_des";await ev.answer(f"Ignorados: {IGNORADOS}\nDigite IDs para designorar:",alert=True)
    elif d==b"o_list":
        t=("📡 Origens:\n"+"\n".join(f"• {s}" for s in SRC)) if SRC else "📡 Monitorando TODOS"
        t+="\n\n🚫 Ignorados:\n"+("\n".join(f"• {s}" for s in IGNORADOS) if IGNORADOS else "nenhum")
        await ev.answer(t,alert=True)
    elif d==b"o_clear": SRC.clear();await ev.answer("🗑 Origens limpas!",alert=True)
    # Destinos
    elif d==b"d_add": AGUARDANDO[uid]="d_add";await ev.answer("Digite ID(s) do(s) destino(s).\nEx: -1003861276779",alert=True)
    elif d==b"d_rem": AGUARDANDO[uid]="d_rem";await ev.answer(f"Destinos: {DESTINOS}\nDigite IDs para remover:",alert=True)
    elif d==b"d_list":
        t=("🎯 Destinos:\n"+"\n".join(f"• {s}" for s in DESTINOS)) if DESTINOS else "⚠️ Nenhum destino!"
        await ev.answer(t,alert=True)
    elif d==b"d_clear": DESTINOS.clear();await ev.answer("🗑 Destinos removidos!",alert=True)
    # Modo
    elif d==b"mo_fwd": MOD="forward";await ev.edit("🔀 *Modo*",buttons=kb_modo(),parse_mode="md");await ev.answer("📨 Modo: forward",alert=True)
    elif d==b"mo_copy": MOD="copy";await ev.edit("🔀 *Modo*",buttons=kb_modo(),parse_mode="md");await ev.answer("📋 Modo: copy",alert=True)
    elif d==b"mo_bots": SEM_BOTS=not SEM_BOTS;await ev.edit("🔀 *Modo*",buttons=kb_modo(),parse_mode="md");await ev.answer(f"🤖 Ignorar bots: {'✅ ON' if SEM_BOTS else '❌ OFF'}",alert=True)
    elif d==b"mo_delay": AGUARDANDO[uid]="mo_delay";await ev.answer(f"Delay atual: {DELAY}s\nDigite em segundos (0=sem delay):",alert=True)
    elif d==b"mo_tipos": await ev.edit("📁 *Tipos de mídia*\nNenhum = encaminha tudo",buttons=kb_tipos(),parse_mode="md")
    elif d==b"mo_tipos_back": await ev.edit("🔀 *Modo*",buttons=kb_modo(),parse_mode="md")
    elif d==b"tp_clear": SOMENTE_TIPOS.clear();await ev.edit("📁 *Tipos* — Todos liberados",buttons=kb_tipos(),parse_mode="md")
    elif d.startswith(b"tp_"):
        t=d.decode().replace("tp_","")
        if t in SOMENTE_TIPOS: SOMENTE_TIPOS.discard(t)
        else: SOMENTE_TIPOS.add(t)
        await ev.edit("📁 *Tipos de mídia*",buttons=kb_tipos(),parse_mode="md")
    # Filtros
    elif d==b"f_add_on": AGUARDANDO[uid]="f_add_on";await ev.answer("Palavras EXIGIDAS (espaço entre elas):",alert=True)
    elif d==b"f_add_off": AGUARDANDO[uid]="f_add_off";await ev.answer("Palavras BLOQUEADAS (espaço entre elas):",alert=True)
    elif d==b"f_rem": AGUARDANDO[uid]="f_rem";await ev.answer(f"ON:{FILTROS_ON}\nOFF:{FILTROS_OFF}\nPalavras para remover:",alert=True)
    elif d==b"f_list": await ev.answer(f"🔍 Exigidas: {FILTROS_ON or 'nenhuma'}\n🚫 Bloqueadas: {FILTROS_OFF or 'nenhuma'}",alert=True)
    elif d==b"f_clear": FILTROS_ON.clear();FILTROS_OFF.clear();await ev.answer("🗑 Filtros removidos!",alert=True)
    # Agenda
    elif d==b"ag_toggle": AGENDAMENTO["ativo"]=not AGENDAMENTO["ativo"];await ev.edit(f"⏰ *Agendamento* {'✅' if AGENDAMENTO['ativo'] else '❌'}",buttons=kb_agenda(),parse_mode="md");await ev.answer(f"Agendamento {'ativado' if AGENDAMENTO['ativo'] else 'desativado'}!",alert=True)
    elif d==b"ag_set": AGUARDANDO[uid]="ag_set";await ev.answer("Horário início e fim:\nEx: 08:00 22:00",alert=True)
    elif d==b"ag_ver": await ev.answer(f"{'✅ Ativo' if AGENDAMENTO['ativo'] else '❌ Inativo'}\nInício: {AGENDAMENTO['inicio']}\nFim: {AGENDAMENTO['fim']}",alert=True)
    # Mensagem
    elif d==b"mg_prefix": AGUARDANDO[uid]="mg_prefix";await ev.answer(f"Prefixo atual: {PREFIXO or 'nenhum'}\nNovo prefixo:",alert=True)
    elif d==b"mg_suffix": AGUARDANDO[uid]="mg_suffix";await ev.answer(f"Rodapé atual: {RODAPE or 'nenhum'}\nNovo rodapé:",alert=True)
    elif d==b"mg_rmpre": PREFIXO="";await ev.answer("✅ Prefixo removido!",alert=True)
    elif d==b"mg_rmsuf": RODAPE="";await ev.answer("✅ Rodapé removido!",alert=True)
    elif d==b"mg_ver": await ev.answer(f"✏️ Prefixo: {PREFIXO or 'nenhum'}\n📝 Rodapé: {RODAPE or 'nenhum'}",alert=True)
    # Info
    elif d==b"i_ping":
        up=datetime.now()-stats["start"];h2,r=divmod(int(up.total_seconds()),3600);mi,s=divmod(r,60)
        await ev.answer(f"🏓 Pong!\nUptime: {h2}h{mi}m{s}s",alert=True)
    elif d==b"i_id": await ev.answer(f"🆔 ID deste chat: {ev.chat_id}",alert=True)
    elif d==b"i_stats":
        horas=dict(sorted(stats["por_hora"].items())[-8:])
        t="📊 Por hora:\n"+"".join(f"  {h2:02d}h: {n}\n" for h2,n in horas.items())
        t+=f"\nTotal: {stats['n']} | Erros: {stats['err']}"
        await ev.answer(t,alert=True)
    elif d==b"i_reset": stats["n"]=0;stats["err"]=0;stats["por_hora"].clear();stats["start"]=datetime.now();await ev.answer("🔄 Stats zeradas!",alert=True)
    elif d==b"i_teste":
        if not DESTINOS: await ev.answer("⚠️ Nenhum destino!",alert=True);return
        ok=0
        for dst in DESTINOS:
            try: await bot.send_message(dst,f"🧪 *{BOT_NOME} — Teste* ✅\n{datetime.now().strftime('%d/%m %H:%M')}",parse_mode="md");ok+=1
            except Exception as e: logger.error(f"Teste falhou em {dst}: {e}")
        await ev.answer(f"📤 Teste enviado para {ok}/{len(DESTINOS)} destino(s)!",alert=True)

# ── HELPERS ──────────────────────────────────────────────────
def dentro_do_horario():
    if not AGENDAMENTO["ativo"]: return True
    return AGENDAMENTO["inicio"]<=datetime.now().strftime("%H:%M")<=AGENDAMENTO["fim"]

def tipo_permitido(msg):
    if not SOMENTE_TIPOS: return True
    if "texto" in SOMENTE_TIPOS and msg.text and not msg.media: return True
    if "foto" in SOMENTE_TIPOS and msg.photo: return True
    if "video" in SOMENTE_TIPOS and msg.video: return True
    if "audio" in SOMENTE_TIPOS and (msg.audio or msg.voice): return True
    if "doc" in SOMENTE_TIPOS and msg.document: return True
    if "sticker" in SOMENTE_TIPOS and msg.sticker: return True
    return False

# ── ENCAMINHADOR (USERBOT) ───────────────────────────────────
@userbot.on(events.NewMessage(incoming=True))
async def handler(event):
    global ultimo_envio
    try:
        if PAUSADO or not DESTINOS: return
        if not dentro_do_horario(): return
        if event.chat_id in DESTINOS or event.chat_id in IGNORADOS: return
        if SRC and event.chat_id not in SRC: return
        if not tipo_permitido(event.message): return
        if SEM_BOTS and event.sender and getattr(event.sender,"bot",False): return

        texto=(event.message.text or "").lower()
        if FILTROS_ON and not any(p in texto for p in FILTROS_ON): return
        if FILTROS_OFF and any(p in texto for p in FILTROS_OFF): return

        if DELAY>0:
            agora=asyncio.get_event_loop().time()
            espera=DELAY-(agora-ultimo_envio)
            if espera>0: await asyncio.sleep(espera)
            ultimo_envio=asyncio.get_event_loop().time()

        ok=0
        for dst in DESTINOS:
            try:
                if MOD=="copy":
                    if (PREFIXO or RODAPE) and event.message.text:
                        novo=f"{PREFIXO}\n{event.message.text}\n{RODAPE}".strip()
                        await userbot.send_message(dst,novo)
                    else:
                        await userbot.send_message(dst,event.message)
                else:
                    await userbot.forward_messages(dst,event.message)
                ok+=1
            except Exception as e:
                stats["err"]+=1;logger.error(f"Erro ao enviar para {dst}: {e}")

        if ok>0:
            stats["n"]+=1
            stats["por_hora"][datetime.now().hour]+=1
            try: chat=await event.get_chat();name=getattr(chat,"title",None) or getattr(chat,"first_name","?")
            except: name=str(event.chat_id)
            HISTORICO.append({"time":datetime.now().strftime("%H:%M"),"chat":name})
            if len(HISTORICO)>200: HISTORICO.pop(0)
            if not MODO_SILENCIOSO:
                logger.info(f"[{BOT_NOME}] #{stats['n']} de '{name}' → {ok} destino(s)")

    except Exception as e: stats["err"]+=1;logger.error(f"Erro geral: {e}")

# ── MAIN ─────────────────────────────────────────────────────
async def main():
    await userbot.start()
    await bot.start(bot_token=BOT_TOKEN)
    me=await userbot.get_me()
    bme=await bot.get_me()
    logger.info(f"✅ [{BOT_NOME}] Userbot: {me.first_name} | Bot: @{bme.username}")
    logger.info(f"   Destinos={DESTINOS} | Origens={SRC or 'todos'} | Modo={MOD}")
    await asyncio.gather(userbot.run_until_disconnected(),bot.run_until_disconnected())

asyncio.run(main())
