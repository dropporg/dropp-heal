#!/usr/bin/env bash
#
# Resolve the versions stamped into Chart.yaml, which ships with
# __chartVersion__ and __appVersion__ placeholders.
#
#   chart-version.sh <ref-name> [chart-version]
#
# The chart version comes from a helm/* tag, or the second argument for a
# manual run. The app version is the product-wide release, taken from the
# newest release/* tag. Writes KEY=VALUE lines for $GITHUB_OUTPUT.
set -euo pipefail

ref=${1:-}
requested=${2:-}
short="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"

# Charts are addressed by plain semver, so `helm install --version 0.1.0`
# resolves whether or not the tag carried a leading v.
if [[ -n $requested ]]; then
  chart_version=${requested#v}
  publish=true
elif [[ $ref == helm/* ]]; then
  # helm/v0.1.0 publishes chart 0.1.0.
  chart_version=${ref#helm/}
  chart_version=${chart_version#v}
  publish=true
else
  # A branch or pull request build, packaged for inspection but never released.
  chart_version="0.0.0-sha.$short"
  publish=false
fi

# The app version is the product-wide release, with its leading v dropped:
# release/v0.1.0 becomes 0.1.0. The chart adds the v back when it builds an
# image reference, since the images are tagged v0.1.0.
if [[ $ref == release/* ]]; then
  app_version=${ref#release/}
else
  latest="$(git tag -l 'release/*' --sort=-v:refname | head -1)"
  app_version=${latest#release/}
fi
app_version=${app_version#v}
[[ -n $app_version ]] || app_version="0.0.0-sha.$short"

echo "chart_version=$chart_version"
echo "app_version=$app_version"
echo "publish=$publish"
