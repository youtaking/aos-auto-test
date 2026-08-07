pipeline {
    agent any

    parameters {
        string(name: 'TEST_REPO_BRANCH', description: 'aos-auto-test 分支', defaultValue: 'feat/jenkins-pipeline')
        booleanParam(name: 'FORCE_REBUILD', description: '强制重新构建（删除旧镜像）', defaultValue: false)
    }

    environment {
        IMAGE_NAME = "unit-runner:latest"
    }

    stages {
        stage('Init') {
            steps {
                sh '''
                    set +x
                    echo "============================================================"
                    echo "Build Unit Runner"
                    echo "  Branch: __BRANCH__"
                    echo "  Force:  __FORCE__"
                    echo "============================================================"
                '''.replace('__BRANCH__', params.TEST_REPO_BRANCH)
                  .replace('__FORCE__', params.FORCE_REBUILD.toString())

                script {
                    if (params.FORCE_REBUILD) {
                        sh '''
                            echo ">>> Removing old image..."
                            docker rmi -f unit-runner:latest || true
                        '''
                    }
                }
            }
        }

        stage('Clone Test Repo') {
            steps {
                sh '''
                    set +x
                    echo ">>> Cloning aos-auto-test (__BRANCH__)..."
                    rm -rf autotest
                    mkdir -p autotest

                    download_repo() {
                        local url="$1"
                        local output="$2"
                        local proxies="https://gh-proxy.com https://mirror.ghproxy.com https://ghfast.top https://ghproxy.net"
                        for proxy in $proxies ""; do
                            if [ -n "$proxy" ]; then
                                full_url="${proxy}/${url}"
                            else
                                full_url="$url"
                            fi
                            echo "    Trying: ${full_url}"
                            for i in 1 2 3; do
                                if curl --fail -SL --connect-timeout 10 --max-time 300 \\
                                  "${full_url}" -o "${output}" 2>/dev/null; then
                                    if [ -s "${output}" ]; then
                                        echo "    OK (proxy: ${proxy:-direct})"
                                        return 0
                                    fi
                                fi
                                echo "    Attempt $i failed, retrying..."
                                sleep 3
                            done
                            echo "    Proxy ${proxy:-direct} failed, trying next..."
                        done
                        echo "    ERROR: All proxies failed!"
                        return 1
                    }

                    download_repo \\
                      "https://github.com/youtaking/aos-auto-test/archive/refs/heads/__BRANCH__.tar.gz" \\
                      /tmp/autotest.tar.gz
                    tar xzf /tmp/autotest.tar.gz --strip-components=1 -C autotest
                    rm -f /tmp/autotest.tar.gz
                    echo "    aos-auto-test: $(ls autotest/ | wc -l) files/dirs"
                '''.replace('__BRANCH__', params.TEST_REPO_BRANCH)
            }
        }

        stage('Build Image') {
            steps {
                sh '''
                    set +x
                    echo ">>> Building unit-runner:latest..."
                    docker build -t unit-runner:latest -f autotest/Dockerfile.unit-runner autotest/
                    echo ""
                    echo ">>> Build complete:"
                    docker images | grep unit-runner
                '''
            }
        }

        stage('Verify') {
            steps {
                sh '''
                    set +x
                    echo ">>> Verifying image..."
                    docker run --rm unit-runner:latest --version
                    echo ""
                    echo ">>> Image details:"
                    docker image inspect unit-runner:latest --format '{{.Id}} {{.Created}} {{.Size}}'
                '''
            }
        }
    }

    post {
        success {
            echo "============================================================"
            echo "unit-runner:latest built successfully!"
            echo "============================================================"
        }
        failure {
            echo "============================================================"
            echo "unit-runner build FAILED"
            echo "============================================================"
        }
        always {
            sh '''
                echo ">>> Cleaning workspace..."
                rm -rf autotest
            '''
        }
    }
}
