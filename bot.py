import os,logging,asyncio,json,re
from telethon import TelegramClient,events,Button
from telethon.sessions import StringSession
from telethon.tl.types import (Channel,Chat,User,
    InputPeerChannel,InputPeerChat,InputPeerUser)
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

# Cache de dialogs para nÃ£o chamar a API toda vez
_dialogs_cache={}
_dialogs_ts=0
DIALOGS_TTL=120  # segundos

userbot=TelegramClient(StringSession(SESSION),API_ID,API_HASH)
bot=TelegramClient(StringSession(""),API_ID,API_HASH)

def is_admin(uid):
    return not ADMIN_IDS or uid in ADMIN_IDS

# â”€â”€ HELPERS DIALOGS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
async def get_dialogs_cached():
    global _dialogs_cache,_dialogs_ts
    agora=asyncio.get_event_loop().time()
    if _dialogs_cache and (agora-_dialogs_ts)<DIALOGS_TTL:
        return _dialogs_cache
    dialogs={}
    async for d in userbot.iter_dialogs():
        e=d.entity
        if isinstance(e,Channel):
            if e.megagroup:
                cat="mygroup"
            elif e.broadcast:
                cat="mychannel"
            elif getattr(e,"forum",False):
                cat="myforum"
            else:
                cat="mygroup"
        elif isinstance(e,Chat):
            cat="mygroup"
        elif isinstance(e,User):
            if e.bot: cat="bot"
            elif e.premium: cat="premium"
            else: cat="user"
        else:
            continue
        dialogs.setdefault(cat,[]).append({
            "id":d.id,
            "name":d.name or getattr(e,"first_name","?"),
            "username":getattr(e,"username",None)
        })
    _dialogs_cache=dialogs
    _dialogs_ts=agora
    return dialogs

def chunks(lst,n):
    for i in range(0,len(lst),n):
        yield lst[i:i+n]

# â”€â”€ TECLADOS PRINCIPAIS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def kb_principal():
    estado="â¸ PAUSAR" if not PAUSADO else "â–¶ï¸ RETOMAR"
    return [
        [Button.inline("ðŸ“¡ Origens",b"m_origens"),Button.inline("ðŸŽ¯ Destinos",b"m_destinos"),Button.inline("ðŸ”€ Modo",b"m_modo")],
        [Button.inline("ðŸ” Filtros",b"m_filtros"),Button.inline("â° HorÃ¡rio",b"m_agenda"),Button.inline("âœï¸ Mensagem",b"m_msg")],
        [Button.inline("ðŸ“Š Status",b"m_status"),Button.inline("ðŸ“œ HistÃ³rico",b"m_hist"),Button.inline("â„¹ï¸ Info",b"m_info")],
        [Button.inline("ðŸ”Ž Descobrir ID",b"disc_menu")],
        [Button.inline(estado,b"m_toggle"),Button.inline("ðŸ”• Silencioso" if not MODO_SILENCIOSO else "ðŸ”” Normal",b"m_silencioso"),Button.inline("âŒ Fechar",b"m_fechar")],
    ]

def kb_select_tipo(contexto):
    """contexto: 'src' ou 'dst'"""
    c=contexto.encode()
    return [
        [Button.inline("ðŸ‘¤ User",      c+b"|user"),   Button.inline("â­ Premium", c+b"|premium"), Button.inline("ðŸ¤– Bot",       c+b"|bot")],
        [Button.inline("ðŸ‘¥ Group",     c+b"|group"),  Button.inline("ðŸ“¢ Channel", c+b"|channel"), Button.inline("ðŸ’¬ Forum",     c+b"|forum")],
        [Button.inline("ðŸ‘¥ My Group",  c+b"|mygroup"),Button.inline("ðŸ“¢ My Channel",c+b"|mychannel"),Button.inline("ðŸ’¬ My Forum",c+b"|myforum")],
        [Button.inline("âœï¸ Digitar ID manualmente",c+b"|manual")],
        [Button.inline("â¬…ï¸ Voltar",b"m_back")],
    ]

def kb_origens_gerenciar():
    return [
        [Button.inline("âž• Adicionar origem",b"o_addtipo"),Button.inline("âž– Remover origem",b"o_rem")],
        [Button.inline("ðŸš« Ignorar chat",b"o_ign"),Button.inline("âœ… Designorar",b"o_des")],
        [Button.inline("ðŸ“‹ Listar origens",b"o_list"),Button.inline("ðŸ—‘ Limpar tudo",b"o_clear")],
        [Button.inline("â¬…ï¸ Voltar",b"m_back")],
    ]

def kb_destinos_gerenciar():
    return [
        [Button.inline("âž• Adicionar destino",b"d_addtipo"),Button.inline("âž– Remover destino",b"d_rem")],
        [Button.inline("ðŸ“‹ Listar destinos",b"d_list"),Button.inline("ðŸ—‘ Limpar destinos",b"d_clear")],
        [Button.inline("â¬…ï¸ Voltar",b"m_back")],
    ]

