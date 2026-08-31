pipeline {
    agent any

    parameters {
        string(name: 'PR_BRANCH',    description: 'PR 分支名（如 feat/xxx）',           defaultValue: 'main')
        string(name: 'PR_ID',        description: 'PR 编号（如 42）',                   defaultValue: '0')
        string(name: 'PR_TITLE',     description: 'PR 标题',                            defaultValue: 'manual build')
        string(name: 'COMMIT_SHA',   description: 'Commit SHA',                        defaultValue: 'unknown')
        string(name: 'AUTHOR',       description: '作者',                               defaultValue: 'unknown')
        string(name: 'APP_REPO',     description: '被测项目仓库地址（如 FenixAgent）',   defaultValue: 'https://github.com/HuangPuStar/FenixAgent.git')
        string(name: 'APP_BRANCH',   description: '被测项目分支',                       defaultValue: 'main')
        string(name: 'TEST_REPO',    description: '测试代码仓库地址（如 aos-auto-test）', defaultValue: 'https://github.com/youtaking/aos-auto-test.git')
        string(name: 'TEST_REPO_BRANCH', description: '测试代码分支',                    defaultValue: 'master')
        string(name: 'AUTOTEST_URL', description: 'AutoTest 后端地址（用于上传测试结果和日志）', defaultValue: 'http://100.105.114.178:8111')
        string(name: 'HOST_IP', description: '宿主机 IP（RCS 服务对外地址，用于健康检查和 target_url）', defaultValue: '100.105.114.178')
        booleanParam(name: 'NOTIFY_WECOM', defaultValue: true, description: '构建完成后发送企业微信通知（手动测试时可取消勾选）')
    }

    environment {
        AUTOTEST_URL = "${params.AUTOTEST_URL}"
        HOST_IP      = "${params.HOST_IP}"
        APP_REPO     = "${params.APP_REPO}"
        TEST_REPO    = "${params.TEST_REPO}"
        PROJECT_NAME = "pr-env-${BUILD_NUMBER}"

        PORT_OFFSET = "${(BUILD_NUMBER.toInteger() % 10) * 3}"
        RCS_PORT    = "${30000 + PORT_OFFSET.toInteger()}"
        PG_PORT     = "${30001 + PORT_OFFSET.toInteger()}"
        LITE_PORT   = "${30002 + PORT_OFFSET.toInteger()}"
        OPENAI_API_KEY    = "***REMOVED***"
        OPENAI_MODEL      = "deepseek-v4-flash"
        OPENAI_BASE_URL   = "https://api.deepseek.com/v1/"
    }

    stages {
        stage('Init') {
            steps {
                sh '''
                    set +x
                    echo "############################################################"
                    echo "#                                                          #"
                    echo "#   PR Pipeline — Build #__BUILD_NUMBER__"
                    echo "#                                                          #"
                    echo "#   Project:    __PROJECT_NAME__"
                    echo "#   Branch:     __PR_BRANCH__"
                    echo "#   Author:     __AUTHOR__"
                    echo "#   RCS Port:   __RCS_PORT__ (host)"
                    echo "#   PG Port:    __PG_PORT__ (host)"
                    echo "#   LiteLLM:    __LITE_PORT__ (host)"
                    echo "#                                                          #"
                    echo "############################################################"

                    echo ""
                    echo ">>> Checking dependencies..."
                    if command -v python3 >/dev/null 2>&1; then
                        echo "    python3: $(python3 --version)"
                    elif command -v python >/dev/null 2>&1; then
                        echo "    python: $(python --version)"
                        echo '#!/bin/sh' > /usr/local/bin/python3
                        echo 'exec python "$@"' >> /usr/local/bin/python3
                        chmod +x /usr/local/bin/python3
                        echo "    python3 alias created -> python"
                    else
                        echo "    python not found, installing..."
                        apt-get update -qq && apt-get install -y -qq python3 > /dev/null 2>&1
                        echo "    python3 installed: $(python3 --version)"
                    fi

                    if ! command -v docker-compose >/dev/null 2>&1; then
                        echo "    docker-compose not found, installing..."
                        curl -sSL "https://github.com/docker/compose/releases/download/v2.29.2/docker-compose-linux-x86_64" -o /usr/local/bin/docker-compose
                        chmod +x /usr/local/bin/docker-compose
                        echo "    docker-compose installed."
                    fi
                    echo "    docker-compose: $(docker-compose --version)"
                    echo ">>> Dependencies ready."
                '''.replace('__BUILD_NUMBER__', BUILD_NUMBER)
                  .replace('__PROJECT_NAME__', PROJECT_NAME)
                  .replace('__PR_BRANCH__', params.PR_BRANCH ?: 'main')
                  .replace('__AUTHOR__', params.AUTHOR ?: 'unknown')
                  .replace('__RCS_PORT__', RCS_PORT)
                  .replace('__PG_PORT__', PG_PORT)
                  .replace('__LITE_PORT__', LITE_PORT)
            }
        }

        stage('Clone Repos') {
            steps {
                sh '''
                    set +x
                    echo "============================================================"
                    echo "[1/7] Clone Repos — START"
                    echo "  Project:  __PROJECT_NAME__"
                    echo "  Branch:   __PR_BRANCH__"
                    echo "  Ports:    RCS=__RCS_PORT__  PG=__PG_PORT__  LiteLLM=__LITE_PORT__"
                    echo "============================================================"
                    echo ""
                    echo ">>> Cleaning previous workspace..."
                    rm -rf app autotest
                    mkdir -p app autotest

                    download_repo() {
                        local url="$1"
                        local output="$2"
                        local proxies="https://gh-proxy.com https://mirror.ghproxy.com https://ghfast.top https://ghproxy.net"
                        for proxy in "" $proxies; do
                            if [ -n "$proxy" ]; then
                                full_url="${proxy}/${url}"
                            else
                                full_url="$url"
                            fi
                            echo "    Trying: ${full_url}"
                            for i in 1 2 3; do
                                if curl --fail -SL --connect-timeout 10 --max-time 300 \\
                                  "${full_url}" -o "${output}" 2>/dev/null; then
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

                    echo ">>> Downloading app (__APP_BRANCH__)..."
                    download_repo \\
                      "__APP_ARCHIVE_URL__" \\
                      /tmp/fenix.tar.gz
                    tar xzf /tmp/fenix.tar.gz --strip-components=1 -C app
                    rm -f /tmp/fenix.tar.gz
                    echo "    App: $(ls app/ | wc -l) files/dirs in app/"

                    echo ">>> Downloading test code (__TEST_REPO_BRANCH__)..."
                    download_repo \\
                      "__TEST_ARCHIVE_URL__" \\
                      /tmp/autotest.tar.gz
                    tar xzf /tmp/autotest.tar.gz --strip-components=1 -C autotest
                    rm -f /tmp/autotest.tar.gz
                    echo "    Test code: $(ls autotest/ | wc -l) files/dirs in autotest/"

                    echo ""
                    echo "<<< [1/7] Clone Repos — DONE"
                '''.replace('__APP_ARCHIVE_URL__', APP_REPO.replace('.git', '') + "/archive/refs/heads/${params.APP_BRANCH ?: 'main'}.tar.gz")
                  .replace('__TEST_ARCHIVE_URL__', TEST_REPO.replace('.git', '') + "/archive/refs/heads/${params.TEST_REPO_BRANCH ?: 'master'}.tar.gz")
                  .replace('__APP_BRANCH__', params.APP_BRANCH ?: 'main')
                  .replace('__TEST_REPO_BRANCH__', params.TEST_REPO_BRANCH ?: 'master')
                  .replace('__PR_BRANCH__', params.PR_BRANCH ?: 'main')
                  .replace('__PROJECT_NAME__', PROJECT_NAME)
                  .replace('__RCS_PORT__', RCS_PORT)
                  .replace('__PG_PORT__', PG_PORT)
                  .replace('__LITE_PORT__', LITE_PORT)
            }
        }

        stage('Build Image') {
            steps {
                sh '''
                    set +x
                    echo ""
                    echo "============================================================"
                    echo "[2/7] Build Image — START"
                    echo "  Runtime image:  __PROJECT_NAME__:__BUILD_NUMBER__"
                    echo "  Migrate image:  __PROJECT_NAME__-migrate:__BUILD_NUMBER__"
                    echo "============================================================"
                '''.replace('__PROJECT_NAME__', PROJECT_NAME)
                  .replace('__BUILD_NUMBER__', BUILD_NUMBER)

                dir('app') {
                    sh '''
                    set +x
                        echo ">>> Building runtime image (this may take a few minutes)..."
                        docker build -t __PROJECT_NAME__:__BUILD_NUMBER__ .
                        echo "    Runtime image built."

                        echo ">>> Building migrate image..."
                        docker build --target migrate -t __PROJECT_NAME__-migrate:__BUILD_NUMBER__ .
                        echo "    Migrate image built."

                        echo ""
                        echo "<<< [2/7] Build Image — DONE"
                        docker images | grep "__PROJECT_NAME__" || true
                    '''.replace('__PROJECT_NAME__', PROJECT_NAME)
                      .replace('__BUILD_NUMBER__', BUILD_NUMBER)
                }
            }
        }

        stage('Check Runner Images') {
            steps {
                sh '''
                    set +x
                    echo ""
                    echo "============================================================"
                    echo "[2b] Check Runner Images — START"
                    echo "============================================================"

                    if docker image inspect test-runner:latest > /dev/null 2>&1; then
                        echo ">>> test-runner:latest already exists, skipping build."
                    else
                        echo ">>> test-runner:latest not found, building..."
                        docker build -t test-runner:latest -f autotest/Dockerfile.runner autotest/
                        echo "    test-runner:latest built."
                    fi

                    if docker image inspect unit-runner:latest > /dev/null 2>&1; then
                        echo ">>> unit-runner:latest already exists, skipping build."
                    else
                        echo ">>> unit-runner:latest not found, building..."
                        mkdir -p autotest/cache
                        [ -f autotest/cache/package.json ] || echo '{"name":"empty","version":"0.0.0"}' > autotest/cache/package.json
                        [ -f autotest/cache/bun.lockb ] || touch autotest/cache/bun.lockb
                        docker build -t unit-runner:latest -f autotest/Dockerfile.unit-runner autotest/
                        echo "    unit-runner:latest built (no dep cache, runtime will install)."
                    fi

                    echo ""
                    echo "<<< [2b] Check Runner Images — DONE"
                '''
            }
        }

        stage('Resolve Tests') {
            steps {
                sh '''
                    set +x
                    echo ""
                    echo "============================================================"
                    echo "[3/7] Resolve Tests — START"
                    echo "============================================================"
                '''
                withCredentials([string(credentialsId: 'autotest-token', variable: 'TOKEN')]) {
                    sh '''
                    set +x
                    set +e
                        echo ">>> Querying AutoTest API for test targets..."
                        BRANCH_PARAM="__PR_BRANCH__"
                        if [ -n "$BRANCH_PARAM" ] && [ "$BRANCH_PARAM" != "main" ]; then
                            RESOLVE_URL="__AUTOTEST_URL__/api/ci/resolve-tests?branch=${BRANCH_PARAM}"
                        else
                            RESOLVE_URL="__AUTOTEST_URL__/api/ci/resolve-tests"
                        fi
                        curl -s -H "Authorization: Bearer $TOKEN" \\
                          "$RESOLVE_URL" > resolve_resp.json

                        echo ">>> API response:"
                        cat resolve_resp.json
                        echo ""

                        python3 -c "
import json
try:
    data = json.load(open('resolve_resp.json'))
    ids = data.get('data', {}).get('node_ids', [])
    if ids:
        fixed = [('/app/' + i if not i.startswith('/') and not i.startswith('branches/') else i) for i in ids]
        print(' '.join(fixed))
except Exception as e:
    import sys
    print(f'Parse error: {e}', file=sys.stderr)
" > test_targets.txt 2>/dev/null

                        if [ -s test_targets.txt ]; then
                            echo "    Source: AutoTest API"
                            echo "    Targets: $(cat test_targets.txt)"
                        elif [ -f autotest/tests/ci/cases.txt ]; then
                            echo "    Source: cases.txt (API unavailable)"
                            grep -v '^#' autotest/tests/ci/cases.txt | grep -v '^$' | sed 's|^tests/|/app/tests/|' | tr '\\n' ' ' > test_targets.txt
                            echo "    Targets: $(cat test_targets.txt)"
                        else
                            echo "    Source: fallback (all tests)"
                            echo "/app/tests/suites /app/tests/api_suites" > test_targets.txt
                            echo "    Targets: /app/tests/suites /app/tests/api_suites"
                        fi

                        echo ""
                        echo "<<< [3/7] Resolve Tests — DONE"
                    '''.replace('__AUTOTEST_URL__', AUTOTEST_URL)
                      .replace('__PR_BRANCH__', params.PR_BRANCH ?: 'main')
                }
            }
        }

        stage('Write Compose') {
            steps {
                sh '''
                    set +x
                    echo ""
                    echo "============================================================"
                    echo "[4/7] Write Compose — START"
                    echo "============================================================"
                '''
                writeFile file: 'docker-compose.yml', text: '''
services:
  postgres:
    image: postgres:16-alpine
    privileged: true
    ports:
      - "__PG_PORT__:5432"
    environment:
      POSTGRES_USER: rcs
      POSTGRES_PASSWORD: rcs
      POSTGRES_DB: rcs
    volumes:
      - ./pg-init:/docker-entrypoint-initdb.d
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U rcs"]
      interval: 5s
      timeout: 5s
      retries: 5

  migrate:
    image: __MIGRATE_IMAGE_TAG__
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      DATABASE_URL: postgres://rcs:rcs@postgres:5432/rcs
    restart: "no"

  litellm:
    image: ghcr.io/berriai/litellm:main-stable
    depends_on:
      postgres:
        condition: service_healthy
    ports:
      - "__LITE_PORT__:4000"
    environment:
      DATABASE_URL: postgresql://rcs:rcs@postgres:5432/litellm
      LITELLM_MASTER_KEY: sk-litellm-admin-dev-key
      STORE_MODEL_IN_DB: "True"

  rcs:
    image: __IMAGE_TAG__
    depends_on:
      postgres:
        condition: service_healthy
    ports:
      - "__RCS_PORT__:3001"
    environment:
      DATABASE_URL: postgres://rcs:rcs@postgres:5432/rcs
      RCS_HOST: 0.0.0.0
      RCS_PORT: 3001
      RCS_API_KEYS: sk-rcs-dev-key
      RCS_SECRET_LITELLM_ADMIN_KEY: sk-litellm-admin-dev-key
      OPENAI_API_KEY: __OPENAI_API_KEY__
      OPENAI_MODEL: __OPENAI_MODEL__
      OPENAI_BASE_URL: __OPENAI_BASE_URL__
      BETTER_AUTH_URL: http://__HOST_IP__:__RCS_PORT__
      NODE_ENV: test
      BUN_TEST: "1"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3001/health"]
      interval: 10s
      timeout: 5s
      retries: 20

  test-runner:
    image: test-runner:latest
    depends_on:
      rcs:
        condition: service_healthy
    volumes:
      - __WORKSPACE__/autotest/tests:/app/tests
      - __WORKSPACE__/autotest/branches:/app/branches
      - __WORKSPACE__/autotest/conftest.py:/app/conftest.py
      - __WORKSPACE__/autotest/pytest.ini:/app/pytest.ini
    environment:
      FENIX_URL: http://rcs:3001
      FENIX_API_BASE_URL: http://rcs:3001
      HEADLESS: "true"
      PYTHONUNBUFFERED: "1"
      PYTHONPATH: /app
    command: 'pytest __TEST_TARGETS__ -v --tb=short --base-url=http://rcs:3001 --json-report --json-report-file=/app/tests/results/report.json --alluredir=/app/tests/results/allure-results'

  unit-runner:
    image: unit-runner:latest
    volumes:
      - __UNIT_TEST_MOUNT__:/app/tests
      - __WORKSPACE__/app:/app/fenix-source-parent
'''.replace('__PG_PORT__', PG_PORT)
  .replace('__LITE_PORT__', LITE_PORT)
  .replace('__IMAGE_TAG__', "${PROJECT_NAME}:${BUILD_NUMBER}")
  .replace('__MIGRATE_IMAGE_TAG__', "${PROJECT_NAME}-migrate:${BUILD_NUMBER}")
  .replace('__RCS_PORT__', RCS_PORT)
  .replace('__HOST_IP__', HOST_IP)
  .replace('__OPENAI_API_KEY__', OPENAI_API_KEY)
  .replace('__OPENAI_MODEL__', OPENAI_MODEL)
  .replace('__OPENAI_BASE_URL__', OPENAI_BASE_URL)
  .replace('__WORKSPACE__', env.WORKSPACE.replace('/var/jenkins_home', '/opt/1panel/apps/jenkins/jenkins/data'))
  .replace('__UNIT_TEST_MOUNT__', (params.PR_BRANCH && params.PR_BRANCH != 'main')
      ? env.WORKSPACE.replace('/var/jenkins_home', '/opt/1panel/apps/jenkins/jenkins/data') + '/autotest/branches/' + params.PR_BRANCH + '/unit_tests'
      : env.WORKSPACE.replace('/var/jenkins_home', '/opt/1panel/apps/jenkins/jenkins/data') + '/autotest/unit_tests')
  .replace('__TEST_TARGETS__', readFile('test_targets.txt').trim())

                sh '''
                    set +x
                    echo ">>> docker-compose.yml written:"
                    echo "    postgres  -> host port __PG_PORT__"
                    echo "    litellm   -> host port __LITE_PORT__"
                    echo "    rcs       -> host port __RCS_PORT__"
                    echo "    test targets: __TEST_TARGETS__"
                    echo ""
                    echo "<<< [4/7] Write Compose — DONE"
                '''.replace('__PG_PORT__', PG_PORT)
                  .replace('__LITE_PORT__', LITE_PORT)
                  .replace('__RCS_PORT__', RCS_PORT)
                  .replace('__TEST_TARGETS__', readFile('test_targets.txt').trim())
            }
        }

        stage('Deploy') {
            steps {
                sh '''
                    set +x
                    echo ""
                    echo "============================================================"
                    echo "[5/7] Deploy — START"
                    echo "  Project: __PROJECT_NAME__"
                    echo "============================================================"
                '''.replace('__PROJECT_NAME__', PROJECT_NAME)

                // 端口清理：防止残留容器占用端口（不影响其他正在运行的 build）
                sh '''
                    set +x
                    echo ">>> Pre-deploy cleanup: freeing ports __RCS_PORT__, __PG_PORT__, __LITE_PORT__..."

                    # 1. 清理同项目名的残留容器（重新触发同一 build 号时）
                    if docker-compose -p __PROJECT_NAME__ ps -q 2>/dev/null | grep -q .; then
                        echo "    Found existing containers for __PROJECT_NAME__, removing..."
                        docker-compose -p __PROJECT_NAME__ down -v --remove-orphans 2>/dev/null || true
                    fi

                    # 2. 检查目标端口是否被占用
                    PORT_CONFLICT=false
                    for port in __RCS_PORT__ __PG_PORT__ __LITE_PORT__; do
                        CONTAINER_ID=$(docker ps --filter "publish=$port" --format "{{.ID}}" 2>/dev/null || true)
                        if [ -n "$CONTAINER_ID" ]; then
                            CONTAINER_NAME=$(docker inspect --format "{{.Name}}" "$CONTAINER_ID" 2>/dev/null | sed 's|^/||')
                            # 只清理已退出/stale 的容器，不杀其他活跃 build 的容器
                            CONTAINER_STATE=$(docker inspect --format "{{.State.Status}}" "$CONTAINER_ID" 2>/dev/null || echo "unknown")
                            # 如果是 pr-env 容器且不是当前 build，检查是否属于已完成的 build
                            if echo "$CONTAINER_NAME" | grep -q "^pr-env-"; then
                                echo "    Port $port used by $CONTAINER_NAME (state=$CONTAINER_STATE)"
                                if [ "$CONTAINER_STATE" = "exited" ] || [ "$CONTAINER_STATE" = "dead" ]; then
                                    echo "    Stale container, removing..."
                                    docker rm -f "$CONTAINER_ID" 2>/dev/null || true
                                else
                                    echo "    WARNING: Port $port occupied by active container $CONTAINER_NAME"
                                    PORT_CONFLICT=true
                                fi
                            else
                                echo "    Port $port used by non-pipeline container $CONTAINER_NAME, skipping."
                                PORT_CONFLICT=true
                            fi
                        else
                            echo "    Port $port is available."
                        fi
                    done

                    if [ "$PORT_CONFLICT" = "true" ]; then
                        echo ""
                        echo "    ERROR: Port conflict detected! Another active build or container is using the same ports."
                        echo "    This build needs a different port offset. Aborting to avoid interference."
                        exit 1
                    fi

                    echo "    Pre-deploy cleanup done."
                '''.replace('__PROJECT_NAME__', PROJECT_NAME)
                  .replace('__RCS_PORT__', RCS_PORT)
                  .replace('__PG_PORT__', PG_PORT)
                  .replace('__LITE_PORT__', LITE_PORT)

                sh '''
                    set +x
                    echo ">>> Preparing pg-init scripts..."
                    mkdir -p pg-init
                    cat > pg-init/10-create-litellm.sh << 'INITEOF'
#!/bin/sh
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    CREATE DATABASE litellm;
EOSQL
INITEOF
                    chmod +x pg-init/10-create-litellm.sh

                    echo ">>> Preparing seed data..."
                    rm -rf seed-data.sql
                    if [ -f autotest/data.sql ]; then
                      cat > /tmp/filter_seed.py << 'PYEOF'
import sys
BS = chr(92)
lines = open('autotest/data.sql', encoding='utf-8').readlines()
out = []
skip = False
for line in lines:
    s = line.strip()
    if s.startswith(BS + 'restrict') or s.startswith(BS + 'unrestrict'):
        continue
    if 'COPY drizzle.__drizzle_migrations' in line:
        skip = True
        continue
    if skip and s == BS + '.':
        skip = False
        continue
    if skip:
        continue
    out.append(line)
open('seed-data.sql', 'w', encoding='utf-8').writelines(out)
PYEOF
                      python3 /tmp/filter_seed.py
                      echo "    seed-data.sql ready ($(wc -l < seed-data.sql) lines)."
                    else
                      echo "    WARNING: autotest/data.sql not found, creating empty seed."
                      echo "-- No seed data" > seed-data.sql
                    fi

                    echo ">>> Starting postgres..."
                    docker-compose -p __PROJECT_NAME__ up -d postgres

                    echo ">>> Waiting for postgres to be ready..."
                    for i in $(seq 1 30); do
                        if docker-compose -p __PROJECT_NAME__ exec -T postgres pg_isready -U rcs > /dev/null 2>&1; then
                            echo "    Postgres is ready! (after ~$((i*2))s)"
                            break
                        fi
                        if [ $i -eq 30 ]; then
                            echo "    ERROR: Postgres did not become ready in 60s!"
                            docker-compose -p __PROJECT_NAME__ logs postgres
                            exit 1
                        fi
                        sleep 2
                    done

                    echo ">>> Running database migration..."
                    docker-compose -p __PROJECT_NAME__ run --rm --no-deps migrate
                    echo "    Migration complete."

                    echo ">>> Importing seed data..."
                    if grep -q '^[^-]' seed-data.sql 2>/dev/null; then
                        PG_CONTAINER=$(docker-compose -p __PROJECT_NAME__ ps -q postgres)
                        docker cp seed-data.sql "$PG_CONTAINER":/tmp/seed-data.sql
                        docker exec "$PG_CONTAINER" \
                          psql -U rcs -d rcs -v ON_ERROR_STOP=1 -f /tmp/seed-data.sql
                        echo "    Seed data imported."
                    else
                        echo "    No seed data to import, skipping."
                    fi

                    echo ">>> Starting litellm + rcs..."
                    docker-compose -p __PROJECT_NAME__ up -d litellm rcs

                    echo ">>> Waiting for RCS health check (max 10min)..."
                    echo "    Health URL: http://__HOST_IP__:__RCS_PORT__/health"
                    for i in $(seq 1 120); do
                        if curl -sf http://__HOST_IP__:__RCS_PORT__/health > /dev/null 2>&1; then
                            echo "    RCS is healthy! (after ~$((i*5))s)"
                            echo ""
                            echo "<<< [5/7] Deploy — DONE"
                            exit 0
                        fi
                        if [ $((i % 10)) -eq 0 ]; then
                            echo "    --- Attempt $i/120 (~$((i*5))s) - RCS logs ---"
                            docker-compose -p __PROJECT_NAME__ logs --tail=10 rcs 2>&1 || true
                        fi
                        sleep 5
                    done
                    echo "    ERROR: RCS health check timeout after 600s! Last logs:"
                    docker-compose -p __PROJECT_NAME__ logs --tail=30 rcs 2>&1 || true
                    exit 1
                '''.replace('__PROJECT_NAME__', PROJECT_NAME)
                  .replace('__HOST_IP__', HOST_IP)
                  .replace('__RCS_PORT__', RCS_PORT)
            }
        }

        stage('Create Pipeline Record') {
            steps {
                sh '''
                    set +x
                    echo ""
                    echo "============================================================"
                    echo "[6/7] Create Pipeline Record — START"
                    echo "  AutoTest URL: __AUTOTEST_URL__"
                    echo "  Branch:       __PR_BRANCH__"
                    echo "============================================================"
                '''.replace('__AUTOTEST_URL__', AUTOTEST_URL)
                  .replace('__PR_BRANCH__', params.PR_BRANCH ?: 'main')

                withCredentials([string(credentialsId: 'autotest-token', variable: 'TOKEN')]) {
                    sh '''
                    set +x
                        echo ">>> Sending pipeline record to AutoTest API..."
                        RESP=$(curl -s -w "\\n%{http_code}" -X POST __AUTOTEST_URL__/api/pipelines \\
                          -H "Authorization: Bearer $TOKEN" \\
                          -H "Content-Type: application/json" \\
                          -d '{
                            "pr_id": __PR_ID__,
                            "pr_title": "__PR_TITLE__",
                            "commit_sha": "__COMMIT_SHA__",
                            "branch": "__PR_BRANCH__",
                            "repo_url": "__APP_REPO__",
                            "author": "__AUTHOR__",
                            "target_url": "http://__HOST_IP__:__RCS_PORT__",
                            "docker_image": "__IMAGE_TAG__",
                            "build_info": {
                              "jenkins_url": "__BUILD_URL__",
                              "build_number": __BUILD_NUMBER__,
                              "docker_image": "__IMAGE_TAG__",
                              "rcs_port": __RCS_PORT__,
                              "pg_port": __PG_PORT__,
                              "litellm_port": __LITE_PORT__
                            }
                          }')

                        HTTP_CODE=$(echo "$RESP" | tail -1)
                        BODY=$(echo "$RESP" | sed '$d')
                        echo "$BODY" > pipeline.json

                        echo ">>> API response (HTTP $HTTP_CODE):"
                        echo "$BODY"

                        if [ "$HTTP_CODE" != "200" ] && [ "$HTTP_CODE" != "201" ]; then
                            echo ""
                            echo "    ERROR: AutoTest API returned HTTP $HTTP_CODE"
                            echo "    Pipeline record creation failed. Check if the API endpoint exists."
                            echo "<<< [6/7] Create Pipeline Record — FAILED"
                            exit 1
                        fi

                        PIPELINE_ID=$(python3 -c "import sys,json; print(json.load(sys.stdin).get('data',{}).get('id',''))" < pipeline.json)
                        if [ -z "$PIPELINE_ID" ]; then
                            echo ""
                            echo "    ERROR: API response missing 'data.id'"
                            echo "<<< [6/7] Create Pipeline Record — FAILED"
                            exit 1
                        fi

                        echo "    Pipeline ID: $PIPELINE_ID"
                        echo ""
                        echo "<<< [6/7] Create Pipeline Record — DONE"
                    '''.replace('__AUTOTEST_URL__', AUTOTEST_URL)
                      .replace('__PR_ID__', params.PR_ID ?: '0')
                      .replace('__PR_TITLE__', params.PR_TITLE ?: 'manual build')
                      .replace('__COMMIT_SHA__', params.COMMIT_SHA ?: 'unknown')
                      .replace('__PR_BRANCH__', params.PR_BRANCH ?: 'main')
                      .replace('__APP_REPO__', APP_REPO)
                      .replace('__AUTHOR__', params.AUTHOR ?: 'unknown')
                      .replace('__HOST_IP__', HOST_IP)
                      .replace('__RCS_PORT__', RCS_PORT)
                      .replace('__BUILD_URL__', env.BUILD_URL ?: '')
                      .replace('__BUILD_NUMBER__', BUILD_NUMBER)
                      .replace('__IMAGE_TAG__', "${PROJECT_NAME}:${BUILD_NUMBER}")
                      .replace('__PG_PORT__', PG_PORT)
                      .replace('__LITE_PORT__', LITE_PORT)
                }
            }
        }

        stage('Run Unit Tests') {
            steps {
                sh '''
                    set +x
                    echo ""
                    echo "============================================================"
                    echo "Run Unit Tests — START"
                    echo "============================================================"
                    echo ">>> Clearing stale test result files..."
                    rm -f autotest/unit_tests/results/unit-junit.xml
                    rm -f autotest/tests/results/report.json
                    rm -f unit-junit.xml report.json
                    echo "    Done."
                '''

                // 1. 获取 PIPELINE_ID 并通知后端"单元测试开始"
                withCredentials([string(credentialsId: 'autotest-token', variable: 'TOKEN')]) {
                    sh '''
                    set +x
                        PIPELINE_ID=""
                        if [ -f pipeline.json ]; then
                            PIPELINE_ID=$(python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('data', {}).get('id', ''))
except:
    print('')
" < pipeline.json)
                        fi
                        echo "$PIPELINE_ID" > .pipeline_id

                        if [ -n "$PIPELINE_ID" ]; then
                            echo ">>> Notifying backend: unit tests starting (pipeline_id=$PIPELINE_ID)..."
                            START_RESP=$(curl -s -X POST __AUTOTEST_URL__/api/unit-tests/runs/start \\
                              -H "Authorization: Bearer $TOKEN" \\
                              -H "Content-Type: application/json" \\
                              -d "{\\"pipeline_id\\": $PIPELINE_ID}")
                            echo "$START_RESP"
                            UNIT_RUN_ID=$(echo "$START_RESP" | python3 -c "
import sys, json
try:
    print(json.load(sys.stdin).get('data', {}).get('run_id', ''))
except:
    print('')
" 2>/dev/null)
                            echo "    Unit run_id: $UNIT_RUN_ID"
                            echo "$UNIT_RUN_ID" > .unit_run_id
                        else
                            echo "    WARNING: No pipeline ID, skipping start notification."
                            echo "" > .unit_run_id
                        fi
                    '''.replace('__AUTOTEST_URL__', AUTOTEST_URL)
                }

                // 2. 运行单元测试（捕获退出码，不立即失败，确保集成测试也能执行）
                sh '''
                    set +x
                    echo ">>> Starting unit-runner (bun:test)..."
                '''
                script {
                    env.UNIT_EXIT = sh(
                        script: "docker-compose -p ${PROJECT_NAME} up --exit-code-from unit-runner unit-runner",
                        returnStatus: true
                    ).toString()
                    echo "    unit-runner exit code: ${env.UNIT_EXIT}"
                }

                sh '''
                    set +x
                    echo ""
                    echo "<<< Run Unit Tests — DONE"
                '''
            }
        }

        stage('Run Tests') {
            steps {
                sh '''
                    set +x
                    echo ""
                    echo "============================================================"
                    echo "[7/7] Run Tests — START"
                    echo "============================================================"
                '''

                // 通知后端：集成测试开始
                withCredentials([string(credentialsId: 'autotest-token', variable: 'TOKEN')]) {
                    sh '''
                    set +x
                        PIPELINE_ID=$(cat .pipeline_id 2>/dev/null || echo "")
                        if [ -n "$PIPELINE_ID" ]; then
                            echo ">>> Notifying backend: integration tests starting (pipeline_id=$PIPELINE_ID)..."
                            curl -s -X PUT __AUTOTEST_URL__/api/pipelines/${PIPELINE_ID}/status \\
                              -H "Authorization: Bearer $TOKEN" \\
                              -H "Content-Type: application/json" \\
                              -d '{"status": "running"}'
                            echo ""
                        fi
                    '''.replace('__AUTOTEST_URL__', AUTOTEST_URL)
                }

                sh '''
                    set +x
                    echo ">>> Starting test-runner (streaming logs)..."
                '''
                sh "docker-compose -p ${PROJECT_NAME} logs -f test-runner &"
                script {
                    env.INTEGRATION_EXIT = sh(
                        script: "docker-compose -p ${PROJECT_NAME} up --exit-code-from test-runner test-runner",
                        returnStatus: true
                    ).toString()
                    echo "    test-runner exit code: ${env.INTEGRATION_EXIT}"
                }
                sh '''
                    set +x
                    echo ""
                    echo "<<< [7/7] Run Tests — DONE"
                '''
            }
        }

        stage('Check Results') {
            steps {
                script {
                    def unitExit = (env.UNIT_EXIT ?: "0") as int
                    def intExit = (env.INTEGRATION_EXIT ?: "0") as int
                    echo "    Unit test exit: ${unitExit}, Integration test exit: ${intExit}"
                    // 退出码 >=2 = 测试执行异常（收集错误/引擎崩溃），判流程失败
                    // 退出码 1 = 有用例失败，属业务结果，不影响 pipeline 成败
                    if (unitExit >= 2 || intExit >= 2) {
                        error("Test execution failed (unit=${unitExit}, integration=${intExit})")
                    }
                }
            }
        }

        stage('Collect Results') {
            steps {
                sh '''
                    set +x
                    echo ""
                    echo "============================================================"
                    echo "Collect Results — START"
                    echo "============================================================"
                    echo ">>> Copying result files from containers..."

                    # 复制单元测试结果
                    cp autotest/unit_tests/results/unit-junit.xml unit-junit.xml 2>/dev/null || true
                    if [ ! -f unit-junit.xml ]; then
                        UNIT_CONTAINER=$(docker-compose -p __PROJECT_NAME__ ps -q unit-runner 2>/dev/null || true)
                        [ -n "$UNIT_CONTAINER" ] && docker cp "$UNIT_CONTAINER":/app/tests/results/unit-junit.xml unit-junit.xml 2>/dev/null || true
                    fi
                    [ -f unit-junit.xml ] && echo "    unit-junit.xml: $(wc -c < unit-junit.xml) bytes" || echo "    unit-junit.xml: not found"

                    # 复制集成测试结果
                    cp autotest/tests/results/report.json report.json 2>/dev/null || true
                    if [ ! -f report.json ]; then
                        TEST_CONTAINER=$(docker-compose -p __PROJECT_NAME__ ps -q test-runner 2>/dev/null || true)
                        [ -n "$TEST_CONTAINER" ] && docker cp "$TEST_CONTAINER":/app/tests/results/report.json report.json 2>/dev/null || true
                    fi
                    [ -f report.json ] && echo "    report.json: $(wc -c < report.json) bytes" || echo "    report.json: not found"

                    # 复制 Allure 原始结果
                    if [ ! -d autotest/tests/results/allure-results ]; then
                        TEST_CONTAINER=$(docker-compose -p __PROJECT_NAME__ ps -q test-runner 2>/dev/null || true)
                        [ -n "$TEST_CONTAINER" ] && docker cp "$TEST_CONTAINER":/app/tests/results/allure-results autotest/tests/results/allure-results 2>/dev/null || true
                    fi
                    ALLURE_COUNT=$(find autotest/tests/results/allure-results -type f 2>/dev/null | wc -l)
                    echo "    allure-results: ${ALLURE_COUNT} files"

                    echo ""
                    echo "<<< Collect Results (local) — DONE"
                    echo ">>> Results will be uploaded in post { always } block."
                '''.replace('__PROJECT_NAME__', PROJECT_NAME)
            }
        }
    }

    post {
        success {
            echo "============================================================"
            echo "PIPELINE RESULT: SUCCESS"
            echo "============================================================"
            withCredentials([string(credentialsId: 'autotest-token', variable: 'TOKEN')]) {
                sh '''
                    set +x
                    PIPELINE_ID=""
                    if [ -f pipeline.json ]; then
                        PIPELINE_ID=$(python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('data', {}).get('id', ''))
except:
    print('')
" < pipeline.json)
                    fi
                    if [ -n "$PIPELINE_ID" ]; then
                        echo ">>> Updating pipeline status to 'passed'..."
                        curl -s -X PUT __AUTOTEST_URL__/api/pipelines/${PIPELINE_ID}/status \\
                          -H "Authorization: Bearer $TOKEN" \\
                          -H "Content-Type: application/json" \\
                          -d '{"status": "passed"}'
                    else
                        echo "    No valid pipeline ID, skipping status update."
                    fi
                '''.replace('__AUTOTEST_URL__', AUTOTEST_URL)
            }
        }
        failure {
            echo "============================================================"
            echo "PIPELINE RESULT: FAILURE"
            echo "============================================================"
            withCredentials([string(credentialsId: 'autotest-token', variable: 'TOKEN')]) {
                sh '''
                    set +x
                    PIPELINE_ID=""
                    if [ -f pipeline.json ]; then
                        PIPELINE_ID=$(python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('data', {}).get('id', ''))
except:
    print('')
" < pipeline.json)
                    fi
                    if [ -n "$PIPELINE_ID" ]; then
                        echo ">>> Updating pipeline status to 'failed'..."
                        curl -s -X PUT __AUTOTEST_URL__/api/pipelines/${PIPELINE_ID}/status \\
                          -H "Authorization: Bearer $TOKEN" \\
                          -H "Content-Type: application/json" \\
                          -d '{"status": "failed"}'
                    else
                        echo "    No valid pipeline ID, skipping status update."
                    fi
                '''.replace('__AUTOTEST_URL__', AUTOTEST_URL)
            }
        }
        always {
            echo ""
            echo "============================================================"
            echo "Upload Results & Cleanup — START"
            echo "============================================================"

            // 统一上传所有结果
            withCredentials([string(credentialsId: 'autotest-token', variable: 'TOKEN')]) {
                sh '''
                    set +x
                    PIPELINE_ID=""
                    if [ -f pipeline.json ] && [ -s pipeline.json ]; then
                        PIPELINE_ID=$(python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('data', {}).get('id', ''))
except:
    print('')
" < pipeline.json)
                    fi
                    UNIT_RUN_ID=$(cat .unit_run_id 2>/dev/null || echo "")

                    # ===== 1. 复制结果文件（确保最新） =====
                    echo ">>> Copying result files from containers..."
                    if [ ! -f unit-junit.xml ]; then
                        cp autotest/unit_tests/results/unit-junit.xml unit-junit.xml 2>/dev/null || true
                    fi
                    if [ ! -f unit-junit.xml ]; then
                        UNIT_CONTAINER=$(docker-compose -p __PROJECT_NAME__ ps -q unit-runner 2>/dev/null || true)
                        [ -n "$UNIT_CONTAINER" ] && docker cp "$UNIT_CONTAINER":/app/tests/results/unit-junit.xml unit-junit.xml 2>/dev/null || true
                    fi
                    if [ ! -f report.json ]; then
                        cp autotest/tests/results/report.json report.json 2>/dev/null || true
                    fi
                    if [ ! -f report.json ]; then
                        TEST_CONTAINER=$(docker-compose -p __PROJECT_NAME__ ps -q test-runner 2>/dev/null || true)
                        [ -n "$TEST_CONTAINER" ] && docker cp "$TEST_CONTAINER":/app/tests/results/report.json report.json 2>/dev/null || true
                    fi

                    # ===== 2. 上传单元测试结果 =====
                    if [ -f unit-junit.xml ] && [ -n "$PIPELINE_ID" ]; then
                        echo ">>> Uploading unit test results (pipeline_id=$PIPELINE_ID)..."
                        python3 -c "
import json, sys
xml_content = open('unit-junit.xml', 'r', encoding='utf-8').read()
run_id = '$UNIT_RUN_ID'.strip()
payload = {'pipeline_id': int($PIPELINE_ID), 'junit_xml': xml_content}
if run_id:
    payload['run_id'] = int(run_id)
open('unit-upload.json', 'w', encoding='utf-8').write(json.dumps(payload))
"
                        curl -s -X POST __AUTOTEST_URL__/api/unit-tests/results \\
                          -H "Authorization: Bearer $TOKEN" \\
                          -H "Content-Type: application/json" \\
                          -d @unit-upload.json
                        echo ""
                        echo "    Unit test results uploaded."
                    else
                        [ ! -f unit-junit.xml ] && echo "    WARNING: unit-junit.xml not found."
                        [ -z "$PIPELINE_ID" ] && echo "    WARNING: No pipeline ID."
                    fi

                    # ===== 3. 上传集成测试结果 =====
                    if [ -f report.json ] && [ -n "$PIPELINE_ID" ]; then
                        echo ">>> Uploading integration test results (pipeline_id=$PIPELINE_ID)..."
                        curl -s -X POST __AUTOTEST_URL__/api/pipelines/${PIPELINE_ID}/results \\
                          -H "Authorization: Bearer $TOKEN" \\
                          -H "Content-Type: application/json" \\
                          -d @report.json
                        echo ""
                        echo "    Integration test results uploaded."
                    else
                        [ ! -f report.json ] && echo "    WARNING: report.json not found."
                        [ -z "$PIPELINE_ID" ] && echo "    WARNING: No pipeline ID."
                    fi

                    # ===== 4. 收集并上传日志 =====
                    echo ">>> Collecting test logs..."
                    UNIT_LOGS=$(docker-compose -p __PROJECT_NAME__ logs unit-runner 2>&1 || echo "unit-runner not found")
                    TEST_LOGS=$(docker-compose -p __PROJECT_NAME__ logs test-runner 2>&1 || echo "test-runner not found")

                    {
                        echo "=========================================="
                        echo "Unit Test Logs"
                        echo "=========================================="
                        echo "$UNIT_LOGS"
                        echo ""
                        echo "=========================================="
                        echo "Integration Test Logs"
                        echo "=========================================="
                        echo "$TEST_LOGS"
                    } > pipeline_logs.txt

                    echo "    Log file size: $(wc -c < pipeline_logs.txt) bytes"

                    if [ -n "$PIPELINE_ID" ] && [ -s pipeline_logs.txt ]; then
                        echo ">>> Uploading logs to AutoTest (pipeline_id=$PIPELINE_ID)..."
                        python3 -c "
import json
logs = open('pipeline_logs.txt', 'r', encoding='utf-8', errors='replace').read()
payload = {'logs': logs}
open('logs_upload.json', 'w', encoding='utf-8').write(json.dumps(payload))
"
                        curl -s -X POST __AUTOTEST_URL__/api/pipelines/${PIPELINE_ID}/upload-logs \\
                          -H "Authorization: Bearer $TOKEN" \\
                          -H "Content-Type: application/json" \\
                          -d @logs_upload.json
                        echo ""
                        echo "    Logs uploaded."
                    fi
                '''.replace('__PROJECT_NAME__', PROJECT_NAME)
                  .replace('__AUTOTEST_URL__', AUTOTEST_URL)
            }

            // 生成 Allure HTML 报告并归档
            script {
                if (fileExists('autotest/tests/results/allure-results')) {
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

            sh '''
                    set +x
                echo ">>> Stopping and removing containers..."
                docker-compose -p __PROJECT_NAME__ down -v || true
                echo ">>> Removing images..."
                docker rmi -f __IMAGE_TAG__ || true
                docker rmi -f __MIGRATE_IMAGE_TAG__ || true
                echo ""
                echo "<<< Upload Results & Cleanup — DONE"
                echo ""
                echo "============================================================"
                echo "Pipeline finished. Build #${BUILD_NUMBER}"
                echo "============================================================"
            '''.replace('__PROJECT_NAME__', PROJECT_NAME)
              .replace('__IMAGE_TAG__', "${PROJECT_NAME}:${BUILD_NUMBER}")
              .replace('__MIGRATE_IMAGE_TAG__', "${PROJECT_NAME}-migrate:${BUILD_NUMBER}")
            // ===== 企业微信群通知（NOTIFY_WECOM=false 时跳过） =====
            script {
                if (params.NOTIFY_WECOM != null ? params.NOTIFY_WECOM : true) {
                    // 用户主动取消构建（ABORTED）不发送企业微信通知
                    if (currentBuild.currentResult == 'ABORTED') {
                        echo '>>> 构建被取消（ABORTED），跳过企业微信通知'
                    } else {
                    // 标题只按执行异常判失败：测试退出码 >=2（引擎执行异常）或流程异常（FAILURE）→ ❌
                    // 测试用例失败（退出码 1，只使 currentResult 变 UNSTABLE）不算失败 → ✅
                    def unitExit = (env.UNIT_EXIT ?: "0") as int
                    def intExit = (env.INTEGRATION_EXIT ?: "0") as int
                    def CR = currentBuild.currentResult
                    def PIPELINE_RESULT = (unitExit >= 2 || intExit >= 2 || CR == 'FAILURE') ? 'FAIL' : 'SUCCESS'
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
pr_id = os.environ.get('PR_ID', '')
title = os.environ.get('PR_TITLE', '')
branch = os.environ.get('PR_BRANCH', '')
author = os.environ.get('AUTHOR', '')
build_url = os.environ.get('BUILD_URL', '')
app_repo = os.environ.get('APP_REPO', '').rstrip('/').replace('.git', '')
pr_link = (app_repo + '/pull/' + pr_id) if (app_repo and pr_id) else ''

def stat_line(name, passed, failed, skipped, error=0):
    line = '> **' + name + '**: ' + str(passed) + ' 通过 / ' + str(failed) + ' 失败 / ' + str(skipped) + ' 跳过'
    if error:
        line += ' / ' + str(error) + ' 错误'
    return line

lines = [
    '### ' + icon + ' PR-Pipeline-FenixAgent 构建' + status,
    '> **PR #' + pr_id + '**: ' + title,
    '> 分支: ' + branch,
    '> 作者: ' + author,
    '> [Jenkins 构建日志](' + build_url + ')',
]

# 接口 / E2E 统计：按 nodeid 分类（先判 api_suites，避免被 suites/ 子串误命中）
api = {'passed': 0, 'failed': 0, 'skipped': 0, 'error': 0}
e2e = {'passed': 0, 'failed': 0, 'skipped': 0, 'error': 0}
if os.path.exists('report.json'):
    data = json.load(open('report.json', 'r', encoding='utf-8'))
    for t in data.get('tests', []):
        outcome = t.get('outcome', '')
        if outcome not in ('passed', 'failed', 'skipped', 'error'):
            continue
        nodeid = t.get('nodeid', '')
        if 'api_suites/' in nodeid:
            api[outcome] += 1
        elif 'suites/' in nodeid:
            e2e[outcome] += 1

# 单元统计：unit-junit.xml 顶层 <testsuites> 的 tests/failures/skipped 属性
unit = {'passed': 0, 'failed': 0, 'skipped': 0}
if os.path.exists('unit-junit.xml'):
    root = ET.parse('unit-junit.xml').getroot()
    total = int(root.get('tests', '0') or '0')
    failed = int(root.get('failures', '0') or '0')
    skipped = int(root.get('skipped', '0') or '0')
    unit['failed'] = failed
    unit['skipped'] = skipped
    unit['passed'] = total - failed - skipped

lines.append(stat_line('单元测试', unit['passed'], unit['failed'], unit['skipped']))
lines.append(stat_line('接口测试', api['passed'], api['failed'], api['skipped'], api['error']))
lines.append(stat_line('E2E 测试', e2e['passed'], e2e['failed'], e2e['skipped'], e2e['error']))

if pr_link:
    lines.append('> [GitHub PR](' + pr_link + ')')
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
                    }
                } else {
                    echo '>>> 企业微信通知已关闭（NOTIFY_WECOM=false）'
                }
            }
        }
    }
}
