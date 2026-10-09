# Bot de Comunidade para Discord (Python)

Bot modular em português do Brasil: moderação, automod, boas-vindas/verificação, tickets e logs.
Stack: `discord.py 2.x` + `aiosqlite` (SQLite).

## Estrutura
```
main.py            # inicialização, helpers e tratamento de erros
database.py        # esquema e consultas (settings, cases, tickets, config_history)
utils.py           # embeds, confirmação, hierarquia, registro de casos
cogs/config.py     # /config ...  (painel administrativo + histórico)
cogs/moderation.py # /aviso /timeout /untimeout /expulsar /banir /desbanir /historico /caso /limpar
cogs/automod.py    # spam, menções, links, detecção de raid
cogs/welcome.py    # boas-vindas, cargo automático, /verificacao painel
cogs/tickets.py    # /ticket painel|adicionar|remover + botões Assumir/Encerrar
```

## Instalação
1. Crie o bot em https://discord.com/developers/applications.
   Em **Bot > Privileged Gateway Intents** ative **Server Members Intent** e **Message Content Intent**.
2. `python -m venv .venv && source .venv/bin/activate` (Windows: `.venv\Scripts\activate`)
3. `pip install -r requirements.txt`
4. `cp .env.example .env` e preencha `DISCORD_TOKEN` (e `DEV_GUILD_ID` para testes).
5. `python main.py`

## Convite (menor privilégio)
Escopos: `bot` + `applications.commands`. Permissões: Ver canais, Enviar mensagens,
Inserir links, Anexar arquivos, Ler histórico, Gerenciar mensagens, Gerenciar canais,
Gerenciar cargos, Expulsar, Banir e Silenciar membros (Moderate Members).
Posicione o cargo do bot **acima** dos cargos que ele precisa gerenciar.

## Configuração rápida
```
/config logs #logs-mod
/config boasvindas canal:#boas-vindas
/config cargo_automatico cargo:@Membro
/config tickets categoria:Tickets cargo_suporte:@Suporte canal_logs:#logs-tickets
/ticket painel
/config automod bloquear_links:true dominios_permitidos:youtube.com,github.com
/config ver
```
- **Verificação:** `/config cargo_verificado` e depois `/verificacao painel`.
- **Módulos:** `/config modulo` liga/desliga Moderação, Automod, Boas-vindas e Tickets.
- **Privacidade:** deixe `#logs-tickets` visível só para a equipe, pois ele recebe as transcrições.
- Placeholders de boas-vindas: `{user}`, `{username}`, `{server}`, `{count}`.

## Segurança
- Token apenas via `.env` (já no `.gitignore`).
- Checagem de hierarquia e permissões antes de toda ação; confirmação em expulsar/banir.
- Sem DMs em massa (apenas aviso individual ao punido) e sem automação de contas de usuário.
- Todas as alterações de configuração e ações de moderação ficam registradas.

## Próximos passos (versão 2)
XP/níveis, sugestões, enquetes, sorteios, mensagens agendadas, cargos autoselecionáveis e canais de voz temporários.