def kb_modo():
    return [
        [Button.inline("ðŸ“¨ Forward (mostra origem)",b"mo_fwd"),Button.inline("ðŸ“‹ Copy (sem origem)",b"mo_copy")],
        [Button.inline("ðŸ¤– Ignorar bots: "+("âœ…" if SEM_BOTS else "âŒ"),b"mo_bots")],
        [Button.inline("â± Delay entre envios",b"mo_delay"),Button.inline("ðŸ“ Tipos de mÃ­dia",b"mo_tipos")],
        [Button.inline("â¬…ï¸ Voltar",b"m_back")],
    ]

def kb_filtros():
    return [
        [Button.inline("ðŸ” Exigir palavra",b"f_add_on"),Button.inline("ðŸš« Bloquear palavra",b"f_add_off")],
        [Button.inline("âž– Remover filtro",b"f_rem"),Button.inline("ðŸ“‹ Ver filtros",b"f_list")],
        [Button.inline("ðŸ—‘ Limpar filtros",b"f_clear"),Button.inline("â¬…ï¸ Voltar",b"m_back")],
    ]

def kb_agenda():
    return [
        [Button.inline("â° Definir horÃ¡rio",b"ag_set"),Button.inline("ðŸ”› Ativar" if not AGENDAMENTO["ativo"] else "ðŸ”´ Desativar",b"ag_toggle")],
        [Button.inline("ðŸ“‹ Ver configuraÃ§Ã£o",b"ag_ver"),Button.inline("â¬…ï¸ Voltar",b"m_back")],
    ]

def kb_msg():
    return [
        [Button.inline("âœï¸ Definir prefixo",b"mg_prefix"),Button.inline("ðŸ“ Definir rodapÃ©",b"mg_suffix")],
        [Button.inline("âŒ Remover prefixo",b"mg_rmpre"),Button.inline("âŒ Remover rodapÃ©",b"mg_rmsuf")],
        [Button.inline("ðŸ‘ Ver configuraÃ§Ã£o",b"mg_ver"),Button.inline("â¬…ï¸ Voltar",b"m_back")],
    ]

def kb_tipos():
    tipos=["texto","foto","video","audio","doc","sticker"]
    linhas=[]
    for i in range(0,len(tipos),2):
        linha=[]
        for t in tipos[i:i+2]:
            ativo="âœ…" if t in SOMENTE_TIPOS else "â˜"
            linha.append(Button.inline(f"{ativo} {t}",f"tp_{t}".encode()))
        linhas.append(linha)
    linhas.append([Button.inline("ðŸ—‘ Todos (limpar filtro)",b"tp_clear"),Button.inline("â¬…ï¸ Voltar",b"mo_tipos_back")])
    return linhas

def kb_info():
    return [
        [Button.inline("ðŸ“ Ping",b"i_ping"),Button.inline("ðŸ†” ID deste chat",b"i_id")],
        [Button.inline("ðŸ“Š EstatÃ­sticas",b"i_stats"),Button.inline("ðŸ”„ Reiniciar stats",b"i_reset")],
        [Button.inline("ðŸ“¤ Testar destinos",b"i_teste"),Button.inline("â¬…ï¸ Voltar",b"m_back")],
    ]

def kb_discover_menu():
    return [
        [Button.inline("ðŸ‘¤ User",b"disc|user"),    Button.inline("â­ Premium",b"disc|premium"),Button.inline("ðŸ¤– Bot",b"disc|bot")],
        [Button.inline("ðŸ‘¥ Group",b"disc|group"),  Button.inline("ðŸ“¢ Channel",b"disc|channel"),Button.inline("ðŸ’¬ Forum",b"disc|forum")],
        [Button.inline("ðŸ‘¥ My Group",b"disc|mygroup"),Button.inline("ðŸ“¢ My Channel",b"disc|mychannel"),Button.inline("ðŸ’¬ My Forum",b"disc|myforum")],
        [Button.inline("â¬…ï¸ Voltar",b"m_back")],
    ]

