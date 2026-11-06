// 测试代码归档地址。GitLab 私有仓库的网页归档路由不认 PRIVATE-TOKEN（未授权会返回 200 登录页），
// 必须走 API 端点；项目路径与分支名都要 URL 编码。
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
        string(name: 'APP_REPO',         defaultValue: 'https://github.com/HuangPuStar/FenixAgent.git', description: '被测项目仓库地址（单元测试需要）')
        string(name: 'APP_BRANCH',       defaultValue: 'main',                               description: '被测项目分支（单元测试源码）')
        string(name: 'POLL_INTERVAL',    defaultValue: '30',                                  description: '轮询间隔（分钟）')
        string(name: 'AUTOTEST_URL',     defaultValue: 'http://100.105.114.178:8111',        description: 'AutoTest 后端地址')
        string(name: 'TEST_REPO',        defaultValue: 'https://gitlab.pazhoulab-huangpu.com/aos-test/aos-auto-test.git', description: '测试代码仓库')
        string(name: 'TEST_REPO_BRANCH', defaultValue: 'main',               description: '测试代码分支')
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
                withCredentials([string(credentialsId: 'gitlab-read-token', variable: 'GL_TOKEN')]) {
                sh '''
                    set +x
                    echo "============================================================"
                    echo "[Staging Monitor] Check Runner Images"
                    echo "============================================================"

                    download_repo() {
                        local url="$1"
                        local output="$2"
                        local proxies="https://gh-proxy.com https://mirror.ghproxy.com https://ghfast.top https://ghproxy.net"
                        local auth_args=""
                        case "$url" in
                            *gitlab.*)
                                # GitLab 是内网域名，代理前缀无效；私有仓库必须带只读令牌
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
                        rm -rf /tmp/staging-autotest
                        mkdir -p /tmp/staging-autotest

                        ARCHIVE_URL="__TEST_ARCHIVE_URL__"
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

                        ARCHIVE_URL="__TEST_ARCHIVE_URL__"
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
                '''.replace('__TEST_ARCHIVE_URL__', buildTestArchiveUrl(params.TEST_REPO, params.TEST_REPO_BRANCH ?: 'main'))
                  .replace('__TEST_BRANCH__', params.TEST_REPO_BRANCH ?: 'main')
                }
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
                        # 首次掉线发告警，持续掉线只在构建状态上体现，避免每 2 小时刷屏
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
                        if (result == 'DOWN_ALERT' || result == 'DOWN') {
                            // 环境不可达必须可见：构建置 UNSTABLE，首次掉线额外发企微告警
                            currentBuild.result = 'UNSTABLE'
                            currentBuild.displayName = "#${env.BUILD_NUMBER} [ALERT] health unreachable"
                            if (result == 'DOWN_ALERT' && (params.NOTIFY_WECOM != null ? params.NOTIFY_WECOM : true)) {
                                withCredentials([string(credentialsId: 'wecom-webhook', variable: 'WECOM_WEBHOOK')]) {
                                    sh '''
                                        set +x
                                        python3 -c "
import json, os, urllib.request
content = '### Staging 环境健康检查失败\\n> 地址: __HEALTH_URL__\\n> [Jenkins 构建日志](' + os.environ.get('BUILD_URL', '') + ')'
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
                withCredentials([string(credentialsId: 'gitlab-read-token', variable: 'GL_TOKEN')]) {
                sh '''
                    set +x
                    echo "============================================================"
                    echo "[Staging Monitor] Clone Test Code"
                    echo "============================================================"

                    rm -rf autotest
                    mkdir -p autotest

                    ARCHIVE_URL="__TEST_ARCHIVE_URL__"
                    echo ">>> Downloading: ${ARCHIVE_URL}"

                    download_repo() {
                        local url="$1"
                        local output="$2"
                        local proxies="https://gh-proxy.com https://mirror.ghproxy.com https://ghfast.top https://ghproxy.net"
                        local auth_args=""
                        case "$url" in
                            *gitlab.*)
                                # GitLab 是内网域名，代理前缀无效；私有仓库必须带只读令牌
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

                    download_repo "${ARCHIVE_URL}" /tmp/autotest.tar.gz
                    tar xzf /tmp/autotest.tar.gz --strip-components=1 -C autotest
                    rm -f /tmp/autotest.tar.gz
                    echo "    Test code: $(ls autotest/ | wc -l) files/dirs"

                    # 克隆/更新被测项目源码（单元测试需要 @fenix/* 路径别名）
                    # 用 git 协议（smart HTTP）替代 archive tar.gz：git 直连更稳，且可增量更新
                    # gh-proxy 系列是"URL前缀反向代理"（https://gh-proxy.com/https://github.com/...），
                    # 不是 HTTP CONNECT 代理，配 -c http.proxy= 会 CONNECT tunnel failed，必须拼 URL 前缀
                    export GIT_HTTP_LOW_SPEED_LIMIT=1000
                    export GIT_HTTP_LOW_SPEED_TIME=300
                    APP_PROXIES="https://gh-proxy.com https://mirror.ghproxy.com https://ghfast.top https://ghproxy.net"
                    git_retry() {
                        local op="$1" url="$2" dir="$3" branch="$4"
                        for proxy in $APP_PROXIES ""; do
                            if [ -n "$proxy" ]; then
                                target="${proxy}/${url}"
                                echo "    Trying via ${proxy}: git $op ..."
                            else
                                target="$url"
                                echo "    Trying direct: git $op ..."
                            fi
                            if [ "$op" = "clone" ]; then
                                if GIT_HTTP_LOW_SPEED_LIMIT=1000 GIT_HTTP_LOW_SPEED_TIME=300 git clone --depth 1 -b "$branch" "$target" "$dir" >/tmp/git_out.log 2>&1; then
                                    echo "    OK (${proxy:-direct})"
                                    return 0
                                fi
                                rm -rf "$dir"
                            else
                                if GIT_HTTP_LOW_SPEED_LIMIT=1000 GIT_HTTP_LOW_SPEED_TIME=300 git fetch --depth 1 "$target" "$branch" >/tmp/git_out.log 2>&1; then
                                    echo "    OK (${proxy:-direct})"
                                    return 0
                                fi
                            fi
                            echo "    Attempt failed: $(tail -1 /tmp/git_out.log)"
                        done
                        return 1
                    }
                    if [ -d app/.git ]; then
                        echo ">>> Updating app source (__APP_BRANCH__)..."
                        # 增量更新：fetch 走代理前缀 URL 拉最新分支，FETCH_HEAD 即本次目标 commit
                        if (cd app && git_retry fetch __APP_REPO__ "" __APP_BRANCH__ && git reset --hard FETCH_HEAD); then
                            echo "    App source updated: $(ls app/ | wc -l) files/dirs"
                        else
                            echo "    Update failed, re-cloning..."
                            rm -rf app
                            if ! git_retry clone __APP_REPO__ app __APP_BRANCH__; then
                                echo "    ERROR: app clone failed"
                                exit 1
                            fi
                            echo "    App source: $(ls app/ | wc -l) files/dirs"
                        fi
                    else
                        rm -rf app
                        mkdir -p app
                        echo ">>> Cloning app source (__APP_REPO__ @ __APP_BRANCH__)..."
                        if ! git_retry clone __APP_REPO__ app __APP_BRANCH__; then
                            echo "    ERROR: app clone failed"
                            exit 1
                        fi
                        echo "    App source: $(ls app/ | wc -l) files/dirs"
                    fi
                '''.replace('__TEST_ARCHIVE_URL__', buildTestArchiveUrl(params.TEST_REPO, params.TEST_REPO_BRANCH ?: 'main'))
                  .replace('__TEST_BRANCH__', params.TEST_REPO_BRANCH ?: 'main')
                  .replace('__APP_REPO__', params.APP_REPO)
                  .replace('__APP_BRANCH__', params.APP_BRANCH ?: 'main')
                }
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

                        # 用例来源：仓库内全量 E2E + API，不再调用 AutoTest 接口解析用例
                        # 优先级 marker 仅用于执行顺序与结果分桶，不影响用例集合
                        echo ">>> Test targets: all E2E + API cases (resolved from repo)"
                        echo "/app/tests/suites /app/tests/api_suites" > test_targets.txt
                        echo "    Targets: $(cat test_targets.txt)"
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
                        # 按优先级顺序执行：p0 → p1 → p2 → 未分级，全部跑完后再汇总
                        JENKINS_WORKSPACE_HOST=$(echo "${WORKSPACE}" | sed 's|/var/jenkins_home|/opt/1panel/apps/jenkins/jenkins/data|')

                        run_priority() {
                            label="$1"
                            expr="$2"
                            echo ""
                            echo ">>> ===== [${label}] pytest -m ${expr} ====="
                            docker run --rm \\
                              --name "staging-test-runner-${BUILD_NUMBER}-${label}" \\
                              -v "${JENKINS_WORKSPACE_HOST}/autotest/tests:/app/tests" \\
                              -v "${JENKINS_WORKSPACE_HOST}/autotest/conftest.py:/app/conftest.py" \\
                              -v "${JENKINS_WORKSPACE_HOST}/autotest/pytest.ini:/app/pytest.ini" \\
                              -e "FENIX_URL=__TARGET_URL__" \\
                              -e "FENIX_API_BASE_URL=__TARGET_URL__" \\
                              -e "HEADLESS=true" \\
                              -e "PYTHONUNBUFFERED=1" \\
                              --network host \\
                              test-runner:latest \\
                              pytest ${TEST_TARGETS} -m "${expr}" -v --tb=short \\
                                --base-url=__TARGET_URL__ \\
                                --json-report --json-report-file="/app/tests/results/report-${label}.json" \\
                                --alluredir=/app/tests/results/allure-results
                            rc=$?
                            echo ">>> [${label}] exit code: ${rc}"
                            # pytest 退出码 5 = 没有匹配到用例，不算失败
                            # 用例失败（1）不改变 Job 结论；执行异常（>=2）优先保留
                            if [ $rc -ne 0 ] && [ $rc -ne 5 ]; then
                                if [ $rc -ge 2 ] || [ $TEST_EXIT -eq 0 ]; then
                                    TEST_EXIT=$rc
                                fi
                            fi
                        }

                        TEST_EXIT=0
                        set +e
                        run_priority p0 "p0"
                        run_priority p1 "p1"
                        run_priority p2 "p2"
                        run_priority unmarked "not p0 and not p1 and not p2"
                        set -e

                        echo ">>> Aggregate test exit code: $TEST_EXIT"
                        echo "$TEST_EXIT" > .test_exit

                        # 合并各优先级报告，供上传与企微通知使用
                        python3 -c "
import json, os
reports = ['report-p0.json', 'report-p1.json', 'report-p2.json', 'report-unmarked.json']
counts = {'passed': 0, 'failed': 0, 'skipped': 0, 'error': 0, 'xfailed': 0, 'xpassed': 0}
tests = []
duration = 0.0
created = None
for name in reports:
    path = os.path.join('autotest/tests/results', name)
    if not os.path.exists(path):
        continue
    data = json.load(open(path, 'r', encoding='utf-8'))
    tests.extend(data.get('tests', []))
    duration += data.get('duration', 0) or 0
    c = data.get('created')
    if c and (created is None or c < created):
        created = c
for t in tests:
    outcome = t.get('outcome', '')
    if outcome in counts:
        counts[outcome] += 1
merged = {
    'tests': tests,
    'duration': duration,
    'created': created or 0,
    'summary': {
        'total': len(tests),
        'passed': counts['passed'],
        'failed': counts['failed'] + counts['error'],
        'skipped': counts['skipped'],
        'xfailed': counts['xfailed'],
        'xpassed': counts['xpassed'],
    },
}
open('autotest/tests/results/report.json', 'w', encoding='utf-8').write(json.dumps(merged, ensure_ascii=False))
print('>>> Merged report:', merged['summary'])
"

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
                                    export ICON="✅"
                                    export STATUS="成功"
                                else
                                    export ICON="❌"
                                    export STATUS="失败"
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

def stat_line(name, s):
    line = '> **' + name + '**: ' + str(s['passed']) + ' 通过 / ' + str(s['failed']) + ' 失败 / ' + str(s['skipped']) + ' 跳过'
    if s['error']:
        line += ' / ' + str(s['error']) + ' 错误'
    return line

def bucket():
    return {'passed': 0, 'failed': 0, 'skipped': 0, 'error': 0}

lines = [
    '### ' + icon + ' Staging 环境测试' + status,
    '> commit: ' + commit,
    '> 版本: ' + version,
]

# 接口 / E2E 各自按优先级分桶：优先级取自 pytest marker（json-report 的 keywords）
PRIORITIES = ('p0', 'p1', 'p2', 'p3', '未分级')
e2e = {}
api = {}
for p in PRIORITIES:
    e2e[p] = bucket()
    api[p] = bucket()
if os.path.exists('autotest/tests/results/report.json'):
    data = json.load(open('autotest/tests/results/report.json', 'r', encoding='utf-8'))
    for t in data.get('tests', []):
        outcome = t.get('outcome', '')
        if outcome not in ('passed', 'failed', 'skipped', 'error'):
            continue
        nodeid = t.get('nodeid', '')
        if 'api_suites/' in nodeid:
            suite = api
        elif 'suites/' in nodeid:
            suite = e2e
        else:
            continue
        kws = t.get('keywords', []) or []
        pri = '未分级'
        for p in ('p0', 'p1', 'p2', 'p3'):
            if p in kws:
                pri = p
                break
        suite[pri][outcome] += 1

# 单元统计：unit-junit.xml 顶层 <testsuites> 的 tests/failures/skipped 属性
unit = bucket()
if os.path.exists('autotest/unit_tests/results/unit-junit.xml'):
    root = ET.parse('autotest/unit_tests/results/unit-junit.xml').getroot()
    total = int(root.get('tests', '0') or '0')
    failed = int(root.get('failures', '0') or '0')
    skipped = int(root.get('skipped', '0') or '0')
    unit['failed'] = failed
    unit['skipped'] = skipped
    unit['passed'] = total - failed - skipped

lines.append(stat_line('单元测试', unit))


def append_suite_lines(prefix, buckets):
    for p in PRIORITIES:
        s = buckets[p]
        total = s['passed'] + s['failed'] + s['skipped'] + s['error']
        if total == 0:
            continue
        lines.append(stat_line(prefix + ' ' + (p.upper() if p != '未分级' else '未分级'), s))


append_suite_lines('接口', api)
append_suite_lines('E2E', e2e)

# 失败分布：按优先级汇总接口 + E2E 的失败/错误条数，不列具体用例名
by_pri = []
for p in PRIORITIES:
    n = api[p]['failed'] + api[p]['error'] + e2e[p]['failed'] + e2e[p]['error']
    if n:
        by_pri.append((p.upper() if p != '未分级' else '未分级') + ' ' + str(n) + ' 条')
if by_pri:
    lines.append('> **失败分布**: ' + ' / '.join(by_pri) + '，详见 Allure 报告')

if build_url:
    lines.append('> [Jenkins 构建日志](' + build_url + ')')
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
