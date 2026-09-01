#!/usr/bin/env bash
#
# Decide which component images to build, and under which tags.
#
#   select-build.sh tag <tag-name>          e.g. worker/v0.1.23
#   select-build.sh branch <sha>            changed paths on stdin
#   select-build.sh manual <component> <sha> [version]
#
# Writes `components` (a JSON array), `version` and `image_tags` (comma
# separated) as KEY=VALUE lines, ready to append to $GITHUB_OUTPUT.
#
# When a push changes no component, the array holds the single value "none"
# rather than being empty: an empty matrix produces no jobs at all, which
# reports as skipped and leaves a required status check waiting forever.
set -euo pipefail

COMPONENTS=(api worker dashboard migrate)

# <app>/<version>, where the version is semver with an optional leading v and
# an optional prerelease suffix: api/v0.1.1, migrate/1.0.0-beta.1.
VERSION_PATTERN='^v?[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z][0-9A-Za-z.-]*)?$'

# A path matched here rebuilds that component. The api package is shared, so a
# change to it rebuilds every Python image but leaves the dashboard alone.
matches() {
  local component=$1 path=$2
  case "$component" in
    api)
      [[ $path == api/* || $path == main.py || $path == requirements.txt ||
         $path == deployments/docker/Dockerfile.api ]]
      ;;
    worker)
      [[ $path == api/* || $path == worker.py || $path == requirements.txt ||
         $path == deployments/docker/Dockerfile.worker ]]
      ;;
    migrate)
      [[ $path == api/* || $path == migrations/* || $path == alembic.ini ||
         $path == requirements.txt || $path == deployments/docker/Dockerfile.migrate ]]
      ;;
    dashboard)
      [[ $path == dashboard/* || $path == deployments/docker/Dockerfile.dashboard ]]
      ;;
    *) return 1 ;;
  esac
}

as_json() {
  local first=1 item
  printf '['
  for item in "$@"; do
    [[ $first -eq 1 ]] || printf ','
    printf '"%s"' "$item"
    first=0
  done
  printf ']'
}

mode=${1:?usage: select-build.sh <tag|branch|manual> <ref>}
ref=${2:?missing ref}
selected=()

case "$mode" in
  tag)
    # worker/v0.1.23 builds only the worker, at exactly that version.
    component=${ref%%/*}
    version=${ref#*/}
    if [[ $component == "$ref" || -z $version ]]; then
      echo "tag '$ref' is not <component>/<version>" >&2
      exit 1
    fi
    if [[ ! " ${COMPONENTS[*]} " == *" $component "* ]]; then
      echo "tag '$ref' names an unknown component '$component'" >&2
      exit 1
    fi
    if [[ ! $version =~ $VERSION_PATTERN ]]; then
      echo "tag '$ref' has a version that is not <major>.<minor>.<patch>[-prerelease]" >&2
      exit 1
    fi
    selected=("$component")
    # The commit, the version verbatim, and - for a stable release only -
    # latest. A prerelease must not become what `latest` resolves to.
    tags=("$GITHUB_SHA" "$version")
    [[ $version == *-* ]] || tags+=(latest)
    ;;
  branch)
    version=$ref
    # Every push to the default branch publishes the commit and moves nightly,
    # which is the newest unstable build of each component.
    tags=("$ref" nightly)
    changed=$(cat)
    for component in "${COMPONENTS[@]}"; do
      while IFS= read -r path; do
        [[ -n $path ]] || continue
        if matches "$component" "$path"; then
          selected+=("$component")
          break
        fi
      done <<<"$changed"
    done
    ;;
  manual)
    sha=${3:?missing sha}
    requested=${4:-}
    if [[ $ref == "all" ]]; then
      selected=("${COMPONENTS[@]}")
    elif [[ " ${COMPONENTS[*]} " == *" $ref "* ]]; then
      selected=("$ref")
    else
      echo "unknown component '$ref'" >&2
      exit 1
    fi
    if [[ -n $requested ]]; then
      version=$requested
      tags=("$sha" "$requested")
    else
      version=$sha
      tags=("$sha" nightly)
    fi
    ;;
  *)
    echo "unknown mode '$mode'" >&2
    exit 1
    ;;
esac

if [[ ${#selected[@]} -eq 0 ]]; then
  selected=(none)
fi

echo "components=$(as_json "${selected[@]}")"
echo "version=$version"
printf 'image_tags=%s\n' "$(IFS=,; echo "${tags[*]}")"