def status_texto():
    up=datetime.now()-stats["start"];h,r=divmod(int(up.total_seconds()),3600);mi,s=divmod(r,60)
    agenda_txt=f"{AGENDAMENTO['inicio']}â€“{AGENDAMENTO['fim']}" if AGENDAMENTO["ativo"] else "desativado"
    tipos_txt=", ".join(SOMENTE_TIPOS) if SOMENTE_TIPOS else "todos"
    return (
        f"ðŸ“Š *{BOT_NOME} â€” STATUS*\n"
        f"â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”\n"
        f"Estado : {'â¸ PAUSADO' if PAUSADO else 'âœ… ATIVO'}\n"
        f"Silenc.: {'ðŸ”• ON' if MODO_SILENCIOSO else 'ðŸ”” OFF'}\n"
        f"Modo   : {MOD} {'| ðŸ¤–sem bots' if SEM_BOTS else ''}\n"
        f"Delay  : {DELAY}s\n"
        f"â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”\n"
        f"Destinos ({len(DESTINOS)}): {DESTINOS or 'nenhum'}\n"
        f"Origens ({len(SRC)}): {SRC or 'todos'}\n"
        f"Ignorados: {IGNORADOS or 'nenhum'}\n"
        f"â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”\n"
        f"Filtros ON : {FILTROS_ON or 'nenhum'}\n"
        f"Filtros OFF: {FILTROS_OFF or 'nenhum'}\n"
        f"Tipos  : {tipos_txt}\n"
        f"HorÃ¡rio: {agenda_txt}\n"
        f"â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”\n"
        f"Prefixo: {PREFIXO or 'nenhum'}\n"
        f"RodapÃ© : {RODAPE or 'nenhum'}\n"
        f"â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”\n"
        f"Encaminhadas: {stats['n']} | Erros: {stats['err']}\n"
        f"Uptime: {h}h{mi}m{s}s"
    )

# â”€â”€ COMANDOS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@bot.on(events.NewMessage(pattern=r"^/menu$"))
async def cmd_menu(ev):
    if not is_admin(ev.sender_id): return
    await ev.respond(f"ðŸŽ› *{BOT_NOME} â€” Painel de Controle*",buttons=kb_principal(),parse_mode="md")

@bot.on(events.NewMessage(pattern=r"^/status$"))
async def cmd_status(ev):
    if not is_admin(ev.sender_id): return
    await ev.respond(status_texto(),parse_mode="md")

@bot.on(events.NewMessage(pattern=r"^/start$"))
async def cmd_start(ev):
    await ev.respond(f"ðŸ‘‹ OlÃ¡! Sou o *{BOT_NOME}*.\nDigite /menu para abrir o painel.",parse_mode="md")

@bot.on(events.NewMessage(pattern=r"^/pausar$"))
async def cmd_pausar(ev):
    global PAUSADO
    if not is_admin(ev.sender_id): return
    PAUSADO=True; await ev.respond("â¸ Bot pausado!")

@bot.on(events.NewMessage(pattern=r"^/retomar$"))
async def cmd_retomar(ev):
    global PAUSADO
    if not is_admin(ev.sender_id): return
    PAUSADO=False; await ev.respond("â–¶ï¸ Bot retomado!")

@bot.on(events.NewMessage(pattern=r"^/stats$"))
async def cmd_stats(ev):
    if not is_admin(ev.sender_id): return
    horas=dict(sorted(stats["por_hora"].items()))
    t="ðŸ“Š *Encaminhamentos por hora:*\n"
    t+="".join(f"  `{h:02d}h` {'â–ˆ'*min(n,20)} {n}\n" for h,n in horas.items())
    t+=f"\n*Total: {stats['n']}* | Erros: {stats['err']}"
    await ev.respond(t,parse_mode="md")

