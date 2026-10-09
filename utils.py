"""Funções auxiliares compartilhadas."""
import datetime as dt
import re

import discord
from discord import app_commands

COLOR_INFO = discord.Color.blurple()
COLOR_OK = discord.Color.green()
COLOR_WARN = discord.Color.orange()
COLOR_BAD = discord.Color.red()

_DURATION_RE = re.compile(r"^(\d+)\s*([smhd])$", re.I)
_UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400}
MAX_TIMEOUT = dt.timedelta(days=28)


def parse_duration(text: str) -> dt.timedelta | None:
    """Converte '10m', '2h', '1d' em timedelta (máx. 28 dias)."""
    match = _DURATION_RE.match(text.strip())
    if not match:
        return None
    delta = dt.timedelta(seconds=int(match.group(1)) * _UNITS[match.group(2).lower()])
    if delta <= dt.timedelta(0) or delta > MAX_TIMEOUT:
        return None
    return delta


def make_embed(title, description=None, color=COLOR_INFO) -> discord.Embed:
    return discord.Embed(
        title=title, description=description, color=color,
        timestamp=dt.datetime.now(dt.timezone.utc),
    )


def guild_perm(**perms):
    """Comando só em servidores, visível e executável apenas com as permissões."""
    def deco(func):
        func = app_commands.checks.has_permissions(**perms)(func)
        func = app_commands.default_permissions(**perms)(func)
        return app_commands.guild_only()(func)
    return deco


def hierarchy_error(guild: discord.Guild, actor: discord.Member, target: discord.Member) -> str | None:
    """Retorna uma mensagem de erro se a ação violar a hierarquia de cargos."""
    if target.id == actor.id:
        return "Você não pode aplicar isso a si mesmo."
    if target.id == guild.me.id:
        return "Não posso aplicar isso a mim mesmo."
    if target.id == guild.owner_id:
        return "Não é possível aplicar isso ao dono do servidor."
    if actor.id != guild.owner_id and target.top_role >= actor.top_role:
        return "O cargo desse membro é igual ou superior ao seu."
    if target.top_role >= guild.me.top_role:
        return "O cargo desse membro é igual ou superior ao meu. Ajuste a hierarquia de cargos."
    return None


class ConfirmView(discord.ui.View):
    """Confirmação efêmera para ações sensíveis."""

    def __init__(self, author_id: int, timeout: float = 30):
        super().__init__(timeout=timeout)
        self.author_id = author_id
        self.value: bool | None = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "Apenas quem executou o comando pode confirmar.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Confirmar", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = True
        await interaction.response.edit_message(content="⏳ Processando...", view=None)
        self.stop()

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        await interaction.response.edit_message(content="Ação cancelada.", view=None)
        self.stop()


async def record_case(bot, guild, user, moderator, action: str, reason: str, extra: str | None = None) -> int:
    """Salva um caso no banco e envia o registro ao canal de logs."""
    number = await bot.db.add_case(guild.id, user.id, moderator.id, action, reason)
    embed = make_embed(f"Caso #{number} · {action}", color=COLOR_WARN)
    embed.add_field(name="Membro", value=f"{user} (`{user.id}`)")
    embed.add_field(name="Responsável", value=f"{moderator.mention}")
    embed.add_field(name="Motivo", value=reason or "Não informado", inline=False)
    if extra:
        embed.add_field(name="Detalhes", value=extra, inline=False)
    await bot.send_log(guild, embed)
    return number
