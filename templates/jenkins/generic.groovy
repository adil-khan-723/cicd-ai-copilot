pipeline {
    agent any

    stages {
        stage('Checkout') {
            steps {
                checkout scm
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
