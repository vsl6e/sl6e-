import discord
from discord.ext import commands
import aiohttp
import os
import asyncio
import time

# معرف السيرفر الحروفي (Cfx Join ID) المستخرج من الصورة حقك
CFX_ID = "49az49"

GUILD_ID     = 1510735912185630812
SERVER_IP    = "212.107.14.169"
SERVER_PORT  = "30120"

# الرابط الرسمي الموحد لفايف إم (البديل لملفات json المحظورة بالسيرفر)
BASE_URL = f"https://servers-frontend.fivem.net/api/servers/single/{CFX_ID}"

FETCH_TIMEOUT = 6
COLOR_DEFAULT = 0x1DA1F2
COLOR_ERROR   = 0xED4245
COLOR_SUCCESS = 0x57F287

BANNER_URL = "https://media.discordapp.net/attachments/1275695804945793035/1511292593605181471/5dc9d6a7d1853123e5ec5c3017944906.webp"

_cache: dict = {}
CACHE_TTL = 10  # رفعنا الكاش شوي عشان حماية Cfx من السبام

def _get_cache(key: str):
    entry = _cache.get(key)
    if entry and time.monotonic() - entry["ts"] < CACHE_TTL:
        return entry["data"]
    return None

def _set_cache(key: str, data):
    _cache[key] = {"data": data, "ts": time.monotonic()}


def extract_identifier(identifiers: list, prefix: str):
    for i in identifiers:
        if i.startswith(prefix):
            return i.replace(prefix, "")
    return None

def format_identifiers(identifiers: list) -> str:
    mapping = {
        "steam:"   : "🟠 Steam",
        "discord:" : "🔵 Discord",
        "license:" : "🔑 License",
        "license2:": "🔑 License2",
        "xbl:"     : "🟢 Xbox",
        "live:"    : "🟢 Live",
        "ip:"      : "🌐 IP",
    }
    lines = []
    for ident in identifiers:
        matched = False
        for prefix, label in mapping.items():
            if ident.startswith(prefix):
                lines.append(f"{label}: `{ident.replace(prefix,'')}`")
                matched = True
                break
        if not matched:
            lines.append(f"🔹 `{ident}`")
    return "\n".join(lines) if lines else "لا توجد معرّفات"

def error_embed(msg: str) -> discord.Embed:
    e = discord.Embed(title="SL6E BOT", description=msg, color=COLOR_ERROR)
    e.set_footer(text=f"Server: {SERVER_IP}:{SERVER_PORT}")
    return e

def panel_embed() -> discord.Embed:
    embed = discord.Embed(
        title="🎮  SL6E BOT — لوحة التحكم",
        description="اختر من الأزرار أدناه",
        color=0x1B6FE4
    )
    embed.set_image(url=BANNER_URL)
    embed.set_footer(text="SL6E BOT  •  لوحة التحكم")
    return embed

# متصفح وهمي كامل لتخطي حماية وبلوك الـ Cloudflare على الاستضافات
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://fivem.net",
    "Referer": "https://fivem.net/",
}

async def _fetch_cfx_data():
    cached = _get_cache("cfx_master")
    if cached is not None:
        return cached

    session: aiohttp.ClientSession = bot.session
    if session is None or session.closed:
        session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False, limit=5))
        bot.session = session

    try:
        async with asyncio.timeout(FETCH_TIMEOUT):
            async with session.get(BASE_URL, headers=_HEADERS) as r:
                if r.status == 200:
                    res = await r.json(content_type=None)
                    if res and "Data" in res:
                        _set_cache("cfx_master", res["Data"])
                        return res["Data"]
                else:
                    print(f"⚠️ Cfx API returned status: {r.status}")
    except Exception as e:
        print(f"⚠️ Error fetching from Cfx: {e}")
    return None

async def fetch_players():
    data = await _fetch_cfx_data()
    return data.get("players", []) if data else None

async def fetch_info():
    return await _fetch_cfx_data()


