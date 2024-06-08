import os

# TODO: idiot proof everything

from dotenv import load_dotenv
import discord
from keycloak import KeycloakAdmin

load_dotenv()

keycloak = KeycloakAdmin(
            server_url=os.environ["KEYCLOAK_URL"],
            username=os.environ["KEYCLOAK_USERNAME"],
            password=os.environ["KEYCLOAK_PASSWORD"],
            realm_name=os.environ["KEYCLOAK_REALM"],
            user_realm_name=os.environ["KEYCLOAK_ADMIN_REALM"])


intents = discord.Intents.default()
intents.members = True
intents.message_content = True

discord = discord.Client(intents=intents)


def get_linked_groups(client: KeycloakAdmin = None):
    """
    Get all Keycloak groups that have the required attributes for linking to a Discord role
    :param client: A KeycloakAdmin instance configured for your realm
    :return: A list of groups with the required attributes
    """

    groups = []

    for group in keycloak.get_groups(query={"briefRepresentation": "false"}):
        try:
            if group["attributes"]["discord-guild"] and group["attributes"]["discord-role"]:
                groups.append(group)
        except KeyError:
            # TODO: add comment
            pass

    return groups


@discord.event
async def on_ready():
    print(f'We have logged in as {discord.user}')

    groups = get_linked_groups(keycloak)

    for group in groups:
        print(group)
        guild = discord.get_guild(int(group["attributes"]["discord-guild"][0]))
        if guild is None:
            continue

        role = guild.get_role(int(group["attributes"]["discord-role"][0]))
        if role is None:
            continue

        for member in role.members:
            keycloak_user = keycloak.get_users(
                query={"idpUserId": member.id, "idpAlias": "discord"})

            if len(keycloak_user) == 0:
                continue

            await guild.text_channels[0].send(
                "%s (%s) should be in keycloak group %s" % (
                    keycloak_user[0]["username"], member.global_name, group["name"]))


@discord.event
async def on_message(message):
    if message.author == discord.user:
        return

    if message.content.startswith('$hello'):
        await message.channel.send('Hello!')


@discord.event
async def on_member_update(old, new):
    if old.id == discord.user.id:
        return

    old_roles = set(old.roles)
    new_roles = set(new.roles)

    added_roles = new_roles.difference(old_roles)
    removed_roles = old_roles.difference(new_roles)

    if new_roles == old_roles:
        return

    keycloak_user = keycloak.get_users(
        query={"idpUserId": old.id, "idpAlias": "discord"})

    if len(keycloak_user) == 0:
        return

    if len(added_roles) > 0:
        for role in added_roles:
            keycloak_group = keycloak.get_groups(
                query={"q": "discord-role:%s" % role.id, "exact": "true"})
            await old.guild.text_channels[0].send(
                'hell yea %s get keycloak role %s' % (keycloak_user[0]["username"], keycloak_group[0]["name"]))

    if len(removed_roles) > 0:
        for role in removed_roles:
            keycloak_group = keycloak.get_groups(
                query={"q": "discord-role:%s" % role.id, "exact": "true"})
            await old.guild.text_channels[0].send(
                'haha %s get demoted from %s idiot' % (keycloak_user[0]["username"], keycloak_group[0]["name"]))


discord.run(os.environ["DISCORD_BOT_TOKEN"])
