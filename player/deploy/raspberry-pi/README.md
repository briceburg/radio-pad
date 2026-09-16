# Raspberry Pi provisioning

This auxiliary Ansible project turns a Raspberry Pi OS Lite host into a supervised RadioPad player. It installs the runtime under `/opt/radio-pad`, synchronizes the locked player environment, writes the player configuration, and enables `radiopad-player.service`. Re-running it updates or repairs the declared configuration rather than layering another startup mechanism on the device.

The service uses `DynamicUser=yes`, so it has no persistent login account or password. systemd gives its transient `radiopad-player` identity access to the existing `audio` and `dialout` groups for ALSA and the USB Macropad. A separate `radiopad` administrator exists only for SSH maintenance and provisioning.

## Quick start

Run both helpers from the repository root. The workstation needs Linux, Raspberry Pi Imager, and `uv`; each helper checks its remaining prerequisites. These commands use the checked-in Cañones deployment as a worked example, not as a required hostname or registry naming convention.

1. Attach an unmounted SD card and run `player/bin/rpi-flash radio-canones`.
2. Move the card to the Pi, connect Ethernet, and power it on.
3. Run `player/bin/rpi-provision --wifi SpringSong radio-canones`.

The provisioner reads the host, registered player identity, and DAC output from `inventory.yml`; it prompts locally for the Wi-Fi passphrase. It validates the registry identity and audio device, installs and configures the player, starts its systemd service, and waits for the player to report ready. Omit `--wifi SpringSong` when Ethernet is sufficient; Wi-Fi can be added later without reflashing.

## Flash Raspberry Pi OS Lite

### Automated flash

On Linux, `rpi-flash` writes and verifies a pinned official Raspberry Pi OS Lite 64-bit image. It supports Raspberry Pi 3, 4, 5, and Zero 2 W-class hardware. Original Pi Zero/W and Pi 1 devices require a 32-bit image and are not currently supported by this player workflow.

Create an SSH key once if the workstation does not already have one, attach the SD card, and leave it unmounted:

```sh
ssh-keygen -t ed25519
player/bin/rpi-flash radio-kitchen
```

The helper uses the first SSH-agent identity, falling back to a standard `~/.ssh/*.pub` key, and detects the target when exactly one removable disk of at least 4 GB is present. Use `--ssh-key` or `--device` to override an ambiguous default. It inherits the workstation locale, time zone, and keyboard layout, derives the Wi-Fi regulatory country from the locale, and falls back to `en_US.UTF-8`, `UTC`, `us`, and `US`; use the corresponding options to override them. The country is configured even for an Ethernet-first flash so Wi-Fi is not rfkill-blocked later. Add `--wifi` for a Wi-Fi-only player; the helper prompts without echoing the passphrase and keeps Ethernet DHCP enabled as a fallback:

```sh
player/bin/rpi-flash --wifi --device /dev/sdX radio-kitchen
```

Before writing, the helper validates its tools, network access, SSH key, hostname, and target type, size, write state, and mounts. It prints the resolved disk and requires its full device path as confirmation. Raspberry Pi Imager verifies both the pinned image checksum and the completed write.

The generated first-boot configuration creates a key-only `radiopad` administrator with passwordless sudo, disables console auto-login, selects the headless boot target, and inherits the workstation time zone. Passwordless sudo enables unattended Ansible provisioning; access to the private SSH key is therefore equivalent to root access on the player.

### Raspberry Pi Imager GUI

