# radio-pad switchboard

websockets :octopus: enabling event driven communication between the [radio-pad player](../player/) and connected [controllers](../remote-control/).

## Usage

TBD

### Connection routing

The switchboard partitions connections by request path and expects clients to connect to:

`wss://<switchboard_domain>/<account_id>/<player_id>`

Example: `wss://switchboard.radiopad.dev/briceburg/living-room`

All clients connected to the same `/{account_id}/{player_id}` path receive each other's events.

TODO: Eventually clients will need an authentication token for connecting to players under an account.

### Environment Variables

- `SWITCHBOARD_HOST`: The hostname or IP address to bind to. Defaults to `localhost`.
- `SWITCHBOARD_PORT`: The port to listen on. Defaults to `1980`.

## Development

### Contributing

Pull requests and bug reports are welcome! Please [open an issue](https://github.com/briceburg/radio-pad/issues) or submit a PR.

## Support

For questions or help, please open an issue on the [GitHub repository](https://github.com/briceburg/radio-pad/issues).

## License

[GNU Affero General Public License v3.0](./LICENSE)
