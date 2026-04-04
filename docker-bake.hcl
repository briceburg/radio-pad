group "default" {
    targets = ["registry", "player", "remote-control"]
}

target "registry" {
    context    = "./registry/"
    target     = "prod"
    tags       = ["ghcr.io/briceburg/radio-pad-registry:latest"]
}

target "player" {
    context    = "./player/"
    target     = "prod"
    tags       = ["ghcr.io/briceburg/radio-pad-player:latest"]
}

target "remote-control" {
    context    = "./remote-control/"
    target     = "prod"
    tags       = ["ghcr.io/briceburg/radio-pad-remote-control:latest"]
}

#
# github-action-docker-bake targets
#

group "ci" {
  targets = ["ci-registry", "ci-player", "ci-remote-control"]
}

target "docker-metadata-action" {tags=[]}
target "ci" {
  matrix = {
    img = ["registry", "player", "remote-control"]
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
