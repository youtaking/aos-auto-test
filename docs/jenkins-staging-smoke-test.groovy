// Staging 冒烟测试：health commitId 变化时运行，只跑 E2E 冒烟用例（pytest -m smoke）
// 参考 staging-monitor，去掉单元测试与全量用例解析，仅保留冒烟链路。
def buildTestArchiveUrl(String repo, String branch) {
    def br = branch ?: 'main'
    def base = repo.replaceAll(/\.git$/, '')
    if (base.contains('gitlab.')) {
        def m = (base =~ /^(https?:\/\/[^\/]+)\/(.+)$/)
        if (!m.matches()) {
            throw new RuntimeException("Cannot parse GitLab repo URL: ${repo}")
        }
        def projectPath = m[0][2].replace('/', '%2F')
        return "${m[0][1]}/api/v4/projects/${projectPath}/repository/archive.tar.gz?sha=${br.replace('/', '%2F')}"
    }
    return "${base}/archive/refs/heads/${br}.tar.gz"
}

pipeline {
    agent any

    parameters {
        string(name: 'HEALTH_URL',       defaultValue: 'http://100.105.9.16:38879/health',   description: '健康检查完整 URL')
        string(name: 'TARGET_URL',       defaultValue: 'http://100.105.9.16:38879',          description: '测试目标地址')
        string(name: 'AUTOTEST_URL',     defaultValue: 'http://100.105.114.178:8111',        description: 'AutoTest 后端地址')
        string(name: 'TEST_REPO',        defaultValue: 'https://gitlab.pazhoulab-huangpu.com/aos-test/aos-auto-test.git', description: '测试代码仓库')
        string(name: 'TEST_REPO_BRANCH', defaultValue: 'main',                            description: '测试代码分支')
        booleanParam(name: 'FORCE_RESET', defaultValue: false,                               description: '强制触发一次冒烟（清除上次 commitId 记录）')
        booleanParam(name: 'NOTIFY_WECOM', defaultValue: true,                               description: '完成后发送企业微信通知（手动触发时可取消勾选）')
    }

    environment {
        AUTOTEST_URL = "${params.AUTOTEST_URL}"
        TARGET_URL   = "${params.TARGET_URL}"
        HEALTH_URL   = "${params.HEALTH_URL}"
    }

    stages {
        stage('Check Runner Image') {
            steps {
                withCredentials([string(credentialsId: 'gitlab-read-token', variable: 'GL_TOKEN')]) {
                sh '''
                    set +x
                    echo "============================================================"
                    echo "[Staging Smoke] Check Runner Image"
                    echo "============================================================"

                    download_repo() {
                        local url="$1"
                        local output="$2"
                        local proxies="https://gh-proxy.com https://mirror.ghproxy.com https://ghfast.top https://ghproxy.net"
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
                                if curl --fail -SL --connect-timeout 10 --max-time 600 $auth_args "${full_url}" -o "${output}" 2>/tmp/curl_err.log; then
                                    if [ -s "${output}" ] && tar tzf "${output}" > /dev/null 2>&1; then
                                        echo "    OK (proxy: ${proxy:-direct})"
                                        return 0
                                    fi
                                fi
                                echo "    Attempt $i failed: $(tail -1 /tmp/curl_err.log)"
                                sleep 3
                            done
                            echo "    Proxy ${proxy:-direct} failed, trying next..."
                        done
                        echo "    ERROR: All proxies failed!"
                        return 1
                    }

                    if docker image inspect test-runner:latest > /dev/null 2>&1; then
                        echo ">>> test-runner:latest exists."
                    else
                        echo ">>> test-runner:latest not found, building..."
                        rm -rf /tmp/smoke-autotest
                        mkdir -p /tmp/smoke-autotest

                        ARCHIVE_URL="__TEST_ARCHIVE_URL__"
                        download_repo "${ARCHIVE_URL}" /tmp/autotest.tar.gz || true
                        if [ -f /tmp/autotest.tar.gz ] && [ -s /tmp/autotest.tar.gz ]; then
                            tar xzf /tmp/autotest.tar.gz --strip-components=1 -C /tmp/smoke-autotest
                        fi
                        if [ -f /tmp/smoke-autotest/Dockerfile.runner ]; then
                            docker build -t test-runner:latest -f /tmp/smoke-autotest/Dockerfile.runner /tmp/smoke-autotest/
                            echo "    test-runner:latest built."
                        else
                            echo "    WARNING: Dockerfile.runner not found, cannot build test-runner."
                        fi
                        rm -rf /tmp/smoke-autotest /tmp/autotest.tar.gz
                    fi
                '''.replace('__TEST_ARCHIVE_URL__', buildTestArchiveUrl(params.TEST_REPO, params.TEST_REPO_BRANCH ?: 'main'))
                }
            }
        }

        stage('Poll Health') {
            steps {
                sh '''
                    set +x
                    echo "============================================================"
                    echo "[Staging Smoke] Poll Health"
                    echo "  HEALTH_URL: __HEALTH_URL__"
                    echo "============================================================"

                    HEALTH_RESP=$(curl -sf --connect-timeout 10 --max-time 15 "__HEALTH_URL__" 2>/dev/null || echo "")

                    if [ -z "$HEALTH_RESP" ]; then
                        echo ">>> Health endpoint unreachable, skipping this poll."
                        if [ -f .health_down ]; then
                            echo "DOWN" > .poll_result
                        else
                            echo "DOWN_ALERT" > .poll_result
                            touch .health_down
                        fi
                        exit 0
                    fi
                    rm -f .health_down

                    echo ">>> Health response: $HEALTH_RESP"

                    CURRENT_COMMIT=$(echo "$HEALTH_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('commitId',''))" 2>/dev/null || echo "")
                    CURRENT_VERSION=$(echo "$HEALTH_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('version',''))" 2>/dev/null || echo "")
                    STARTED_AT=$(echo "$HEALTH_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('startedAt',''))" 2>/dev/null || echo "")

                    if [ -z "$CURRENT_COMMIT" ]; then
                        echo ">>> No commitId in health response, skipping."
                        echo "SKIP" > .poll_result
                        exit 0
                    fi

                    if [ "__FORCE_RESET__" = "true" ]; then
                        rm -f .last_commit_id
                        echo ">>> FORCE_RESET: cleared last commit record"
                    fi

                    LAST_COMMIT=$(cat .last_commit_id 2>/dev/null || echo "")

                    if [ "$CURRENT_COMMIT" = "$LAST_COMMIT" ]; then
                        echo ">>> No change: commitId=$CURRENT_COMMIT (same as last poll)"
                        echo "SKIP" > .poll_result
                        exit 0
                    fi

                    echo ">>> Commit changed: $LAST_COMMIT → $CURRENT_COMMIT"
                    echo "$CURRENT_COMMIT" > .last_commit_id
                    echo "$CURRENT_COMMIT" > .current_commit
                    echo "$CURRENT_VERSION" > .current_version
                    echo "$STARTED_AT" > .started_at
                    echo "$HEALTH_RESP" > .health_resp
                    echo "CHANGED" > .poll_result
                '''.replace('__HEALTH_URL__', params.HEALTH_URL)
                  .replace('__FORCE_RESET__', params.FORCE_RESET ? 'true' : 'false')
            }
            post {
                always {
                    script {
                        def result = readFile('.poll_result').trim()
                        if (result == 'DOWN_ALERT' || result == 'DOWN') {
                            currentBuild.result = 'UNSTABLE'
                            currentBuild.displayName = "#${env.BUILD_NUMBER} [ALERT] health unreachable"
                            if (result == 'DOWN_ALERT' && (params.NOTIFY_WECOM != null ? params.NOTIFY_WECOM : true)) {
                                withCredentials([string(credentialsId: 'wecom-webhook', variable: 'WECOM_WEBHOOK')]) {
                                    sh '''
                                        set +x
                                        python3 -c "
import json, os, urllib.request
content = '### Staging 冒烟环境健康检查失败\\n> 地址: __HEALTH_URL__\\n> [Jenkins 构建日志](' + os.environ.get('BUILD_URL', '') + ')'
msg = {'msgtype': 'markdown', 'markdown': {'content': content}}
req = urllib.request.Request(os.environ['WECOM_WEBHOOK'], data=json.dumps(msg).encode('utf-8'), headers={'Content-Type': 'application/json'})
try:
    print(urllib.request.urlopen(req, timeout=10).read().decode('utf-8'))
except Exception as e:
    print('wecom notify failed:', e)
"
                                    '''.replace('__HEALTH_URL__', params.HEALTH_URL)
                                }
                            }
                        } else if (result == 'SKIP') {
                            currentBuild.displayName = "#${env.BUILD_NUMBER} [SKIP] no change"
                        } else if (result == 'CHANGED') {
                            def commit = readFile('.current_commit').trim()
                            def version = readFile('.current_version').trim()
                            currentBuild.displayName = "#${env.BUILD_NUMBER} [SMOKE] ${commit} v${version}"
                        } else {
                            currentBuild.displayName = "#${env.BUILD_NUMBER} [SKIP] ${result}"
                        }
                    }
                }
            }
        }

        stage('Clone Test Code') {
            when {
                expression { readFile('.poll_result').trim() == 'CHANGED' }
            }
            steps {
                withCredentials([string(credentialsId: 'gitlab-read-token', variable: 'GL_TOKEN')]) {
                sh '''
                    set +x
                    echo "============================================================"
                    echo "[Staging Smoke] Clone Test Code"
                    echo "============================================================"

                    rm -rf autotest
                    mkdir -p autotest

                    download_repo() {
                        local url="$1"
                        local output="$2"
                        local proxies="https://gh-proxy.com https://mirror.ghproxy.com https://ghfast.top https://ghproxy.net"
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
                                if curl --fail -SL --connect-timeout 10 --max-time 600 $auth_args "${full_url}" -o "${output}" 2>/tmp/curl_err.log; then
                                    if [ -s "${output}" ] && tar tzf "${output}" > /dev/null 2>&1; then
                                        echo "    OK (proxy: ${proxy:-direct})"
                                        return 0
                                    fi
                                fi
                                echo "    Attempt $i failed: $(tail -1 /tmp/curl_err.log)"
                                sleep 2
                            done
                            echo "    Proxy ${proxy:-direct} failed, trying next..."
                        done
                        echo "    ERROR: All proxies failed!"
                        return 1
                    }

                    ARCHIVE_URL="__TEST_ARCHIVE_URL__"
                    download_repo "${ARCHIVE_URL}" /tmp/autotest.tar.gz
                    tar xzf /tmp/autotest.tar.gz --strip-components=1 -C autotest
                    rm -f /tmp/autotest.tar.gz
                    echo "    Test code: $(ls autotest/ | wc -l) files/dirs"
                    echo "    Test branch: __TEST_BRANCH__"
                '''.replace('__TEST_ARCHIVE_URL__', buildTestArchiveUrl(params.TEST_REPO, params.TEST_REPO_BRANCH ?: 'main'))
                  .replace('__TEST_BRANCH__', params.TEST_REPO_BRANCH ?: 'main')
                }
            }
        }

        stage('Prepare Smoke Record') {
            when {
                expression { readFile('.poll_result').trim() == 'CHANGED' }
            }
            steps {
                withCredentials([string(credentialsId: 'autotest-token', variable: 'TOKEN')]) {
                    sh '''
                        set +x
                        echo "============================================================"
                        echo "[Staging Smoke] Create Pipeline Record"
                        echo "============================================================"

                        CURRENT_COMMIT=$(cat .current_commit)
                        CURRENT_VERSION=$(cat .current_version)
                        STARTED_AT=$(cat .started_at)

                        CREATE_RESP=$(curl -sf -X POST \\
                          -H "Authorization: Bearer $TOKEN" \\
                          -H "Content-Type: application/json" \\
                          -d "{
                            \\"pr_title\\": \\"Smoke: v${CURRENT_VERSION}\\",
                            \\"commit_sha\\": \\"${CURRENT_COMMIT}\\",
                            \\"branch\\": \\"smoke\\",
                            \\"author\\": \\"system\\",
                            \\"target_url\\": \\"__TARGET_URL__\\",
                            \\"build_info\\": {\\"version\\": \\"${CURRENT_VERSION}\\", \\"startedAt\\": \\"${STARTED_AT}\\", \\"commitId\\": \\"${CURRENT_COMMIT}\\", \\"jenkins_url\\": \\"${BUILD_URL}\\", \\"build_number\\": ${BUILD_NUMBER}, \\"suite\\": \\"smoke\\"}
                          }" \\
                          "__AUTOTEST_URL__/api/pipelines" 2>/dev/null || echo "")

                        echo ">>> Create pipeline response: $CREATE_RESP"

                        PIPELINE_ID=$(echo "$CREATE_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('data',{}).get('id',''))" 2>/dev/null || echo "")
                        echo "$PIPELINE_ID" > .pipeline_id
                        echo "    Pipeline ID: $PIPELINE_ID"
                    '''.replace('__AUTOTEST_URL__', params.AUTOTEST_URL)
                      .replace('__TARGET_URL__', params.TARGET_URL)
                }
            }
        }

        stage('Run Smoke Tests') {
            when {
                expression { readFile('.poll_result').trim() == 'CHANGED' }
            }
            steps {
                withCredentials([string(credentialsId: 'autotest-token', variable: 'TOKEN')]) {
                    sh '''
                        set +x
                        echo "============================================================"
                        echo "[Staging Smoke] Run Smoke Tests"
                        echo "  Target: __TARGET_URL__"
                        echo "  Marker: smoke"
                        echo "============================================================"

                        PIPELINE_ID=$(cat .pipeline_id 2>/dev/null || echo "")

                        if [ -n "$PIPELINE_ID" ]; then
                            curl -sf -X PUT \\
                              -H "Authorization: Bearer $TOKEN" \\
                              -H "Content-Type: application/json" \\
                              -d '{"status": "running"}' \\
                              "__AUTOTEST_URL__/api/pipelines/${PIPELINE_ID}/status" > /dev/null 2>&1 || true
                        fi

                        mkdir -p autotest/tests/results

                        set +e
                        JENKINS_WORKSPACE_HOST=$(echo "${WORKSPACE}" | sed 's|/var/jenkins_home|/opt/1panel/apps/jenkins/jenkins/data|')

                        docker run --rm \\
                          --name "smoke-test-runner-${BUILD_NUMBER}" \\
                          -v "${JENKINS_WORKSPACE_HOST}/autotest/tests:/app/tests" \\
                          -v "${JENKINS_WORKSPACE_HOST}/autotest/conftest.py:/app/conftest.py" \\
                          -v "${JENKINS_WORKSPACE_HOST}/autotest/pytest.ini:/app/pytest.ini" \\
                          -e "FENIX_URL=__TARGET_URL__" \\
                          -e "FENIX_API_BASE_URL=__TARGET_URL__" \\
                          -e "HEADLESS=true" \\
                          -e "PYTHONUNBUFFERED=1" \\
                          --network bridge \\
                          test-runner:latest \\
                          pytest /app/tests/suites -m smoke -v --tb=short \\
                            --base-url=__TARGET_URL__ \\
                            --json-report --json-report-file=/app/tests/results/report.json \\
                            --alluredir=/app/tests/results/allure-results
                        TEST_EXIT=$?
                        set -e

                        echo ">>> Smoke test exit code: $TEST_EXIT"
                        echo "$TEST_EXIT" > .test_exit

                        if [ $TEST_EXIT -eq 5 ]; then
                            echo ">>> WARNING: 未收集到任何 smoke 用例，请确认测试分支包含 @pytest.mark.smoke 标记"
                        fi

                        if [ -f autotest/tests/results/report.json ] && [ -n "$PIPELINE_ID" ]; then
                            echo ">>> Uploading smoke test results..."
                            curl -sf -X POST \\
                              -H "Authorization: Bearer $TOKEN" \\
                              -H "Content-Type: application/json" \\
                              -d @autotest/tests/results/report.json \\
                              "__AUTOTEST_URL__/api/pipelines/${PIPELINE_ID}/results" > /dev/null 2>&1 || true
                        fi

                        if [ $TEST_EXIT -eq 0 ]; then
                            FINAL_STATUS="passed"
                        else
                            FINAL_STATUS="failed"
                        fi

                        if [ -n "$PIPELINE_ID" ]; then
                            curl -sf -X PUT \\
                              -H "Authorization: Bearer $TOKEN" \\
                              -H "Content-Type: application/json" \\
                              -d "{\\"status\\": \\"${FINAL_STATUS}\\"}" \\
                              "__AUTOTEST_URL__/api/pipelines/${PIPELINE_ID}/status" > /dev/null 2>&1 || true
                        fi

                        echo ">>> Pipeline ${PIPELINE_ID}: ${FINAL_STATUS}"

                        # 非零退出码不阻塞 Jenkins job（下次 commit 变化仍会继续触发）
                        exit 0
                    '''.replace('__TARGET_URL__', params.TARGET_URL)
                      .replace('__AUTOTEST_URL__', params.AUTOTEST_URL)
                }
            }
        }

        stage('Generate Allure Report') {
            when {
                expression { readFile('.poll_result').trim() == 'CHANGED' }
            }
            steps {
                script {
                    try {
                        allure includeProperties: false,
                               jdk: '',
                               results: [[path: 'autotest/tests/results/allure-results']]
                    } catch (Exception e) {
                        echo "Allure report generation failed: ${e.message}"
                    }
                    sh 'zip -r allure-report.zip allure-report 2>/dev/null || true'
                    if (fileExists('allure-report.zip')) {
                        archiveArtifacts artifacts: 'allure-report.zip', allowEmptyArchive: true
                    }
                }
            }
        }

        stage('Notify WeCom') {
            when {
                expression { readFile('.poll_result').trim() == 'CHANGED' }
            }
            steps {
                script {
                    if (params.NOTIFY_WECOM != null ? params.NOTIFY_WECOM : true) {
                        def testExit = (fileExists('.test_exit') ? readFile('.test_exit').trim() : '0') as int
                        def CR = currentBuild.currentResult
                        def PIPELINE_RESULT = (testExit >= 2 || CR == 'FAILURE' || CR == 'ABORTED') ? 'FAIL' : 'SUCCESS'
                        withCredentials([string(credentialsId: 'wecom-webhook', variable: 'WECOM_WEBHOOK')]) {
                            sh '''
                                set +x
                                RESULT="__RESULT__"
                                if [ "$RESULT" = "SUCCESS" ]; then
                                    export ICON="✅"
                                    export STATUS="成功"
                                else
                                    export ICON="❌"
                                    export STATUS="失败"
                                fi
                                python3 -c "
import json, os
icon = os.environ.get('ICON', '')
status = os.environ.get('STATUS', '')
build_url = os.environ.get('BUILD_URL', '')

def read_file(path):
    try:
        return open(path, 'r', encoding='utf-8').read().strip()
    except Exception:
        return ''

commit = read_file('.current_commit')
version = read_file('.current_version')

e2e = {'passed': 0, 'failed': 0, 'skipped': 0, 'error': 0}
failed_names = []
report = 'autotest/tests/results/report.json'
if os.path.exists(report):
    data = json.load(open(report, 'r', encoding='utf-8'))
    for t in data.get('tests', []):
        outcome = t.get('outcome', '')
        if outcome not in ('passed', 'failed', 'skipped', 'error'):
            continue
        e2e[outcome] += 1
        if outcome in ('failed', 'error') and len(failed_names) < 10:
            failed_names.append(t.get('nodeid', ''))

lines = [
    '### ' + icon + ' Staging 冒烟测试' + status,
    '> commit: ' + commit,
    '> 版本: ' + version,
    '> **冒烟用例**: ' + str(e2e['passed']) + ' 通过 / ' + str(e2e['failed']) + ' 失败 / ' + str(e2e['skipped']) + ' 跳过' + (' / ' + str(e2e['error']) + ' 错误' if e2e['error'] else ''),
    '> [Jenkins 构建日志](' + build_url + ')',
]
if failed_names:
    lines.append('> 失败用例: ' + ', '.join(failed_names))
if build_url:
    lines.append('> [Allure 报告](' + build_url + 'allure/)')
payload = {'msgtype': 'markdown', 'markdown': {'content': chr(10).join(lines)}}
open('wecom_payload.json', 'w', encoding='utf-8').write(json.dumps(payload, ensure_ascii=False))
                                "
                                curl -s -X POST "$WECOM_WEBHOOK" \
                                  -H "Content-Type: application/json" \
                                  -d @wecom_payload.json
                            '''.replace('__RESULT__', PIPELINE_RESULT)
                        }
                    } else {
                        echo '>>> 企业微信通知已关闭（NOTIFY_WECOM=false）'
                    }
                }
            }
        }
    }
}
