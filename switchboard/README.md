# radio-pad switchboard

websockets :octopus: enabling event driven communication between the [radio-pad player](../player/) and connected [controllers](../remote-control/).

## Usage

TBD

### Environment Variables

- `SWITCHBOARD_HOST`: The hostname or IP address to bind to. Defaults to `localhost`.
- `SWITCHBOARD_PORT`: The port to listen on. Defaults to `1980`.
- `SWITCHBOARD_PARTITION_BY_HTTP_HOST`: When set to `'true'`, the switchboard will partition broadcasts by the `Host` header of incoming websocket connections. This allows multiple radio-pad instances to share the same switchboard without interfering with each other -- e.g. foo.switchboard.dev and bar.switchboard.dev would have separate broadcasts and currently playing stations.

## Development

### Contributing

Pull requests and bug reports are welcome! Please [open an issue](https://github.com/briceburg/radio-pad/issues) or submit a PR.

## Support

For questions or help, please open an issue on the [GitHub repository](https://github.com/briceburg/radio-pad/issues).

## License

[GNU Affero General Public License v3.0](./LICENSE)
