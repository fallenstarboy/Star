"""Ponto de entrada do bot de comunidade."""
import logging
import os

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from database import Database

load_dotenv()
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("bot")

EXTENSIONS = [
    "cogs.config",
    "cogs.moderation",
    "cogs.automod",
    "cogs.welcome",
    "cogs.tickets",
]


class CommunityBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True          # boas-vindas, raid, cargos (Server Members Intent)
        intents.message_content = True  # automod de links (Message Content Intent)
        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=intents,
            help_command=None,
            allowed_mentions=discord.AllowedMentions(everyone=False, roles=False),
        )
        self.db = Database(os.getenv("DATABASE_PATH", "data/bot.db"))

    async def setup_hook(self):
        await self.db.connect()
        for ext in EXTENSIONS:
            await self.load_extension(ext)
            log.info("Módulo carregado: %s", ext)

        dev_guild = os.getenv("DEV_GUILD_ID")
        if dev_guild:
            guild = discord.Object(int(dev_guild))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()
        self.tree.on_error = self.on_tree_error

    async def close(self):
        await self.db.close()
        await super().close()

    async def on_ready(self):
        log.info("Conectado como %s (%s)", self.user, self.user.id)

    # ---------- helpers usados pelos módulos ----------
    async def module_enabled(self, guild_id: int, module: str) -> bool:
        return await self.db.get_setting(guild_id, f"module.{module}") == "1"

    async def update_setting(self, guild_id: int, user_id: int, key: str, value: str):
        old = await self.db.get_setting(guild_id, key)
        await self.db.set_setting(guild_id, key, value)
        await self.db.add_history(guild_id, user_id, key, old, value)

    async def send_log(self, guild: discord.Guild, embed: discord.Embed, key: str = "log_channel"):
        channel_id = await self.db.get_int(guild.id, key) or await self.db.get_int(guild.id, "log_channel")
        channel = guild.get_channel(channel_id) if channel_id else None
        if isinstance(channel, discord.TextChannel):
            try:
                await channel.send(embed=embed)
            except discord.HTTPException:
                log.warning("Sem permissão para enviar logs em %s (%s)", channel_id, guild.id)

    async def on_tree_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            msg = "Você não tem permissão para usar este comando."
        elif isinstance(error, app_commands.BotMissingPermissions):
            perms = ", ".join(error.missing_permissions)
            msg = f"Eu preciso das seguintes permissões: {perms}."
        elif isinstance(error, app_commands.CommandOnCooldown):
            msg = f"Aguarde {error.retry_after:.0f}s para usar novamente."
        elif isinstance(error, app_commands.CheckFailure):
            msg = str(error) or "Você não pode usar este comando agora."
        else:
            log.exception("Erro inesperado em comando", exc_info=error)
            msg = "Ocorreu um erro inesperado. Tente novamente em instantes."
        try:
            if interaction.response.is_done():
                await interaction.followup.send(f"❌ {msg}", ephemeral=True)
            else:
                await interaction.response.send_message(f"❌ {msg}", ephemeral=True)
        except discord.HTTPException:
            pass


def main():
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise SystemExit("Defina DISCORD_TOKEN no arquivo .env")
    CommunityBot().run(token, log_handler=None)


if __name__ == "__main__":
    main()