class SearchIDModal(discord.ui.Modal, title="🔍 بحث بـ Server ID"):
    server_id = discord.ui.TextInput(label="Server ID", placeholder="مثال: 5", min_length=1, max_length=6)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)
        try:
            sid = int(self.server_id.value.strip())
        except ValueError:
            await interaction.followup.send(embed=error_embed("❌ أدخل رقماً صحيحاً."), ephemeral=True)
            return

        data = await fetch_players()
        if data is None:
            await interaction.followup.send(embed=error_embed("❌ فشل الاتصال بـ Cfx API حالياً."), ephemeral=True)
            return

        target = next((p for p in data if p.get("id") == sid), None)
        if not target:
            await interaction.followup.send(embed=error_embed(f"❌ لا يوجد لاعب بالـ ID **{sid}** حالياً."), ephemeral=True)
            return

        ids = target.get("identifiers", [])
        embed = discord.Embed(title="🔍 نتيجة البحث عن اللاعب", color=COLOR_DEFAULT)
        embed.add_field(name="👤 الاسم",   value=f"`{target.get('name','Unknown')}`", inline=True)
        embed.add_field(name="🆔 ID",      value=f"`{target.get('id','?')}`",         inline=True)
        embed.add_field(name="📶 Ping",    value=f"`{target.get('ping','?')} ms`",    inline=True)
        embed.add_field(name="🔵 Discord", value=f"<@{extract_identifier(ids,'discord:') or '1'}>", inline=True)
        embed.add_field(name="📋 كل المعرّفات", value=format_identifiers(ids), inline=False)
        embed.set_footer(text=f"Cfx ID: {CFX_ID}")
        await interaction.followup.send(embed=embed, ephemeral=True)


class SearchNameModal(discord.ui.Modal, title="🔎 بحث بالاسم"):
    player_name = discord.ui.TextInput(label="اسم اللاعب", placeholder="اكتب الاسم أو جزء منه", min_length=2, max_length=50)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)
        name = self.player_name.value.strip()

        data = await fetch_players()
        if data is None:
            await interaction.followup.send(embed=error_embed("❌ فشل جلب بيانات السيرفر."), ephemeral=True)
            return

        results = [p for p in data if name.lower() in p.get("name", "").lower()]
        if not results:
            await interaction.followup.send(embed=error_embed(f"❌ لم يُعثر على **\"{name}\"**."), ephemeral=True)
            return

        show = results[:20]
        lines = "".join(f"[{str(p.get('id','?')).ljust(4)}] {p.get('name','?')} ({p.get('ping','?')}ms)\n" for p in show)
        
        embed = discord.Embed(title="🔎 نتائج البحث", description=f"**\"{name}\"** — وُجد {len(results)} لاعب", color=COLOR_SUCCESS)
        embed.add_field(name="النتائج", value=f"```yaml\n{lines}```", inline=False)
        await interaction.followup.send(embed=embed, ephemeral=True)


