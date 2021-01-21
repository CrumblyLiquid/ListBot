# General discord imports
import discord
from discord.ext import commands

# General bot imports
from time import sleep
from pathlib import Path
from os import makedirs, path as ospath
from json import load as jsonload
import logging

# List imports
from random import randint

# Error handler imports
from sys import stderr
from traceback import print_exception

# Database imports
import sqlite3 as sql
import aiosqlite as asql
import asyncio

class DB():
    def __init__(self, path):
        self.path = path
        self.dbname = str(path).split("/")[-1].split("\\")

        self.connect()

    def connect(self, path = None):
        if path is None:
            path = self.path
        else:
            self.path = path
            self.dbname = str(path).split("/")[-1].split("\\")
        self.connection = sql.connect(path)
        self.cursor = self.connection.cursor()

    def execute(self, command, args=None, commit = False):
        if args == None:
            self.cursor.execute(command)
        else:
            self.cursor.execute(command, args)
        if commit == True:
            self.connection.commit()

    def fetchone(self):
        return self.cursor.fetchone()

    def fetchall(self):
        return self.cursor.fetchall()

    def commit(self):
        self.connection.commit()

    def close(self):
        self.connection.close()

class aDB():
    def __init__(self, bot, path):
        self.bot = bot
        self.path = path
        self.dbname = str(path).split("/")[-1].split("\\")

        self.bot.loop.create_task(self.connect())

    async def connect(self, path = None):
        if path is None:
            path = self.path
        else:
            self.path = path
            self.dbname = str(path).split("/")[-1].split("\\")

        self.connection = await asql.connect(path)
        self.cursor = await self.connection.cursor()

    async def execute(self, command, args=None, commit = False):
        if args == None:
            await self.cursor.execute(command)
        else:
            await self.cursor.execute(command, args)
        if commit == True:
            await self.connection.commit()

    async def fetchone(self):
        return await self.cursor.fetchone()

    async def fetchall(self):
        return await self.cursor.fetchall()

    async def commit(self):
        await self.connection.commit()

    async def close(self):
        await self.connection.close()

# Load config
class Config:
    def __init__(self, path=None):
        if path is None:
            path = Path(__file__).parent.absolute()/"config.json"
        self.path = path
        self.load()

    def load(self):
        # Tries to load config file
        try:
            with open(self.path, "r") as file:
                config = jsonload(file)
        # If it fails it will print error and end itself.
        except FileNotFoundError as e:
            print(f"Config file not found!\n{e}")
            sleep(2)
            print("Exiting...")
            sleep(7)
            quit()
        try:
            self.token = config["token"]
            if self.token == "":
                print("No token found!")
                sleep(2)
                print("Exiting...")
                sleep(7)
                quit()
            self.prefix = config["prefix"]
            if self.prefix == "":
                self.prefix = "!"
        except KeyError as e:
            print(f"{e} is missing in config!")
            sleep(2)
            print("Exiting...")
            sleep(7)
            quit()

# Custom help implementation
class CustomHelp(commands.HelpCommand):
    def get_command_signature(self, command):
        return "%s%s %s" % (self.clean_prefix, command.qualified_name, command.signature)

    async def send_bot_help(self, mapping):
        embed = discord.Embed(title="ListBot Help")
        embed.set_footer(text="Made with <3 by Jaro#5648")
        for cog, commands in mapping.items():
           filtered = await self.filter_commands(commands, sort=True)
           command_signatures = [self.get_command_signature(c) for c in filtered]
           if command_signatures:
                cog_name = getattr(cog, "qualified_name", "No Category")
                embed.add_field(name=cog_name, value="\n".join(command_signatures), inline=False)

        channel = self.get_destination()
        await channel.send(embed=embed)

