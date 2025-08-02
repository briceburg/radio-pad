# radio-pad-registry

registry.radiopad.dev - uniting players, remote-controls, and switchboards

## Usage

```bash
# run these once
python -m venv venv
. venv/bin/activate
pip3 install -r requirements.txt

# run everytime you want to start the registry
bin/registry
```

see the swagger API docs by visiting: http://localhost:8080/

## Testing

To run the tests, first install the development dependencies:

```sh
pip install -r requirements-dev.txt
```

Then, run the tests using pytest:

```sh
pytest
```