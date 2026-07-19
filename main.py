import discord
from discord.ext import commands
import aiohttp
import os
import asyncio
import time


SERVER_IP   = "185.161.42.49"
SERVER_PORT = "30120"
GUILD_ID    = 1126668886985670696

BASE_URL = f"http://{SERVER_IP}:{SERVER_PORT}/players.json"
INFO_URL = f"http://{SERVER_IP}:{SERVER_PORT}/info.json"

FETCH_TIMEOUT = 5
COLOR_DEFAULT = 0x1DA1F2
COLOR_ERROR   = 0xED4245
COLOR_SUCCESS = 0x57F287

BANNER_URL = "https://media.discordapp.net/attachments/1275695804945793035/1528448435810730014/sHet8AAAAAZJREFUAwCZWWojKDIiIAAAAABJRU5ErkJggg.png?ex=6a5e5608&is=6a5d0488&hm=c8640252464f04b76fad6f2209967c972702b13e9e2ce1e24b96beb31f802bca&=&format=webp&quality=lossless&width=446&height=446"


_cache: dict = {}
CACHE_TTL = 8

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


_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}

async def _fetch_json(url: str, cache_key: str):
    cached = _get_cache(cache_key)
    if cached is not None:
        return cached

    session: aiohttp.ClientSession = bot.session
    if session is None or session.closed:
        session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(ssl=False, limit=10)
        )
        bot.session = session

    try:
        async with asyncio.timeout(FETCH_TIMEOUT):
            async with session.get(url, headers=_HEADERS) as r:
                if r.status == 200:
                    data = await r.json(content_type=None)
                    _set_cache(cache_key, data)
                    return data
    except TimeoutError:
        print(f"⏱️ timeout: {url}")
    except Exception as e:
        print(f"⚠️ fetch error [{url}]: {e}")
    return None

async def fetch_players():
    return await _fetch_json(BASE_URL, "players")

async def fetch_info():
    return await _fetch_json(INFO_URL, "info")


class SearchIDModal(discord.ui.Modal, title="🔍 بحث بـ Server ID"):
    server_id = discord.ui.TextInput(
        label="Server ID",
        placeholder="مثال: 5",
        min_length=1,
        max_length=6,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)
        try:
            sid = int(self.server_id.value.strip())
        except ValueError:
            await interaction.followup.send(embed=error_embed("❌ أدخل رقماً صحيحاً."), ephemeral=True)
            return

        data = await fetch_players()
        if data is None:
            await interaction.followup.send(
                embed=error_embed("❌ فشل جلب بيانات السيرفر."),
                ephemeral=True,
            )
            return

        target = next((p for p in data if p.get("id") == sid), None)
        if not target:
            await interaction.followup.send(
                embed=error_embed(f"❌ لا يوجد لاعب بالـ ID **{sid}**.\n⚡ المتصلون الآن: **{len(data)}**"),
                ephemeral=True,
            )
            return

        ids = target.get("identifiers", [])
        embed = discord.Embed(title="🔍 نتيجة البحث", color=COLOR_DEFAULT)
        embed.add_field(name="👤 الاسم",   value=f"`{target.get('name','Unknown')}`", inline=True)
        embed.add_field(name="🆔 ID",      value=f"`{target.get('id','?')}`",         inline=True)
        embed.add_field(name="📶 Ping",    value=f"`{target.get('ping','?')} ms`",    inline=True)
        embed.add_field(
            name="🟠 Steam",
            value=f"`{extract_identifier(ids,'steam:') or '—'}`",
            inline=True,
        )
        embed.add_field(
            name="🔵 Discord",
            value=f"`{extract_identifier(ids,'discord:') or '—'}`",
            inline=True,
        )
        embed.add_field(
            name="🔑 License",
            value=f"`{extract_identifier(ids,'license:') or '—'}`",
            inline=True,
        )
        embed.add_field(
            name="🌐 IP",
            value=f"`{extract_identifier(ids,'ip:') or '—'}`",
            inline=True,
        )
        embed.add_field(name="📋 كل المعرّفات", value=format_identifiers(ids), inline=False)
        embed.set_footer(text=f"Server: {SERVER_IP}:{SERVER_PORT}")
        await interaction.followup.send(embed=embed, ephemeral=True)


