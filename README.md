# Heal chart repository

This branch is not source. It is the published Helm repository for
[dropp-heal](https://github.com/dropporg/dropp-heal), served by GitHub Pages
from <https://dropporg.github.io/dropp-heal>.

```bash
helm repo add heal https://dropporg.github.io/dropp-heal
helm repo update
helm search repo heal
```

`index.yaml` and the packaged `*.tgz` charts are written by the `Chart`
workflow on a `helm/vX.Y.Z` tag. Do not commit here by hand: the workflow
regenerates `index.yaml` with `helm repo index --merge`, so a hand-written
entry is either overwritten or silently duplicated.

`.nojekyll` disables Jekyll processing, which would otherwise ignore the
packaged charts and rewrite the paths Helm expects.
