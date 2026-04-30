pipeline {
    agent any

    stages {
        stage('Checkout') {
            steps {
                git(url: 'YOUR_REPO_URL', branch: 'YOUR_BRANCH', credentialsId: 'YOUR_GIT_CREDENTIALS_ID')
            }
        }

        stage('Build') {
            steps {
                echo 'Add your build steps here'
                sh 'make build'
            }
        }

        stage('Test') {
            steps {
                echo 'Add your test steps here'
                sh 'make test'
            }
        }

        stage('Deploy') {
            when {
                branch 'main'
            }
            steps {
                echo 'Add your deploy steps here'
            }
        }
    }

    post {
        failure {
            echo "Pipeline failed — review the stage logs above."
        }
        success {
            echo "Pipeline completed successfully."
        }
    }
}
