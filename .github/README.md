# Discord Roles to Keycloak Groups sync

This is a python application that will sync Discord Roles to Keycloak Groups.

For this to work you need to:
1. Implement the [Discord Keycloak Identity Provider](https://github.com/wadahiro/keycloak-discord)
2. Set up the Keycloak groups you'd like to sync with the following attributes:
   - `discord-role` containing the ID of the role (requires dev mode for Discord to be enabled)
   - `discord-guild` containing the ID of the guild the role is in
3. Create a Keycloak user with Admin API access
   - If you have fine-grained authz enabled, provide the account with the  `view-users` & `manage-users` roles
4. Create a Discord Application ([here](https://discord.com/developers/applications)) & add the bot to your server.
   - Make sure it has the Server Members intent, otherwise it won't receive role membership updates

## Example config

```yaml
      DISCORD_BOT_TOKEN: MZ1yGvKTjE0rY0cV8i47CjAa.uRHQPq.Xb1Mk2nEhe-4iUcrGOuegj57zMC
      KEYCLOAK_URL: https://keycloak.example.com
      KEYCLOAK_USERNAME: KeycloakUsername
      KEYCLOAK_PASSWORD: KeycloakPassword
      KEYCLOAK_REALM: Example-Corp
      # Only required if KeycloakUsername isn't an account under the Example-Corp realm
      KEYCLOAK_ADMIN_REALM: master
```
