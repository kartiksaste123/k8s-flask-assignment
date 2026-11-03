#!/usr/bin/env bash
# End-to-end run: test -> build -> run container -> kind cluster -> deploy -> verify.
# Every command and its output is saved to evidence/logs/NN_name.txt,
# then rendered to PNG screenshots in evidence/screenshots/.
set -u
cd "$(dirname "$0")/.."
L=scripts/run_and_log.sh
rm -f evidence/logs/*.txt evidence/screenshots/*.png

# ---------- Part A: Docker ----------
$L 00_versions "docker --version && kubectl version --client && kind version && python3 --version"
$L 01_pytest ".venv/bin/pytest -v tests/"
docker rm -f kartik-flask-app >/dev/null 2>&1
$L 02_docker_build "docker build --no-cache --progress=plain -t kartik-flask-app:1.0 ."
$L 03_docker_images "docker images kartik-flask-app"
$L 03b_docker_inspect "docker inspect kartik-flask-app:1.0 --format '{{json .Config.Labels}}' | python3 -m json.tool && docker inspect kartik-flask-app:1.0 --format 'User={{.Config.User}}  ExposedPorts={{json .Config.ExposedPorts}}  Healthcheck={{json .Config.Healthcheck.Test}}'"
$L 04_docker_run "docker run -d -p 5000:5000 --name kartik-flask-app kartik-flask-app:1.0"
echo "waiting for Docker HEALTHCHECK..."; for i in $(seq 1 30); do [ "$(docker inspect -f '{{.State.Health.Status}}' kartik-flask-app)" = healthy ] && break; sleep 2; done
$L 05_docker_ps "docker ps --filter name=kartik-flask-app && docker inspect -f 'Health: {{.State.Health.Status}}' kartik-flask-app"
$L 06_curl_container "curl -s http://localhost:5000/health; curl -s http://localhost:5000/api/info | python3 -m json.tool; curl -s -o /dev/null -w 'GET / -> HTTP %{http_code}, %{size_download} bytes\n' http://localhost:5000/"
$L 07_docker_logs "docker logs kartik-flask-app"

# ---------- Part B: Kubernetes (kind) ----------
pkill -f "port-forward svc/kartik-flask-service" 2>/dev/null
kind delete cluster --name kartik-cluster >/dev/null 2>&1
$L 08_kind_create "kind create cluster --config kind-config.yaml --wait 120s"
$L 09_cluster_info "kubectl cluster-info && kubectl get nodes -o wide"
$L 10_kind_load "kind load docker-image kartik-flask-app:1.0 --name kartik-cluster"
$L 11_kubectl_apply "kubectl apply -f k8s/deployment.yaml -f k8s/service.yaml"
$L 12_rollout_status "kubectl rollout status deployment/kartik-flask-app --timeout=120s && kubectl wait --for=condition=Ready pod -l app=kartik-flask-app --timeout=120s"
sleep 3
$L 13_get_pods "kubectl get pods -l app=kartik-flask-app -o wide --show-labels"
$L 14_get_deploy "kubectl get deploy kartik-flask-app -o wide && kubectl get rs -l app=kartik-flask-app"
$L 15_get_svc "kubectl get svc kartik-flask-service -o wide && kubectl get endpointslices -l kubernetes.io/service-name=kartik-flask-service"
$L 16_describe_svc "kubectl describe svc kartik-flask-service"
$L 17_curl_nodeport "curl -s http://localhost:30080/health; curl -s http://localhost:30080/api/info | python3 -m json.tool; curl -s -o /dev/null -w 'GET / -> HTTP %{http_code}, %{size_download} bytes\n' http://localhost:30080/"
$L 18_load_balancing "for i in \$(seq 1 10); do echo \"request \$i -> \$(curl -s http://localhost:30080/health)\"; done; echo; echo 'Requests served per pod (50 requests):'; for i in \$(seq 1 50); do curl -s http://localhost:30080/api/info | python3 -c 'import sys,json;print(json.load(sys.stdin)[\"pod_name\"])'; done | sort | uniq -c"
$L 20_describe_deploy "kubectl describe deploy kartik-flask-app"
$L 21_pod_env_user_logs "P=\$(kubectl get pods -l app=kartik-flask-app -o jsonpath='{.items[0].metadata.name}'); echo \"# env inside \$P\"; kubectl exec \$P -- env | grep -E 'APP_|POD_|NODE_' | sort; echo; echo '# user inside container'; kubectl exec \$P -- id; echo; echo '# logs (note kube-probe health checks)'; kubectl logs \$P --tail=6"
$L 23_self_healing "P=\$(kubectl get pods -l app=kartik-flask-app -o jsonpath='{.items[0].metadata.name}'); echo \"Deleting pod \$P ...\"; kubectl delete pod \$P; kubectl wait --for=condition=Ready pod -l app=kartik-flask-app --timeout=90s; kubectl get pods -l app=kartik-flask-app -o wide"
$L 24_scaling "kubectl scale deploy/kartik-flask-app --replicas=3 && kubectl rollout status deploy/kartik-flask-app --timeout=90s && kubectl get pods -l app=kartik-flask-app && kubectl scale deploy/kartik-flask-app --replicas=2 && sleep 8 && kubectl get pods -l app=kartik-flask-app"

# port-forward after self-healing/scaling so it targets a live pod
nohup kubectl port-forward svc/kartik-flask-service 8080:80 > /tmp/pf.log 2>&1 &
sleep 4
{
  echo 'kartik@cloud-lab:~/k8s-assignment$ kubectl port-forward svc/kartik-flask-service 8080:80 &'
  grep Forwarding /tmp/pf.log; echo
  echo 'kartik@cloud-lab:~/k8s-assignment$ curl -s http://localhost:8080/health'
  curl -s http://localhost:8080/health
  echo 'kartik@cloud-lab:~/k8s-assignment$ curl -s http://localhost:8080/api/info | python3 -m json.tool'
  curl -s http://localhost:8080/api/info | python3 -m json.tool
  echo 'kartik@cloud-lab:~/k8s-assignment$ curl -s -o /dev/null -w "GET / -> HTTP %{http_code}\n" http://localhost:8080/'
  curl -s -o /dev/null -w "GET / -> HTTP %{http_code}\n" http://localhost:8080/
  echo
} | tee evidence/logs/19_port_forward.txt
$L 25_final_state "kubectl get all -l app=kartik-flask-app -o wide && echo && docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'"

# ---------- Screenshots ----------
.venv/bin/python scripts/browser_screenshots.py
.venv/bin/python scripts/render_terminal_png.py
