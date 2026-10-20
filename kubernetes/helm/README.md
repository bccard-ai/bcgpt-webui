# Helm Charts
The BCGPT Helm chart lives in this directory (`kubernetes/helm`) of
https://github.com/bccard-ai/bcgpt-webui. Install it from a checkout:

```bash
helm install bcgpt ./kubernetes/helm --set secrets.BCGPT_SECRET_KEY="<random secret>"
```

The default image is `ghcr.io/bccard-ai/bcgpt-webui`, built by this repository's
Docker workflow. No other registry, Helm repository or domain is an official
distribution channel.