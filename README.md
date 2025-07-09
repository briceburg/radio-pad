# radio-pad 

A 🎵 radio station player 🎵 with real-time syncing controllers.

## overview

* radio-pad runs on a host, such as a raspberry pi, connected to a stereo/speakers.
* controllers, such as a USB-connected macropad, request the station to play.
* stations are configurable by editting [stations.json](./player/stations.json).

### local control

**radio-pad** lets you use a USB-connected [macropad](./macropad-controller/) as a controller for playing internet radio stations on your computer (such as a Raspberry Pi).

* each Macropad button is mapped to a different station.
* the encoder knob adjusts volume if a station is playing, or switches station pages if there are more than 12 stations.
* pressing the encoder knob will stop playing.

![ai-enhanced-macropad-image](./macropad-controller/docs/img/radio-macropad-ai-image.webp)

### remote control

**radio-pad** is optionally controlled through a [switchboard](./switchboard/) of connected [clients](./remote-controller/), such as mobile apps or web browsers.

* clients and the radio-pad player connect to the switchboard to request and broadcast station changes.
* the switchboard can run on the local network, or as an internet available service.
* websockets are used for real-time syncing of clients, such as updating the currently playing station.

## getting started

there are four components that makeup radio-pad. each is broken out into a folder which _may_ become a git repository. visit this folder for details/installation/use.

* the [player](./player/), this runs on a host and defines [stations](./player/README.md#editing-stations).
* the [macropad-controller](./macropad-controller/), this connects to the host over USB.
* the [switchboard](./switchboard/), this is _optional_ and needed to support remote-control.
* the [remote-control](./remote-controller/), used to create mobile and web clients for controlling the player.

## Development

### Reference

```mermaid
flowchart TD
    subgraph Host
        Player["Player<br/>(runs on host,<br/>plays stations)"]
    end

    subgraph Controllers
        Macropad["Macropad Controller<br/>(USB, local control)"]
        Remote["Remote Controller<br/>(Web/Mobile client)"]
    end

    subgraph Optional
        Switchboard["Switchboard<br/>(WebSocket server,<br/>syncs clients & player)"]
    end

    Macropad -- USB --> Player
    Remote -- WebSocket --> Switchboard
    Player -- WebSocket --> Switchboard
    Switchboard -- WebSocket --> Remote
    Switchboard -- WebSocket --> Player

    %% Notes
    Macropad -.->|Each button maps to a station\nEncoder knob for volume/page\nPress to stop| Player
    Remote -.->|Mobile/web app\nControls player remotely| Switchboard
    Switchboard -.->|Optional for remote control\nSyncs state between clients and player| Player
```

### Contributing

Pull requests and bug reports are welcome! Please [open an issue](https://github.com/briceburg/radio-pad/issues) or submit a PR.

## Support

For questions or help, please open an issue on the [GitHub repository](https://github.com/briceburg/radio-pad/issues).

### TODO

* use MIDI control sequences or usb-cdc instead of keypresses for radio control. this is necessary to support bi-directial communication, e.g. to notify macropad of station changes from remote controls.
* pass the list of stations to macropad (via usb connection) and controllers (via switchboard). we can thus handle live station updates, as well as defer startup until communication with the player has been established.