# â”€â”€ ENTRADA DE TEXTO â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@bot.on(events.NewMessage())
async def entrada_usuario(ev):
    global PAUSADO,MOD,PREFIXO,RODAPE,DELAY,SEM_BOTS,AGENDAMENTO
    uid=ev.sender_id
    if not is_admin(uid): return
    if uid not in AGUARDANDO: return
    acao=AGUARDANDO.pop(uid)
    txt=ev.raw_text.strip()

    def parse_ids(t): return [x.strip() for x in re.split(r"[,; ]+",t) if x.strip().lstrip("-").isdigit()]

    # Descobrir ID por username/forward
    if acao=="disc_input":
        if ev.forward:
            fwd=ev.forward
            peer_id=getattr(fwd,"from_id",None) or getattr(fwd,"channel_id",None)
            if peer_id:
                real_id=getattr(peer_id,"user_id",None) or getattr(peer_id,"channel_id",None) or getattr(peer_id,"chat_id",None)
                if real_id:
                    final_id=-100*10**len(str(real_id))+real_id if hasattr(peer_id,"channel_id") else real_id
                    await ev.respond(
                        f"ðŸ†” *ID descoberto:*\n`{final_id}`",
                        buttons=[[Button.inline("ðŸ”Ž Descobrir outro",b"disc_menu"),Button.inline("â¬…ï¸ Menu",b"m_back")]],
                        parse_mode="md"
                    )
                    return
        if txt.startswith("@") or not txt.startswith("-"):
            try:
                entity=await userbot.get_entity(txt)
                eid=getattr(entity,"id",None)
                ename=getattr(entity,"title",None) or getattr(entity,"first_name","?")
                euser=getattr(entity,"username",None)
                if isinstance(entity,Channel):
                    final_id=int(f"-100{eid}")
                else:
                    final_id=eid
                info=f"ðŸ†” *{ename}*\n"
                if euser: info+=f"@{euser}\n"
                info+=f"ID: `{final_id}`"
                await ev.respond(info,
                    buttons=[[Button.inline("ðŸ”Ž Descobrir outro",b"disc_menu"),Button.inline("â¬…ï¸ Menu",b"m_back")]],
                    parse_mode="md")
            except Exception as e:
                await ev.respond(f"âŒ NÃ£o encontrado: {e}",
                    buttons=[[Button.inline("ðŸ”Ž Tentar novamente",b"disc_menu"),Button.inline("â¬…ï¸ Menu",b"m_back")]])
            return

    if acao=="o_add":
        ids=parse_ids(txt)
        for i in ids: SRC.add(int(i))
        await ev.respond(f"âž• Adicionado(s): `{ids}`\nðŸ“¡ Origens: `{SRC or 'todos'}`",buttons=kb_origens_gerenciar(),parse_mode="md")
    elif acao=="o_rem":
        ids=parse_ids(txt)
        for i in ids: SRC.discard(int(i))
        await ev.respond(f"âž– Removido(s): `{ids}`\nðŸ“¡ Origens: `{SRC or 'todos'}`",buttons=kb_origens_gerenciar(),parse_mode="md")
    elif acao=="o_ign":
        ids=parse_ids(txt)
        for i in ids: IGNORADOS.add(int(i))
        await ev.respond(f"ðŸš« Ignorando: `{ids}`",buttons=kb_origens_gerenciar(),parse_mode="md")
    elif acao=="o_des":
        ids=parse_ids(txt)
        for i in ids: IGNORADOS.discard(int(i))
        await ev.respond(f"âœ… Designorado(s): `{ids}`",buttons=kb_origens_gerenciar(),parse_mode="md")
    elif acao=="d_add":
        ids=parse_ids(txt)
        for i in ids: DESTINOS.add(int(i))
        await ev.respond(f"âž• Destino(s) adicionado(s): `{ids}`\nðŸŽ¯ Destinos: `{DESTINOS}`",buttons=kb_destinos_gerenciar(),parse_mode="md")
    elif acao=="d_rem":
        ids=parse_ids(txt)
        for i in ids: DESTINOS.discard(int(i))
        await ev.respond(f"âž– Removido(s): `{ids}`\nðŸŽ¯ Destinos: `{DESTINOS}`",buttons=kb_destinos_gerenciar(),parse_mode="md")
    elif acao=="f_add_on":
        palavras=[p.lower() for p in txt.split()]
        FILTROS_ON.update(palavras)
        await ev.respond(f"ðŸ” Palavras exigidas: `{FILTROS_ON}`",buttons=kb_filtros(),parse_mode="md")
    elif acao=="f_add_off":
        palavras=[p.lower() for p in txt.split()]
        FILTROS_OFF.update(palavras)
        await ev.respond(f"ðŸš« Palavras bloqueadas: `{FILTROS_OFF}`",buttons=kb_filtros(),parse_mode="md")
    elif acao=="f_rem":
        palavras=[p.lower() for p in txt.split()]
        for p in palavras: FILTROS_ON.discard(p);FILTROS_OFF.discard(p)
        await ev.respond(f"ðŸ—‘ Removido.\nON:`{FILTROS_ON}` | OFF:`{FILTROS_OFF}`",buttons=kb_filtros(),parse_mode="md")
    elif acao=="mg_prefix":
        PREFIXO=txt
        await ev.respond(f"âœï¸ Prefixo: `{PREFIXO}`",buttons=kb_msg(),parse_mode="md")
    elif acao=="mg_suffix":
        RODAPE=txt
        await ev.respond(f"ðŸ“ RodapÃ©: `{RODAPE}`",buttons=kb_msg(),parse_mode="md")
    elif acao=="mo_delay":
        if txt.isdigit(): DELAY=int(txt);await ev.respond(f"â± Delay: `{DELAY}s`",buttons=kb_modo(),parse_mode="md")
        else: await ev.respond("âŒ Digite apenas nÃºmeros",buttons=kb_modo())
    elif acao=="ag_set":
        try:
            partes=txt.split()
            AGENDAMENTO["inicio"]=partes[0];AGENDAMENTO["fim"]=partes[1]
            await ev.respond(f"â° HorÃ¡rio: `{AGENDAMENTO['inicio']} â€“ {AGENDAMENTO['fim']}`",buttons=kb_agenda(),parse_mode="md")
        except: await ev.respond("âŒ Formato: `HH:MM HH:MM`  ex: `08:00 22:00`",buttons=kb_agenda(),parse_mode="md")

