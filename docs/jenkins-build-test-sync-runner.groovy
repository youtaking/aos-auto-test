pipeline {
    agent any

    parameters {
        string(name: 'TEST_REPO_BRANCH', description: 'aos-auto-test 分支', defaultValue: 'main')
        string(name: 'CLAUDE_CODE_VERSION', description: 'Claude Code CLI 版本（latest 或具体版本号）', defaultValue: 'latest')
        booleanParam(name: 'FORCE_REBUILD', description: '强制重新构建（删除旧镜像）', defaultValue: false)
    }

    environment {
        IMAGE_NAME = "test-sync-runner:latest"
    }

    stages {
        stage('Init') {
            steps {
                sh '''
                    set +x
                    echo "============================================================"
                    echo "Build Test Sync Runner"
                    echo "  Branch:  __BRANCH__"
                    echo "  Claude:  __CLAUDE__"
                    echo "============================================================"
                '''.replace('__BRANCH__', params.TEST_REPO_BRANCH)
                  .replace('__CLAUDE__', params.CLAUDE_CODE_VERSION)

                script {
                    if (params.FORCE_REBUILD) {
                        sh '''
                            echo ">>> Removing old image..."
                            docker rmi -f test-sync-runner:latest || true
                        '''
                    }
                }
            }
        }

        stage('Clone Test Repo') {
            steps {
                withCredentials([string(credentialsId: 'gitlab-read-token', variable: 'GL_TOKEN')]) {
                sh '''
                    set +x
                    echo ">>> Cloning aos-auto-test (__BRANCH__)..."
                    rm -rf autotest
                    mkdir -p autotest

                    download_repo() {
                        local url="$1"
                        local output="$2"
                        local proxies="https://gh-proxy.com https://ghproxy.net https://ghfast.top https://gh-proxy.com"
                        local auth_args=""
                        case "$url" in
                            *gitlab.*)
                                proxies=""
                                auth_args="-H PRIVATE-TOKEN:${GL_TOKEN}"
                                ;;
                        esac
                        for proxy in $proxies ""; do
                            if [ -n "$proxy" ]; then
                                full_url="${proxy}/${url}"
                            else
                                full_url="$url"
                            fi
                            echo "    Trying: ${full_url}"
                            for i in 1 2 3; do
                                if curl --fail -SL --connect-timeout 10 --max-time 300 \\
                                  $auth_args "${full_url}" -o "${output}" 2>/dev/null; then
                                    if [ -s "${output}" ] && tar tzf "${output}" > /dev/null 2>&1; then
                                        echo "    OK (proxy: ${proxy:-direct})"
                                        return 0
                                    fi
                                fi
                                echo "    Attempt $i failed, retrying..."
                                sleep 3
                            done
                        done
                        echo "    ERROR: All proxies failed!"
                        return 1
                    }

                    download_repo \\
                      "https://gitlab.pazhoulab-huangpu.com/api/v4/projects/aos-test%2Faos-auto-test/repository/archive.tar.gz?sha=__BRANCH__" \\
                      /tmp/autotest.tar.gz
                    tar xzf /tmp/autotest.tar.gz --strip-components=1 -C autotest
                    rm -f /tmp/autotest.tar.gz
                    echo "    aos-auto-test: $(ls autotest/ | wc -l) files/dirs"
                '''.replace('__BRANCH__', params.TEST_REPO_BRANCH)
                }
            }
        }

        stage('Build Image') {
            steps {
                sh '''
                    set +x
                    echo ">>> Building test-sync-runner:latest..."
                    docker build \
                      --build-arg CLAUDE_CODE_VERSION=__CLAUDE__ \
                      -t test-sync-runner:latest \
                      -f autotest/Dockerfile.test-sync-runner autotest/
                    echo ""
                    docker images | grep test-sync-runner
                '''.replace('__CLAUDE__', params.CLAUDE_CODE_VERSION)
            }
        }

        stage('Verify') {
            steps {
                sh '''
                    set +x
                    echo ">>> Verifying image toolchain..."
                    docker run --rm --entrypoint sh test-sync-runner:latest -c "python --version && bun --version && node --version && git --version && claude --version"
                    echo ""
                    docker image inspect test-sync-runner:latest --format '{{.Id}} {{.Created}} {{.Size}}'
                '''
            }
        }
    }

    post {
        success {
            echo "============================================================"
            echo "test-sync-runner:latest built successfully!"
            echo "============================================================"
        }
        failure {
            echo "============================================================"
            echo "test-sync-runner build FAILED"
            echo "============================================================"
        }
        always {
            sh '''
                rm -rf autotest
            '''
        }
    }
}
