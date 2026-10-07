# Raspberry Pi provisioning

Install a [RadioPad player](../../) under `/opt/radio-pad` with Ansible and systemd. Provisioning starts the service immediately and enables it at boot; no console login is needed.

`radiopad` is the SSH administrator with passwordless sudo. Playback runs as a separate, transient systemd user with audio and USB access.

## Quick start

Run commands from the repository root on a workstation with [uv](https://docs.astral.sh/uv/). Flashing also requires Linux and [Raspberry Pi Imager](https://www.raspberrypi.com/software/). Use Raspberry Pi OS Lite (64-bit) and an [8 GB or larger SD card](https://www.raspberrypi.com/documentation/computers/getting-started.html#recommended-minimum-storage-requirements). Pi 1 and original Zero/W models are unsupported.

For the registered [Cañones example](#register-and-provision-a-player):

1. Attach an unmounted SD card and run `player/bin/rpi-flash radio-canones`.
2. Move the card to the Pi, connect Ethernet, and power it on.
3. Run `player/bin/rpi-provision radio-canones`.

Add `--wifi` when flashing without Ethernet. Already have an OS and SSH? [Use the existing installation](#use-an-existing-installation) without reflashing. For a new player, [register its identity](#register-and-provision-a-player) first.

## Flash Raspberry Pi OS Lite

### Automated flash

Attach an unmounted SD card, then run:

```sh
player/bin/rpi-flash radio-kitchen
```

The helper selects the first SSH-agent key or a standard Ed25519, ECDSA, or RSA public-key file. If neither exists, run `ssh-keygen -t ed25519`; use `--ssh-key FILE` to select another public key.

It detects a single removable disk of at least 4 GB, checks tools, image access, key, hostname, and disk safety, and requires the full disk path as confirmation. **Flashing erases the selected disk.** Imager verifies the pinned official image checksum and completed write. Use `--device` when detection is ambiguous:

```sh
player/bin/rpi-flash --wifi --device /dev/sdX radio-kitchen
```

`--wifi` prompts for the SSID and passphrase; an empty passphrase selects an open network. Ethernet DHCP remains enabled.

Locale, time zone, and keyboard defaults come from the workstation; missing settings fall back to `en_US.UTF-8`, `UTC`, and `us`. Wi-Fi country comes from the locale, falling back to `US`, even without `--wifi`. Override these with `--locale`, `--timezone`, `--keyboard-layout`, and `--country` for the deployment location.

First boot creates a key-only `radiopad` administrator and disables the GUI and console auto-login. Its SSH key grants root access through passwordless sudo.

### Imager GUI alternative

In [Raspberry Pi Imager](https://www.raspberrypi.com/documentation/computers/getting-started.html#install-using-imager):

1. Select the Pi model, **Raspberry Pi OS Lite (64-bit)**, and the SD card.
2. Set the hostname, user `radiopad`, and localisation settings for the deployment location.
3. Add Wi-Fi if needed and enable SSH with your public key.
4. Flash the card and boot the Pi.

Provisioning sets headless boot and removes console auto-login. Add `--ask-become-pass` if sudo requires a password; the provisioner waits up to five minutes for SSH.

## Use an existing installation

A 64-bit Raspberry Pi OS host with SSH needs no reflash. Add it to [inventory.yml](./inventory.yml), then use its existing sudo-capable administrator for the first run. Living Room illustrates the distinction between inventory name `radio-living-room` and network address `radio.lan`:

```sh
ssh-copy-id ADMIN@radio.lan
player/bin/rpi-provision ADMIN@radio-living-room
ssh radiopad@radio.lan
```

Replace `ADMIN` with the current administrator. Skip `ssh-copy-id` if key access already works; otherwise it prompts for the login password. Add `--ask-become-pass` if sudo needs a password.

Provisioning creates `radiopad`, copies the administrator's authorized SSH keys without removing existing keys, and enables passwordless sudo. The original account remains available. Later runs use `player/bin/rpi-provision radio-living-room`.

Stop any manually started player and remove its shell startup command first. An existing desktop boots without the GUI after the next reboot; the player service starts without a reboot.

## Register and provision a player

Provisioning validates an existing registry identity; it does not register players. Add one through the [registry-data repository](https://github.com/briceburg/radio-pad-registry-data). [The Cañones registration PR](https://github.com/briceburg/radio-pad-registry-data/pull/1) added `data/accounts/briceburg/players/canones.json`:

```json
{
  "name": "Cañones",
  "radio_dial": "community/briceburg",
  "switchboard_url": null
}
```

Display names may contain Unicode; identities such as `briceburg/canones` use lowercase registry slugs. The player must exist in the deployed registry before provisioning.

Add its network address, identity, and hardware settings under `radiopad_players.hosts` in [inventory.yml](./inventory.yml):

```yaml
radio-canones:
  ansible_host: radio-canones.lan
  radiopad_player: briceburg/canones
  radiopad_audio_device: alsa/default:CARD=DAC
  radiopad_timezone: America/Denver
```

Provision by inventory name; repeat for each Pi:

```sh
player/bin/rpi-provision radio-canones
```

For a host not yet in inventory, supply its identity:

```sh
player/bin/rpi-provision --player ACCOUNT/PLAYER HOSTNAME.local
```

SSH key access and sudo are required. Unknown host keys are saved; changed keys are rejected. Remove an old `known_hosts` entry only after verifying a reflash or key change.

The first run installs packages and a pinned uv, then synchronizes locked Python dependencies. Allow a few minutes. Later runs reconcile configuration; local checkout changes are not overwritten. Deployments follow `main` unless inventory pins another Git ref.

### Audio

Find the device on the Pi:

```sh
ssh radiopad@HOST mpv --no-config --audio-device=help
```

Set `radiopad_audio_device` in inventory, or override it once with `--audio-device DEVICE`. Provisioning checks that it exists. Cañones uses `alsa/default:CARD=DAC`; Living Room uses `alsa/default:CARD=S3`. For a HAT that requires a boot overlay, follow its vendor's setup first; provisioning selects an existing device, not HAT drivers.

### Wi-Fi and password access

Add a WPA Wi-Fi network or password fallback over the current SSH connection, without reflashing:

```sh
player/bin/rpi-provision --wifi NETWORK_NAME --wifi-country CC HOST
player/bin/rpi-provision --ssh-password HOST
```

Repeat `--wifi` to save additional networks. Existing profiles and Ethernet remain; each saved profile autoconnects with power saving disabled. Visible networks are activated, otherwise saved for deployment. Country defaults from the workstation locale or `US`; omit `--wifi-country` when correct.

Prompts hide passwords; temporary credentials are removed after provisioning. Wi-Fi credentials remain in the Pi's NetworkManager profile. Keep secrets out of inventory; use Ansible Vault for stored credentials.

`--ssh-password` sets a password for `radiopad` and enables SSH password authentication while retaining keys. Password authentication also becomes available to other password-enabled accounts. Treat the `radiopad` password as a root credential because sudo is passwordless. Without this option, existing SSH settings are preserved.

## Operate and update

SSH uses the Pi's network address, not its inventory alias. On the Pi:

```sh
ssh radiopad@HOST
cd /opt/radio-pad/player
sudo bin/player status
sudo bin/player logs
sudo bin/player logs --follow
sudo bin/player restart
sudo bin/player update
```

The service runs independently of SSH. Readiness checks startup and connectivity, not audible playback. Restarting stops playback; select a station with a controller to start it again.

`update` requires a clean `main` checkout that can fast-forward from `origin/main`. Unchanged code leaves a running service alone; otherwise it stops, updates locked dependencies, restarts, and waits for readiness. No Ansible workstation is needed. A failed dependency sync leaves the service stopped; retry the command or re-provision.

Use `player/bin/rpi-provision HOST` from the workstation for inventory, OS packages, service configuration, credentials, or pinned Git refs. It stops an installed player before replacing dependencies. Configuration is rendered to `/etc/radiopad/player.env`; change inventory rather than editing the Pi or running `git pull` there. Do not provision and update the same Pi simultaneously.

One `Player already connected` message after restart can indicate a lingering switchboard connection; the player retries. Repeated messages suggest another process or device shares the identity.

## Inventory reference

| Variable | Purpose | Default |
| --- | --- | --- |
| `radiopad_player` | Required `account/player` identity. | none |
| `radiopad_audio_device` | mpv device; verified during provisioning. | unset |
| `radiopad_audio_output` | mpv audio driver. | `alsa` |
| `radiopad_extra_environment` | Extra player settings; managed values take precedence. | `{}` |
| `radiopad_install_root` | Checkout directory. | `/opt/radio-pad` |
| `radiopad_repo_url` | Git repository. | RadioPad GitHub repository |
| `radiopad_repo_version` | Git ref; use provisioning to update pins. | `main` |
| `radiopad_registry_url` | Registry API. | `https://registry.radiopad.dev/api` |
| `radiopad_ssh_password_hash` | Password hash that enables SSH password authentication. | unset |
| `radiopad_timezone` | Canonical tzdb time zone. | unchanged |
| `radiopad_wifi_country` | Two-letter country; required with Wi-Fi. | unset |
| `radiopad_wifi_password` | WPA passphrase or hexadecimal PSK. | unset |
| `radiopad_wifi_ssid` | Network to add or update. | unset |
