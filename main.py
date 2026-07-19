import discord
from discord.ext import commands
import os
import asyncio
import time
import socket

GUILD_ID     = 1510735912185630812
SERVER_IP    = "212.107.14.169"
SERVER_PORT  = 30120  # جعلناه رقم انتجر (Integer) للـ Socket

COLOR_DEFAULT = 0x1DA1F2
COLOR_ERROR   = 0xED4245
COLOR_SUCCESS = 0x57F287

BANNER_URL = "https://media.discordapp.net/attachments/1275695804945793035/1528448435810730014/sHet8AAAAAZJREFUAwCZWWojKDIiIAAAAABJRU5ErkJggg.png?ex=6a5e5608&is=6a5d0488&hm=c8640252464f04b76fad6f2209967c972702b13e9e2ce1e24b96beb31f802bca&=&format=webp&quality=lossless&width=446&height=446"

# الكاش الخاص بنظام الـ UDP المباشر
_cache: dict = {}
CACHE_TTL = 8

def _get_cache(key: str):
    entry = _cache.get(key)
    if entry and time.monotonic() - entry["ts"] < CACHE_TTL:
        return entry["data"]
    return None

def _set_cache(key: str, data):
    _cache[key] = {"data": data, "ts": time.monotonic()}


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


async def fetch_server_udp():
    """يتصل مباشرة بالسيرفر عبر منفذ UDP لجلب عدد اللاعبين والحد الأقصى وتخطي حظر الويب"""
    cached = _get_cache("udp_data")
    if cached is not None:
        return cached

    # بروتوكول A2S_INFO المعتمد للاستعلام المباشر من سيرفرات الألعاب
    query = b'\xFF\xFF\xFF\xFFTSource Engine Query\x00'
    
    def query_socket():
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(3.0)
        try:
            sock.sendto(query, (SERVER_IP, SERVER_PORT))
            data, _ = sock.recvfrom(4096)
            return data
        except Exception as e:
            print(f"⚠️ UDP Query Error: {e}")
            return None
        finally:
            sock.close()

    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(None, query_socket)
    
    if response and len(response) > 6:
        try:
            payload = response[6:]
            idx = 0
            # تخطي النصوص الأربعة الأولى القادمة بالحزمة (اسم السيرفر، الخريطة، المجلد، اللعبة)
            for _ in range(4):
                idx = payload.find(b'\x00', idx) + 1
            
            idx += 2  # تخطي معرف التطبيق (AppID)
            players = payload[idx]
            max_players = payload[idx + 1]
            
            result = {"players_count": players, "max_clients": max_players}
            _set_cache("udp_data", result)
            return result
        except Exception as e:
            print(f"❌ Error parsing UDP packet: {e}")
            
    return None


class PanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎮 اللاعبين", style=discord.ButtonStyle.primary, row=0)
    async def btn_players(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(thinking=True, ephemeral=True)
        data = await fetch_server_udp()
        if data is None:
            await interaction.followup.send(embed=error_embed("❌ السيرفر غير متاح حالياً للاتصال المباشر."), ephemeral=True)
            return
            
        total = data["players_count"]
        max_p = data["max_clients"]
        
        embed = discord.Embed(
            title="🎮 اللاعبون المتصلون حالياً",
            description=f"⚠️ بسبب حظر الويب على الـ API، تم جلب الإحصائيات العددية المباشرة:\n\n👤 عدد المتواجدين الآن: **{total} / {max_p}** لاعب.",
            color=COLOR_DEFAULT
        )
        embed.set_footer(text=f"Server: {SERVER_IP}:{SERVER_PORT} • UDP Mode")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="📊 إحصائيات", style=discord.ButtonStyle.primary, row=0)
    async def btn_stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(thinking=True, ephemeral=True)
        
        data = await fetch_server_udp()
        if data is None:
            await interaction.followup.send(embed=error_embed("❌ السيرفر غير متاح حالياً عبر الاتصال المباشر."), ephemeral=True)
            return
            
        total = data["players_count"]
        max_p = data["max_clients"]
        
        bar_filled = int((total / max_p) * 10) if max_p > 0 else 0
        bar = "█" * bar_filled + "░" * (10 - bar_filled)

        embed = discord.Embed(title="📊 إحصائيات السيرفر العامة", color=COLOR_DEFAULT)
        embed.add_field(name="🖥️ السيرفر",      value="`FuryFight Server`",            inline=False)
        embed.add_field(name="🟢 الحالة",        value="**أونلاين (اتصال مباشر)**",      inline=True)
        embed.add_field(name="👥 اللاعبون",      value=f"`{total} / {max_p}`",         inline=True)
        embed.add_field(name="📈 نسبة الامتلاء", value=f"`[{bar}] {total}/{max_p}`",  inline=False)
        embed.add_field(name="🌐 العنوان المباشر", value=f"`connect {SERVER_IP}:{SERVER_PORT}`", inline=True)
        embed.set_footer(text="SL6E BOT • UDP Query Mode")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="ℹ️ مساعدة", style=discord.ButtonStyle.primary, row=0)
    async def btn_info(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="ℹ️ دليل الاستخدام", color=COLOR_DEFAULT)
        embed.add_field(
            name="الأزرار المتاحة",
            value=(
                "🎮 **اللاعبين** — عرض إجمالي عدد المتصلين المتواجدين فوراً بالسيرفر\n"
                "📊 **إحصائيات** — إحصائيات تفصيلية حية مع شريط تقدم ونسبة الامتلاء\n"
                "ℹ️ **مساعدة** — هذه الرسالة الاسترشادية"
            ),
            inline=False,
        )
        embed.add_field(
            name="💡 نصائح لتخطي حظر الـ API",
            value=(
                "• البوت يتصل الآن بشكل آمن ومباشر عبر بروتوكول الـ UDP (Query Mode).\n"
                "• البيانات يتم حفظها في الكاش تلقائياً لمدة 8 ثوانٍ لحماية البوت وسرعة الأزرار.\n"
                "• تم إلغاء البحث النصي مؤقتاً لتجنب الاعتماد على نظام الـ HTTP المحظور من Cloudflare."
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

    async def setup_hook(self):
        guild = discord.Object(id=GUILD_ID)
        self.tree.copy_global_to(guild=guild)
        synced = await self.tree.sync(guild=guild)
        print(f"✅ مزامنة {len(synced)} أمر للسيرفر {GUILD_ID}")


bot = FiveMBot()


@bot.event
async def on_ready():
    await bot.change_presence(
        activity=discord.Streaming(
            name="by sl6e",
            url="https://www.twitch.tv/placeholder"
        )
    )
    print(f"✅ البوت جاهز ويعمل كلياً | الاتصال بـ {SERVER_IP}:{SERVER_PORT}")


async def _auto_delete(interaction: discord.Interaction, delay: int = 900):
    await asyncio.sleep(delay)
    try:
        await interaction.delete_original_response()
    except Exception:
        pass


@bot.tree.command(name="لوحة", description="🎮 لوحة تحكم السيرفر الكاملة (مقاومة للحظر)")
async def cmd_panel(interaction: discord.Interaction):
    await interaction.response.send_message(embed=panel_embed(), view=PanelView(), ephemeral=True)
    asyncio.create_task(_auto_delete(interaction, delay=900))


TOKEN = os.environ.get("DISCORD_TOKEN")
if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ DISCORD_TOKEN غير موجود. أضفه في متغيرات البيئة.")
