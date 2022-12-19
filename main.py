from __future__ import annotations

import asyncio
import logging
import os
import sys
from logging import StreamHandler, FileHandler
from typing import Optional, Literal

import discord
import dotenv
from discord import app_commands, Interaction, ui
from discord.ext import commands
from discord.ext.commands import Context, Greedy

BASE_DIR = os.path.normpath(os.path.dirname(os.path.realpath(__file__)))
handler_console = StreamHandler(stream=sys.stdout)
handler_console.setLevel(logging.DEBUG)
handler_filestream = FileHandler(filename=f"{BASE_DIR}/bot.log", encoding='utf-8')
handler_filestream.setLevel(logging.INFO)

logging_handlers = [
        handler_console,
        handler_filestream
]

logging.basicConfig(
    format="%(asctime)s | %(name)25s | %(funcName)25s | %(levelname)6s | %(message)s",
    datefmt="%b %d %H:%M:%S",
    level=logging.DEBUG,
    handlers=logging_handlers
)
logging.getLogger('asyncio').setLevel(logging.ERROR)
logging.getLogger('discord').setLevel(logging.ERROR)
logging.getLogger('websockets').setLevel(logging.ERROR)
log = logging.getLogger(__name__)


dotenv.load_dotenv()
log = logging.getLogger(__name__)

extensions = (
    'bot.core',
    'bot.example',
)


class MissingConfigurationException(Exception):
    pass


def assert_envs_exist():
    envs = (
        ('TOKEN', 'The Bot Token', str),
    )
    for e in envs:
        ident = f"{e[0]}/{e[1]}"
        value = os.environ.get(e[0])
        if value is None:
            raise MissingConfigurationException(f"{ident} needs to be- defined")
        try:
            _ = e[2](value)
        except ValueError:
            raise MissingConfigurationException(f"{ident} is not the required type of {e[2]}")


class CoreCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name='help', description="See the commands that this bot has to offer")
    async def help_cmd(self, itx: Interaction):
        title = "Bot Help Commands"

        description = textwrap.dedent(
            """For further help, use /cmd and see the hints that discord provides

            **Available Commands**

        """)
        embed = discord.Embed(title=title, description=description)

        await itx.response.send_message(embed=embed, ephemeral=True)

    @commands.is_owner()
    @commands.guild_only()
    @commands.command()
    async def sync(self,
                   ctx: Context, guilds: Greedy[discord.Object], spec: Optional[Literal["~", "*", "^"]] = None) -> None:
        if not guilds:
            if spec == "~":
                synced = await ctx.bot.tree.sync(guild=ctx.guild)
            elif spec == "*":
                ctx.bot.tree.copy_global_to(guild=ctx.guild)
                synced = await ctx.bot.tree.sync(guild=ctx.guild)
            elif spec == "^":
                ctx.bot.tree.clear_commands(guild=ctx.guild)
                await ctx.bot.tree.sync(guild=ctx.guild)
                synced = []
            else:
                synced = await ctx.bot.tree.sync()

            await ctx.send(
                f"Synced {len(synced)} commands {'globally' if spec is None else 'to the current guild.'}"
            )
            return
        ret = 0
        for guild in guilds:
            try:
                await ctx.bot.tree.sync(guild=guild)
            except discord.HTTPException:
                pass
            else:
                ret += 1
        await ctx.send(f"Synced the tree to {ret}/{len(guilds)}.")

# Create Select options. This is a List of SelectOption. I just use a list comprehension here to make it easier
SELECT_OPTIONS = [discord.SelectOption(label=f"Value{x}", value=f"Value{x}") for x in range(1, 4)]


def make_embed(text: str):
    """Helper function that just keeps the embed consistent"""
    return discord.Embed(
        title="Component Example",
        description=text
    )


class MyModal(ui.Modal, title="Enter a value"):
    """Modals are a good way to get text input. They don't have reference to a view since they are sent on their own.
    When using discord app_commands and components, it is important to decide where you want to store the state.
    In our case, most of the interaction happens in the view that houses the buttons and the select, so I am storing
    it there.

    """
    def __init__(self, view: 'ComponentView', **kwargs):
        super().__init__(**kwargs)
        self.view = view

    text_value = ui.TextInput(label="Please enter a text value")

    async def on_submit(self, interaction: discord.Interaction):
        value = self.text_value.value
        # Append to the text line.
        self.view.text += f"\n Modal was called and value entered is {value}"
        await interaction.response.edit_message(embed=make_embed(self.view.text), view=self.view)


class MyButton(ui.Button):
    """Since we want to change view state, it is easier to subclass this than use the decorator like we used
    with a select option. That way we can add them to the view and hold a reference to it easily.

    Likewise all buttons act the same where it updates the text of a view and calls a modal (a way to get input).
    So we can utilize subclassing to not have to duplicate code.
    """

    def __init__(self, name: str, **kwargs):
        super().__init__(label=name, **kwargs)
        self.name = name

    async def callback(self, interaction: discord.Interaction):
        # For most editor type inference and autocomplete support
        view: ComponentView = self.view
        view.text += f"\n {self.name} was pressed!"
        await interaction.response.send_modal(MyModal(self.view))


class ComponentView(ui.View):
    """A view holds components such as dropdowns and lists.
    You can also use it to hold state which we will do with the content it outputs"""

    # This is a class attribute that we can attach a message to later. For views, we can't do this in a constructor
    # since you must create the message with the view first. This allows us to attach it later.
    message: discord.Message

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.text = ""

        # create and hold a reference, but don't add them to the view. Once added to a view they "appear".
        self.button1 = MyButton("Button1", style=discord.ButtonStyle.red)
        self.button2 = MyButton("Button2", style=discord.ButtonStyle.green)
        self.button3 = MyButton("Button3", style=discord.ButtonStyle.blurple)

    @ui.select(options=SELECT_OPTIONS)
    async def dropdown_selected(self, interaction: discord.Interaction, select: ui.Select):
        """Dropdown was selected. Set the flag to display the buttons and update the text"""

        # Make each select option comma separated for text
        values = ', '.join([v for v in select.values])

        # This is the beginning of the chain so reset the entire text field and update
        self.text = f"{values} selected in select option"

        # Add the referenced buttons to the view if they aren't in it already
        self.add_button_to_view(self.button1)
        self.add_button_to_view(self.button2)
        self.add_button_to_view(self.button3)
        await interaction.response.edit_message(embed=make_embed(self.text), view=self)

    def add_button_to_view(self, button: MyButton):
        """Helper function to make sure we don't re-add the same item to the view"""
        if button not in self.children:
            self.add_item(button)


class ExampleCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='start', description="Starts the example with components")
    async def start_cmd(self, interaction: discord.Interaction):

        embed = make_embed("Please choose an option to start")
        await interaction.response.send_message(embed=embed, view=ComponentView())


async def run_bot():
    assert_envs_exist()
    token = os.environ['TOKEN']
    intents = discord.Intents.none()
    intents.messages = True
    intents.guilds = True
    bot = commands.Bot(
        intents=intents,
        command_prefix=commands.when_mentioned,
        slash_commands=True,
    )
    async with bot:
        await bot.add_cog(CoreCog(bot))
        await bot.add_cog(ExampleCog(bot))
        await bot.start(token)


if __name__ == "__main__":
    asyncio.run(run_bot())