class PlayersPaginationView(discord.ui.View):
    def __init__(self, players_data: list, per_page: int = 25):
        super().__init__(timeout=90)
        self.data = players_data
        self.per_page = per_page
        self.current_page = 0
        self.total_pages = max(1, (len(players_data) + per_page - 1) // per_page)
        self._update_buttons()

    def get_page_embed(self) -> discord.Embed:
        start = self.current_page * self.per_page
        end   = start + self.per_page
        chunk = self.data[start:end]
        total = len(self.data)

        embed = discord.Embed(title="🎮 اللاعبون المتصلون", description=f"**إجمالي المتصلين: {total} لاعب**", color=COLOR_DEFAULT)
        if total == 0:
            embed.description = "⚠️ لا يوجد لاعبون متصلون حالياً."
        else:
            lines = "".join(f"[{str(p.get('id','?')).ljust(4)}] {p.get('name','Unknown')}\n" for p in chunk)
            embed.add_field(name=f"الصفحة {self.current_page + 1} من {self.total_pages}", value=f"```yaml\n{lines}```", inline=False)
        embed.set_footer(text=f"Cfx ID: {CFX_ID}")
        return embed

    def _update_buttons(self):
        self.btn_prev.disabled = self.current_page == 0
        self.btn_next.disabled = self.current_page == self.total_pages - 1

    @discord.ui.button(label="◀️ السابق", style=discord.ButtonStyle.secondary)
    async def btn_prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            self._update_buttons()
            await interaction.response.edit_message(embed=self.get_page_embed(), view=self)

    @discord.ui.button(label="التالي ▶️", style=discord.ButtonStyle.secondary)
    async def btn_next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self._update_buttons()
            await interaction.response.edit_message(embed=self.get_page_embed(), view=self)

    @discord.ui.button(label="🔄 تحديث", style=discord.ButtonStyle.success)
    async def btn_refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        _cache.pop("cfx_master", None)
        fresh = await fetch_players()
        if fresh is None: return
        self.data = fresh
        self.total_pages = max(1, (len(fresh) + self.per_page - 1) // self.per_page)
        self.current_page = min(self.current_page, self.total_pages - 1)
        self._update_buttons()
        await interaction.edit_original_response(embed=self.get_page_embed(), view=self)


class PanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎮 اللاعبين", style=discord.ButtonStyle.primary, row=0)
    async def btn_players(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(thinking=True, ephemeral=True)
        data = await fetch_players()
        if data is None:
            await interaction.followup.send(embed=error_embed("❌ عذراً، حماية فايف إم ترفض الطلب حالياً. جرب لاحقاً."), ephemeral=True)
            return
        paginator = PlayersPaginationView(data, per_page=25)
        await interaction.followup.send(embed=paginator.get_page_embed(), view=paginator, ephemeral=True)

    @discord.ui.button(label="📊 إحصائيات", style=discord.ButtonStyle.primary, row=0)
    async def btn_stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(thinking=True, ephemeral=True)
        info = await fetch_info()
        if info is None:
            await interaction.followup.send(embed=error_embed("❌ فشل سحب الإحصائيات من Cfx Master Server."), ephemeral=True)
            return
            
        total = info.get("clients", 0)
        max_p = info.get("vars", {}).get("sv_maxClients", "32")
        
        try: max_p_int = int(max_p)
        except: max_p_int = 32
        
        bar_filled = int((total / max_p_int) * 10) if max_p_int > 0 else 0
        bar = "█" * bar_filled + "░" * (10 - bar_filled)

        embed = discord.Embed(title="📊 إحصائيات سيرفر FuryFight", color=COLOR_DEFAULT)
        embed.add_field(name="🟢 الحالة",        value="**أونلاين (Cfx API)**",         inline=True)
        embed.add_field(name="👥 اللاعبون",      value=f"`{total} / {max_p}`",         inline=True)
        embed.add_field(name="📈 نسبة الامتلاء", value=f"`[{bar}] {total}/{max_p}`",  inline=False)
        embed.add_field(name="🌐 ربط الدخول المباشر", value=f"`connect {SERVER_IP}:{SERVER_PORT}`", inline=False)
        embed.set_footer(text=f"Cfx ID: {CFX_ID}")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="🔍 بحث بـ ID", style=discord.ButtonStyle.primary, row=1)
    async def btn_search_id(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SearchIDModal())

    @discord.ui.button(label="🔎 بحث بالاسم", style=discord.ButtonStyle.primary, row=1)
    async def btn_search_name(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SearchNameModal())


class FiveMBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        self.session: aiohttp.ClientSession | None = None

    async def setup_hook(self):
        self.session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False, limit=5))
        guild = discord.Object(id=GUILD_ID)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)

    async def close(self):
        if self.session and not self.session.closed: await self.session.close()
        await super().close()


bot = FiveMBot()

@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Streaming(name="BY SL6E & ABO 5LOOD", url="https://www.twitch.tv/placeholder"))
    print(f"✅ {bot.user.name} جاهز باللوحة الكاملة!")

@bot.tree.command(name="لوحة", description="🎮 لوحة تحكم السيرفر الكاملة مع البحث والصفحات")
async def cmd_panel(interaction: discord.Interaction):
    await interaction.response.send_message(embed=panel_embed(), view=PanelView(), ephemeral=True)

TOKEN = os.environ.get("DISCORD_TOKEN")
if TOKEN: bot.run(TOKEN)
