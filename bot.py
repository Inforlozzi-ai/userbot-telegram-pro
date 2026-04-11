import os,logging,asyncio,re
from telethon import TelegramClient,events,Button
from telethon.sessions import StringSession
from telethon.tl.types import Channel,Chat,User
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

_dialogs_cache={}
_dialogs_ts=0
DIALOGS_TTL=180

userbot=TelegramClient(StringSession(SESSION),API_ID,API_HASH)
bot=TelegramClient(StringSession(""),API_ID,API_HASH)

def is_admin(uid):
    return not ADMIN_IDS or uid in ADMIN_IDS

# â”€â”€â”€ CACHE DE DIALOGS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
async def get_dialogs():
    global _dialogs_cache,_dialogs_ts
    agora=asyncio.get_event_loop().time()
    if _dialogs_cache and (agora-_dialogs_ts)<DIALOGS_TTL:
        return _dialogs_cache
    dialogs={}
    async for d in userbot.iter_dialogs():
        e=d.entity
        if isinstance(e,Channel):
            if getattr(e,"forum",False): cat="myforum"
            elif e.megagroup: cat="mygroup"
            elif e.broadcast: cat="mychannel"
            else: cat="mygroup"
        elif isinstance(e,Chat): cat="mygroup"
        elif isinstance(e,User):
            if e.bot: cat="bot"
            elif getattr(e,"premium",False): cat="premium"
            else: cat="user"
        else: continue
        dialogs.setdefault(cat,[]).append({
            "id":d.id,
            "name":(d.name or getattr(e,"first_name","?"))[:35],
            "username":getattr(e,"username",None)
        })
    _dialogs_cache=dialogs; _dialogs_ts=agora
    return dialogs

def tipo_icon(cat):
    m={"user":"Usr","premium":"VIP","bot":"Bot","mygroup":"Grp","mychannel":"Chn","myforum":"Frm"}
    return m.get(cat,"?")

# â”€â”€â”€ TECLADOS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def kb_principal():
    estado="|| PAUSAR" if not PAUSADO else ">> RETOMAR"
    sil="SILENC. ON" if not MODO_SILENCIOSO else "SILENC. OFF"
    return [
        [Button.inline("[ ORIGENS ]",  b"m_origens"),
         Button.inline("[ DESTINOS ]", b"m_destinos"),
         Button.inline("[ MODO ]",     b"m_modo")],
        [Button.inline("[ FILTROS ]",  b"m_filtros"),
         Button.inline("[ HORARIO ]",  b"m_agenda"),
         Button.inline("[ MENSAGEM ]", b"m_msg")],
        [Button.inline("[ STATUS ]",   b"m_status"),
         Button.inline("[ HIST. ]",    b"m_hist"),
         Button.inline("[ INFO ]",     b"m_info")],
        [Button.inline("[ DESCOBRIR ID ]", b"disc_menu")],
        [Button.inline(estado,         b"m_toggle"),
         Button.inline(sil,            b"m_silencioso"),
         Button.inline("[ FECHAR ]",   b"m_fechar")],
    ]

def kb_tipo_selector(ctx):
    c=ctx.encode()
    return [
        [Button.inline("User",    c+b"|user"),
         Button.inline("Premium", c+b"|premium"),
         Button.inline("Bot",     c+b"|bot")],
        [Button.inline("Group",   c+b"|mygroup"),
         Button.inline("Channel", c+b"|mychannel"),
         Button.inline("Forum",   c+b"|myforum")],
        [Button.inline("-- Digitar ID manualmente --", c+b"|manual")],
        [Button.inline("<< Voltar", b"m_origens" if ctx=="src" else (b"m_destinos" if ctx=="dst" else b"disc_menu"))],
    ]

def kb_lista_chats(items,ctx,cat,pagina=0,por_pagina=8):
    inicio=pagina*por_pagina
    pagina_items=items[inicio:inicio+por_pagina]
    linhas=[]
    for item in pagina_items:
        label=f"{item['name']}"
        dado=f"{ctx}|sel|{item['id']}|{cat}".encode()
        linhas.append([Button.inline(label[:48],dado)])
    nav=[]
    if pagina>0:
        nav.append(Button.inline("<< Anterior",f"{ctx}|pg|{cat}|{pagina-1}".encode()))
    if inicio+por_pagina<len(items):
        nav.append(Button.inline("Proxima >>",f"{ctx}|pg|{cat}|{pagina+1}".encode()))
    if nav: linhas.append(nav)
    linhas.append([Button.inline("-- Manual --",f"{ctx}|manual".encode()),
                   Button.inline("<< Voltar",f"{ctx}|back".encode())])
    return linhas

