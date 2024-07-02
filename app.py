import os
import discord
from keycloak import KeycloakAdmin


KeycloakClient = KeycloakAdmin(
            server_url=os.environ["KEYCLOAK_URL"],
            username=os.environ["KEYCLOAK_USERNAME"],
            password=os.environ["KEYCLOAK_PASSWORD"],
            realm_name=os.environ["KEYCLOAK_REALM"],
            user_realm_name=os.environ["KEYCLOAK_ADMIN_REALM"])


# We require the Members intent to receive updates to role membership
intents = discord.Intents.default()
intents.members = True

DiscordClient = discord.Client(intents=intents)


def get_linked_groups(client: KeycloakAdmin = None) -> list:
    """
    Get all Keycloak groups that have the required attributes for linking to a Discord role
    :param client: A KeycloakAdmin instance configured for your realm
    :rtype: list
    :return: A list of groups with the required attributes
    """

    # Keycloak paginates the response on the Admin API endpoints
    # Therefore, we'll need to make sure we grab every group
    page_start = 0
    page_size = 100
    all_groups = []

    # Grab the first page of groups and add them to the list of groups
    # We're setting briefRepresentation to false, so it'll return the groups' attributes
    # These will be useful later on
    groups = client.get_groups(
        query={"briefRepresentation": "false",
               "first": page_start,
               "max": page_size}
    )
    all_groups += groups

    # Check if the size of the page matches what page size we asked for
    # If it does, request the next page and add them to the list of groups
    # Keep going until the page size doesn't match the requested page size
    while len(groups) == page_size:
        page_start += page_size
        groups = client.get_groups(
            query={"briefRepresentation": "false",
                   "first": page_start,
                   "max": page_size}
        )
        all_groups += groups

    # Create a list of all groups with the required Keycloak attributes
    valid_groups = []

    for group in all_groups:
        try:
            if group["attributes"]["discord-guild"] and group["attributes"]["discord-role"]:
                valid_groups.append(group)
        except KeyError:

            # If the group doesn't have the required attributes, it'll throw a KeyError
            # We can just catch and kill the error :)
            pass

    return valid_groups


def get_linked_role(client: discord.client.Client = None, group: dict = None) -> discord.Role | None:
    """
    Get the Discord role that is linked to a Keycloak group
    :param client: A Discord Client instance
    :param group: A dict containing a Keycloak group with attributes `discord-guild` and `discord-role`
    :rtype: discord.Role | None
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


def get_group_members(client: KeycloakAdmin = None, group_id: str = None) -> list:
    """
    Get the users that are in the Keycloak group
    :param client: A :class:`KeycloakAdmin` client
    :param group_id: A :class:`str` with the group's UUID in Keycloak
    :rtype: list
    :return: A :class:`list` containing all users in the group
    """

    # See comments in the get_linked_groups function for how we're handling Keycloak's Admin API pagination
    page_start = 0
    page_size = 100
    members = []

    group_members = client.get_group_members(
        group_id=group_id,
        query={"first": page_start, "max": page_size}
    )
    members += group_members

    while len(group_members) == page_size:
        page_start += page_size
        group_members = client.get_group_members(
            group_id=group_id,
            query={"first": page_start, "max": page_size}
        )
        members += group_members

    return members


def get_discord_id(client: KeycloakAdmin = None, user_id: str = None) -> int:
    """
    Gets the Discord ID from the user's Keycloak profile
    This only works if the Keycloak realm has Discord set up
    as an Identity provider.
    :param client: A KeycloakAdmin client
    :param user_id: The user's UUID in Keycloak
    :rtype: int
    :return: The user's Discord ID
    """

    profile = client.get_user(user_id=user_id)
    discord_id = None

    for provider in profile["federatedIdentities"]:
        if provider["identityProvider"] == "discord":
            discord_id = provider["userId"]

    if not discord_id:
        raise Exception("Cannot find Github username")

    return int(discord_id)


@DiscordClient.event
async def on_ready():
    print(f'We have logged in as {DiscordClient.user}')

    groups = get_linked_groups(client=KeycloakClient)

    for group in groups:
        role = get_linked_role(client=DiscordClient, group=group)
        if not role:
            continue

        print(f'Syncing Keycloak group {group["name"]} with Discord role {role.name}')
        group_members = get_group_members(client=KeycloakClient, group_id=group["id"])

        # Add users to the Keycloak group if they're a part of the Discord role
        for discord_user in role.members:
            keycloak_user = KeycloakClient.get_users(
                query={"idpUserId": discord_user.id, "idpAlias": "discord"})

            if len(keycloak_user) == 0:
                continue

            if keycloak_user[0]["id"] in [user["id"] for user in group_members]:
                continue

            print("Adding %s (%s) to Keycloak group %s" % (
                    keycloak_user[0]["username"], discord_user.global_name, group["name"]))

            KeycloakClient.group_user_add(user_id=keycloak_user[0]["id"], group_id=group["id"])

        # Remove users from the Keycloak group if they're not a part of the Discord role
        for keycloak_user in group_members:
            discord_id = get_discord_id(client=KeycloakClient, user_id=keycloak_user["id"])
            discord_user = DiscordClient.get_guild(role.guild.id).get_member(discord_id)

            if discord_user.id not in [user.id for user in role.members]:
                print("Removing %s (%s) from Keycloak group %s" % (
                        keycloak_user["username"], discord_user.global_name, group["name"]))

                KeycloakClient.group_user_remove(user_id=keycloak_user["id"], group_id=group["id"])


@DiscordClient.event
async def on_member_update(previous, current):
    if current.id == DiscordClient.user.id:
        return

    # Create sets of the roles a user previously had and currently has
    # Makes it easy to check for differences between the two
    previous_roles = set(previous.roles)
    current_roles = set(current.roles)

    # If a role exists in the current set but not the previous set, it was added
    added_roles = current_roles.difference(previous_roles)

    # If a role existed in the previous set but not the current set, it was removed
    removed_roles = previous_roles.difference(current_roles)

    # If the sets are the same, the member update was for something else
    if current_roles == previous_roles:
        return

    keycloak_user = KeycloakClient.get_users(
        query={"idpUserId": previous.id, "idpAlias": "discord"})

    # If there isn't a Keycloak user, we can't really action anything
    # They should've been cleaned up in the sync performed at launch
    if len(keycloak_user) == 0:
        return

    # Process all Discord roles the user has been added to
    if len(added_roles) > 0:
        for role in added_roles:
            keycloak_group = KeycloakClient.get_groups(
                query={"q": "discord-role:%s" % role.id, "exact": "true"})

            print('Adding %s (%s) to Keycloak group %s' % (
                    keycloak_user[0]["username"], current.global_name, keycloak_group[0]["name"]))

            KeycloakClient.group_user_add(user_id=keycloak_user[0]["id"], group_id=keycloak_group[0]["id"])

    # Process all Discord roles the user was removed from
    if len(removed_roles) > 0:
        for role in removed_roles:
            keycloak_group = KeycloakClient.get_groups(
                query={"q": "discord-role:%s" % role.id, "exact": "true"})

            print('Removing %s (%s) from Keycloak group %s' % (
                    keycloak_user[0]["username"], current.global_name, keycloak_group[0]["name"]))

            KeycloakClient.group_user_remove(user_id=keycloak_user[0]["id"], group_id=keycloak_group[0]["id"])


DiscordClient.run(os.environ["DISCORD_BOT_TOKEN"])
