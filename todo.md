KAFKA + TEMPORAL + REDIS + CHARTJS
- [ ] Add Kafka (or Redpanda — lighter, same API) K8s deployment + Service
- [ ] Add Zookeeper deployment if using Kafka (not needed for Redpanda)
- [ ] Create kafka topic "user-logins"
- [ ] Backend: publish login event to kafka on successful authentication
        { user_id, timestamp, ip, device }
- [ ] Build Temporal server K8s deployment + Service
        point it at existing postgres instance, separate database "temporal"
- [ ] Build Temporal worker deployment
        thin kafka consumer → receives event → calls temporal_client.start_workflow()
- [ ] Build workflow: ProcessLoginEvent
        activity 1: HINCRBY logins:YYYY-MM-DD user_id 1
        activity 2: SET user:last_seen:user_id timestamp
- [ ] FastAPI endpoint GET /api/v1/analytics/logins
        reads redis hashes for date range → returns data
- [ ] Frontend: chart.js table consuming that endpoint
        rows = users, columns = days, values = login counts

OBSERVABILITY (scoped to temporal worker only)
- [ ] Add Prometheus K8s deployment + Service
- [ ] Add Grafana K8s deployment + Service
- [ ] Expose /metrics endpoint on Temporal worker (prometheus_client library)
        track: workflows started, activities completed, redis write latency,
               kafka consumer lag, workflow failures
- [ ] Configure Prometheus scrape job pointing at temporal worker /metrics
- [ ] Build Grafana dashboard
        panel 1: workflows processed per minute
        panel 2: redis write latency histogram
        panel 3: kafka consumer lag
        panel 4: failed workflows count

CI/CD
- [ ] Add GitHub Actions workflow
        on push to main:
          run pytest
          build images
          push to registry or scp to droplet
- [ ] Add webhook listener service on droplet
        tiny FastAPI or Flask app listening for GitHub push events
        on receive: pull latest, run deploy-k3s-local.sh
- [ ] OR Jenkins deployment on droplet as alternative to Actions

HELM / KUSTOMIZE
- [ ] Refactor sequential bash deploy into Helm chart or Kustomize overlays
        base: current single-droplet setup
        overlay/values: local dev vs droplet (replicas, memory, storage)