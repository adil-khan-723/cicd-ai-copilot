/**
 * DevOps AI Agent — Jenkins RunListener
 *
 * Paste this into Jenkins → Manage Jenkins → Script Console and click Run.
 * After that, every build (any job) will automatically notify the DevOps AI Agent.
 *
 * For automatic registration after Jenkins restarts, copy this file to:
 *   JENKINS_HOME/init.groovy.d/devops_agent_listener.groovy
 *
 * ENDPOINT: change this to wherever the DevOps AI Agent server is running.
 *   - Jenkins in Docker, agent on host (Docker Desktop): http://host.docker.internal:8000/...
 *   - Both on the same machine:                          http://localhost:8000/...
 *   - Agent on a different server:                       http://<server-ip>:8000/...
 */

import hudson.model.listeners.RunListener
import hudson.model.Run
import groovy.json.JsonOutput
import java.net.http.HttpClient
import java.net.http.HttpRequest
import java.net.http.HttpResponse
import java.net.URI
import java.time.Duration
import jenkins.model.Jenkins

class DevOpsAgentListener extends RunListener<Run> {
    static final String ENDPOINT = "http://host.docker.internal:8000/webhook/jenkins-notification"

    void onFinalized(Run run) {
        Thread.start("devops-notifier") {
            try {
                def buildUrl = ""
                try { buildUrl = run.absoluteUrl } catch (e) { buildUrl = "" }

                def payload = [
                    name : run.parent.fullName,
                    build: [
                        number  : run.number,
                        phase   : "FINALIZED",
                        status  : run.result?.toString() ?: "UNKNOWN",
                        full_url: buildUrl,
                    ]
                ]
                def body = JsonOutput.toJson(payload)

                // HTTP/1.1 required — uvicorn does not support HTTP/2
                def client = HttpClient.newBuilder()
                    .version(HttpClient.Version.HTTP_1_1)
                    .connectTimeout(Duration.ofSeconds(5))
                    .build()
                def request = HttpRequest.newBuilder()
                    .uri(URI.create(ENDPOINT))
                    .header("Content-Type", "application/json")
                    .timeout(Duration.ofSeconds(10))
                    .POST(HttpRequest.BodyPublishers.ofString(body))
                    .build()
                def response = client.send(request, HttpResponse.BodyHandlers.ofString())
                println "[DevOpsAgent] ${run.parent.fullName} #${run.number} ${run.result} -> HTTP ${response.statusCode()}"
            } catch (Exception e) {
                println "[DevOpsAgent] Failed: ${e.class.simpleName}: ${e.message}"
            }
        }
    }
}

def extList = Jenkins.get().getExtensionList(RunListener.class)
extList.findAll { it.class.simpleName == "DevOpsAgentListener" }.each { extList.remove(it) }
extList.add(new DevOpsAgentListener())
println "DevOpsAgentListener registered"