class SearchNameModal(discord.ui.Modal, title="🔎 بحث بالاسم"):
    player_name = discord.ui.TextInput(
        label="اسم اللاعب",
        placeholder="اكتب الاسم أو جزء منه",
        min_length=2,
        max_length=50,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)
        name = self.player_name.value.strip()

        data = await fetch_players()
        if data is None:
            await interaction.followup.send(
                embed=error_embed("❌ فشل جلب بيانات السيرفر."),
                ephemeral=True,
            )
            return

        results = [p for p in data if name.lower() in p.get("name", "").lower()]
        if not results:
            await interaction.followup.send(
                embed=error_embed(f"❌ لم يُعثر على **\"{name}\"** بين {len(data)} لاعب متصل."),
                ephemeral=True,
            )
            return

        show = results[:20]
        lines = ""
        for p in show:
            lines += f"[{str(p.get('id','?')).ljust(4)}] {p.get('name','?')}  ({p.get('ping','?')}ms)\n"
        
        embed = discord.Embed(
            title="🔎 نتائج البحث",
            description=f"**\"{name}\"** — وُجد {len(results)} لاعب" + ("\n⚠️ يُعرض أول 20 فقط" if len(results) > 20 else ""),
            color=COLOR_SUCCESS,
        )
        embed.add_field(name="النتائج", value=f"```yaml\n{lines}```", inline=False)
        embed.set_footer(text=f"Server: {SERVER_IP}:{SERVER_PORT}")
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

        embed = discord.Embed(
            title="🎮 اللاعبون المتصلون",
            description=f"**{total} لاعب**",
            color=COLOR_DEFAULT,
        )
        if total == 0:
            embed.description = "⚠️ لا يوجد لاعبون متصلون حالياً."
        else:
            lines = ""
            for p in chunk:
                lines += f"[{str(p.get('id','?')).ljust(4)}] {p.get('name','Unknown')}\n"
            embed.add_field(
                name=f"الصفحة {self.current_page + 1} من {self.total_pages}  (#{start+1}–#{min(end,total)})",
                value=f"```yaml\n{lines}```",
                inline=False,
            )
        embed.set_footer(text=f"Server: {SERVER_IP}:{SERVER_PORT}")
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
        else:
            await interaction.response.defer()

    @discord.ui.button(label="التالي ▶️", style=discord.ButtonStyle.secondary)
    async def btn_next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self._update_buttons()
            await interaction.response.edit_message(embed=self.get_page_embed(), view=self)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="🔄 تحديث", style=discord.ButtonStyle.success)
    async def btn_refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        _cache.pop("players", None)
        fresh = await fetch_players()
        if fresh is None:
            await interaction.followup.send(embed=error_embed("❌ فشل التحديث."), ephemeral=True)
            return
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
            await interaction.followup.send(
                embed=error_embed("❌ السيرفر غير متاح حالياً."),
                ephemeral=True,
            )
            return
        paginator = PlayersPaginationView(data, per_page=25)
        await interaction.followup.send(embed=paginator.get_page_embed(), view=paginator, ephemeral=True)

    @discord.ui.button(label="📊 إحصائيات", style=discord.ButtonStyle.primary, row=0)
    async def btn_stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(thinking=True, ephemeral=True)
        data, info = await asyncio.gather(fetch_players(), fetch_info())
        if data is None:
            await interaction.followup.send(
                embed=error_embed("❌ السيرفر غير متاح حالياً."),
                ephemeral=True,
            )
            return
        total    = len(data)
        vars_    = (info or {}).get("vars", {})
        max_p    = vars_.get("sv_maxClients", "?")
        srv_name = (info or {}).get("name", vars_.get("sv_hostname", "Unknown"))
        pings    = [p.get("ping", 0) for p in data if isinstance(p.get("ping"), int)]
        avg_ping = round(sum(pings) / len(pings)) if pings else 0

        bar_filled = int((total / int(max_p)) * 10) if str(max_p).isdigit() and int(max_p) > 0 else 0
        bar = "█" * bar_filled + "░" * (10 - bar_filled)

        embed = discord.Embed(title="📊 إحصائيات السيرفر", color=COLOR_DEFAULT)
        embed.add_field(name="🖥️ السيرفر",      value=f"`{srv_name}`",                inline=False)
        embed.add_field(name="🟢 الحالة",        value="**أونلاين**",                  inline=True)
        embed.add_field(name="👥 اللاعبون",      value=f"`{total} / {max_p}`",         inline=True)
        embed.add_field(name="📶 متوسط البينج",  value=f"`{avg_ping} ms`",             inline=True)
        embed.add_field(name="📈 نسبة الامتلاء", value=f"`[{bar}] {total}/{max_p}`",  inline=False)
        embed.add_field(name="🌐 العنوان",       value=f"`{SERVER_IP}:{SERVER_PORT}`", inline=True)
        embed.set_footer(text=f"Server: {SERVER_IP}:{SERVER_PORT}")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="🔍 بحث بـ ID", style=discord.ButtonStyle.primary, row=1)
    async def btn_search_id(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SearchIDModal())

    @discord.ui.button(label="🔎 بحث بالاسم", style=discord.ButtonStyle.primary, row=1)
    async def btn_search_name(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SearchNameModal())

    @discord.ui.button(label="ℹ️ مساعدة", style=discord.ButtonStyle.primary, row=1)
    async def btn_info(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="ℹ️ دليل الاستخدام", color=COLOR_DEFAULT)
        embed.add_field(
            name="الأزرار المتاحة",
            value=(
                "🎮 **اللاعبين** — عرض اللاعبين المتصلين مع التنقل بين الصفحات وزر تحديث\n"
                "📊 **إحصائيات** — إحصائيات تفصيلية للسيرفر مع شريط الامتلاء\n"
                "🔍 **بحث بـ ID** — ابحث بـ Server ID للحصول على معلومات اللاعب\n"
                "🔎 **بحث بالاسم** — ابحث باسم اللاعب أو جزء منه\n"
                "ℹ️ **مساعدة** — هذه الرسالة"
            ),
            inline=False,
        )
        embed.add_field(
            name="💡 نصائح",
            value=(
                "• البيانات محفوظة في الكاش لمدة 8 ثواني لتسريع الاستجابة\n"
                "• استخدم زر 🔄 تحديث في قائمة اللاعبين لجلب أحدث البيانات\n"
                "• جميع الردود خاصة (ephemeral) لا يراها غيرك"
            ),
            inline=False,
        )
        embed.set_footer(text=f"Server: {SERVER_IP}:{SERVER_PORT}")
        await interaction.response.send_message(embed=embed, ephemeral=True)


class FiveMBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)
        self.session: aiohttp.ClientSession | None = None

    async def setup_hook(self):
        self.session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(ssl=False, limit=10),
        )
        guild = discord.Object(id=GUILD_ID)
        self.tree.copy_global_to(guild=guild)
        synced = await self.tree.sync(guild=guild)
        print(f"✅ مزامنة {len(synced)} أمر للسيرفر {GUILD_ID}")

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
        await super().close()


bot = FiveMBot()


@bot.event
async def on_ready():
    await bot.change_presence(
        activity=discord.Streaming(
            name="by sl6e",
            url="https://www.twitch.tv/placeholder"
        )
    )
    print(f"✅ {bot.user.name}  |  {SERVER_IP}:{SERVER_PORT}")


async def _auto_delete(interaction: discord.Interaction, delay: int = 900):
    await asyncio.sleep(delay)
    try:
        await interaction.delete_original_response()
    except Exception:
        pass


@bot.tree.command(name="لوحة", description="🎮 لوحة تحكم السيرفر الكاملة")
async def cmd_panel(interaction: discord.Interaction):
    await interaction.response.send_message(embed=panel_embed(), view=PanelView(), ephemeral=True)
    asyncio.create_task(_auto_delete(interaction, delay=900))



TOKEN = os.environ.get("DISCORD_TOKEN")
if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ DISCORD_TOKEN غير موجود. أضفه في .env أو متغيرات البيئة.")