# â”€â”€ HELPER: monta lista de chats como botÃµes inline â”€â”€â”€â”€â”€â”€
async def enviar_lista_chats(ev, tipo, contexto):
    """
    contexto: 'src' (origem) ou 'dst' (destino)
    tipo: user|premium|bot|group|channel|forum|mygroup|mychannel|myforum
    """
    TIPO_LABEL={
        "user":"ðŸ‘¤ Users","premium":"â­ Premium","bot":"ðŸ¤– Bots",
        "group":"ðŸ‘¥ Groups","channel":"ðŸ“¢ Channels","forum":"ðŸ’¬ Forums",
        "mygroup":"ðŸ‘¥ My Groups","mychannel":"ðŸ“¢ My Channels","myforum":"ðŸ’¬ My Forums"
    }
    await ev.answer("â³ Buscando...",alert=False)

    # Invalida cache para buscar fresco
    global _dialogs_ts
    _dialogs_ts=0
    dialogs=await get_dialogs_cached()
    lista=dialogs.get(tipo,[])

    # Grupos/Channels/Forums externos sem "my" â†’ filtra sÃ³ os que NÃƒO sÃ£o do userbot
    # My* â†’ todos onde o userbot Ã© membro/admin
    if not lista:
        back_data=f"o_addtipo" if contexto=="src" else "d_addtipo"
        await ev.edit(
            f"ðŸ˜• Nenhum *{TIPO_LABEL.get(tipo,tipo)}* encontrado.",
            buttons=[[Button.inline("â¬…ï¸ Voltar",back_data.encode())]],
            parse_mode="md"
        )
        return

    # Monta botÃµes: cada item = 1 botÃ£o com nome + clique adiciona
    # Marca os jÃ¡ configurados
    conjunto=SRC if contexto=="src" else DESTINOS
    botoes=[]
    for item in lista[:48]:  # mÃ¡x 48 para caber no Telegram
        cid=item["id"]
        nome=item["name"][:28]
        ja=("âœ… " if cid in conjunto else "")
        cb=f"add|{contexto}|{cid}|{tipo}".encode()
        botoes.append(Button.inline(f"{ja}{nome}",cb))

    linhas=list(chunks(botoes,2))
    back_data=b"o_addtipo" if contexto=="src" else b"d_addtipo"
    linhas.append([Button.inline("â¬…ï¸ Voltar",back_data)])

    label="origem" if contexto=="src" else "destino"
    await ev.edit(
        f"*{TIPO_LABEL.get(tipo,tipo)}* â€” toque para adicionar como {label}:\n"
        f"_(âœ… = jÃ¡ configurado)_",
        buttons=linhas,
        parse_mode="md"
    )

