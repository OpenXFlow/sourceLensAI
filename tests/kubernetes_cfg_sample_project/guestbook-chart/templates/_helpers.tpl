{{/*
Common labels for the guestbook application.
*/}}
{{- define "guestbook.labels" -}}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}