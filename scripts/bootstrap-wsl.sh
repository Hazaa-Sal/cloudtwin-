#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export DOCKER_HOST=unix:///var/run/docker.sock
export PATH="/usr/bin:$PATH"
mkdir -p .local/bin
if [ ! -s .local/bin/kind ]; then
  curl -fsSL https://github.com/kubernetes-sigs/kind/releases/download/v0.33.0/kind-linux-amd64 -o .local/bin/kind
fi
curl -fsSL https://github.com/kubernetes-sigs/kind/releases/download/v0.33.0/kind-linux-amd64.sha256sum -o .local/bin/kind.sha256
echo "$(cut -d' ' -f1 .local/bin/kind.sha256)  .local/bin/kind" | sha256sum --check
chmod +x .local/bin/kind
if [ ! -s .local/bin/kubectl ]; then
  curl -fsSL https://dl.k8s.io/release/v1.36.4/bin/linux/amd64/kubectl -o .local/bin/kubectl
fi
curl -fsSL https://dl.k8s.io/release/v1.36.4/bin/linux/amd64/kubectl.sha256 -o .local/bin/kubectl.sha256
echo "$(cat .local/bin/kubectl.sha256)  .local/bin/kubectl" | sha256sum --check
chmod +x .local/bin/kubectl
docker version
if ! .local/bin/kind get clusters | grep -Fxq cloudtwin; then
  .local/bin/kind create cluster --name cloudtwin --kubeconfig .local/kubeconfig \
    --image kindest/node:v1.36.4@sha256:099e049362a1526b2db71494e1947aae99bd16290d7c895f2b7ea312e3cbfaed --wait 120s
else
  .local/bin/kind export kubeconfig --name cloudtwin --kubeconfig .local/kubeconfig
fi
.local/bin/kubectl --kubeconfig .local/kubeconfig --context kind-cloudtwin wait --for=condition=Ready nodes --all --timeout=120s
.local/bin/kubectl --kubeconfig .local/kubeconfig --context kind-cloudtwin get nodes,storageclass
docker build -t cloudtwin-api:day1 .
.local/bin/kind load docker-image cloudtwin-api:day1 --name cloudtwin
echo 'PASS: local WSL cluster ready and API image loaded.'
