group "default" {
    targets = ["switchboard"]
}

target "switchboard" {
    context    = "./switchboard/"
    tags       = ["ghcr.io/briceburg/radio-pad-switchboard:latest"]
}

#
# github-action-docker-bake targets
#

group "ci" {
  targets = ["ci-switchboard"]
}

target "docker-metadata-action" {tags=[]}
target "ci" {
  matrix = {
    img = ["switchboard"]
  }

  name       = "ci-${img}"
  inherits   = ["${img}", "docker-metadata-action"]
  cache-from = ["type=gha,scope=${img}"]
  cache-to   = ["type=gha,scope=${img}"]

  tags = [
    for tag in target.docker-metadata-action.tags :
    "ghcr.io/briceburg/radio-pad-${img}:${tag}"
  ]
}
