# radio-pad-registry

registry.radiopad.dev - uniting players, remote-controls, and switchboards

## Usage

TBD

### API Endpoints

```sh
curl https://registry.radiopad.dev/ # serves v1 API docs
curl https://registry.radiopad.dev/v1/api-docs/
curl https://registry.radiopad.dev/v1/players
curl https://registry.radiopad.dev/v1/players/foo
curl https://registry.radiopad.dev/v1/players/foo/stations
```

#### List Players

```
GET /v1/players?page=1&per_page=10
```

**Response:**
```json
{
  "items": [
    {"id": "foo", "name": "Foo Player"},
    {"id": "briceburg", "name": "bonjour briceburg"}
  ],
  "page": 1,
  "per_page": 10,
  "total": 2,
  "total_pages": 1
}
```

#### Get Player by ID

```
GET /v1/players/{player_id}
```

**Response:**
```json
{
  "id": "foo",
  "name": "Foo Player",
  "stationsUrl": "https://registry.radiopad.dev/players/foo/stations.json",
  "switchboardUrl": "wss://foo.player-switchboard.radiopad.dev"
}
```

#### Get Stations for a Player

```
GET /v1/players/{player_id}/stations
```

**Response:**
```json
[
  {
    "name": "wwoz",
    "url": "https://www.wwoz.org/listen/hi"
  },
  {
    "name": "wmse",
    "url": "https://wmse.streamguys1.com/wmselivemp3"
  }
  // ... more stations ...
]
```