def kb_origens():
    return [
        [Button.inline("+ Adicionar origem",  b"src|tipo"),
         Button.inline("- Remover origem",    b"src|remtipo")],
        [Button.inline("x Ignorar chat",      b"src|igntipo"),
         Button.inline("v Designorar",        b"o_des")],
        [Button.inline("= Ver origens ativas",b"o_list"),
         Button.inline("~ Limpar tudo",       b"o_clear")],
        [Button.inline("<< Voltar",           b"m_back")],
    ]

def kb_destinos():
    return [
        [Button.inline("+ Adicionar destino",  b"dst|tipo"),
         Button.inline("- Remover destino",    b"dst|remtipo")],
        [Button.inline("= Ver destinos ativos",b"d_list"),
         Button.inline("~ Limpar destinos",    b"d_clear")],
        [Button.inline("<< Voltar",            b"m_back")],
    ]

def kb_modo():
    return [
        [Button.inline(">> Forward (mostra origem)", b"mo_fwd"),
         Button.inline(">> Copy (sem origem)",       b"mo_copy")],
        [Button.inline("Bot OFF: "+"SIM" if SEM_BOTS else "Bot OFF: NAO", b"mo_bots")],
        [Button.inline("Delay entre envios", b"mo_delay"),
         Button.inline("Tipos de midia",     b"mo_tipos")],
        [Button.inline("<< Voltar", b"m_back")],
    ]

def kb_filtros():
    return [
        [Button.inline("+ Exigir palavra",   b"f_add_on"),
         Button.inline("x Bloquear palavra", b"f_add_off")],
        [Button.inline("- Remover filtro",   b"f_rem"),
         Button.inline("= Ver filtros",      b"f_list")],
        [Button.inline("~ Limpar filtros",   b"f_clear"),
         Button.inline("<< Voltar",          b"m_back")],
    ]

def kb_agenda():
    ativo="ATIVO" if AGENDAMENTO["ativo"] else "INATIVO"
    return [
        [Button.inline("Definir horario",    b"ag_set"),
         Button.inline(f"Agendamento: {ativo}", b"ag_toggle")],
        [Button.inline("Ver configuracao",   b"ag_ver"),
         Button.inline("<< Voltar",          b"m_back")],
    ]

def kb_msg():
    return [
        [Button.inline("Definir prefixo",    b"mg_prefix"),
         Button.inline("Definir rodape",     b"mg_suffix")],
        [Button.inline("Remover prefixo",    b"mg_rmpre"),
         Button.inline("Remover rodape",     b"mg_rmsuf")],
        [Button.inline("Ver configuracao",   b"mg_ver"),
         Button.inline("<< Voltar",          b"m_back")],
    ]

def kb_tipos():
    tipos=["texto","foto","video","audio","doc","sticker"]
    linhas=[]
    for i in range(0,len(tipos),3):
        linha=[]
        for t in tipos[i:i+3]:
            ativo="[x]" if t in SOMENTE_TIPOS else "[ ]"
            linha.append(Button.inline(f"{ativo} {t}",f"tp_{t}".encode()))
        linhas.append(linha)
    linhas.append([Button.inline("~ Todos (sem filtro)",b"tp_clear"),
                   Button.inline("<< Voltar",           b"mo_tipos_back")])
    return linhas

def kb_info():
    return [
        [Button.inline("Ping",           b"i_ping"),
         Button.inline("ID deste chat",  b"i_id")],
        [Button.inline("Estatisticas",   b"i_stats"),
         Button.inline("Zerar stats",    b"i_reset")],
        [Button.inline("Testar destinos",b"i_teste"),
         Button.inline("<< Voltar",      b"m_back")],
    ]

def status_texto():
    up=datetime.now()-stats["start"]; h,r=divmod(int(up.total_seconds()),3600); mi,s=divmod(r,60)
    agenda_txt=f"{AGENDAMENTO['inicio']} ate {AGENDAMENTO['fim']}" if AGENDAMENTO["ativo"] else "desativado"
    tipos_txt=", ".join(SOMENTE_TIPOS) if SOMENTE_TIPOS else "todos"
    estado="PAUSADO" if PAUSADO else "ATIVO"
    silenc="ON" if MODO_SILENCIOSO else "OFF"
    return (
        f"*{BOT_NOME} -- STATUS*
"
        f"{'='*22}
"
        f"Estado   : {estado}
"
        f"Silenc.  : {silenc}
"
        f"Modo     : {MOD}{'  |sem bots' if SEM_BOTS else ''}
"
        f"Delay    : {DELAY}s
"
        f"{'='*22}
"
        f"Destinos ({len(DESTINOS)}): {DESTINOS or 'nenhum'}
"
        f"Origens  ({len(SRC)}): {SRC or 'todos'}
"
        f"Ignorados: {IGNORADOS or 'nenhum'}
"
        f"{'='*22}
"
        f"Filtros +: {FILTROS_ON or 'nenhum'}
"
        f"Filtros -: {FILTROS_OFF or 'nenhum'}
"
        f"Tipos    : {tipos_txt}
"
        f"Horario  : {agenda_txt}
"
        f"{'='*22}
"
        f"Prefixo  : {PREFIXO or 'nenhum'}
"
        f"Rodape   : {RODAPE or 'nenhum'}
"
        f"{'='*22}
"
        f"Enviadas : {stats['n']}  |  Erros: {stats['err']}
"
        f"Uptime   : {h}h {mi}m {s}s"
    )

