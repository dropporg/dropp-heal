{{- define "heal.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "heal.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name (include "heal.name" .) | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}

{{- define "heal.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" }}
{{ include "heal.selectorLabels" . }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: heal
{{- end }}

{{- define "heal.selectorLabels" -}}
app.kubernetes.io/name: {{ include "heal.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "heal.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "heal.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{- define "heal.secretName" -}}
{{- .Values.secrets.existingSecret | default (printf "%s-secrets" (include "heal.fullname" .)) }}
{{- end }}

{{/*
Resolve an image, honouring the shared registry and tag fallbacks.
Falling back to the chart's appVersion means v0.1.0 for appVersion 0.1.0: the
images are published from tags that keep their leading v, while the chart
version itself must stay plain semver.
*/}}
{{- define "heal.image" -}}
{{- $tag := .component.image.tag | default .root.Values.image.tag | default (printf "v%s" .root.Chart.AppVersion) -}}
{{- if .root.Values.image.registry -}}
{{ .root.Values.image.registry }}/{{ .component.image.repository }}:{{ $tag }}
{{- else -}}
{{ .component.image.repository }}:{{ $tag }}
{{- end -}}
{{- end }}

{{- define "heal.envFrom" -}}
- configMapRef:
    name: {{ include "heal.fullname" . }}-config
- secretRef:
    name: {{ include "heal.secretName" . }}
{{- with .Values.extraEnvVarsCM }}
- configMapRef:
    name: {{ . }}
{{- end }}
{{- with .Values.extraEnvVarsSecret }}
- secretRef:
    name: {{ . }}
{{- end }}
{{- end }}

{{/*
Environment variables for one component: the chart-wide extras first, then the
component's own, so a component can override a shared value.
Call with (dict "root" $ "component" .Values.<component>).
*/}}
{{- define "heal.extraEnvVars" -}}
{{- $vars := concat (.root.Values.extraEnvVars | default list) (.component.extraEnvVars | default list) -}}
{{- with $vars }}
{{- toYaml . }}
{{- end }}
{{- end }}

{{- define "heal.metricsAnnotations" -}}
{{- if .Values.metrics.annotations }}
prometheus.io/scrape: "true"
prometheus.io/port: "8000"
prometheus.io/path: /metrics
{{- end }}
{{- end }}
