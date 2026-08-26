pipeline {
    agent any

    parameters {
        string(name: 'HEALTH_URL',       defaultValue: 'http://192.168.122.18:38879/health',   description: '健康检查完整 URL')
        string(name: 'TARGET_URL',       defaultValue: 'http://192.168.122.18:38879',          description: '测试目标地址')
        string(name: 'APP_REPO',         defaultValue: 'https://github.com/HuangPuStar/FenixAgent.git', description: '被测项目仓库地址（单元测试需要）')
        string(name: 'APP_BRANCH',       defaultValue: 'main',                               description: '被测项目分支（单元测试源码）')
        string(name: 'POLL_INTERVAL',    defaultValue: '30',                                  description: '轮询间隔（分钟）')
        string(name: 'AUTOTEST_URL',     defaultValue: 'http://100.105.181.173:8111',        description: 'AutoTest 后端地址')
        string(name: 'TEST_REPO',        defaultValue: 'https://github.com/youtaking/aos-auto-test.git', description: '测试代码仓库')
        string(name: 'TEST_REPO_BRANCH', defaultValue: 'master',               description: '测试代码分支')
        booleanParam(name: 'FORCE_RESET', defaultValue: false,                                description: '强制触发测试（清除上次 commitId 记录）')
        booleanParam(name: 'NOTIFY_WECOM', defaultValue: true,                                 description: '测试完成后发送企业微信通知（手动触发时可取消勾选）')
    }

    environment {
        AUTOTEST_URL = "${params.AUTOTEST_URL}"
        TARGET_URL   = "${params.TARGET_URL}"
        HEALTH_URL   = "${params.HEALTH_URL}"
    }

    stages {
        stage('Check Runner Images') {
            steps {
                sh '''
                    set +x
                    echo "============================================================"
                    echo "[Staging Monitor] Check Runner Images"
                    echo "============================================================"

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
                                if curl --fail -SL --connect-timeout 10 --max-time 300 "${full_url}" -o "${output}" 2>/dev/null; then
                                    if [ -s "${output}" ] && tar tzf "${output}" > /dev/null 2>&1; then
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

                    if docker image inspect test-runner:latest > /dev/null 2>&1; then
                        echo ">>> test-runner:latest exists."
                    else
                        echo ">>> test-runner:latest not found, building..."
                        rm -rf /tmp/staging-autotest
                        mkdir -p /tmp/staging-autotest

                        ARCHIVE_URL="__TEST_REPO__/archive/refs/heads/__TEST_BRANCH__.tar.gz"
                        download_repo "${ARCHIVE_URL}" /tmp/autotest.tar.gz || true
                        if [ -f /tmp/autotest.tar.gz ] && [ -s /tmp/autotest.tar.gz ]; then
                            tar xzf /tmp/autotest.tar.gz --strip-components=1 -C /tmp/staging-autotest
                        fi
                        if [ -f /tmp/staging-autotest/Dockerfile.runner ]; then
                            docker build -t test-runner:latest -f /tmp/staging-autotest/Dockerfile.runner /tmp/staging-autotest/
                            echo "    test-runner:latest built."
                        else
                            echo "    WARNING: Dockerfile.runner not found, cannot build test-runner."
                        fi
                        rm -rf /tmp/staging-autotest /tmp/autotest.tar.gz
                    fi

                    if docker image inspect unit-runner:latest > /dev/null 2>&1; then
                        echo ">>> unit-runner:latest exists."
                    else
                        echo ">>> unit-runner:latest not found, building..."
                        rm -rf /tmp/staging-autotest
                        mkdir -p /tmp/staging-autotest

                        ARCHIVE_URL="__TEST_REPO__/archive/refs/heads/__TEST_BRANCH__.tar.gz"
                        download_repo "${ARCHIVE_URL}" /tmp/autotest.tar.gz || true
                        if [ -f /tmp/autotest.tar.gz ] && [ -s /tmp/autotest.tar.gz ]; then
                            tar xzf /tmp/autotest.tar.gz --strip-components=1 -C /tmp/staging-autotest
                        fi
                        if [ -f /tmp/staging-autotest/Dockerfile.unit-runner ]; then
                            mkdir -p /tmp/staging-autotest/cache
                            [ -f /tmp/staging-autotest/cache/package.json ] || echo '{"name":"empty","version":"0.0.0"}' > /tmp/staging-autotest/cache/package.json
                            [ -f /tmp/staging-autotest/cache/bun.lockb ] || touch /tmp/staging-autotest/cache/bun.lockb
                            docker build -t unit-runner:latest -f /tmp/staging-autotest/Dockerfile.unit-runner /tmp/staging-autotest/
                            echo "    unit-runner:latest built."
                        else
                            echo "    WARNING: Dockerfile.unit-runner not found, cannot build unit-runner."
                        fi
                        rm -rf /tmp/staging-autotest /tmp/autotest.tar.gz
                    fi
                '''.replace('__TEST_REPO__', params.TEST_REPO.replace('.git', ''))
                  .replace('__TEST_BRANCH__', params.TEST_REPO_BRANCH ?: 'master')
            }
        }

        stage('Poll Health') {
            steps {
                sh '''
                    set +x
                    echo "============================================================"
                    echo "[Staging Monitor] Poll Health"
                    echo "  HEALTH_URL: __HEALTH_URL__"
                    echo "============================================================"

                    HEALTH_RESP=$(curl -sf --connect-timeout 10 --max-time 15 "__HEALTH_URL__" 2>/dev/null || echo "")

                    if [ -z "$HEALTH_RESP" ]; then
                        echo ">>> Health endpoint unreachable, skipping this poll."
                        echo "SKIP" > .poll_result
                        exit 0
                    fi

                    echo ">>> Health response: $HEALTH_RESP"

                    CURRENT_COMMIT=$(echo "$HEALTH_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('commitId',''))" 2>/dev/null || echo "")
                    CURRENT_VERSION=$(echo "$HEALTH_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('version',''))" 2>/dev/null || echo "")
                    STARTED_AT=$(echo "$HEALTH_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('startedAt',''))" 2>/dev/null || echo "")

                    if [ -z "$CURRENT_COMMIT" ]; then
                        echo ">>> No commitId in health response, skipping."
                        echo "SKIP" > .poll_result
                        exit 0
                    fi

                    # FORCE_RESET: 清除上次记录，强制认为有变化
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

                    # 保存环境信息供后续 stage 使用
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
                        if (result == 'SKIP') {
                            currentBuild.displayName = "#${env.BUILD_NUMBER} [SKIP] no change"
                        } else if (result == 'CHANGED') {
                            def commit = readFile('.current_commit').trim()
                            def version = readFile('.current_version').trim()
                            currentBuild.displayName = "#${env.BUILD_NUMBER} [TEST] ${commit} v${version}"
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
                sh '''
                    set +x
                    echo "============================================================"
                    echo "[Staging Monitor] Clone Test Code"
                    echo "============================================================"

                    rm -rf autotest
                    mkdir -p autotest

                    ARCHIVE_URL="__TEST_REPO__/archive/refs/heads/__TEST_BRANCH__.tar.gz"
                    echo ">>> Downloading: ${ARCHIVE_URL}"

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
                                if curl --fail -SL --connect-timeout 10 --max-time 300 "${full_url}" -o "${output}" 2>/dev/null; then
                                    if [ -s "${output}" ] && tar tzf "${output}" > /dev/null 2>&1; then
                                        echo "    OK (proxy: ${proxy:-direct})"
                                        return 0
                                    fi
                                fi
                                echo "    Attempt $i failed, retrying..."
                                sleep 2
                            done
                            echo "    Proxy ${proxy:-direct} failed, trying next..."
                        done
                        echo "    ERROR: All proxies failed!"
                        return 1
                    }

                    download_repo "${ARCHIVE_URL}" /tmp/autotest.tar.gz
                    tar xzf /tmp/autotest.tar.gz --strip-components=1 -C autotest
                    rm -f /tmp/autotest.tar.gz
                    echo "    Test code: $(ls autotest/ | wc -l) files/dirs"

                    # 克隆被测项目源码（单元测试需要 @fenix/* 路径别名）
                    rm -rf app
                    mkdir -p app
                    APP_ARCHIVE_URL="__APP_REPO__/archive/refs/heads/__APP_BRANCH__.tar.gz"
                    echo ">>> Downloading app source (${APP_ARCHIVE_URL})..."
                    download_repo "${APP_ARCHIVE_URL}" /tmp/fenix.tar.gz
                    tar xzf /tmp/fenix.tar.gz --strip-components=1 -C app
                    rm -f /tmp/fenix.tar.gz
                    echo "    App source: $(ls app/ | wc -l) files/dirs"
                '''.replace('__TEST_REPO__', params.TEST_REPO.replace('.git', ''))
                  .replace('__TEST_BRANCH__', params.TEST_REPO_BRANCH ?: 'master')
                  .replace('__APP_REPO__', params.APP_REPO.replace('.git', ''))
                  .replace('__APP_BRANCH__', params.APP_BRANCH ?: 'main')
            }
        }

        stage('Prepare Tests') {
            when {
                expression { readFile('.poll_result').trim() == 'CHANGED' }
            }
            steps {
                withCredentials([string(credentialsId: 'autotest-token', variable: 'TOKEN')]) {
                    sh '''
                        set +x
                        echo "============================================================"
                        echo "[Staging Monitor] Create Pipeline Record + Resolve Tests"
                        echo "============================================================"

                        CURRENT_COMMIT=$(cat .current_commit)
                        CURRENT_VERSION=$(cat .current_version)
                        STARTED_AT=$(cat .started_at)

                        # 创建 Pipeline 记录
                        CREATE_RESP=$(curl -sf -X POST \\
                          -H "Authorization: Bearer $TOKEN" \\
                          -H "Content-Type: application/json" \\
                          -d "{
                            \\"pr_title\\": \\"Staging: v${CURRENT_VERSION}\\",
                            \\"commit_sha\\": \\"${CURRENT_COMMIT}\\",
                            \\"branch\\": \\"staging\\",
                            \\"author\\": \\"system\\",
                            \\"target_url\\": \\"__TARGET_URL__\\",
                            \\"build_info\\": {\\"version\\": \\"${CURRENT_VERSION}\\", \\"startedAt\\": \\"${STARTED_AT}\\", \\"commitId\\": \\"${CURRENT_COMMIT}\\", \\"jenkins_url\\": \\"${BUILD_URL}\\", \\"build_number\\": ${BUILD_NUMBER}}
                          }" \\
                          "__AUTOTEST_URL__/api/pipelines" 2>/dev/null || echo "")

                        echo ">>> Create pipeline response: $CREATE_RESP"

                        PIPELINE_ID=$(echo "$CREATE_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('data',{}).get('id',''))" 2>/dev/null || echo "")
                        echo "$PIPELINE_ID" > .pipeline_id
                        echo "    Pipeline ID: $PIPELINE_ID"

                        # 解析测试用例
                        echo ">>> Resolving staging tests..."
                        curl -sf -H "Authorization: Bearer $TOKEN" \\
                          "__AUTOTEST_URL__/api/ci/staging-resolve-tests" > resolve_resp.json 2>/dev/null || true

                        python3 -c "
import json
try:
    data = json.load(open('resolve_resp.json'))
    ids = data.get('data', {}).get('node_ids', [])
    if ids:
        fixed = [('/app/' + i if not i.startswith('/') else i) for i in ids]
        print(' '.join(fixed))
except Exception as e:
    import sys
    print(f'Parse error: {e}', file=sys.stderr)
" > test_targets.txt 2>/dev/null

                        if [ -s test_targets.txt ]; then
                            echo "    Source: AutoTest API (staging)"
                            echo "    Targets: $(cat test_targets.txt)"
                        elif [ -f autotest/tests/ci/staging-cases.txt ]; then
                            echo "    Source: staging-cases.txt (API unavailable)"
                            grep -v '^#' autotest/tests/ci/staging-cases.txt | grep -v '^$' | sed 's|^tests/|/app/tests/|' | tr '\\n' ' ' > test_targets.txt
                            echo "    Targets: $(cat test_targets.txt)"
                        else
                            echo "    Source: fallback (all tests)"
                            echo "/app/tests/suites /app/tests/api_suites" > test_targets.txt
                            echo "    Targets: /app/tests/suites /app/tests/api_suites"
                        fi
                    '''.replace('__AUTOTEST_URL__', params.AUTOTEST_URL)
                      .replace('__TARGET_URL__', params.TARGET_URL)
                }
            }
        }

        stage('Run Unit Tests') {
            when {
                expression { readFile('.poll_result').trim() == 'CHANGED' }
            }
            steps {
                withCredentials([string(credentialsId: 'autotest-token', variable: 'TOKEN')]) {
                    sh '''
                        set +x
                        echo "============================================================"
                        echo "[Staging Monitor] Run Unit Tests"
                        echo "============================================================"

                        PIPELINE_ID=$(cat .pipeline_id 2>/dev/null || echo "")
                        echo "  Pipeline ID: $PIPELINE_ID"

                        # 1. 通知后端：单元测试开始
                        UNIT_RUN_ID=""
                        if [ -n "$PIPELINE_ID" ] && [ "$PIPELINE_ID" != "" ]; then
                            echo ">>> Notifying backend: unit tests starting..."
                            START_RESP=$(curl -sf -X POST \\
                              -H "Authorization: Bearer $TOKEN" \\
                              -H "Content-Type: application/json" \\
                              -d "{\\"pipeline_id\\": $PIPELINE_ID}" \\
                              "__AUTOTEST_URL__/api/unit-tests/runs/start" 2>/dev/null || echo "")
                            echo "    Response: $START_RESP"
                            UNIT_RUN_ID=$(echo "$START_RESP" | python3 -c "
import sys, json
try:
    print(json.load(sys.stdin).get('data', {}).get('run_id', ''))
except:
    print('')
" 2>/dev/null)
                            echo "    Unit run_id: $UNIT_RUN_ID"
                        fi
                        echo "$UNIT_RUN_ID" > .unit_run_id

                        # 2. 运行 unit-runner
                        JENKINS_WORKSPACE_HOST=$(echo "${WORKSPACE}" | sed 's|/var/jenkins_home|/opt/1panel/apps/jenkins/jenkins/data|')

                        mkdir -p autotest/unit_tests/results

                        set +e
                        docker run --rm \\
                          --name "staging-unit-runner-${BUILD_NUMBER}" \\
                          -v "${JENKINS_WORKSPACE_HOST}/autotest/unit_tests:/app/tests" \\
                          -v "${JENKINS_WORKSPACE_HOST}/app:/app/fenix-source-parent" \\
                          unit-runner:latest
                        UNIT_EXIT=$?
                        set -e

                        echo ">>> Unit test exit code: $UNIT_EXIT"
                        echo "$UNIT_EXIT" > .unit_exit

                        if [ -f autotest/unit_tests/results/unit-junit.xml ]; then
                            echo "    junit XML: $(wc -c < autotest/unit_tests/results/unit-junit.xml) bytes"
                        else
                            echo "    WARNING: unit-junit.xml not found!"
                        fi

                        echo ""
                        echo "<<< Run Unit Tests — DONE"
                    '''.replace('__AUTOTEST_URL__', params.AUTOTEST_URL)
                }
            }
        }

        stage('Run Tests') {
            when {
                expression { readFile('.poll_result').trim() == 'CHANGED' }
            }
            steps {
                withCredentials([string(credentialsId: 'autotest-token', variable: 'TOKEN')]) {
                    sh '''
                        set +x
                        echo "============================================================"
                        echo "[Staging Monitor] Run Tests"
                        echo "  Target: __TARGET_URL__"
                        echo "============================================================"

                        PIPELINE_ID=$(cat .pipeline_id)
                        TEST_TARGETS=$(cat test_targets.txt)

                        echo "  Pipeline ID: $PIPELINE_ID"
                        echo "  Targets: $TEST_TARGETS"

                        # 更新状态为 running
                        if [ -n "$PIPELINE_ID" ] && [ "$PIPELINE_ID" != "" ]; then
                            curl -sf -X PUT \\
                              -H "Authorization: Bearer $TOKEN" \\
                              -H "Content-Type: application/json" \\
                              -d '{"status": "running"}' \\
                              "__AUTOTEST_URL__/api/pipelines/${PIPELINE_ID}/status" > /dev/null 2>&1 || true
                        fi

                        # 确保结果目录存在
                        mkdir -p autotest/tests/results

                        # 跑测试（直接在 Jenkins 机器上用 docker run）
                        set +e
                        JENKINS_WORKSPACE_HOST=$(echo "${WORKSPACE}" | sed 's|/var/jenkins_home|/opt/1panel/apps/jenkins/jenkins/data|')

                        docker run --rm \\
                          --name "staging-test-runner-${BUILD_NUMBER}" \\
                          -v "${JENKINS_WORKSPACE_HOST}/autotest/tests:/app/tests" \\
                          -v "${JENKINS_WORKSPACE_HOST}/autotest/conftest.py:/app/conftest.py" \\
                          -v "${JENKINS_WORKSPACE_HOST}/autotest/pytest.ini:/app/pytest.ini" \\
                          -e "FENIX_URL=__TARGET_URL__" \\
                          -e "FENIX_API_BASE_URL=__TARGET_URL__" \\
                          -e "HEADLESS=true" \\
                          -e "PYTHONUNBUFFERED=1" \\
                          --network host \\
                          test-runner:latest \\
                          pytest ${TEST_TARGETS} -v --tb=short \\
                            --base-url=__TARGET_URL__ \\
                            --json-report --json-report-file=/app/tests/results/report.json \\
                            --alluredir=/app/tests/results/allure-results
                        TEST_EXIT=$?
                        set -e

                        echo ">>> Test exit code: $TEST_EXIT"
                        echo "$TEST_EXIT" > .test_exit

                        # 上报集成测试结果
                        if [ -f autotest/tests/results/report.json ]; then
                            echo ">>> Uploading integration test results..."
                            curl -sf -X POST \\
                              -H "Authorization: Bearer $TOKEN" \\
                              -H "Content-Type: application/json" \\
                              -d @autotest/tests/results/report.json \\
                              "__AUTOTEST_URL__/api/pipelines/${PIPELINE_ID}/results" > /dev/null 2>&1 || true
                        fi

                        # 上报单元测试结果
                        UNIT_RUN_ID=$(cat .unit_run_id 2>/dev/null || echo "")
                        if [ -f autotest/unit_tests/results/unit-junit.xml ] && [ -n "$PIPELINE_ID" ]; then
                            echo ">>> Uploading unit test results (pipeline_id=$PIPELINE_ID)..."
                            python3 -c "
import json
xml_content = open('autotest/unit_tests/results/unit-junit.xml', 'r', encoding='utf-8').read()
run_id = '$UNIT_RUN_ID'.strip()
payload = {'pipeline_id': int($PIPELINE_ID), 'junit_xml': xml_content}
if run_id:
    payload['run_id'] = int(run_id)
open('/tmp/unit-upload.json', 'w', encoding='utf-8').write(json.dumps(payload))
"
                            curl -sf -X POST \\
                              -H "Authorization: Bearer $TOKEN" \\
                              -H "Content-Type: application/json" \\
                              -d @/tmp/unit-upload.json \\
                              "__AUTOTEST_URL__/api/unit-tests/results" > /dev/null 2>&1 || true
                            echo "    Unit test results uploaded."
                        else
                            [ ! -f autotest/unit_tests/results/unit-junit.xml ] && echo "    WARNING: unit-junit.xml not found."
                            [ -z "$PIPELINE_ID" ] && echo "    WARNING: No pipeline ID."
                        fi

                        # 更新最终状态
                        if [ $TEST_EXIT -eq 0 ]; then
                            FINAL_STATUS="passed"
                        else
                            FINAL_STATUS="failed"
                        fi

                        if [ -n "$PIPELINE_ID" ] && [ "$PIPELINE_ID" != "" ]; then
                            curl -sf -X PUT \\
                              -H "Authorization: Bearer $TOKEN" \\
                              -H "Content-Type: application/json" \\
                              -d "{\\"status\\": \\"${FINAL_STATUS}\\"}" \\
                              "__AUTOTEST_URL__/api/pipelines/${PIPELINE_ID}/status" > /dev/null 2>&1 || true
                        fi

                        echo ">>> Pipeline ${PIPELINE_ID}: ${FINAL_STATUS}"

                        # 非零退出码不阻塞 Jenkins job（下次还会继续轮询）
                        exit 0
                    '''.replace('__TARGET_URL__', params.TARGET_URL)
                      .replace('__AUTOTEST_URL__', params.AUTOTEST_URL)
                }
            }
        }

        stage('Generate Allure Report') {
            when {
                expression {
                    readFile('.poll_result').trim() == 'CHANGED'
                }
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
                        // 标题只按执行异常判失败：测试退出码 >=2（引擎执行异常）或流程异常（FAILURE/ABORTED）→ ❌
                        // 测试用例失败（退出码 1，只使 currentResult 变 UNSTABLE）不算失败 → ✅
                        def unitExit = (fileExists('.unit_exit') ? readFile('.unit_exit').trim() : '0') as int
                        def testExit = (fileExists('.test_exit') ? readFile('.test_exit').trim() : '0') as int
                        def CR = currentBuild.currentResult
                        def PIPELINE_RESULT = (unitExit >= 2 || testExit >= 2 || CR == 'FAILURE' || CR == 'ABORTED') ? 'FAIL' : 'SUCCESS'
                        withCredentials([string(credentialsId: 'wecom-webhook', variable: 'WECOM_WEBHOOK')]) {
                            sh '''
                                set +x
                                RESULT="__RESULT__"
                                if [ "$RESULT" = "SUCCESS" ]; then
                                    ICON="✅"
                                    STATUS="成功"
                                else
                                    ICON="❌"
                                    STATUS="失败"
                                fi
                                python3 -c "
import json, os
import xml.etree.ElementTree as ET
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

def stat_line(name, passed, failed, skipped):
    return '> **' + name + '**: ' + str(passed) + ' 通过 / ' + str(failed) + ' 失败 / ' + str(skipped) + ' 跳过'

lines = [
    '### ' + icon + ' Staging 环境测试' + status,
    '> commit: ' + commit,
    '> 版本: ' + version,
    '> [Jenkins 构建日志](' + build_url + ')',
]

# 接口 / E2E 统计：按 nodeid 分类（先判 api_suites，避免被 suites/ 子串误命中）
api = {'passed': 0, 'failed': 0, 'skipped': 0}
e2e = {'passed': 0, 'failed': 0, 'skipped': 0}
if os.path.exists('autotest/tests/results/report.json'):
    data = json.load(open('autotest/tests/results/report.json', 'r', encoding='utf-8'))
    for t in data.get('tests', []):
        outcome = t.get('outcome', '')
        if outcome not in ('passed', 'failed', 'skipped'):
            continue
        nodeid = t.get('nodeid', '')
        if 'api_suites/' in nodeid:
            api[outcome] += 1
        elif 'suites/' in nodeid:
            e2e[outcome] += 1

# 单元统计：unit-junit.xml 顶层 <testsuites> 的 tests/failures/skipped 属性
unit = {'passed': 0, 'failed': 0, 'skipped': 0}
if os.path.exists('autotest/unit_tests/results/unit-junit.xml'):
    root = ET.parse('autotest/unit_tests/results/unit-junit.xml').getroot()
    total = int(root.get('tests', '0') or '0')
    failed = int(root.get('failures', '0') or '0')
    skipped = int(root.get('skipped', '0') or '0')
    unit['failed'] = failed
    unit['skipped'] = skipped
    unit['passed'] = total - failed - skipped

lines.append(stat_line('单元测试', unit['passed'], unit['failed'], unit['skipped']))
lines.append(stat_line('接口测试', api['passed'], api['failed'], api['skipped']))
lines.append(stat_line('E2E 测试', e2e['passed'], e2e['failed'], e2e['skipped']))

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
