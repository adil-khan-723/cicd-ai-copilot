pipeline {
    agent any

    environment {
        APP_NAME   = 'my-java-app'
        IMAGE_TAG  = "${BUILD_NUMBER}"
    }

    tools {
        maven 'Maven 3.9'
        jdk   'JDK 17'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Build & Test') {
            steps {
                sh 'mvn clean verify -B'
            }
            post {
                always {
                    junit '**/target/surefire-reports/*.xml'
                }
            }
        }

        stage('Package') {
            steps {
                sh 'mvn package -DskipTests -B'
                archiveArtifacts artifacts: 'target/*.jar', fingerprint: true
            }
        }

        stage('Deploy') {
            when {
                branch 'main'
            }
            steps {
                echo 'Add your deployment steps here (e.g. scp, Docker, Ansible)'
            }
        }
    }

    post {
        failure {
            echo "Build failed — check the Build & Test stage logs."
        }
        success {
            echo "Build ${BUILD_NUMBER} succeeded."
        }
    }
}
