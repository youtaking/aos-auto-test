pipeline {
    agent any

    environment {
        AUTOTEST_URL = "http://100.105.181.173:8000"
        APP_REPO     = "https://github.com/youtaking/FenixAgent.git"
        TEST_REPO    = "https://github.com/youtaking/aos-auto-test.git"
        PROJECT_NAME = "pr-env-${BUILD_NUMBER}"

        PORT_OFFSET = "${(BUILD_NUMBER.toInteger() % 10) * 3}"
        RCS_PORT    = "${30000 + PORT_OFFSET.toInteger()}"
        PG_PORT     = "${30001 + PORT_OFFSET.toInteger()}"
        LITE_PORT   = "${30002 + PORT_OFFSET.toInteger()}"
    }

    stages {
        stage('Clone Repos') {
            steps {
                dir('app') {
                    git url: env.APP_REPO,
                        branch: params.PR_BRANCH,
                        credentialsId: 'github-token'
                }
                dir('autotest') {
                    git url: env.TEST_REPO,
                        branch: 'feat/jenkins-pipeline',
                        credentialsId: 'github-token'
                }
            }
        }

        stage('Build Image') {
            steps {
                dir('app') {
                    sh "docker build -t ${PROJECT_NAME}:${BUILD_NUMBER} ."
                }
            }
        }

        stage('Write Compose') {
            steps {
                writeFile file: 'docker-compose.yml', text: """
services:
  postgres:
    image: postgres:16-alpine
    privileged: true
    ports:
      - "${PG_PORT}:5432"
    environment:
      POSTGRES_USER: rcs
      POSTGRES_PASSWORD: rcs
      POSTGRES_DB: rcs
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U rcs"]
      interval: 5s
      timeout: 5s
      retries: 5

  litellm:
    image: ghcr.io/berriai/litellm:main-stable
    depends_on:
      postgres:
        condition: service_healthy
    ports:
      - "${LITE_PORT}:4000"
    environment:
      DATABASE_URL: postgresql://rcs:rcs@postgres:5432/litellm
      LITELLM_MASTER_KEY: sk-litellm-admin-dev-key
      STORE_MODEL_IN_DB: "True"

  rcs:
    image: ${PROJECT_NAME}:${BUILD_NUMBER}
    depends_on:
      postgres:
        condition: service_healthy
    ports:
      - "${RCS_PORT}:3000"
    environment:
      DATABASE_URL: postgres://rcs:rcs@postgres:5432/rcs
      RCS_HOST: 0.0.0.0
      RCS_PORT: 3000
      RCS_API_KEYS: sk-rcs-dev-key
      RCS_SECRET_LITELLM_ADMIN_KEY: sk-litellm-admin-dev-key
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/health"]
      interval: 10s
      timeout: 5s
      retries: 12

  test-runner:
    image: test-runner:latest
    depends_on:
      rcs:
        condition: service_healthy
    volumes:
      - ${WORKSPACE}/autotest/tests:/app/tests
      - ${WORKSPACE}/autotest/conftest.py:/app/conftest.py
      - ${WORKSPACE}/autotest/test_targets.txt:/app/test_targets.txt
    environment:
      FENIX_URL: http://rcs:3000
      FENIX_API_BASE_URL: http://rcs:3000
      HEADLESS: "true"
      PYTHONUNBUFFERED: "1"
    command: >
      sh -c "pytest \\$(cat /app/test_targets.txt) -v --tb=short
      --base-url=http://rcs:3000
      --json-report --json-report-file=/app/results/report.json"
"""
            }
        }

        stage('Deploy') {
            steps {
                sh "docker compose -p ${PROJECT_NAME} up -d postgres litellm rcs"
                sh """
                    echo "Waiting for RCS to be healthy..."
                    for i in \$(seq 1 60); do
                        if curl -sf http://localhost:${RCS_PORT}/health > /dev/null 2>&1; then
                            echo "RCS is healthy!"
                            exit 0
                        fi
                        echo "Attempt \$i/60 - waiting..."
                        sleep 5
                    done
                    echo "RCS health check timeout!"
                    exit 1
                """
            }
        }

        stage('Create Pipeline Record') {
            steps {
                withCredentials([string(credentialsId: 'autotest-token', variable: 'TOKEN')]) {
                    sh """
                        curl -s -X POST ${AUTOTEST_URL}/api/pipelines \\
                          -H "Authorization: Bearer \$TOKEN" \\
                          -H "Content-Type: application/json" \\
                          -d '{
                            "pr_id": ${params.PR_ID ?: 0},
                            "pr_title": "${params.PR_TITLE ?: ""}",
                            "commit_sha": "${params.COMMIT_SHA ?: env.GIT_COMMIT}",
                            "branch": "${params.PR_BRANCH}",
                            "repo_url": "${env.APP_REPO}",
                            "author": "${params.AUTHOR ?: ""}",
                            "target_url": "http://localhost:${RCS_PORT}",
                            "build_info": {
                              "jenkins_url": "${env.BUILD_URL}",
                              "build_number": ${BUILD_NUMBER},
                              "docker_image": "${PROJECT_NAME}:${BUILD_NUMBER}",
                              "rcs_port": ${RCS_PORT},
                              "pg_port": ${PG_PORT},
                              "litellm_port": ${LITE_PORT}
                            }
                          }' > pipeline.json

                        echo "Pipeline created:"
                        cat pipeline.json
                    """
                }
            }
        }

        stage('Resolve Tests') {
            steps {
                withCredentials([string(credentialsId: 'autotest-token', variable: 'TOKEN')]) {
                    sh """
                        # 尝试从 AutoTest API 解析用例集
                        RESOLVE_RESP=\\$(curl -s -w "\\n%{http_code}" \\
                          -H "Authorization: Bearer \$TOKEN" \\
                          ${AUTOTEST_URL}/api/ci/resolve-tests)

                        HTTP_CODE=\\$(echo "\$RESOLVE_RESP" | tail -1)
                        BODY=\\$(echo "\$RESOLVE_RESP" | sed '\\$d')

                        if [ "\$HTTP_CODE" = "200" ]; then
                            # API 成功，提取 node_ids
                            NODE_IDS=\\$(echo "\$BODY" | python3 -c "
                        import sys, json
                        data = json.load(sys.stdin)
                        ids = data.get('data', {}).get('node_ids', [])
                        print(' '.join(ids))
                        " 2>/dev/null)
                        fi

                        if [ -n "\$NODE_IDS" ]; then
                            echo "AutoTest API resolved: \$NODE_IDS"
                            echo "\$NODE_IDS" > test_targets.txt
                        elif [ -f autotest/tests/ci/cases.txt ]; then
                            echo "AutoTest API unavailable, using cases.txt fallback"
                            grep -v '^#' autotest/tests/ci/cases.txt | grep -v '^\\$' | tr '\\n' ' ' > test_targets.txt
                            echo "Fallback targets: \\$(cat test_targets.txt)"
                        else
                            echo "No test targets resolved, running all tests"
                            echo "/app/tests/suites /app/tests/api_suites" > test_targets.txt
                        fi
                    """
                }
                // 将 test_targets.txt 复制到 autotest 目录（通过 volume 挂载进容器）
                sh "cp test_targets.txt autotest/test_targets.txt"
            }
        }

        stage('Run Tests') {
            steps {
                sh "docker compose -p ${PROJECT_NAME} logs -f test-runner &"
                sh "docker compose -p ${PROJECT_NAME} up test-runner"
            }
        }

        stage('Collect Results') {
            steps {
                sh "docker cp ${PROJECT_NAME}-test-runner-1:/app/results/report.json report.json || true"
                withCredentials([string(credentialsId: 'autotest-token', variable: 'TOKEN')]) {
                    sh """
                        PIPELINE_ID=\$(cat pipeline.json | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['id'])")
                        if [ -f report.json ]; then
                            curl -s -X POST ${AUTOTEST_URL}/api/pipelines/\${PIPELINE_ID}/results \\
                              -H "Authorization: Bearer \$TOKEN" \\
                              -H "Content-Type: application/json" \\
                              -d @report.json
                        fi
                    """
                }
            }
        }
    }

    post {
        success {
            withCredentials([string(credentialsId: 'autotest-token', variable: 'TOKEN')]) {
                sh """
                    PIPELINE_ID=\$(cat pipeline.json | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['id'])")
                    curl -s -X PUT ${AUTOTEST_URL}/api/pipelines/\${PIPELINE_ID}/status \\
                      -H "Authorization: Bearer \$TOKEN" \\
                      -H "Content-Type: application/json" \\
                      -d '{"status": "passed"}'
                """
            }
        }
        failure {
            withCredentials([string(credentialsId: 'autotest-token', variable: 'TOKEN')]) {
                sh """
                    if [ -f pipeline.json ]; then
                        PIPELINE_ID=\$(cat pipeline.json | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['id'])")
                        curl -s -X PUT ${AUTOTEST_URL}/api/pipelines/\${PIPELINE_ID}/status \\
                          -H "Authorization: Bearer \$TOKEN" \\
                          -H "Content-Type: application/json" \\
                          -d '{"status": "failed"}'
                    fi
                """
            }
        }
        always {
            sh """
                docker compose -p ${PROJECT_NAME} down -v || true
                docker rmi -f ${PROJECT_NAME}:${BUILD_NUMBER} || true
            """
        }
    }
}