# â”€â”€â”€ COMANDOS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@bot.on(events.NewMessage(pattern=r"^/menu$"))
async def cmd_menu(ev):
    if not is_admin(ev.sender_id): return
    await ev.respond(
        f"*{BOT_NOME} -- Painel de Controle*
"
        f"{'='*24}
"
        f"Destinos: {len(DESTINOS)}  |  Origens: {len(SRC) or 'todos'}
"
        f"Estado: {'PAUSADO' if PAUSADO else 'ATIVO'}  |  Modo: {MOD}",
        buttons=kb_principal(),parse_mode="md")

@bot.on(events.NewMessage(pattern=r"^/status$"))
async def cmd_status(ev):
    if not is_admin(ev.sender_id): return
    await ev.respond(status_texto(),parse_mode="md")

@bot.on(events.NewMessage(pattern=r"^/start$"))
async def cmd_start(ev):
    await ev.respond(f"Ola! Sou o *{BOT_NOME}*.
Digite /menu para abrir o painel.",parse_mode="md")

@bot.on(events.NewMessage(pattern=r"^/pausar$"))
async def cmd_pausar(ev):
    global PAUSADO
    if not is_admin(ev.sender_id): return
    PAUSADO=True; await ev.respond("PAUSADO.")

@bot.on(events.NewMessage(pattern=r"^/retomar$"))
async def cmd_retomar(ev):
    global PAUSADO
    if not is_admin(ev.sender_id): return
    PAUSADO=False; await ev.respond("RETOMADO.")

@bot.on(events.NewMessage(pattern=r"^/stats$"))
async def cmd_stats(ev):
    if not is_admin(ev.sender_id): return
    horas=dict(sorted(stats["por_hora"].items()))
    t="*Envios por hora:*
"
    t+="".join(f"  {h:02d}h: {'|'*min(n,20)} {n}
" for h,n in horas.items())
    t+=f"
Total: {stats['n']}  |  Erros: {stats['err']}"
    await ev.respond(t,parse_mode="md")

# â”€â”€â”€ ENTRADA DE TEXTO â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@bot.on(events.NewMessage())
async def entrada_usuario(ev):
    global PAUSADO,MOD,PREFIXO,RODAPE,DELAY,SEM_BOTS,AGENDAMENTO
    uid=ev.sender_id
    if not is_admin(uid): return
    if uid not in AGUARDANDO: return
    acao=AGUARDANDO.pop(uid)
    txt=ev.raw_text.strip()

    def parse_ids(t): return [x.strip() for x in re.split(r"[,; ]+",t) if x.strip().lstrip("-").isdigit()]

    if acao=="src|manual":
        ids=parse_ids(txt)
        if not ids: await ev.respond("ID invalido."); return
        for i in ids: SRC.add(int(i))
        await ev.respond(f"Origens adicionadas: {ids}
Ativas: {SRC or 'todos'}",buttons=kb_origens(),parse_mode="md")
    elif acao=="src|manual_rem":
        ids=parse_ids(txt)
        for i in ids: SRC.discard(int(i))
        await ev.respond(f"Removidas: {ids}
Ativas: {SRC or 'todos'}",buttons=kb_origens(),parse_mode="md")
    elif acao=="src|manual_ign":
        ids=parse_ids(txt)
        for i in ids: IGNORADOS.add(int(i))
        await ev.respond(f"Ignorando: {ids}",buttons=kb_origens(),parse_mode="md")
    elif acao=="dst|manual":
        ids=parse_ids(txt)
        if not ids: await ev.respond("ID invalido."); return
        for i in ids: DESTINOS.add(int(i))
        await ev.respond(f"Destinos adicionados: {ids}
Ativos: {DESTINOS}",buttons=kb_destinos(),parse_mode="md")
    elif acao=="dst|manual_rem":
        ids=parse_ids(txt)
        for i in ids: DESTINOS.discard(int(i))
        await ev.respond(f"Removidos: {ids}
Ativos: {DESTINOS}",buttons=kb_destinos(),parse_mode="md")
    elif acao=="disc_manual":
        try:
            entity=await userbot.get_entity(txt)
            eid=getattr(entity,"id",None)
            nome=getattr(entity,"title",None) or getattr(entity,"first_name","?")
            uname=getattr(entity,"username",None)
            tipo="Canal" if isinstance(entity,Channel) and entity.broadcast else                  "Grupo" if isinstance(entity,(Channel,Chat)) else                  "Bot" if isinstance(entity,User) and entity.bot else "Usuario"
            resp=f"*Resultado:*
{'='*16}
Tipo: {tipo}
Nome: {nome}
ID: `{eid}`"
            if uname: resp+=f"
Username: @{uname}"
            await ev.respond(resp,parse_mode="md",
                buttons=[[Button.inline("Descobrir outro",b"disc_menu"),Button.inline("<< Menu",b"m_back")]])
        except Exception as e:
            await ev.respond(f"Nao encontrado: {e}
Digite /menu para voltar.")
    elif acao=="o_des":
        ids=parse_ids(txt)
        for i in ids: IGNORADOS.discard(int(i))
        await ev.respond(f"Designorado(s): {ids}",buttons=kb_origens(),parse_mode="md")
    elif acao=="f_add_on":
        p=[x.lower() for x in txt.split()]
        FILTROS_ON.update(p)
        await ev.respond(f"Exigidas: {FILTROS_ON}",buttons=kb_filtros(),parse_mode="md")
    elif acao=="f_add_off":
        p=[x.lower() for x in txt.split()]
        FILTROS_OFF.update(p)
        await ev.respond(f"Bloqueadas: {FILTROS_OFF}",buttons=kb_filtros(),parse_mode="md")
    elif acao=="f_rem":
        p=[x.lower() for x in txt.split()]
        for x in p: FILTROS_ON.discard(x);FILTROS_OFF.discard(x)
        await ev.respond(f"Removido.
+:{FILTROS_ON} | -:{FILTROS_OFF}",buttons=kb_filtros(),parse_mode="md")
    elif acao=="mg_prefix": PREFIXO=txt; await ev.respond(f"Prefixo: `{PREFIXO}`",buttons=kb_msg(),parse_mode="md")
    elif acao=="mg_suffix": RODAPE=txt; await ev.respond(f"Rodape: `{RODAPE}`",buttons=kb_msg(),parse_mode="md")
    elif acao=="mo_delay":
        if txt.isdigit(): DELAY=int(txt); await ev.respond(f"Delay: {DELAY}s",buttons=kb_modo(),parse_mode="md")
        else: await ev.respond("Digite apenas numeros.",buttons=kb_modo())
    elif acao=="ag_set":
        try:
            p=txt.split(); AGENDAMENTO["inicio"]=p[0]; AGENDAMENTO["fim"]=p[1]
            await ev.respond(f"Horario: {AGENDAMENTO['inicio']} ate {AGENDAMENTO['fim']}",buttons=kb_agenda(),parse_mode="md")
        except: await ev.respond("Formato: HH:MM HH:MM  ex: 08:00 22:00",buttons=kb_agenda())

# â”€â”€â”€ CALLBACKS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@bot.on(events.CallbackQuery)
async def callback(ev):
    global PAUSADO,MOD,SEM_BOTS,AGENDAMENTO,PREFIXO,RODAPE,MODO_SILENCIOSO
    if not is_admin(ev.sender_id):
        await ev.answer("Sem permissao!",alert=True); return
    d=ev.data; uid=ev.sender_id

    def painel_txt():
        return (
            f"*{BOT_NOME} -- Painel de Controle*
"
            f"{'='*24}
"
            f"Destinos: {len(DESTINOS)}  |  Origens: {len(SRC) or 'todos'}
"
            f"Estado: {'PAUSADO' if PAUSADO else 'ATIVO'}  |  Modo: {MOD}"
        )

    # â”€â”€ Principal â”€â”€
    if d==b"m_back":
        await ev.edit(painel_txt(),buttons=kb_principal(),parse_mode="md")
    elif d==b"m_origens":
        src_lista=", ".join(str(x) for x in SRC) if SRC else "todos"
        await ev.edit(
            f"*ORIGENS*
{'='*20}
"
            f"Ativas: {src_lista}
"
            f"Ignorados: {len(IGNORADOS)}
"
            f"{'='*20}",
            buttons=kb_origens(),parse_mode="md")
    elif d==b"m_destinos":
        dst_lista=", ".join(str(x) for x in DESTINOS) if DESTINOS else "nenhum"
        await ev.edit(
            f"*DESTINOS*
{'='*20}
"
            f"Ativos ({len(DESTINOS)}): {dst_lista}
"
            f"{'='*20}",
            buttons=kb_destinos(),parse_mode="md")
    elif d==b"m_modo":
        await ev.edit(
            f"*MODO DE ENCAMINHAMENTO*
{'='*20}
"
            f"Atual: {MOD}
"
            f"Delay: {DELAY}s  |  Sem bots: {'SIM' if SEM_BOTS else 'NAO'}",
            buttons=kb_modo(),parse_mode="md")
    elif d==b"m_filtros":
        await ev.edit(
            f"*FILTROS*
{'='*20}
"
            f"Exigidas (+): {FILTROS_ON or 'nenhuma'}
"
            f"Bloqueadas (-): {FILTROS_OFF or 'nenhuma'}",
            buttons=kb_filtros(),parse_mode="md")
    elif d==b"m_agenda":
        ativo="ATIVO" if AGENDAMENTO["ativo"] else "INATIVO"
        await ev.edit(
            f"*HORARIO*
{'='*20}
"
            f"Estado: {ativo}
"
            f"Janela: {AGENDAMENTO['inicio']} ate {AGENDAMENTO['fim']}",
            buttons=kb_agenda(),parse_mode="md")
    elif d==b"m_msg":
        await ev.edit(
            f"*PERSONALIZAR MENSAGEM*
{'='*20}
"
            f"Prefixo: {PREFIXO or 'nenhum'}
"
            f"Rodape: {RODAPE or 'nenhum'}",
            buttons=kb_msg(),parse_mode="md")
    elif d==b"m_info":
        await ev.edit("*INFO*
"+"="*20,buttons=kb_info(),parse_mode="md")
    elif d==b"m_hist":
        if not HISTORICO:
            await ev.edit("Nenhuma mensagem ainda.",buttons=[[Button.inline("<< Voltar",b"m_back")]])
        else:
            t="*Ultimas mensagens:*
"+"".join(f"{h['time']} -- {h['chat']}
" for h in HISTORICO[-15:])
            await ev.edit(t,buttons=[[Button.inline("<< Voltar",b"m_back")]],parse_mode="md")
    elif d==b"m_status":
        await ev.edit(status_texto(),buttons=[[Button.inline("Atualizar",b"m_status"),Button.inline("<< Voltar",b"m_back")]],parse_mode="md")
    elif d==b"m_fechar": await ev.delete()
    elif d==b"m_toggle":
        PAUSADO=not PAUSADO
        await ev.edit(painel_txt(),buttons=kb_principal(),parse_mode="md")
        await ev.answer("PAUSADO!" if PAUSADO else "RETOMADO!",alert=True)
    elif d==b"m_silencioso":
        MODO_SILENCIOSO=not MODO_SILENCIOSO
        await ev.edit(painel_txt(),buttons=kb_principal(),parse_mode="md")
        await ev.answer("Silencioso ON" if MODO_SILENCIOSO else "Silencioso OFF",alert=True)

    # â”€â”€ Abrir seletor de tipo â”€â”€
    elif d in (b"src|tipo",b"dst|tipo"):
        ctx="src" if d==b"src|tipo" else "dst"
        label="ORIGEM" if ctx=="src" else "DESTINO"
        await ev.edit(f"*ADICIONAR {label}*
{'='*20}
Escolha o tipo de chat:",buttons=kb_tipo_selector(ctx),parse_mode="md")
    elif d in (b"src|remtipo",b"dst|remtipo"):
        ctx="src" if d==b"src|remtipo" else "dst"
        label="ORIGEM" if ctx=="src" else "DESTINO"
        await ev.edit(f"*REMOVER {label}*
{'='*20}
Escolha o tipo:",buttons=kb_tipo_selector(ctx),parse_mode="md")
    elif d==b"src|igntipo":
        await ev.edit("*IGNORAR CHAT*
"+"="*20+"
Escolha o tipo:",buttons=kb_tipo_selector("src_ign"),parse_mode="md")

    # â”€â”€ Paginacao â”€â”€
    elif b"|pg|" in d:
        partes=d.decode().split("|")
        ctx,cat,pagina=partes[0],partes[2],int(partes[3])
        await ev.answer("Carregando...",alert=False)
        dialogs=await get_dialogs()
        items=dialogs.get(cat,[])
        if not items: await ev.answer(f"Nenhum {cat} encontrado.",alert=True); return
        await ev.edit(
            f"*{cat.upper()}* -- {len(items)} encontrado(s)
Selecione:",
            buttons=kb_lista_chats(items,ctx,cat,pagina),parse_mode="md")

    # â”€â”€ Callbacks src/dst dinamicos â”€â”€
    elif b"|" in d and not any(d.startswith(x) for x in [b"disc",b"tp_",b"mo_",b"mg_",b"ag_",b"f_",b"i_",b"o_",b"d_",b"m_"]):
        partes=d.decode().split("|")
        if len(partes)<2: return
        ctx=partes[0]; sub=partes[1]

        if sub=="back":
            if ctx in ("src","src_ign"): await ev.edit("*ORIGENS*",buttons=kb_origens(),parse_mode="md")
            elif ctx=="dst": await ev.edit("*DESTINOS*",buttons=kb_destinos(),parse_mode="md")
            else: await ev.edit("*DESCOBRIR ID*",buttons=[[Button.inline("<< Menu",b"m_back")]],parse_mode="md")
            return

        if sub=="manual":
            if ctx=="src": AGUARDANDO[uid]="src|manual"
            elif ctx=="dst": AGUARDANDO[uid]="dst|manual"
            else: AGUARDANDO[uid]="disc_manual"
            await ev.answer("Digite o @username ou ID:",alert=True); return

        if sub=="sel" and len(partes)>=4:
            chat_id=int(partes[2]); cat=partes[3]
            dialogs=await get_dialogs()
            all_items=[i for its in dialogs.values() for i in its]
            item=next((i for i in all_items if i["id"]==chat_id),None)
            nome=item["name"] if item else str(chat_id)

            if ctx=="src":
                SRC.add(chat_id)
                await ev.edit(
                    f"*ORIGEM ADICIONADA*
{'='*20}
{nome}
ID: `{chat_id}`
"
                    f"{'='*20}
Origens ativas: {len(SRC)}",
                    buttons=[[Button.inline("+ Adicionar outra",b"src|tipo")],
                             [Button.inline("= Ver origens",b"o_list")],
                             [Button.inline("<< Origens",b"m_origens"),Button.inline("Home",b"m_back")]],
                    parse_mode="md")
            elif ctx=="src_rem":
                SRC.discard(chat_id)
                await ev.edit(
                    f"*ORIGEM REMOVIDA*
{'='*20}
{nome}
ID: `{chat_id}`
Restantes: {len(SRC)}",
                    buttons=[[Button.inline("<< Origens",b"m_origens"),Button.inline("Home",b"m_back")]],
                    parse_mode="md")
            elif ctx=="src_ign":
                IGNORADOS.add(chat_id)
                await ev.edit(
                    f"*CHAT IGNORADO*
{'='*20}
{nome}
ID: `{chat_id}`",
                    buttons=[[Button.inline("<< Origens",b"m_origens"),Button.inline("Home",b"m_back")]],
                    parse_mode="md")
            elif ctx=="dst":
                DESTINOS.add(chat_id)
                await ev.edit(
                    f"*DESTINO ADICIONADO*
{'='*20}
{nome}
ID: `{chat_id}`
"
                    f"{'='*20}
Destinos ativos: {len(DESTINOS)}",
                    buttons=[[Button.inline("+ Adicionar outro",b"dst|tipo")],
                             [Button.inline("= Ver destinos",b"d_list")],
                             [Button.inline("<< Destinos",b"m_destinos"),Button.inline("Home",b"m_back")]],
                    parse_mode="md")
            elif ctx=="dst_rem":
                DESTINOS.discard(chat_id)
                await ev.edit(
                    f"*DESTINO REMOVIDO*
{'='*20}
{nome}
ID: `{chat_id}`
Restantes: {len(DESTINOS)}",
                    buttons=[[Button.inline("<< Destinos",b"m_destinos"),Button.inline("Home",b"m_back")]],
                    parse_mode="md")
            return

        # Tipo selecionado -> lista
        cat=sub
        if cat not in ("user","premium","bot","mygroup","mychannel","myforum"): return
        await ev.answer("Carregando...",alert=False)
        dialogs=await get_dialogs()
        items=dialogs.get(cat,[])
        if not items: await ev.answer(f"Nenhum {cat} encontrado.",alert=True); return
        ctxmap={"src":"src","dst":"dst"}
        # remap para src_rem ou dst_rem se vier de remtipo
        await ev.edit(
            f"*{cat.upper()}* -- {len(items)} encontrado(s)
Selecione:",
            buttons=kb_lista_chats(items,ctx,cat,0),parse_mode="md")

    # â”€â”€ Origens â”€â”€
    elif d==b"o_des": AGUARDANDO[uid]="o_des"; await ev.answer(f"Ignorados: {IGNORADOS}
Digite IDs para designorar:",alert=True)
    elif d==b"o_list":
        t=("Origens:
"+"".join(f"  {s}
" for s in SRC)) if SRC else "Monitorando TODOS os grupos"
        t+="

Ignorados:
"+("".join(f"  {s}
" for s in IGNORADOS) if IGNORADOS else "nenhum")
        await ev.answer(t[:200],alert=True)
    elif d==b"o_clear": SRC.clear(); await ev.answer("Origens limpas! Monitorando todos.",alert=True)
    # â”€â”€ Destinos â”€â”€
    elif d==b"d_list":
        t=("Destinos:
"+"".join(f"  {s}
" for s in DESTINOS)) if DESTINOS else "Nenhum destino!"
        await ev.answer(t[:200],alert=True)
    elif d==b"d_clear": DESTINOS.clear(); await ev.answer("Destinos removidos!",alert=True)
    # â”€â”€ Modo â”€â”€
    elif d==b"mo_fwd": MOD="forward"; await ev.edit(f"*MODO*
Atual: forward",buttons=kb_modo(),parse_mode="md"); await ev.answer("Modo: forward",alert=True)
    elif d==b"mo_copy": MOD="copy"; await ev.edit(f"*MODO*
Atual: copy",buttons=kb_modo(),parse_mode="md"); await ev.answer("Modo: copy",alert=True)
    elif d==b"mo_bots":
        SEM_BOTS=not SEM_BOTS
        await ev.edit(f"*MODO*
Sem bots: {'SIM' if SEM_BOTS else 'NAO'}",buttons=kb_modo(),parse_mode="md")
        await ev.answer(f"Bots ignorados: {'SIM' if SEM_BOTS else 'NAO'}",alert=True)
    elif d==b"mo_delay": AGUARDANDO[uid]="mo_delay"; await ev.answer(f"Delay atual: {DELAY}s
Digite em segundos:",alert=True)
    elif d==b"mo_tipos": await ev.edit("*TIPOS DE MIDIA*
[x]=ativo  [ ]=inativo",buttons=kb_tipos(),parse_mode="md")
    elif d==b"mo_tipos_back": await ev.edit("*MODO*",buttons=kb_modo(),parse_mode="md")
    elif d==b"tp_clear": SOMENTE_TIPOS.clear(); await ev.edit("Todos os tipos liberados",buttons=kb_tipos())
    elif d.startswith(b"tp_"):
        t=d.decode().replace("tp_","")
        if t in SOMENTE_TIPOS: SOMENTE_TIPOS.discard(t)
        else: SOMENTE_TIPOS.add(t)
        await ev.edit("*TIPOS DE MIDIA*",buttons=kb_tipos(),parse_mode="md")
    # â”€â”€ Filtros â”€â”€
    elif d==b"f_add_on": AGUARDANDO[uid]="f_add_on"; await ev.answer("Palavras EXIGIDAS (separe por espaco):",alert=True)
    elif d==b"f_add_off": AGUARDANDO[uid]="f_add_off"; await ev.answer("Palavras BLOQUEADAS (separe por espaco):",alert=True)
    elif d==b"f_rem": AGUARDANDO[uid]="f_rem"; await ev.answer(f"+:{FILTROS_ON}
-:{FILTROS_OFF}
Palavras para remover:",alert=True)
    elif d==b"f_list": await ev.answer(f"Exigidas: {FILTROS_ON or 'nenhuma'}
Bloqueadas: {FILTROS_OFF or 'nenhuma'}",alert=True)
    elif d==b"f_clear": FILTROS_ON.clear(); FILTROS_OFF.clear(); await ev.answer("Filtros removidos!",alert=True)
    # â”€â”€ Agenda â”€â”€
    elif d==b"ag_toggle":
        AGENDAMENTO["ativo"]=not AGENDAMENTO["ativo"]
        ativo="ATIVO" if AGENDAMENTO["ativo"] else "INATIVO"
        await ev.edit(f"*HORARIO*
Estado: {ativo}
Janela: {AGENDAMENTO['inicio']} ate {AGENDAMENTO['fim']}",buttons=kb_agenda(),parse_mode="md")
        await ev.answer(f"Agendamento {ativo}!",alert=True)
    elif d==b"ag_set": AGUARDANDO[uid]="ag_set"; await ev.answer("Formato: HH:MM HH:MM
Ex: 08:00 22:00",alert=True)
    elif d==b"ag_ver": await ev.answer(f"{'ATIVO' if AGENDAMENTO['ativo'] else 'INATIVO'}
Inicio: {AGENDAMENTO['inicio']}
Fim: {AGENDAMENTO['fim']}",alert=True)
    # â”€â”€ Mensagem â”€â”€
    elif d==b"mg_prefix": AGUARDANDO[uid]="mg_prefix"; await ev.answer(f"Prefixo atual: {PREFIXO or 'nenhum'}
Novo prefixo:",alert=True)
    elif d==b"mg_suffix": AGUARDANDO[uid]="mg_suffix"; await ev.answer(f"Rodape atual: {RODAPE or 'nenhum'}
Novo rodape:",alert=True)
    elif d==b"mg_rmpre": PREFIXO=""; await ev.answer("Prefixo removido!",alert=True)
    elif d==b"mg_rmsuf": RODAPE=""; await ev.answer("Rodape removido!",alert=True)
    elif d==b"mg_ver": await ev.answer(f"Prefixo: {PREFIXO or 'nenhum'}
Rodape: {RODAPE or 'nenhum'}",alert=True)
    # â”€â”€ Info â”€â”€
    elif d==b"i_ping":
        up=datetime.now()-stats["start"]; h2,r=divmod(int(up.total_seconds()),3600); mi,s=divmod(r,60)
        await ev.answer(f"Pong!
Uptime: {h2}h {mi}m {s}s",alert=True)
    elif d==b"i_id": await ev.answer(f"ID deste chat: {ev.chat_id}",alert=True)
    elif d==b"i_stats":
        horas=dict(sorted(stats["por_hora"].items())[-8:])
        t="Por hora:
"+"".join(f"  {h2:02d}h: {n}
" for h2,n in horas.items())
        t+=f"
Total: {stats['n']} | Erros: {stats['err']}"
        await ev.answer(t,alert=True)
    elif d==b"i_reset": stats["n"]=0;stats["err"]=0;stats["por_hora"].clear();stats["start"]=datetime.now(); await ev.answer("Stats zeradas!",alert=True)
    elif d==b"i_teste":
        if not DESTINOS: await ev.answer("Nenhum destino!",alert=True); return
        ok=0
        for dst in DESTINOS:
            try: await bot.send_message(dst,f"*{BOT_NOME} -- Teste OK*
{datetime.now().strftime('%d/%m %H:%M')}",parse_mode="md"); ok+=1
            except Exception as e: logger.error(f"Teste falhou em {dst}: {e}")
        await ev.answer(f"Teste enviado: {ok}/{len(DESTINOS)} destino(s)!",alert=True)
    # â”€â”€ Descobrir ID â”€â”€
    elif d==b"disc_menu":
        await ev.edit(
            f"*DESCOBRIR ID*
{'='*20}
"
            f"Escolha o tipo ou busque pelo username:",
            buttons=[
                [Button.inline("User",     b"disc|user"),
                 Button.inline("Premium",  b"disc|premium"),
                 Button.inline("Bot",      b"disc|bot")],
                [Button.inline("Group",    b"disc|mygroup"),
                 Button.inline("Channel",  b"disc|mychannel"),
                 Button.inline("Forum",    b"disc|myforum")],
                [Button.inline("-- Buscar @username / ID --", b"disc|manual")],
                [Button.inline("<< Voltar", b"m_back")],
            ],parse_mode="md")
    elif d==b"disc|manual":
        AGUARDANDO[uid]="disc_manual"
        await ev.answer("Digite o @username ou ID:",alert=True)
    elif d.startswith(b"disc|"):
        cat=d.decode().split("|")[1]
        if cat=="manual":
            AGUARDANDO[uid]="disc_manual"
            await ev.answer("Digite o @username ou ID:",alert=True); return
        await ev.answer("Carregando...",alert=False)
        dialogs=await get_dialogs()
        items=dialogs.get(cat,[])
        if not items: await ev.answer(f"Nenhum {cat} encontrado.",alert=True); return
        linhas=[]
        for item in items[:20]:
            uname=f" @{item['username']}" if item.get("username") else ""
            linhas.append([Button.inline(f"{item['name']}{uname}",f"disc_show|{item['id']}".encode())])
        linhas.append([Button.inline("-- Buscar manual --",b"disc|manual"),
                       Button.inline("<< Voltar",b"disc_menu")])
        await ev.edit(
            f"*{cat.upper()}* -- {len(items)} encontrado(s)
Toque para ver o ID:",
            buttons=linhas,parse_mode="md")
    elif d.startswith(b"disc_show|"):
        chat_id=int(d.decode().split("|")[1])
        dialogs=await get_dialogs()
        all_items=[i for its in dialogs.values() for i in its]
        item=next((i for i in all_items if i["id"]==chat_id),None)
        nome=item["name"] if item else "?"
        uname=f"
Username: @{item['username']}" if item and item.get("username") else ""
        await ev.answer(f"{nome}
ID: {chat_id}{uname}",alert=True)

# â”€â”€â”€ HELPERS ENCAMINHADOR â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

# â”€â”€â”€ ENCAMINHADOR â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
                        novo=f"{PREFIXO}
{event.message.text}
{RODAPE}".strip()
                        await userbot.send_message(dst,novo)
                    else: await userbot.send_message(dst,event.message)
                else: await userbot.forward_messages(dst,event.message)
                ok+=1
            except Exception as e: stats["err"]+=1; logger.error(f"Erro ao enviar {dst}: {e}")
        if ok>0:
            stats["n"]+=1
            stats["por_hora"][datetime.now().hour]+=1
            try: chat=await event.get_chat(); name=getattr(chat,"title",None) or getattr(chat,"first_name","?")
            except: name=str(event.chat_id)
            HISTORICO.append({"time":datetime.now().strftime("%H:%M"),"chat":name})
            if len(HISTORICO)>200: HISTORICO.pop(0)
            if not MODO_SILENCIOSO: logger.info(f"[{BOT_NOME}] #{stats['n']} de '{name}' -> {ok} destino(s)")
    except Exception as e: stats["err"]+=1; logger.error(f"Erro geral: {e}")

# â”€â”€â”€ MAIN â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
async def main():
    await userbot.start()
    await bot.start(bot_token=BOT_TOKEN)
    me=await userbot.get_me()
    bme=await bot.get_me()
    logger.info(f"[{BOT_NOME}] Userbot: {me.first_name} | Bot: @{bme.username}")
    logger.info(f"Destinos={DESTINOS} | Origens={SRC or 'todos'} | Modo={MOD}")
    await asyncio.gather(userbot.run_until_disconnected(),bot.run_until_disconnected())

asyncio.run(main())