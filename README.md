# radio-pad 

A 🎵 radio station player 🎵 with real-time syncing controllers.

The registry API and datastore implementation live in [`radio-pad-registry`](https://github.com/briceburg/radio-pad-registry).

![radio-pad-logo](./shared/assets/logo-dark.svg)

## overview

* the radio-pad [player](./player/) runs on a host, such as a raspberry pi, connected to a stereo/speakers.
* controllers, such as a USB-connected [macropad](./macropad-control/), request the station to play.
* [stations](./player/stations.json) are configurable.

### local control

**radio-pad** lets you use a USB-connected [macropad](./macropad-control/) as a controller for playing internet radio stations on your computer (such as a Raspberry Pi).

* each Macropad button is mapped to a different station.
* the encoder knob adjusts volume if a station is playing, or switches station pages if there are more than 12 stations.
* pressing the encoder knob will stop playing.

![ai-enhanced-macropad-image](./shared/assets/radio-macropad-ai-image.webp)

### remote control

**radio-pad** is optionally controlled through a [switchboard](./switchboard/) of connected [clients](./remote-control/), such as mobile apps or web browsers.

* clients and the radio-pad player connect to the switchboard to request and broadcast station changes.
* the switchboard can run on the local network, or as an internet available service.
* websockets are used for real-time syncing of clients, such as updating the currently playing station.

## getting started

there are four components that makeup radio-pad. each is broken out into a folder which _may_ become a git repository. visit this folder for details/installation/use.

* the [player](./player/), this runs on a host and defines [stations](./player/README.md#editing-stations).
* the [macropad-control](./macropad-control/), this connects to the host over USB.
* the [switchboard](./switchboard/), this is _optional_ and needed to support remote-control.
* the [remote-control](./remote-control/), used to create mobile and web clients for controlling the player.

<p align="center" width="100%">
  <img src="./shared/assets/icon-fancy-bg.svg" />
</p>

## Architecture

### Core control flow

```mermaid
flowchart TD
    Macropad["Macropad controller"]
    Player["Player device<br/>🎵🎵🎵"]
    Switchboard["Switchboard"]
    Remote["Remote-control app<br/>(mobile / web)"]

    Macropad <-- USB --> Player
    Player -- ws:station_playing --> Switchboard
    Switchboard -- ws:station_request --> Player
    Switchboard -- ws:station_playing --> Remote
    Remote -- ws:station_request --> Switchboard

    style Player stroke:#f9f,stroke-width:3px
    style Switchboard stroke:#bbf,stroke-width:3px
```

This is the baseline runtime view: controllers talk to players directly over USB or indirectly through the switchboard.

### Registry auth and player access

```mermaid
flowchart TD
    Human["Signed-in owner/admin"]
    Remote["Remote-control app"]
    Switchboard["Switchboard"]
    Player["Player device"]
    Registry["radio-pad-registry API"]
    Access["Ownership + access rules"]

    Human -->|"sign in with OIDC provider"| Remote
    Remote -->|"request player access"| Registry
    Registry -->|"check access"| Access
    Remote -->|"send player-scoped control"| Switchboard
    Player -->|"connect as player"| Switchboard
    Switchboard -->|"forward only to matching player"| Player

    Player -->|"public reads"| Registry
    Remote -->|"public reads"| Registry
    Remote -->|"authenticated write requests"| Registry

    Note1["Remote-control acts as the signed-in human."]
    Note2["Reads stay public. Writes require owner/admin auth."]
    Note3["No global control path: only owned/admin-managed players can be controlled."]

    Remote -.-> Note1
    Registry -.-> Note2
    Switchboard -.-> Note3
```

This direction keeps player control scoped instead of global:

* remote-control signs in as the human and asks the registry for access to one player.
* the registry only issues that player-scoped session when the user owns that player or is an admin.
* the switchboard only forwards commands to the connected player that matches that session.

### Contributing

Pull requests and bug reports are welcome! Please [open an issue](https://github.com/briceburg/radio-pad/issues) or submit a PR.

## Support

For questions or help, please open an issue on the [GitHub repository](https://github.com/briceburg/radio-pad/issues).

### TODO

* use MIDI control sequences or usb-cdc instead of keypresses for radio control. this is necessary to support bi-directial communication, e.g. to notify macropad of station changes from remote controls.
* pass the list of stations to macropad (via usb connection) and controllers (via switchboard). we can thus handle live station updates, as well as defer startup until communication with the player has been established.
