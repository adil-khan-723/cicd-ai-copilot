pipeline {
    agent any

    environment {
        ECR_REGISTRY   = credentials('ECR_REGISTRY_URL')
        AWS_REGION     = 'us-east-1'
        IMAGE_NAME     = 'my-python-app'
        IMAGE_TAG      = "${BUILD_NUMBER}"
    }

    tools {
        // Ensure these names match your Jenkins Global Tool Configuration
    }

    stages {
        stage('Checkout') {
            steps {
                git(url: 'YOUR_REPO_URL', branch: 'YOUR_BRANCH', credentialsId: 'YOUR_GIT_CREDENTIALS_ID')
            }
        }

        stage('Test') {
            steps {
                sh '''
                    python -m pip install --upgrade pip
                    pip install -r requirements.txt
                    pytest tests/ --junitxml=test-results.xml
                '''
            }
            post {
                always {
                    junit 'test-results.xml'
                }
            }
        }

        stage('Docker Build') {
            steps {
                sh "docker build -t ${IMAGE_NAME}:${IMAGE_TAG} ."
            }
        }

        stage('Push to ECR') {
            steps {
                withCredentials([[$class: 'AmazonWebServicesCredentialsBinding',
                                  credentialsId: 'AWS_CREDENTIALS']]) {
                    sh '''
                        aws ecr get-login-password --region ${AWS_REGION} \
                          | docker login --username AWS --password-stdin ${ECR_REGISTRY}
                        docker tag ${IMAGE_NAME}:${IMAGE_TAG} ${ECR_REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}
                        docker push ${ECR_REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}
                    '''
                }
            }
        }
    }

    post {
        failure {
            echo "Build failed — check the Docker Build or Push to ECR stage logs."
        }
        success {
            echo "Image pushed: ${ECR_REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"
        }
    }
}