# â”€â”€ CALLBACKS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@bot.on(events.CallbackQuery)
async def callback(ev):
    global PAUSADO,MOD,SEM_BOTS,AGENDAMENTO,PREFIXO,RODAPE,MODO_SILENCIOSO
    if not is_admin(ev.sender_id):
        await ev.answer("â›” Sem permissÃ£o!",alert=True); return
    d=ev.data; uid=ev.sender_id

    # â”€â”€ ADD direto pelo lista de chats â”€â”€
    if d.startswith(b"add|"):
        partes=d.decode().split("|")
        # add|contexto|chat_id|tipo
        contexto=partes[1]; cid=int(partes[2]); tipo=partes[3]
        conjunto=SRC if contexto=="src" else DESTINOS
        label="origem" if contexto=="src" else "destino"
        if cid in conjunto:
            conjunto.discard(cid)
            await ev.answer(f"âž– Removido dos {label}s!",alert=False)
        else:
            conjunto.add(cid)
            await ev.answer(f"âœ… Adicionado como {label}!",alert=False)
        # Recarrega a lista
        await enviar_lista_chats(ev,tipo,contexto)
        return

    # â”€â”€ Selecionar tipo para origens/destinos â”€â”€
    if b"|" in d and not d.startswith(b"disc") and not d.startswith(b"add"):
        partes=d.decode().split("|")
        if len(partes)==2:
            contexto=partes[0]; tipo=partes[1]
            if contexto in ("src","dst"):
                if tipo=="manual":
                    acao="o_add" if contexto=="src" else "d_add"
                    AGUARDANDO[uid]=acao
                    label="origem(ns)" if contexto=="src" else "destino(s)"
                    await ev.answer(f"Digite o(s) ID(s) de {label}.\nEx: -1001234567890",alert=True)
                else:
                    await enviar_lista_chats(ev,tipo,contexto)
                return

    # â”€â”€ Discover menu â”€â”€
    if d.startswith(b"disc|"):
        tipo=d.decode().split("|")[1]
        await ev.answer("â³ Buscando...",alert=False)
        global _dialogs_ts
        _dialogs_ts=0
        dialogs=await get_dialogs_cached()
        lista=dialogs.get(tipo,[])
        TIPO_LABEL={
            "user":"ðŸ‘¤ Users","premium":"â­ Premium","bot":"ðŸ¤– Bots",
            "group":"ðŸ‘¥ Groups","channel":"ðŸ“¢ Channels","forum":"ðŸ’¬ Forums",
            "mygroup":"ðŸ‘¥ My Groups","mychannel":"ðŸ“¢ My Channels","myforum":"ðŸ’¬ My Forums"
        }
        if not lista:
            await ev.edit(f"ðŸ˜• Nenhum *{TIPO_LABEL.get(tipo,tipo)}* encontrado.\nEncaminhe uma mensagem ou envie @username para descobrir o ID.",
                buttons=[[Button.inline("â¬…ï¸ Voltar",b"disc_menu")]],parse_mode="md")
            AGUARDANDO[uid]="disc_input"
            return

        botoes=[]
        for item in lista[:48]:
            nome=item["name"][:30]
            cid=item["id"]
            cb=f"disc_show|{cid}".encode()
            botoes.append(Button.inline(nome,cb))
        linhas=list(chunks(botoes,2))
        linhas.append([Button.inline("ðŸ”Ž Buscar por @username",b"disc_manual"),Button.inline("â¬…ï¸ Voltar",b"disc_menu")])
        await ev.edit(f"*{TIPO_LABEL.get(tipo,tipo)}* â€” toque para ver o ID:",
            buttons=linhas,parse_mode="md")
        return

    if d.startswith(b"disc_show|"):
        cid=d.decode().split("|")[1]
        await ev.answer(f"ðŸ†” ID: {cid}",alert=True)
        return

    if d==b"disc_manual":
        AGUARDANDO[uid]="disc_input"
        await ev.answer("Encaminhe uma mensagem ou envie @username:",alert=True)
        return

    if d==b"disc_menu":
        await ev.edit("ðŸ”Ž *Descobrir ID â€” Selecione o tipo:*",buttons=kb_discover_menu(),parse_mode="md")
        return

    # â”€â”€ NavegaÃ§Ã£o principal â”€â”€
    if d==b"m_back": await ev.edit(f"ðŸŽ› *{BOT_NOME} â€” Painel*",buttons=kb_principal(),parse_mode="md")
    elif d==b"m_origens": await ev.edit("ðŸ“¡ *Gerenciar Origens*",buttons=kb_origens_gerenciar(),parse_mode="md")
    elif d==b"m_destinos": await ev.edit(f"ðŸŽ¯ *Destinos* ({len(DESTINOS)} configurado(s))",buttons=kb_destinos_gerenciar(),parse_mode="md")
    elif d==b"o_addtipo": await ev.edit("ðŸ“¡ *Adicionar Origem â€” Selecione o tipo:*",buttons=kb_select_tipo("src"),parse_mode="md")
    elif d==b"d_addtipo": await ev.edit("ðŸŽ¯ *Adicionar Destino â€” Selecione o tipo:*",buttons=kb_select_tipo("dst"),parse_mode="md")
    elif d==b"m_modo": await ev.edit("ðŸ”€ *Modo de Encaminhamento*",buttons=kb_modo(),parse_mode="md")
    elif d==b"m_filtros": await ev.edit("ðŸ” *Filtros de Mensagem*",buttons=kb_filtros(),parse_mode="md")
    elif d==b"m_agenda": await ev.edit(f"â° *Agendamento* {'âœ…' if AGENDAMENTO['ativo'] else 'âŒ'}\n{AGENDAMENTO['inicio']}â€“{AGENDAMENTO['fim']}",buttons=kb_agenda(),parse_mode="md")
    elif d==b"m_msg": await ev.edit("âœï¸ *Personalizar Mensagens*",buttons=kb_msg(),parse_mode="md")
    elif d==b"m_info": await ev.edit("â„¹ï¸ *InformaÃ§Ãµes*",buttons=kb_info(),parse_mode="md")
    elif d==b"m_hist":
        if not HISTORICO: await ev.edit("ðŸ“œ Nenhuma mensagem ainda.",buttons=[[Button.inline("â¬…ï¸ Voltar",b"m_back")]])
        else:
            t="ðŸ“œ *Ãšltimas mensagens:*\n"+"".join(f"`{h['time']}` {h['chat']}\n" for h in HISTORICO[-15:])
            await ev.edit(t,buttons=[[Button.inline("â¬…ï¸ Voltar",b"m_back")]],parse_mode="md")
    elif d==b"m_status": await ev.edit(status_texto(),buttons=[[Button.inline("ðŸ”„ Atualizar",b"m_status"),Button.inline("â¬…ï¸ Voltar",b"m_back")]],parse_mode="md")
    elif d==b"m_fechar": await ev.delete()
    elif d==b"m_toggle":
        PAUSADO=not PAUSADO
        await ev.edit(f"ðŸŽ› *{BOT_NOME} â€” Painel*",buttons=kb_principal(),parse_mode="md")
        await ev.answer("â¸ PAUSADO!" if PAUSADO else "â–¶ï¸ RETOMADO!",alert=True)
    elif d==b"m_silencioso":
        MODO_SILENCIOSO=not MODO_SILENCIOSO
        await ev.edit(f"ðŸŽ› *{BOT_NOME} â€” Painel*",buttons=kb_principal(),parse_mode="md")
        await ev.answer("ðŸ”• Modo silencioso ON" if MODO_SILENCIOSO else "ðŸ”” Modo normal ON",alert=True)
    # Origens
    elif d==b"o_rem": AGUARDANDO[uid]="o_rem";await ev.answer(f"Origens: {SRC or 'todos'}\nDigite IDs para remover:",alert=True)
    elif d==b"o_ign": AGUARDANDO[uid]="o_ign";await ev.answer("Digite IDs para ignorar:",alert=True)
    elif d==b"o_des": AGUARDANDO[uid]="o_des";await ev.answer(f"Ignorados: {IGNORADOS}\nDigite IDs para designorar:",alert=True)
    elif d==b"o_list":
        t=("ðŸ“¡ Origens:\n"+"".join(f"â€¢ `{s}`\n" for s in SRC)) if SRC else "ðŸ“¡ Monitorando TODOS"
        t+="\n\nðŸš« Ignorados:\n"+("".join(f"â€¢ `{s}`\n" for s in IGNORADOS) if IGNORADOS else "nenhum")
        await ev.answer(t,alert=True)
    elif d==b"o_clear": SRC.clear();await ev.answer("ðŸ—‘ Origens limpas!",alert=True)
    # Destinos
    elif d==b"d_rem": AGUARDANDO[uid]="d_rem";await ev.answer(f"Destinos: {DESTINOS}\nDigite IDs para remover:",alert=True)
    elif d==b"d_list":
        t=("ðŸŽ¯ Destinos:\n"+"".join(f"â€¢ `{s}`\n" for s in DESTINOS)) if DESTINOS else "âš ï¸ Nenhum destino!"
        await ev.answer(t,alert=True)
    elif d==b"d_clear": DESTINOS.clear();await ev.answer("ðŸ—‘ Destinos removidos!",alert=True)
    # Modo
    elif d==b"mo_fwd": MOD="forward";await ev.edit("ðŸ”€ *Modo*",buttons=kb_modo(),parse_mode="md");await ev.answer("ðŸ“¨ Modo: forward",alert=True)
    elif d==b"mo_copy": MOD="copy";await ev.edit("ðŸ”€ *Modo*",buttons=kb_modo(),parse_mode="md");await ev.answer("ðŸ“‹ Modo: copy",alert=True)
    elif d==b"mo_bots": SEM_BOTS=not SEM_BOTS;await ev.edit("ðŸ”€ *Modo*",buttons=kb_modo(),parse_mode="md");await ev.answer(f"ðŸ¤– Ignorar bots: {'âœ… ON' if SEM_BOTS else 'âŒ OFF'}",alert=True)
    elif d==b"mo_delay": AGUARDANDO[uid]="mo_delay";await ev.answer(f"Delay atual: {DELAY}s\nDigite em segundos (0=sem delay):",alert=True)
    elif d==b"mo_tipos": await ev.edit("ðŸ“ *Tipos de mÃ­dia*\nNenhum = encaminha tudo",buttons=kb_tipos(),parse_mode="md")
    elif d==b"mo_tipos_back": await ev.edit("ðŸ”€ *Modo*",buttons=kb_modo(),parse_mode="md")
    elif d==b"tp_clear": SOMENTE_TIPOS.clear();await ev.edit("ðŸ“ *Tipos* â€” Todos liberados",buttons=kb_tipos(),parse_mode="md")
    elif d.startswith(b"tp_"):
        t=d.decode().replace("tp_","")
        if t in SOMENTE_TIPOS: SOMENTE_TIPOS.discard(t)
        else: SOMENTE_TIPOS.add(t)
        await ev.edit("ðŸ“ *Tipos de mÃ­dia*",buttons=kb_tipos(),parse_mode="md")
    # Filtros
    elif d==b"f_add_on": AGUARDANDO[uid]="f_add_on";await ev.answer("Palavras EXIGIDAS (espaÃ§o entre elas):",alert=True)
    elif d==b"f_add_off": AGUARDANDO[uid]="f_add_off";await ev.answer("Palavras BLOQUEADAS (espaÃ§o entre elas):",alert=True)
    elif d==b"f_rem": AGUARDANDO[uid]="f_rem";await ev.answer(f"ON:{FILTROS_ON}\nOFF:{FILTROS_OFF}\nPalavras para remover:",alert=True)
    elif d==b"f_list": await ev.answer(f"ðŸ” Exigidas: {FILTROS_ON or 'nenhuma'}\nðŸš« Bloqueadas: {FILTROS_OFF or 'nenhuma'}",alert=True)
    elif d==b"f_clear": FILTROS_ON.clear();FILTROS_OFF.clear();await ev.answer("ðŸ—‘ Filtros removidos!",alert=True)
    # Agenda
    elif d==b"ag_toggle": AGENDAMENTO["ativo"]=not AGENDAMENTO["ativo"];await ev.edit(f"â° *Agendamento* {'âœ…' if AGENDAMENTO['ativo'] else 'âŒ'}",buttons=kb_agenda(),parse_mode="md");await ev.answer(f"Agendamento {'ativado' if AGENDAMENTO['ativo'] else 'desativado'}!",alert=True)
    elif d==b"ag_set": AGUARDANDO[uid]="ag_set";await ev.answer("HorÃ¡rio inÃ­cio e fim:\nEx: 08:00 22:00",alert=True)
    elif d==b"ag_ver": await ev.answer(f"{'âœ… Ativo' if AGENDAMENTO['ativo'] else 'âŒ Inativo'}\nInÃ­cio: {AGENDAMENTO['inicio']}\nFim: {AGENDAMENTO['fim']}",alert=True)
    # Mensagem
    elif d==b"mg_prefix": AGUARDANDO[uid]="mg_prefix";await ev.answer(f"Prefixo atual: {PREFIXO or 'nenhum'}\nNovo prefixo:",alert=True)
    elif d==b"mg_suffix": AGUARDANDO[uid]="mg_suffix";await ev.answer(f"RodapÃ© atual: {RODAPE or 'nenhum'}\nNovo rodapÃ©:",alert=True)
    elif d==b"mg_rmpre": PREFIXO="";await ev.answer("âœ… Prefixo removido!",alert=True)
    elif d==b"mg_rmsuf": RODAPE="";await ev.answer("âœ… RodapÃ© removido!",alert=True)
    elif d==b"mg_ver": await ev.answer(f"âœï¸ Prefixo: {PREFIXO or 'nenhum'}\nðŸ“ RodapÃ©: {RODAPE or 'nenhum'}",alert=True)
    # Info
    elif d==b"i_ping":
        up=datetime.now()-stats["start"];h2,r=divmod(int(up.total_seconds()),3600);mi,s=divmod(r,60)
        await ev.answer(f"ðŸ“ Pong!\nUptime: {h2}h{mi}m{s}s",alert=True)
    elif d==b"i_id": await ev.answer(f"ðŸ†” ID deste chat: {ev.chat_id}",alert=True)
    elif d==b"i_stats":
        horas=dict(sorted(stats["por_hora"].items())[-8:])
        t="ðŸ“Š Por hora:\n"+"".join(f"  {h2:02d}h: {n}\n" for h2,n in horas.items())
        t+=f"\nTotal: {stats['n']} | Erros: {stats['err']}"
        await ev.answer(t,alert=True)
    elif d==b"i_reset": stats["n"]=0;stats["err"]=0;stats["por_hora"].clear();stats["start"]=datetime.now();await ev.answer("ðŸ”„ Stats zeradas!",alert=True)
    elif d==b"i_teste":
        if not DESTINOS: await ev.answer("âš ï¸ Nenhum destino!",alert=True);return
        ok=0
        for dst in DESTINOS:
            try: await bot.send_message(dst,f"ðŸ§ª *{BOT_NOME} â€” Teste* âœ…\n{datetime.now().strftime('%d/%m %H:%M')}",parse_mode="md");ok+=1
            except Exception as e: logger.error(f"Teste falhou em {dst}: {e}")
        await ev.answer(f"ðŸ“¤ Teste enviado para {ok}/{len(DESTINOS)} destino(s)!",alert=True)

# â”€â”€ HELPERS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

# â”€â”€ ENCAMINHADOR â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
                logger.info(f"[{BOT_NOME}] #{stats['n']} de '{name}' â†’ {ok} destino(s)")

    except Exception as e: stats["err"]+=1;logger.error(f"Erro geral: {e}")

# â”€â”€ MAIN â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
async def main():
    await userbot.start()
    await bot.start(bot_token=BOT_TOKEN)
    me=await userbot.get_me()
    bme=await bot.get_me()
    logger.info(f"âœ… [{BOT_NOME}] Userbot: {me.first_name} | Bot: @{bme.username}")
    logger.info(f"   Destinos={DESTINOS} | Origens={SRC or 'todos'} | Modo={MOD}")
    await asyncio.gather(userbot.run_until_disconnected(),bot.run_until_disconnected())

asyncio.run(main())