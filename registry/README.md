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

see the swagger API docs by visiting: http://localhost:8000/


### Environment Variables

name | description | default
--- | --- | ---
REGISTRY_BACKEND | datastore backend, either `s3` or `local` | `local`
REGISTRY_BACKEND_S3_BUCKET | name of S3 bucket. required when backend is `s3` | `None`
REGISTRY_BACKEND_S3_PREFIX | path prefix of objects in S3 bucket | `registry-v1/`
REGISTRY_BIND_HOST | host to bind to | `localhost`
REGISTRY_BIND_PORT | port to bind to | `8000`
REGISTRY_LOG_LEVEL | uvicorn log level, e.g. `debug`, `error` | `info`
REGISTRY_PATH_DATA | datastore location | `tmp/data`
REGISTRY_PATH_SEED | location of seed data for the datastore | `data`

### Backend selection

The registry supports pluggable storage backends.

- Default: file store on local disk.
- Optional: S3-backed store using boto3.

Select the backend via the `REGISTRY_BACKEND` environment variable.

#### S3 Backend

If using the S3 backend, it is assumed your environment provides the authentication necessary for _reading_ and _writing_ to the `REGISTRY_BACKEND_S3_BUCKET` bucket -- e.g. the evironment provides an appropriate AWS_ACCESS_KEY, [IAM Roles Anywhere](https://docs.aws.amazon.com/rolesanywhere/latest/userguide/introduction.html), or ec2/ecs-task metadata identity to the AWS SDK with these _minimal_ permissions:


```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:DeleteObject",
                "s3:GetObject",
                "s3:HeadObject",
                "s3:ListBucket",
                "s3:PutObject",
            ],
            "Resource": [
                "arn:aws:s3:::your-bucket-name",
                "arn:aws:s3:::your-bucket-name/*"
            ]
        }
    ]
}
```

## Testing

To run the tests, first install the development dependencies:

```sh
pip install -r requirements-dev.txt
```

Then, run the tests using pytest:

```sh
pytest
```