# Custom bot class
class CBot(commands.Bot):
    def __init__(self, help_command=None, description=None, intents=discord.Intents.default(), **options):
        # Load config
        self.config = Config()
        super().__init__(command_prefix=self.config.prefix, help_command=help_command, description=description, intents=intents, **options)

        # Initialize the original bot instance
        # super().__init__(
        # command_prefix=self.config.prefix,
        # help_command=help_cmd,
        # intents=intents,
        # description="Discord.py bot used for saving lists")

        # Logging | Logs discords internal stuff
        self.logger = logging.getLogger("discord")
        self.logger.setLevel(logging.DEBUG)
        self.handler = logging.FileHandler(filename="bot.log", encoding="utf-8", mode="w")
        self.handler.setFormatter(logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s"))
        self.logger.addHandler(self.handler)

        self.filepath = Path(__file__).parent.absolute()

        self.dbname = "SQLite.sql"
        self.dbfolder = self.filepath/"db"
        self.dbpath = self.filepath/"db"/self.dbname

        try:
            if not ospath.exists(self.dbfolder):
                makedirs(self.dbfolder)
                print(f"[OK]: Created folder 'db'.")
        except OSError as error:
            print(f"Error while creating {self.dbfolder}: ", error)

        # Create DB connection instances
        self.DB = DB(self.dbpath) # synchronous instance
        self.aDB = aDB(self, self.dbpath) # asynchronous instance

        # Create table needed for storing lists, lists are separated by `;`
        self.DB.execute("CREATE TABLE IF NOT EXISTS lists (id INTEGER PRIMARY KEY, guild_id INTEGER, name TEXT, list TEXT)", commit=True)

    #     self.loop.create_task(self.setup_func())

    # async def setup_func(self):
    #     await self.wait_until_ready()

    async def close(self):
        self.DB.close()
        await self.aDB.close()
        await super().close()

    # Will fetch list from DB
    async def lists_get_list(self, id: int, name: str):
        await self.aDB.execute("SELECT list FROM lists WHERE guild_id=? AND name=?", (id, name))
        result = await self.aDB.fetchone()
        if result == (): return None
        result = result[0]
        return result

    # Will parse list(str) into list(list)
    async def lists_parse_list(self, list: str):
        return list.split(";")

    # Will fetch parsed list
    async def lists_get_parsed_list(self, id: int, name: str):
        result = await self.lists_get_list(id, name)
        return await self.lists_parse_list(result)

    # Will fetch all lists for certain guild
    async def lists_get_lists(self, id: int):
        await self.aDB.execute("SELECT name FROM lists WHERE guild_id=?", (id, ))
        result = await self.aDB.fetchall()
        if result == []: return ["No lists found."]
        res = []
        for tuple in result:
            res.append(tuple[0])
        return res

# Setup the help command
attributes = {
    "cooldown": commands.Cooldown(2, 5.0, commands.BucketType.user),
}
help_cmd = CustomHelp(command_attrs=attributes)

# Create intents
intents = discord.Intents(messages=True, guilds=True)

# Create new bot instance | Note: don't register help command - it's broken
bot = CBot(help_command=None, description="Discord.py bot used for saving lists", intents=intents)

@bot.event
async def on_ready():
    print("Bot ready.\nLogged in as {0}".format(bot.user))

@bot.group(name="list", aliases=["l", "li", "lists"])
async def _list_(ctx):
    if ctx.invoked_subcommand is None:
        if ctx.guild is None:
            id = ctx.author.id
        else:
            id = ctx.guild.id
        lists = await bot.lists_get_lists(id)
        title = f"Lists:"
        description = f"**Available lists:**\n- " + "\n- ".join(lists)
        footer = "Made with <3 by Jaro#5648"
        embed = discord.Embed(title=title, description=description, color=discord.Color.dark_gold())
        embed.set_footer(text=footer)
        await ctx.send(embed=embed)

@_list_.command(aliases=["c", "m", "make"])
async def create(ctx, name: str, *,list: str):
    if ctx.guild is None:
        id = ctx.author.id
    else:
        id = ctx.guild.id
    await bot.aDB.execute("INSERT INTO lists (guild_id, name, list) VALUES(?,?,?)", (id, name, list), commit=True)
    lists = await bot.lists_get_lists(id)
    title = f"List {name} created!"
    description = "**Available lists:**\n- " + "\n".join(lists)
    footer = "Made with <3 by Jaro#5648"
    embed = discord.Embed(title=title, description=description, color=discord.Color.dark_gold())
    embed.set_footer(text=footer)
    await ctx.send(embed=embed)

@_list_.command(aliases=["d", "r", "remove"])
async def delete(ctx, name: str):
    if ctx.guild is None:
        id = ctx.author.id
    else:
        id = ctx.guild.id
    await bot.aDB.execute("DELETE FROM lists WHERE guild_id=? AND name=?", (id, name), commit=True)
    lists = await bot.lists_get_lists(id)
    title = f"List {name} deleted!"
    description = "**Available lists:**\n- " + "\n".join(lists)
    footer = "Made with <3 by Jaro#5648"
    embed = discord.Embed(title=title, description=description, color=discord.Color.dark_gold())
    embed.set_footer(text=footer)
    await ctx.send(embed=embed)


@_list_.command(aliases=["p", "ch", "choose"])
async def pick(ctx, name: str, amount: int = 1):
    if ctx.guild is None:
        id = ctx.author.id
    else:
        id = ctx.guild.id
    list = await bot.lists_get_parsed_list(id, name)
    if list is None:
        e = discord.Embed(title=f"List: {name}", description="Invalid list name.")
        return await ctx.send(e)
    temp_list = []
    temp_list += list
    picked = []
    for i in range(amount):
        if len(temp_list) == 0:
            temp_list += list
        index = randint(0, len(temp_list)-1)
        picked.append(temp_list[index])
        temp_list.pop(index)

    title = f"List: {name}"
    # description = f"**Available picks:**\n- " + "\n- ".join(list) + "\n**Picked:**\n- " + "\n- ".join(picked)
    description = f"**Picked:**\n- " + "\n- ".join(picked)
    footer = "Made with <3 by Jaro#5648"
    embed = discord.Embed(title=title, description=description, color=discord.Color.dark_gold())
    embed.set_footer(text=footer)
    await ctx.send(embed=embed)

# Simple error handler
@commands.Cog.listener()
async def on_command_error(ctx, error):
    # Don"t hadnle commands that have their own error handlers
    if hasattr(ctx.command, "on_error"):
        return

    # Get the error
    error = getattr(error, "original", error)

    # Ignored exceptions go here
    ignored = ()

    # Ignore exceptions here
    if isinstance(error, ignored):
        return

    # Handle general exceptions
    elif isinstance(error, commands.DisabledCommand):
        return await ctx.send(f"This command is disabled. Try again later")

    elif isinstance(error, commands.CommandOnCooldown):
        return await ctx.send(f"Command is on cooldown. Timeout: {round(error.retry_after)}sec")

    elif isinstance(error, commands.CommandNotFound):
        return await ctx.send(f"Command not found.")

    elif isinstance(error, commands.MissingRequiredArgument):
        return await ctx.send(f"Missing argument.")

    elif isinstance(error, commands.TooManyArguments):
        return await ctx.send(f"Too many arguments!")

    elif isinstance(error, commands.BadArgument):
        return await ctx.send(f"Invalid argument.")

    # Print stacktrace
    print("Ignoring exception in command {}:".format(ctx.command), file=stderr)
    print_exception(type(error), error, error.__traceback__, file=stderr)

# Start up the bot
bot.run(bot.config.token)