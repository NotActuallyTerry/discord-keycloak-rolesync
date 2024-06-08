import os

# TODO: idiot proof everything

from dotenv import load_dotenv
import discord
from keycloak import KeycloakAdmin

load_dotenv()

KeycloakClient = KeycloakAdmin(
            server_url=os.environ["KEYCLOAK_URL"],
            username=os.environ["KEYCLOAK_USERNAME"],
            password=os.environ["KEYCLOAK_PASSWORD"],
            realm_name=os.environ["KEYCLOAK_REALM"],
            user_realm_name=os.environ["KEYCLOAK_ADMIN_REALM"])


intents = discord.Intents.default()
intents.members = True
intents.message_content = True

DiscordClient = discord.Client(intents=intents)


def get_linked_groups(client: KeycloakAdmin = None):
    """
    Get all Keycloak groups that have the required attributes for linking to a Discord role
    :param client: A KeycloakAdmin instance configured for your realm
    :return: A list of groups with the required attributes
    """

    all_groups = client.get_groups(query={"briefRepresentation": "false"})
    valid_groups = []

    for group in all_groups:
        try:
            if group["attributes"]["discord-guild"] and group["attributes"]["discord-role"]:
                valid_groups.append(group)
        except KeyError:
            # TODO: add comment
            pass

    return valid_groups


def get_linked_role(client: discord.client.Client = None, group: dict = None):
    """
    Get the Discord role that is linked to a Keycloak group
    :param client: A Discord Client instance
    :param group: A dict containing a Keycloak group with attributes `discord-guild` and `discord-role`
    :return: The Discord role linked to the provided Keycloak group
    """

    guild_id = int(group["attributes"]["discord-guild"][0])
    role_id = int(group["attributes"]["discord-role"][0])

    guild = client.get_guild(guild_id)
    if guild is None:
        return None

    role = guild.get_role(role_id)
    if role is None:
        return None

    return role


@DiscordClient.event
async def on_ready():
    print(f'We have logged in as {discord.user}')

    groups = get_linked_groups(KeycloakClient)

    for group in groups:
        print(group)

        role = get_linked_role(client=DiscordClient, group=group)

        for member in role.members:
            keycloak_user = KeycloakClient.get_users(
                query={"idpUserId": member.id, "idpAlias": "discord"})

            if len(keycloak_user) == 0:
                continue

            await role.guild.text_channels[0].send(
                "%s (%s) should be in keycloak group %s" % (
                    keycloak_user[0]["username"], member.global_name, group["name"]))


@DiscordClient.event
async def on_message(message):
    if message.author == DiscordClient.user:
        return

    if message.content.startswith('$hello'):
        await message.channel.send('Hello!')


@DiscordClient.event
async def on_member_update(old, new):
    if old.id == DiscordClient.user.id:
        return

    old_roles = set(old.roles)
    new_roles = set(new.roles)

    added_roles = new_roles.difference(old_roles)
    removed_roles = old_roles.difference(new_roles)

    if new_roles == old_roles:
        return

    keycloak_user = KeycloakClient.get_users(
        query={"idpUserId": old.id, "idpAlias": "discord"})

    if len(keycloak_user) == 0:
        return

    if len(added_roles) > 0:
        for role in added_roles:
            keycloak_group = KeycloakClient.get_groups(
                query={"q": "discord-role:%s" % role.id, "exact": "true"})
            await old.guild.text_channels[0].send(
                'hell yea %s get keycloak role %s' % (keycloak_user[0]["username"], keycloak_group[0]["name"]))

    if len(removed_roles) > 0:
        for role in removed_roles:
            keycloak_group = KeycloakClient.get_groups(
                query={"q": "discord-role:%s" % role.id, "exact": "true"})
            await old.guild.text_channels[0].send(
                'haha %s get demoted from %s idiot' % (keycloak_user[0]["username"], keycloak_group[0]["name"]))


DiscordClient.run(os.environ["DISCORD_BOT_TOKEN"])
