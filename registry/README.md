# radio-pad-registry
registry.radiopad.dev - uniting players, remote-controls, and switchboards

## WIP

```sh
GET registry.radiopad.dev/players 
  -> [{"id":"foo","name":"Foo Player"},{"id":"bar","name":"Bar Player"}]

GET registry.radiopad.dev/players/foo
  -> {"stations":[
    {"id":"station1","name":"Station 1"},
    {"id":"station2","name":"Station 2"}
    ], "switchboard": "foo.player.radiopad.dev"} }

GET foo.player-switchboard.radiopad.dev
  -> WSS://fly.dev:1980/
```
