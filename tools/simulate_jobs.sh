#!/usr/bin/env bash
# Simulates three Jenkins pipeline failure scenarios against the running agent.
# Usage: bash tools/simulate_jobs.sh [1|2|3|all]
# Requires: agent server running on localhost:8000

set -euo pipefail

BASE_URL="http://localhost:8000"

_check_server() {
  if ! curl -sf "$BASE_URL/health" > /dev/null; then
    echo "ERROR: Agent server not running at $BASE_URL"
    echo "Run: cd /Users/oggy/PlatformTool && bash start.sh"
    exit 1
  fi
}

# ---------------------------------------------------------------------------
# Job 1: docker-build-api
# Scenario: Docker daemon not running — fixable (clear_cache / retry)
# Stages: Checkout PASS, Unit Test PASS, Docker Build FAIL, Deploy SKIPPED
# ---------------------------------------------------------------------------
job1() {
  echo "==> Sending Job 1: docker-build-api (Docker Build failure)"
  curl -s -X POST "$BASE_URL/webhook/pipeline-failure" \
    -H "Content-Type: application/json" \
    -d '{
      "job_name": "docker-build-api",
      "build_number": 42,
      "result": "FAILURE",
      "branch": "main",
      "log": "[Pipeline] { (Checkout)\nChecking out from git...\nCheckout complete\n[Pipeline] }\n[Pipeline] { (Unit Test)\nRunning tests...\nTests passed: 42/42\n[Pipeline] }\n[Pipeline] { (Docker Build)\nBuilding image api:latest...\nERROR: Cannot connect to the Docker daemon at unix:///var/run/docker.sock.\nIs the docker daemon running?\nFAILURE: Build failed in stage Docker Build\n[Pipeline] }\n[Pipeline] { (Deploy)\nStage \"Deploy\" skipped due to earlier failure\n[Pipeline] }\n",
      "jenkinsfile": "pipeline {\n  agent any\n  stages {\n    stage(\"Checkout\") { steps { checkout scm } }\n    stage(\"Unit Test\") { steps { sh \"npm test\" } }\n    stage(\"Docker Build\") { steps { sh \"docker build -t api:latest .\" } }\n    stage(\"Deploy\") { steps { sh \"kubectl apply -f k8s/\" } }\n  }\n}"
    }'
  echo ""
  echo "Job 1 sent. Watch UI for analysis_complete event."
}

# ---------------------------------------------------------------------------
# Job 2: node-deploy
# Scenario: Credential mismatch — Jenkinsfile refs ECR_CREDENTIALS, Jenkins has ECR_CREDS
# Stages: Checkout PASS, Build PASS, Push to Registry FAIL, Notify SKIPPED
# fix_type: configure_credential
# ---------------------------------------------------------------------------
job2() {
  echo "==> Sending Job 2: node-deploy (credential mismatch)"
  curl -s -X POST "$BASE_URL/webhook/pipeline-failure" \
    -H "Content-Type: application/json" \
    -d '{
      "job_name": "node-deploy",
      "build_number": 3,
      "result": "FAILURE",
      "branch": "main",
      "log": "[Pipeline] { (Checkout)\nChecking out from git...\n[Pipeline] }\n[Pipeline] { (Build)\nRunning npm install && npm run build...\nBuild complete\n[Pipeline] }\n[Pipeline] { (Push to Registry)\nAttempting docker push to ECR...\nERROR: CredentialsNotFoundException: No credentials found with id ECR_CREDENTIALS\nFAILURE: Build failed in stage Push to Registry\n[Pipeline] }\n[Pipeline] { (Notify)\nStage \"Notify\" skipped due to earlier failure\n[Pipeline] }\n",
      "jenkinsfile": "pipeline {\n  agent any\n  stages {\n    stage(\"Checkout\") { steps { checkout scm } }\n    stage(\"Build\") { steps { sh \"npm install && npm run build\" } }\n    stage(\"Push to Registry\") {\n      steps {\n        withCredentials([usernamePassword(credentialsId: '\''ECR_CREDENTIALS'\'', usernameVariable: '\''AWS_USER'\'', passwordVariable: '\''AWS_PASS'\'')]) {\n          sh \"docker push ecr.io/myapp:latest\"\n        }\n      }\n    }\n    stage(\"Notify\") { steps { sh \"curl -X POST $SLACK_URL\" } }\n  }\n}"
    }'
  echo ""
  echo "Job 2 sent. Crawler finds ECR_CREDENTIALS missing -> configure_credential fix offered."
}

# ---------------------------------------------------------------------------
# Job 3: java-pipeline
# Scenario: Tool name mismatch — Jenkinsfile refs Maven3, Jenkins configured as Maven-3
# Stages: Checkout PASS, Compile FAIL, Test SKIPPED, Package SKIPPED
# fix_type: configure_tool
# ---------------------------------------------------------------------------
job3() {
  echo "==> Sending Job 3: java-pipeline (tool name mismatch)"
  curl -s -X POST "$BASE_URL/webhook/pipeline-failure" \
    -H "Content-Type: application/json" \
    -d '{
      "job_name": "java-pipeline",
      "build_number": 5,
      "result": "FAILURE",
      "branch": "main",
      "log": "[Pipeline] { (Checkout)\nChecking out from git...\n[Pipeline] }\n[Pipeline] { (Compile)\nRunning Maven build...\n/var/jenkins_home/tools/hudson.tasks.Maven_MavenInstallation/Maven3: not found\nERROR: No such installation: Maven3. The tool '\''Maven3'\'' is not configured in Jenkins Global Tool Configuration.\nFAILURE: Build failed in stage Compile\n[Pipeline] }\n[Pipeline] { (Test)\nStage \"Test\" skipped due to earlier failure\n[Pipeline] }\n[Pipeline] { (Package)\nStage \"Package\" skipped due to earlier failure\n[Pipeline] }\n",
      "jenkinsfile": "pipeline {\n  agent any\n  tools {\n    maven '\''Maven3'\''\n    jdk '\''JDK17'\''\n  }\n  stages {\n    stage(\"Checkout\") { steps { checkout scm } }\n    stage(\"Compile\") { steps { sh \"mvn compile\" } }\n    stage(\"Test\") { steps { sh \"mvn test\" } }\n    stage(\"Package\") { steps { sh \"mvn package\" } }\n  }\n}"
    }'
  echo ""
  echo "Job 3 sent. Crawler finds Maven3 vs Maven-3 mismatch -> configure_tool fix offered."
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
_check_server

case "${1:-all}" in
  1) job1 ;;
  2) job2 ;;
  3) job3 ;;
  all)
    job1; sleep 2
    job2; sleep 2
    job3
    echo ""
    echo "All three jobs sent. Open the UI to see the cards."
    ;;
  *)
    echo "Usage: $0 [1|2|3|all]"
    exit 1
    ;;
esac