As a manual alternative, open [Raspberry Pi Imager](https://www.raspberrypi.com/software/) and make these selections:

1. Select the exact Pi model under **Device**.
2. Under **OS**, choose **Raspberry Pi OS (other)** and then **Raspberry Pi OS Lite (64-bit)**. Use Lite (32-bit) only for a model without 64-bit support. Do not choose the desktop image when boot time and footprint are priorities.
3. Select the storage device and open **OS Customisation**.
4. Set a hostname such as `radio-kitchen`, create the administrative user `radiopad`, and configure the correct locale, time zone, keyboard layout, and Wi-Fi country.
5. Configure Wi-Fi only when Ethernet will not be used.
6. Enable SSH with public-key authentication.
7. Enable passwordless sudo and disable console auto-login when those options are available. Otherwise, pass `--ask-become-pass` to the provisioning helper.

Boot the Pi and proceed directly to provisioning. You can start the command while a newly flashed Pi is still booting; it waits up to five minutes for SSH. For an existing password-only installation, run `ssh-copy-id USER@HOST`. The playbook also selects `multi-user.target` by default, so an existing desktop installation boots without its GUI after the next reboot; reflashing with Lite still produces the leanest installation.

## Register and provision a player

Provisioning consumes an existing registry identity; it does not create shared registry data. While the registry API and clients are still evolving, add players through the registry-data workflow. [The PR that registered Cañones](https://github.com/briceburg/radio-pad-registry-data/pull/1) is the concrete onboarding example; it added `data/accounts/briceburg/players/canones.json`:

```json
{
  "name": "Cañones",
  "radio_dial": "community/briceburg",
  "switchboard_url": null
}
```

The display name may contain `ñ`, while the qualified player identity uses lowercase registry slugs. Check that deployed registry data is available before provisioning:

```sh
curl --fail https://registry.radiopad.dev/api/accounts/briceburg/players/canones
```

The checked-in inventory completes the Cañones deployment definition without storing credentials:

```yaml
radio-canones:
  ansible_host: radio-canones.lan
  radiopad_player: briceburg/canones
  radiopad_audio_device: alsa/default:CARD=DAC
```

Provision it by inventory name:

```sh
player/bin/rpi-provision --wifi SpringSong radio-canones
```

For a new host that is not yet in inventory, provide its registered identity explicitly, then add its durable non-secret configuration to `inventory.yml`:

```sh
player/bin/rpi-provision --player ACCOUNT/PLAYER HOSTNAME.local
```

Use `USER@HOST` only for a nonstandard existing installation and `--audio-device DEVICE` for a one-run audio override. The helper uses `uvx` to run pinned Ansible Core and collection versions, requires SSH public-key authentication, accepts and records only a previously unknown host key, and expects passwordless sudo by default. Add `--ask-become-pass` for an account that requires a sudo password. A changed host key still fails closed and should be removed from `known_hosts` only after confirming that the device was intentionally reflashed.

SSH remains key-only by default. To add a persistent password fallback for the `radiopad` administrator, use `player/bin/rpi-provision --ssh-password HOST`; the helper prompts twice without echoing the password, keeps public-key access enabled, and does not impose a password-strength policy. Because `radiopad` has passwordless sudo, treat this password as a root credential.

Wi-Fi can also be added later over Ethernet without reflashing. Each `--wifi SSID` run adds or updates that network's autoconnect profile without removing existing profiles, so repeat the command for every deployment or fallback network. If the requested SSID is visible, provisioning activates it as a connectivity check; otherwise, provisioning stages it for NetworkManager to connect when it becomes available. The helper prompts locally without echoing the passphrase, stores it only in a mode-0600 temporary Ansible variables file, and keeps Ethernet enabled.

The country defaults from the workstation locale; add `--wifi-country CC` only when that default is wrong for the Pi's location.

The initial run installs system packages, a pinned `uv`, and Python 3.13, so it can take a few minutes. The locked player environment includes yt-dlp and its Deno JavaScript runtime for site URLs such as YouTube; mpv handles direct streams and playlists itself. Later runs fast-forward a clean checkout, reconcile configuration, and restart the player only when managed content changes. Ansible refuses to overwrite local changes under `/opt/radio-pad`.

## Configure several players

Add each Pi's hostname, registered identity, and hardware-specific settings to `inventory.yml`. Keep secrets out of the plain inventory: continue using the wrapper's Wi-Fi prompt for one host, or use Ansible Vault for persistent fleet credentials. Run every inventoried player directly with:

```sh
cd player/deploy/raspberry-pi
uvx --from ansible-core==2.21.4 ansible-galaxy collection install --requirements-file requirements.yml
uvx --from ansible-core==2.21.4 ansible-playbook playbook.yml
```

Add `--ask-become-pass` only when an inventory administrator requires a sudo password. Limit a fleet run with `--limit HOST`.

The playbook accepts these inventory variables:

| Name | Purpose | Default |
| --- | --- | --- |
| `radiopad_player` | Required `account/player` registry identity. | none |
| `radiopad_audio_device` | Optional device reported by `mpv --no-config --audio-device=help`; provisioning verifies it exists. | unset |
| `radiopad_audio_output` | mpv audio driver. | `alsa` |
| `radiopad_extra_environment` | Additional or overriding player environment mapping. | `{}` |
| `radiopad_headless` | Make `multi-user.target` the default boot target. | `true` |
| `radiopad_repo_url` | Git repository installed on the Pi. | RadioPad GitHub repository |
| `radiopad_repo_version` | Branch or tag to deploy. | `main` |
| `radiopad_registry_url` | Registry API used by validation and the player. | RadioPad production registry |
| `radiopad_ssh_password_hash` | Optional hashed `radiopad` password that also enables SSH password authentication; use Ansible Vault in persistent inventories. | unset |
| `radiopad_wifi_country` | Two-letter regulatory country when configuring Wi-Fi. | unset |
| `radiopad_wifi_password` | WPA passphrase; use Ansible Vault in persistent inventories. | unset |
| `radiopad_wifi_ssid` | One Wi-Fi profile to add or update alongside Ethernet and existing profiles. | unset |

## Operate, update, and troubleshoot

The player is independent of SSH sessions, shell startup files, and console auto-login. Its checkout includes one small service helper. Bare `bin/player` still runs the player in the foreground on any development host; service commands require root, a running systemd instance, and a `radiopad-player.service` whose working directory is that exact checkout. From a workstation, replace `HOST` with the Pi's DNS/mDNS name or DHCP address, then inspect its status, read recent logs, or follow logs live:

```sh
ssh -t radiopad@HOST 'sudo /opt/radio-pad/player/bin/player status'
ssh -t radiopad@HOST 'sudo /opt/radio-pad/player/bin/player logs'
ssh -t radiopad@HOST 'sudo /opt/radio-pad/player/bin/player logs --follow'
```

Routine code updates do not require Ansible or the provisioning workstation. The on-device updater refuses a dirty or detached checkout, fast-forwards its current branch from `origin`, synchronizes the locked environment, restarts the service, and waits for readiness:

```sh
ssh -t radiopad@HOST 'sudo /opt/radio-pad/player/bin/player update'
```

Use `player/bin/rpi-provision HOST` from a workstation for inventory, operating-system, service, credential, or updater changes. Configuration is owned by the inventory and rendered to `/etc/radiopad/player.env`; do not edit the Pi or run `git pull` there directly. To request an immediate managed restart, use the helper's `restart` command.

A single `Player already connected` message immediately after a restart can be the switchboard releasing the previous connection; the player reconnects automatically. Repeated messages mean another process or device is using the same player identity.

On an older manually configured Pi, remove the `.bashrc` block and stop the tmux player before provisioning so two players do not compete for audio or the same switchboard identity. In headless mode the playbook also removes Raspberry Pi OS's standard tty1 auto-login override.

To inspect ALSA card names before choosing an mpv device, run `ssh radiopad@HOST cat /proc/asound/cards`. For example, the Cañones Raspberry Pi DAC Plus HAT registers as card `DAC`, corresponding to `alsa/default:CARD=DAC`.

## Why not a custom image?

Raspberry Pi Imager plus Ansible keeps the standard Raspberry Pi OS image and gives both first-install and ongoing-update workflows. [`rpi-image-gen`](https://github.com/raspberrypi/rpi-image-gen) becomes worthwhile when provisioning must work offline, the base filesystem itself needs customization, or many identical devices should be manufactured from one reproducible image. It is intentionally not required by this auxiliary tool.
