# Minimal packaging of the official published CLI, not the cloud-computer entrypoint.
FROM node:22.23.1-bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends git python3 ca-certificates build-essential && apt-get clean
RUN npm install --omit=dev --prefix /opt/letta @letta-ai/letta-code@0.31.13
ENV PATH=/opt/letta/node_modules/.bin:$PATH
WORKDIR /work
USER 1000:1000
ENTRYPOINT ["letta"]
