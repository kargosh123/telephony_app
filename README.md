# Self-hosted Telephony Server

See https://docs.vocode.dev/open-source/telephony for setup steps!
Just used Eleven Labs instead of Azure for TTS
For future steps and non-local deployment, I think I would use the following methodology:
- Set up a GKE cluster on GCP with the docker image
- Use a Helm chart and deploy the app with kubernetes
- Use kubectl to interact with the deployed contain